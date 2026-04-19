from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.column import Column
from app.db.models.task import Task


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


async def max_position_for_board(session: AsyncSession, board_id: int) -> int | None:
    """Return `MAX(position)` across columns on `board_id`, or None if empty.

    Used by `create_column` to compute the new column's tail position as
    `max + 1000` (see `columns_service.create_column`). None means the
    board currently has zero columns — the caller starts at `1000`.
    """
    stmt = select(func.max(Column.position)).where(Column.board_id == board_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    board_id: int,
    name: str,
    position: int,
    wip_limit: int | None,
) -> Column:
    """Insert a new column under `board_id` at `position`.

    Caller owns the surrounding transaction (services commit per
    ADR-0001). Caller also computes `position` — typically via
    `max_position_for_board(...) + 1000` for an append.
    """
    column = Column(
        board_id=board_id,
        name=name,
        position=position,
        wip_limit=wip_limit,
    )
    session.add(column)
    await session.flush()
    return column


async def task_count_for_column(session: AsyncSession, column_id: int) -> int:
    """Return the number of tasks attached to `column_id`.

    Used by `columns_service.delete_column` (issue #79) to enforce the
    "non-empty column cannot be deleted" rule. Lives here rather than in
    `task_repo` because the count is column-scoped policy — the column
    repo owns the column's invariants, and `task_repo` shouldn't grow a
    column-shaped helper just to satisfy one service. A single
    `SELECT COUNT(*)` is cheap (the `(column_id, position)` index on
    `tasks` makes this an index-only scan in Postgres).
    """
    stmt = select(func.count()).select_from(Task).where(Task.column_id == column_id)
    result = await session.execute(stmt)
    return result.scalar_one()


async def delete(session: AsyncSession, column: Column) -> None:
    """Delete the loaded `column` row.

    Caller (the service) is responsible for the surrounding transaction
    AND for enforcing the "column must be empty" precondition before
    calling this — see `columns_service.delete_column`. We intentionally
    do not check task count here: the repo is a thin SQL layer per
    ADR-0001, not a policy boundary.

    `Column.tasks` has `cascade="all, delete-orphan"` and the FK on
    `tasks.column_id` is `ON DELETE CASCADE`, so a non-empty delete
    would silently take the tasks with it. The service guards against
    that case with a 409 — this call only runs after the count is zero.
    """
    await session.delete(column)
    await session.flush()


async def apply_updates(session: AsyncSession, column: Column, fields: dict[str, object]) -> Column:
    """Apply a partial update to an already-loaded `column` row.

    `fields` is the caller's pre-filtered dict of attributes to write
    (typically `ColumnUpdate.model_dump(exclude_unset=True)` — i.e. only
    fields the client explicitly sent). Empty `fields` is a valid no-op
    and just returns the same row unchanged.

    Mirrors `board_repo.apply_updates` — done in-Python (mutate attrs +
    flush) rather than as a single `update().where(...).values(...)`
    because the service has already loaded the row to enforce 404 +
    archive policy, so the row is in the identity map either way.
    `TimestampMixin.updated_at` (`onupdate=func.now()`) fires on flush
    of dirty attributes regardless of path.

    Caller (the service) owns the surrounding transaction.
    """
    for key, value in fields.items():
        setattr(column, key, value)
    await session.flush()
    return column
