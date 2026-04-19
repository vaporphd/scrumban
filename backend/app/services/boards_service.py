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


async def get_board(session: AsyncSession, *, actor: User, board_id: int) -> Board:
    raise NotImplementedError("get_board lands with the board-detail endpoint issue")


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
    raise NotImplementedError("update_board lands with the board-update endpoint issue")


async def archive_board(session: AsyncSession, *, actor: User, board_id: int) -> Board:
    raise NotImplementedError("archive_board lands with the archive endpoint issue")
