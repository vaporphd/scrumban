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
    """Revoke every non-expired, non-revoked refresh token for a user.

    Used on replay detection (ADR-0005): seeing a revoked token used
    again is positive evidence of theft, so we invalidate every live
    session for that user. Already-expired rows are left alone — the
    expires_at check is enough to keep them unusable, and not touching
    them keeps this UPDATE's row count matching the ADR wording.
    """
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .values(revoked_at=now)
    )
    await session.execute(stmt)
