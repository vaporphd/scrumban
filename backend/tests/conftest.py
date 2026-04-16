"""Test fixtures.

Uses the real async engine but wipes the data-tables between tests so
each test starts with an empty auth surface.

The DB URL must be set via `DATABASE__URL` (see `backend/.env.example`
or CI). We don't apply migrations here — CI / the developer is expected
to have run `alembic upgrade head` first.

Both the test and fixture loop scopes are pinned to `session` in
`pyproject.toml`. The async engine in `app.db.session` is created once
at import time and bound to the first loop that touches it; per-test
loops would orphan that engine after the first test, so one
session-scoped loop is the cleanest fix.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal, engine
from app.main_api import app


@pytest_asyncio.fixture(autouse=True)
async def _clean_db() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE TABLE refresh_tokens, tg_link_codes, users RESTART IDENTITY CASCADE")
        )
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Async HTTP client wired into the FastAPI app via ASGI transport."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_pair(client: AsyncClient) -> tuple[str, str, str]:
    """Register + log in a fresh user; return (username, access, refresh).

    Avoids repeating the three-call dance across tests that just need a
    valid Bearer token. Each test gets its own user since `_clean_db`
    truncates between tests.
    """
    username = "fixture-user"
    password = "correct-horse-battery"
    await client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": password,
            "display_name": "Fixture User",
        },
    )
    login = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    body = login.json()
    return username, body["access_token"], body["refresh_token"]
