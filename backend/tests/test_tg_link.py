"""Tests for the Telegram link-code endpoint (issue 20, ADR-0003).

Three cases cover the AC:

- Happy path: POST returns a fresh 6-digit code with a future `expires_at`
  and the configured `bot_username`.
- Re-issue invariant: hitting the endpoint twice in a row invalidates the
  first code, leaving exactly one active row in `tg_link_codes`.
- Auth gate: POST without a Bearer token is 401 (no code is issued).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.tg_link_code import TgLinkCode

_SIX_DIGITS = re.compile(r"^\d{6}$")


@pytest.mark.asyncio
async def test_issue_link_code_returns_fresh_code(
    client: AsyncClient, auth_pair: tuple[str, str, str]
) -> None:
    _, access, _ = auth_pair

    response = await client.post(
        "/api/me/tg-link-code",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert _SIX_DIGITS.match(body["code"]), f"expected 6 decimal digits, got {body['code']!r}"

    expires_at = datetime.fromisoformat(body["expires_at"])
    assert expires_at > datetime.now(tz=UTC), "expires_at must be in the future"

    # bot_username defaults to None in tests (env var unset). Make the
    # assertion explicit so a future env-leak surfaces as a test failure
    # rather than as a silent change in API shape.
    assert body["bot_username"] == get_settings().telegram.bot_username


@pytest.mark.asyncio
async def test_issue_link_code_invalidates_prior_active(
    client: AsyncClient, auth_pair: tuple[str, str, str], db_session: AsyncSession
) -> None:
    """ADR-0003: at most one active code per user. The second POST must
    invalidate the first by stamping `consumed_at`, leaving exactly one
    row with `consumed_at IS NULL`."""
    _, access, _ = auth_pair
    headers = {"Authorization": f"Bearer {access}"}

    first = await client.post("/api/me/tg-link-code", headers=headers)
    second = await client.post("/api/me/tg-link-code", headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["code"] != second.json()["code"], (
        "second issuance must produce a different code; same value is a bug "
        "(or an absurd 1-in-a-million coincidence — re-run if so)"
    )

    active_count = await db_session.scalar(
        select(func.count()).select_from(TgLinkCode).where(TgLinkCode.consumed_at.is_(None))
    )
    assert active_count == 1, f"expected 1 active code after re-issue, got {active_count}"

    total_count = await db_session.scalar(select(func.count()).select_from(TgLinkCode))
    assert total_count == 2, f"expected 2 total rows (1 consumed, 1 active), got {total_count}"


@pytest.mark.asyncio
async def test_link_code_endpoint_requires_auth(client: AsyncClient) -> None:
    response = await client.post("/api/me/tg-link-code")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
