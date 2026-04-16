from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.tg_link_code import TgLinkCode


async def get_active_for_user(session: AsyncSession, user_id: int) -> TgLinkCode | None:
    """Return the user's active (non-consumed) link code, if any.

    Mirrors the partial unique index `uq_active_link_code_per_user`
    (`WHERE consumed_at IS NULL`) — at most one row can match. The service
    layer relies on this to invalidate a prior code before issuing a new one.
    """
    stmt = select(TgLinkCode).where(
        TgLinkCode.user_id == user_id,
        TgLinkCode.consumed_at.is_(None),
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def mark_consumed(
    session: AsyncSession, code: TgLinkCode, *, when: datetime | None = None
) -> None:
    """Stamp `consumed_at` on a code so it no longer matches the partial index.

    Used both by `issue_link_code` (to invalidate a prior active code before
    inserting a new one) and — later, in Phase 4 — by the bot's `/start <code>`
    handler when redeeming a code.
    """
    code.consumed_at = when if when is not None else datetime.now(tz=code.expires_at.tzinfo)
    await session.flush()


async def create(
    session: AsyncSession,
    *,
    user_id: int,
    code: str,
    expires_at: datetime,
) -> TgLinkCode:
    row = TgLinkCode(user_id=user_id, code=code, expires_at=expires_at)
    session.add(row)
    await session.flush()
    return row
