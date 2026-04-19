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
    itself doesn't exist (404) or — for `column_has_tasks` (#79) — it
    holds tasks that block deletion (409). Kept distinct from
    `BoardError` so the exception type encodes which resource is
    missing; "column not found on a board that does exist" deserves a
    different exception than "board not found / archived" (which is a
    `BoardError` because the parent is what's gone).

    `task_count` is set only for the `column_has_tasks` code (the 409
    DELETE branch) so the router can echo it back in the response body
    per the issue spec — `{"detail": "column_has_tasks", "task_count":
    N}`. Stored as an instance attribute (rather than a constructor
    arg) so the existing `ColumnError(code, message)` call sites stay
    untouched; the DELETE service path attaches it explicitly before
    raising.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.task_count: int | None = None


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


async def delete_column(
    session: AsyncSession,
    *,
    actor: User,
    column_id: int,
) -> None:
    """Delete column `column_id`, refusing if it still holds tasks.

    Per issue #79: 204 on empty column; 409 on a column that still
    contains one or more tasks (the count is echoed back via
    `ColumnError.task_count` so the router can build the
    `{"detail": "column_has_tasks", "task_count": N}` body the issue
    requires); 404 on unknown column id and on columns whose parent
    board is archived (same read-only-and-obscure model as
    `update_column` — probers can't tell archived-but-exists from
    never-existed).

    Why guard against task-cascade rather than rely on the model:
    `Column.tasks` declares `cascade="all, delete-orphan"` and the
    `tasks.column_id` FK is `ON DELETE CASCADE`, so a naive delete
    would silently take every task on the column with it. The 409
    contract exists precisely to surface that as a deliberate user
    decision (the UI then offers to move the tasks first) rather than
    a footgun.

    Raises:
        ColumnError("column_not_found"): unknown column id (404).
        BoardError("board_not_found"): column's parent board is missing
            or archived (404, same obscurity contract as
            `update_column`).
        ColumnError("column_has_tasks"): column still holds N > 0
            tasks; `err.task_count == N` is set for the router (409).

    RBAC is Phase 7 — for now any authenticated user can delete any
    column, matching the rest of the Phase 2 endpoints. The `actor`
    parameter is kept in the signature so the future RBAC filter can
    land without a router change.

    TODO(ws): publish `column.deleted` on the `board:{id}` Redis
    channel once the realtime layer lands (Phase 3, issues 123-134).
    Same deferred-publish stance as `create_column` / `update_column`
    — see those docstrings.
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
        # `update_column`).
        raise BoardError("board_not_found", f"Board {column.board_id} not found.")

    task_count = await column_repo.task_count_for_column(session, column_id)
    if task_count > 0:
        err = ColumnError(
            "column_has_tasks",
            f"Column {column_id} has {task_count} task(s); cannot delete.",
        )
        err.task_count = task_count
        raise err

    await column_repo.delete(session, column)
    await session.commit()


async def reorder_columns(
    session: AsyncSession,
    *,
    actor: User,
    board_id: int,
    ordered_column_ids: list[int],
) -> list[Column]:
    """Rewrite all column positions on `board_id` to match `ordered_column_ids`.

    Per issue #80: the request body is the **complete** desired order —
    every column on the board must appear exactly once. The service
    refuses partial lists, extras, duplicates, and unknown ids with a
    single `ColumnError("invalid_reorder")` → 400 (see the validation
    branch below). Same archived-board → 404 obscurity contract as the
    other column verbs (`update_column` / `delete_column`).

    Position rewrite strategy: assign `COLUMN_POSITION_STEP * (i + 1)`
    for each column in the new order — i.e. `1000, 2000, 3000, ...`.
    Full rewrite rather than ADR-0004's float `(prev + next) / 2`
    in-place insert because column reorders are rare AND the typical
    column count is 3-7 (per the board-design conventions in
    `db/models/column.py`). Cascading integer rewrites stay cheap; the
    float scheme exists for the *task* hot path where every drag
    triggers a position update.

    Why collapse partial / extra / duplicate / unknown onto one
    `invalid_reorder` code rather than four discrete codes: the client
    UX is the same in every case ("the list you sent doesn't match the
    board") and the four shapes are easier to validate as one set
    comparison than as four sequential predicate checks. A duplicate
    `[A, A, B]` against a board `{A, B, C}` fails the set-equality
    branch (the set is `{A, B}`, missing C), and the length-vs-
    set-length check then catches the duplicate flavor explicitly even
    on boards where the multiset would otherwise match. Either branch
    raises the same code — the 400 body is the contract, not the
    failure flavor.

    Transactional: the validation runs *before* any mutation. If
    validation passes, all position updates flush in one batch and one
    commit. If anything raises after the first `position` write but
    before commit (DB error, etc.), the AsyncSession rolls back the
    transaction on exception — the half-written positions never persist.

    Raises:
        BoardError("board_not_found"): unknown board id, or board is
            archived (read-only model — same obscurity contract as
            `update_column`).
        ColumnError("invalid_reorder"): `ordered_column_ids` does not
            match the board's column set exactly (missing ids, extra
            ids, unknown ids from another board, or duplicates).

    RBAC is Phase 7 — for now any authenticated user can reorder any
    board's columns, matching the rest of the Phase 2 endpoints. The
    `actor` parameter is kept in the signature so the future RBAC
    filter can land without a router change.

    TODO(ws): publish `column.reordered` on the `board:{id}` Redis
    channel once the realtime layer lands (Phase 3, issues 123-134).
    Same deferred-publish stance as `create_column` / `update_column`
    / `delete_column` — see those docstrings.
    """
    _ = actor  # RBAC lands in Phase 7; keep the parameter for forward-compat.
    board = await board_repo.get_by_id(session, board_id)
    if board is None or board.archived_at is not None:
        # Same 404 obscurity model as `create_column` — archived parent
        # boards are read-only and we don't reveal exists-but-archived.
        raise BoardError("board_not_found", f"Board {board_id} not found.")

    existing = await column_repo.list_for_board(session, board_id)
    existing_ids = {c.id for c in existing}
    requested_ids = set(ordered_column_ids)

    # Two-condition check (set equality + length parity) covers all
    # four invalid shapes. The length check catches duplicates that the
    # set comparison would otherwise mask on the perfect-multiset case
    # (a board {A, B} with payload [A, A] has set {A} != {A, B} so the
    # first branch fires — but the explicit length check makes the
    # duplicate-rejection guarantee independent of the board's contents
    # and is cheaper than constructing a Counter).
    if existing_ids != requested_ids or len(ordered_column_ids) != len(requested_ids):
        raise ColumnError(
            "invalid_reorder",
            f"ordered_column_ids must match board {board_id}'s columns exactly.",
        )

    by_id = {c.id: c for c in existing}
    reordered: list[Column] = []
    for i, cid in enumerate(ordered_column_ids):
        col = by_id[cid]
        col.position = COLUMN_POSITION_STEP * (i + 1)
        reordered.append(col)
    await session.flush()
    # `updated_at` has `onupdate=func.now()` (TimestampMixin) — the DB
    # computes new values on flush and SQLAlchemy expires the attrs.
    # Without an explicit refresh, the router's `ColumnRead.model_validate`
    # would lazy-load outside the async context → `MissingGreenlet`.
    # Same trap `update_column` documents.
    for col in reordered:
        await session.refresh(col, ["updated_at"])
    await session.commit()
    return reordered
