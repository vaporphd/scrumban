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
from app.domain.columns import ColumnCreate
from app.repositories import board_repo, column_repo
from app.services.boards_service import BoardError

# Append step for new columns. The issue spec calls for `max + 1000` —
# wide enough to leave plenty of room between siblings for future
# reorder / insert-between operations without immediately needing a
# rebalance. Column reorders are rare (see ADR-0004's "tasks-only" carve-
# out: integer column positions are fine), but a generous step keeps
# rebalance pressure low even with hundreds of inserts on a single board.
COLUMN_POSITION_STEP = 1000


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
