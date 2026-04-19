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


class BoardError(Exception):
    """Domain-level board failure. Routers map to HTTP 403/404/409."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def create_board(session: AsyncSession, *, creator: User, payload: BoardCreate) -> Board:
    raise NotImplementedError("create_board lands in issue #69")


async def get_board(session: AsyncSession, *, actor: User, board_id: int) -> Board:
    raise NotImplementedError("get_board lands with the board-detail endpoint issue")


async def list_boards(session: AsyncSession, *, actor: User) -> list[Board]:
    raise NotImplementedError("list_boards lands in issue #70")


async def update_board(
    session: AsyncSession, *, actor: User, board_id: int, payload: BoardUpdate
) -> Board:
    raise NotImplementedError("update_board lands with the board-update endpoint issue")


async def archive_board(session: AsyncSession, *, actor: User, board_id: int) -> Board:
    raise NotImplementedError("archive_board lands with the archive endpoint issue")
