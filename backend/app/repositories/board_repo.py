from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.board import Board


async def get_by_id(session: AsyncSession, board_id: int) -> Board | None:
    return await session.get(Board, board_id)


async def get_by_id_with_relations(session: AsyncSession, board_id: int) -> Board | None:
    """Return the board + eager-loaded columns + labels in 3 SELECTs total.

    Used by `GET /api/boards/{id}` (issue #71) to avoid N+1 when the
    detail endpoint serializes the columns and labels collections.

    `selectinload` issues one extra SELECT per relationship (board → 1
    columns SELECT, board → 1 labels SELECT) — three queries total
    regardless of how many columns/labels exist. We deliberately avoid
    `joinedload` here because the cartesian product of columns x labels
    would re-emit board / column rows once per label, blowing up payload
    transfer for boards with many of each.

    `Column.position` ordering for the columns list comes from the
    relationship's `order_by="Column.position"` declared on the model
    (`app/db/models/board.py`); no extra `order_by` needed here.
    """
    stmt = (
        select(Board)
        .where(Board.id == board_id)
        .options(selectinload(Board.columns), selectinload(Board.labels))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_active(session: AsyncSession) -> list[Board]:
    """Return all non-archived boards, newest first.

    Writes (create / update / archive) land with the endpoint issues
    (#69+). This read-only surface is enough for the endpoint issues to
    build on without depending on an unrelated repository PR.

    `id DESC` is a deterministic tiebreaker — Postgres `now()` is fixed
    per transaction, so multiple boards inserted in one txn share an
    identical `created_at` and would otherwise come back in undefined
    order. `id` is monotonic so newest-id ≈ newest-row.
    """
    stmt = (
        select(Board)
        .where(Board.archived_at.is_(None))
        .order_by(Board.created_at.desc(), Board.id.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_all(session: AsyncSession) -> list[Board]:
    """Return every board (archived and active), newest first.

    Used by `GET /api/boards?include_archived=true` (issue #70). Kept
    as a sibling of `list_active` rather than a parameter on it so the
    common case (`list_active`) stays a one-line call site. Same
    `id DESC` tiebreaker as `list_active` — see that docstring.
    """
    stmt = select(Board).order_by(Board.created_at.desc(), Board.id.desc())
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
