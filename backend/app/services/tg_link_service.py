"""Telegram-link business logic (ADR-0003).

The web UI is the only surface that issues a one-time code; the bot's
`/start <code>` handler (Phase 4) consumes it. Both code-issuance and
prior-code invalidation must run inside the same transaction so a
concurrent second request can't race past the partial unique index
`uq_active_link_code_per_user`.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.tg_link_code import TgLinkCode
from app.db.models.user import User
from app.repositories import tg_link_code_repo


async def issue_link_code(session: AsyncSession, user: User) -> TgLinkCode:
    """Generate a fresh 6-digit link code, invalidating any prior active code.

    Per ADR-0003 a user has at most one active code at a time. The
    invalidate-then-insert pair runs in one transaction so we can't violate
    the partial unique index on a race. The CSPRNG (`secrets.randbelow`)
    matters — a 6-digit code is short enough that `random.randint` would be
    a real exposure.
    """
    now = datetime.now(tz=UTC)
    existing = await tg_link_code_repo.get_active_for_user(session, user.id)
    if existing is not None:
        await tg_link_code_repo.mark_consumed(session, existing, when=now)

    settings = get_settings()
    code_value = f"{secrets.randbelow(1_000_000):06d}"
    fresh = await tg_link_code_repo.create(
        session,
        user_id=user.id,
        code=code_value,
        expires_at=now + timedelta(minutes=settings.telegram.link_code_ttl_minutes),
    )
    await session.commit()
    return fresh
