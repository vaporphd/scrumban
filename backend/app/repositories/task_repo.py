from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.task import Task


async def get_by_id(session: AsyncSession, task_id: int) -> Task | None:
    return await session.get(Task, task_id)


async def list_for_column(session: AsyncSession, column_id: int) -> list[Task]:
    """Return a column's tasks in display order (position ASC per ADR-0004).

    Read-only for now; CRUD + `/move` with transactional position recompute
    land in a later issue.
    """
    stmt = select(Task).where(Task.column_id == column_id).order_by(Task.position.asc())
    result = await session.execute(stmt)
    return list(result.scalars().all())
