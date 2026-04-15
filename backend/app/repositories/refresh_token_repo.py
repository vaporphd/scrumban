from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.refresh_token import RefreshToken


async def get_by_hash(
    session: AsyncSession, token_hash: str, *, for_update: bool = False
) -> RefreshToken | None:
    """Look up a refresh token by its hex SHA-256 hash.

    `for_update=True` acquires a row-level lock (SELECT ... FOR UPDATE).
    ADR-0005 requires this inside the refresh transaction so concurrent
    refreshes of the same token serialize instead of racing.
    """
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    user_id: int,
    token_hash: str,
    expires_at: datetime,
) -> RefreshToken:
    token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(token)
    await session.flush()
    return token


async def revoke_chain_for_user(session: AsyncSession, user_id: int, *, now: datetime) -> None:
    """Revoke all non-revoked refresh tokens for a user.

    Used on replay detection (ADR-0005): seeing a revoked token used
    again is positive evidence of theft, so we invalidate every session
    for that user.
    """
    stmt = (
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    await session.execute(stmt)
