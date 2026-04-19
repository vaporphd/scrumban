from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.label import Label


async def get_by_id(session: AsyncSession, label_id: int) -> Label | None:
    return await session.get(Label, label_id)


async def list_for_board(session: AsyncSession, board_id: int) -> list[Label]:
    """Return every label defined on a board, name-sorted for stable UI order.

    Read-only for now; CRUD lands in a later issue.
    """
    stmt = select(Label).where(Label.board_id == board_id).order_by(Label.name.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())
