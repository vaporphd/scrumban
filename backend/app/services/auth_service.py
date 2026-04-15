"""Authentication business logic.

Routers stay thin (ADR-0001) and delegate here. The refresh path is
transactional per ADR-0005: we `SELECT ... FOR UPDATE` the token row,
revoke it, insert the successor, and set `replaced_by_id` — all in one
transaction — so concurrent double-refreshes can't split rotation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    issue_access_token,
    verify_password,
)
from app.db.models.user import User, UserRole
from app.repositories import refresh_token_repo, user_repo


class AuthError(Exception):
    """Domain-level auth failure. Routers map this to HTTP 401/409."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(slots=True)
class TokenPair:
    access_token: str
    refresh_token: str


async def register(
    session: AsyncSession, *, username: str, password: str, display_name: str
) -> User:
    username_normalized = username.strip().lower()
    existing = await user_repo.get_by_username(session, username_normalized)
    if existing is not None:
        raise AuthError("username_taken", "Username is already taken.")
    try:
        user = await user_repo.create(
            session,
            username=username_normalized,
            password_hash=hash_password(password),
            display_name=display_name.strip(),
            role=UserRole.MEMBER,
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise AuthError("username_taken", "Username is already taken.") from None
    return user


async def authenticate(session: AsyncSession, *, username: str, password: str) -> User:
    user = await user_repo.get_by_username(session, username.strip().lower())
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("invalid_credentials", "Invalid username or password.")
    return user


async def issue_tokens(session: AsyncSession, user: User) -> TokenPair:
    settings = get_settings()
    now = datetime.now(tz=UTC)
    access = issue_access_token(user.id, now=now)
    refresh_plain = generate_refresh_token()
    await refresh_token_repo.create(
        session,
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_plain),
        expires_at=now + timedelta(days=settings.jwt.refresh_ttl_days),
    )
    await session.commit()
    return TokenPair(access_token=access, refresh_token=refresh_plain)


async def refresh(session: AsyncSession, *, refresh_token: str) -> TokenPair:
    """Rotate a refresh token atomically.

    Per ADR-0005 this must be transactional: look up the row with
    SELECT ... FOR UPDATE, validate, revoke old, insert new with
    replaced_by_id, commit. On replay (revoked row presented again) we
    chain-revoke every live token for the user and return 401.
    """
    settings = get_settings()
    token_hash = hash_refresh_token(refresh_token)

    # Transactional per ADR-0005: lookup → validate → revoke old →
    # insert new must be atomic, so concurrent double-refreshes serialize
    # on `SELECT ... FOR UPDATE` instead of racing. We commit explicitly
    # rather than using `async with session.begin()` because the replay
    # branch needs to commit the chain-revocation UPDATE and *then*
    # raise — the context-manager flavor would roll it back with the
    # raised exception.
    await session.begin()
    try:
        existing = await refresh_token_repo.get_by_hash(session, token_hash, for_update=True)
        if existing is None:
            await session.rollback()
            raise AuthError("invalid_refresh_token", "Invalid refresh token.")

        now = datetime.now(tz=UTC)

        if existing.revoked_at is not None:
            # Replay: a revoked token came back. Positive evidence of
            # theft — chain-revoke every live token for the user, commit
            # that, then 401.
            await refresh_token_repo.revoke_chain_for_user(session, existing.user_id, now=now)
            await session.commit()
            raise AuthError("refresh_token_replayed", "Refresh token has been revoked.")

        if existing.expires_at <= now:
            await session.rollback()
            raise AuthError("refresh_token_expired", "Refresh token has expired.")

        new_plain = generate_refresh_token()
        successor = await refresh_token_repo.create(
            session,
            user_id=existing.user_id,
            token_hash=hash_refresh_token(new_plain),
            expires_at=now + timedelta(days=settings.jwt.refresh_ttl_days),
        )
        existing.revoked_at = now
        existing.replaced_by_id = successor.id
        access = issue_access_token(existing.user_id, now=now)
        await session.commit()
    except BaseException:
        if session.in_transaction():
            await session.rollback()
        raise

    return TokenPair(access_token=access, refresh_token=new_plain)


async def load_user_from_access_token(session: AsyncSession, token: str) -> User | None:
    user_id = decode_access_token(token)
    if user_id is None:
        return None
    return await user_repo.get_by_id(session, user_id)
