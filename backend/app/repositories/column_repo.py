from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.column import Column


async def get_by_id(session: AsyncSession, column_id: int) -> Column | None:
    return await session.get(Column, column_id)


async def list_for_board(session: AsyncSession, board_id: int) -> list[Column]:
    """Return a board's columns in display order (position ASC).

    Read-only for now; create / update / reorder endpoints land in later
    issues (#69+).
    """
    stmt = select(Column).where(Column.board_id == board_id).order_by(Column.position.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())
