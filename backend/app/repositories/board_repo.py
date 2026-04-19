from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.board import Board


async def get_by_id(session: AsyncSession, board_id: int) -> Board | None:
    return await session.get(Board, board_id)


async def list_active(session: AsyncSession) -> list[Board]:
    """Return all non-archived boards, newest first.

    Writes (create / update / archive) land with the endpoint issues
    (#69+). This read-only surface is enough for the endpoint issues to
    build on without depending on an unrelated repository PR.
    """
    stmt = select(Board).where(Board.archived_at.is_(None)).order_by(Board.created_at.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create(
    session: AsyncSession,
    *,
    name: str,
    description: str | None,
    created_by: int,
) -> Board:
    """Insert a new board owned by `created_by`.

    Caller is responsible for the surrounding transaction (the service
    commits — see ADR-0001: routers stay thin, services own
    transactions). `created_by` is required at write-time; it can become
    NULL later only if the user row is deleted (FK ON DELETE SET NULL).
    """
    board = Board(name=name, description=description, created_by=created_by)
    session.add(board)
    await session.flush()
    return board
