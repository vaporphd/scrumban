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
from sqlalchemy import text

from app.db.session import SessionLocal, engine


@pytest_asyncio.fixture(autouse=True)
async def _clean_db() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.execute(
            text("TRUNCATE TABLE refresh_tokens, tg_link_codes, users RESTART IDENTITY CASCADE")
        )
    yield


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[object]:
    async with SessionLocal() as session:
        yield session
