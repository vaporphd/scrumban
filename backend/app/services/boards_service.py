"""Boards business logic.

Skeleton only — bodies land with the Phase 2 endpoint issues (#69+). The
shape of these functions is fixed here so router PRs can import cleanly
and each endpoint PR stays diff-focused.

Every mutating call below must eventually (per ADR-0001 / `CLAUDE.md`)
publish a Redis event on `board:{id}` so WebSocket subscribers and the
Telegram bot stay in sync.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.board import Board
from app.db.models.user import User
from app.domain.boards import BoardCreate, BoardUpdate
from app.repositories import board_repo


class BoardError(Exception):
    """Domain-level board failure. Routers map to HTTP 403/404/409."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def create_board(session: AsyncSession, *, creator: User, payload: BoardCreate) -> Board:
    """Create a board owned by `creator`.

    Per ADR-0001 the service owns the transaction; the router stays
    thin. Pydantic has already enforced field-level invariants
    (`name` 1-128, `description` ≤ 4096) — see `app.domain.boards`.

    TODO(ws): publish `board.created` on the `board:{id}` Redis channel
    once the realtime layer lands (Phase 3, issues 123-134). The
    `app/realtime/` package does not yet exist; inventing the publisher
    here would be premature infra. Tracked by the Phase 3 plan in
    `tasks/todo.md`; the `board:{id}` contract is fixed in ADR-0002.
    """
    board = await board_repo.create(
        session,
        name=payload.name,
        description=payload.description,
        created_by=creator.id,
    )
    await session.commit()
    return board


async def get_board(
    session: AsyncSession,
    *,
    actor: User,
    board_id: int,
    include_archived: bool = False,
) -> Board:
    """Return board `board_id` with columns + labels eager-loaded.

    Per issue #71: 404 on unknown id; 404 on archived board unless
    `include_archived=True`. RBAC is Phase 7 — for now any authenticated
    user can read any board, matching the rest of the Phase 2 endpoints.
    The `actor` parameter is kept in the signature so the future RBAC
    filter can land without a router change.

    The single repo call performs three SELECTs (board + columns +
    labels via `selectinload`) — the N+1 assertion in
    `tests/test_boards_get.py` locks this.
    """
    board = await board_repo.get_by_id_with_relations(session, board_id)
    if board is None:
        raise BoardError("board_not_found", f"Board {board_id} not found.")
    if board.archived_at is not None and not include_archived:
        # Archived boards are hidden from default reads — same model as
        # `list_boards`. We use 404 (not 410 / 403) so unauthorized
        # probers can't tell archived-but-exists from never-existed.
        raise BoardError("board_not_found", f"Board {board_id} not found.")
    return board


async def list_boards(
    session: AsyncSession, *, actor: User, include_archived: bool = False
) -> list[Board]:
    """List boards visible to `actor`, newest first.

    By default returns only non-archived boards (the common UI case).
    `include_archived=True` returns every board for admin / archive
    views. RBAC is Phase 7 — for now any authenticated user can list
    every board, matching the rest of the Phase 2 endpoints. The
    `actor` parameter is kept in the signature so the future RBAC
    filter can land without a router change.
    """
    if include_archived:
        return await board_repo.list_all(session)
    return await board_repo.list_active(session)


async def update_board(
    session: AsyncSession, *, actor: User, board_id: int, payload: BoardUpdate
) -> Board:
    """Apply a partial update (`name` and/or `description`) to board `board_id`.

    Per issue #72: 404 on unknown id; 404 on archived board (same model
    as `get_board` — archived boards are read-only by default and updates
    on them are indistinguishable from "doesn't exist" so probers can't
    detect archived state). Field-level invariants (`name` 1-128,
    `description` ≤ 4096) are enforced by pydantic on `BoardUpdate`.

    Uses `model_dump(exclude_unset=True)` rather than `exclude_none`:
    a client that explicitly sends `description: null` is asking to
    clear the description, which is different from omitting the field
    (= leave it alone). `exclude_none` would conflate the two and
    silently turn a clear-request into a no-op.

    Empty payload (no fields sent) is a valid no-op — same row returned
    unchanged. The pydantic schema does not enforce "at least one field
    must be present" because there's no harm in returning the current
    state on `PATCH {}`.

    RBAC is Phase 7 — for now any authenticated user can update any
    board, matching the rest of the Phase 2 endpoints. The `actor`
    parameter is kept in the signature so the future RBAC filter can
    land without a router change.

    TODO(ws): publish `board.updated` on the `board:{id}` Redis channel
    once the realtime layer lands (Phase 3, issues 123-134). Same
    deferred-publish stance as `create_board` — see that docstring.
    """
    board = await board_repo.get_by_id(session, board_id)
    if board is None:
        raise BoardError("board_not_found", f"Board {board_id} not found.")
    if board.archived_at is not None:
        # Archived boards are read-only by default — same 404-not-403
        # model as `get_board` so probers can't tell archived-but-exists
        # from never-existed.
        raise BoardError("board_not_found", f"Board {board_id} not found.")

    fields = payload.model_dump(exclude_unset=True)
    if fields:
        await board_repo.apply_updates(session, board, fields)
        # `updated_at` has `onupdate=func.now()` (TimestampMixin) — the DB
        # computes the new value, so SQLAlchemy expires the attribute on
        # flush. Without an explicit refresh, the router's
        # `BoardRead.model_validate(board)` would trigger a lazy-load
        # outside the async context → `MissingGreenlet`.
        await session.refresh(board, ["updated_at"])
    await session.commit()
    return board


async def archive_board(session: AsyncSession, *, actor: User, board_id: int) -> Board:
    raise NotImplementedError("archive_board lands with the archive endpoint issue")
