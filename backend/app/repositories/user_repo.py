from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User, UserRole


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    return await session.get(User, user_id)


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create(
    session: AsyncSession,
    *,
    username: str,
    password_hash: str,
    display_name: str,
    role: UserRole = UserRole.MEMBER,
) -> User:
    user = User(
        username=username,
        password_hash=password_hash,
        display_name=display_name,
        role=role,
    )
    session.add(user)
    await session.flush()
    return user
