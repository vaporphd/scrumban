"""Columns business logic.

Per ADR-0001 the service owns the transaction; routers stay thin and
just delegate. Mutations on a board's columns must eventually publish
on the `board:{id}` Redis channel (ADR-0002) so WebSocket subscribers
and the Telegram bot stay in sync — that publish lands with the Phase 3
realtime issues (#123-#134); see the `TODO(ws)` markers below.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.column import Column
from app.db.models.user import User
from app.domain.columns import ColumnCreate, ColumnUpdate
from app.repositories import board_repo, column_repo
from app.services.boards_service import BoardError

# Append step for new columns. The issue spec calls for `max + 1000` —
# wide enough to leave plenty of room between siblings for future
# reorder / insert-between operations without immediately needing a
# rebalance. Column reorders are rare (see ADR-0004's "tasks-only" carve-
# out: integer column positions are fine), but a generous step keeps
# rebalance pressure low even with hundreds of inserts on a single board.
COLUMN_POSITION_STEP = 1000


class ColumnError(Exception):
    """Domain-level column failure. Routers map to HTTP 404/409.

    Sibling of `BoardError` for column-scoped failures: the column
    itself doesn't exist (404) or — when issue #79 lands — it has tasks
    blocking deletion (409). Kept distinct from `BoardError` so the
    exception type encodes which resource is missing; "column not found
    on a board that does exist" deserves a different exception than
    "board not found / archived" (which is a `BoardError` because the
    parent is what's gone). Routers map both to 404 today, but the
    branching surface will widen with #79.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def create_column(
    session: AsyncSession,
    *,
    actor: User,
    board_id: int,
    payload: ColumnCreate,
) -> Column:
    """Append a new column to `board_id`.

    Per issue #77: 404 on unknown board id; 404 on archived board (same
    archived = read-only model as `boards_service.update_board`). The new
    column's `position` is `MAX(position) + COLUMN_POSITION_STEP` over
    the board's existing columns, or `COLUMN_POSITION_STEP` if the board
    has none. `Column.position` is `Integer` (the model docstring
    explains why ADR-0004's float scheme is task-only); the issue body's
    "+ 1000.0" is satisfied by integer arithmetic — there's no precision
    loss possible at this granularity.

    Field-level invariants (`name` 1-64, `wip_limit` 1-1000 or None) are
    enforced by pydantic on `ColumnCreate` — see `app.domain.columns`.

    RBAC is Phase 7 — for now any authenticated user can add columns to
    any board, matching the rest of the Phase 2 endpoints. The `actor`
    parameter is kept in the signature so the future RBAC filter can
    land without a router change.

    TODO(ws): publish `column.created` on the `board:{id}` Redis channel
    once the realtime layer lands (Phase 3, issues #123-#134). Same
    deferred-publish stance as `boards_service.create_board` — see that
    docstring.
    """
    board = await board_repo.get_by_id(session, board_id)
    if board is None:
        raise BoardError("board_not_found", f"Board {board_id} not found.")
    if board.archived_at is not None:
        # Archived boards are read-only by default — same 404-not-403
        # model as `boards_service.update_board` so probers can't tell
        # archived-but-exists from never-existed.
        raise BoardError("board_not_found", f"Board {board_id} not found.")

    max_position = await column_repo.max_position_for_board(session, board_id)
    next_position = (max_position or 0) + COLUMN_POSITION_STEP

    column = await column_repo.create(
        session,
        board_id=board_id,
        name=payload.name,
        position=next_position,
        wip_limit=payload.wip_limit,
    )
    await session.commit()
    return column


async def update_column(
    session: AsyncSession,
    *,
    actor: User,
    column_id: int,
    payload: ColumnUpdate,
) -> Column:
    """Apply a partial update (`name` and/or `wip_limit`) to column `column_id`.

    Per issue #78: 404 on unknown column id; 404 on column belonging to
    an archived board (archived = read-only — same model as
    `boards_service.update_board`; we don't reveal whether the column
    exists when the parent board is archived, so probers can't tell
    archived-but-exists from never-existed). Field-level invariants
    (`name` 1-64, `wip_limit` 1-1000 or None) are enforced by pydantic
    on `ColumnUpdate`.

    Uses `model_dump(exclude_unset=True)` rather than `exclude_none`:
    a client that explicitly sends `wip_limit: null` is asking to clear
    the limit, which is different from omitting the field (= leave it
    alone). Mirrors the boards PATCH semantics — see
    `boards_service.update_board` for the rationale.

    Empty payload (no fields sent) is a valid no-op — same row returned
    unchanged. The pydantic schema does not enforce "at least one field
    must be present" because there's no harm in returning the current
    state on `PATCH {}`.

    Raises:
        ColumnError("column_not_found"): unknown column id.
        BoardError("board_not_found"): column exists but its board is
            archived or somehow missing — both conditions surface as
            "board not found" to keep the 404 obscurity contract.

    RBAC is Phase 7 — for now any authenticated user can update any
    column, matching the rest of the Phase 2 endpoints. The `actor`
    parameter is kept in the signature so the future RBAC filter can
    land without a router change.

    TODO(ws): publish `column.updated` on the `board:{id}` Redis
    channel once the realtime layer lands (Phase 3, issues 123-134).
    Same deferred-publish stance as `create_column` — see that
    docstring.
    """
    _ = actor  # RBAC lands in Phase 7; keep the parameter for forward-compat.
    column = await column_repo.get_by_id(session, column_id)
    if column is None:
        raise ColumnError("column_not_found", f"Column {column_id} not found.")

    board = await board_repo.get_by_id(session, column.board_id)
    if board is None or board.archived_at is not None:
        # Archived parent board → column is read-only. Surface as
        # "board not found" so probers can't tell archived-but-exists
        # from never-existed (same 404-not-403 model as
        # `boards_service.update_board`).
        raise BoardError("board_not_found", f"Board {column.board_id} not found.")

    fields = payload.model_dump(exclude_unset=True)
    if fields:
        await column_repo.apply_updates(session, column, fields)
        # `updated_at` has `onupdate=func.now()` (TimestampMixin) — the
        # DB computes the new value, so SQLAlchemy expires the attribute
        # on flush. Without an explicit refresh, the router's
        # `ColumnRead.model_validate(column)` would trigger a lazy-load
        # outside the async context → `MissingGreenlet`. Same trap
        # `boards_service.update_board` documents.
        await session.refresh(column, ["updated_at"])
    await session.commit()
    return column
