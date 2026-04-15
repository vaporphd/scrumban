"""Minimum-viable sanity tests for the auth endpoints.

The full suite — including replay detection, transactional refresh,
expiry edges, and 401-distinction — lives under issue #4. This file
keeps issue #2 closeable by proving the happy paths and the one
behavior the AC calls out explicitly (401 without a valid Bearer).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main_api import app


@pytest.mark.asyncio
async def test_register_happy_path() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "alice",
                "password": "correct-horse-battery",
                "display_name": "Alice",
            },
        )

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "alice"
    assert body["display_name"] == "Alice"
    assert body["role"] == "member"
    assert "password" not in body
    assert "password_hash" not in body


@pytest.mark.asyncio
async def test_login_returns_tokens() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/register",
            json={
                "username": "bob",
                "password": "correct-horse-battery",
                "display_name": "Bob",
            },
        )
        response = await client.post(
            "/api/auth/login",
            json={"username": "bob", "password": "correct-horse-battery"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]
    assert isinstance(body["refresh_token"], str) and body["refresh_token"]


@pytest.mark.asyncio
async def test_me_requires_auth() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # No header → 401.
        no_auth = await client.get("/api/me")
        assert no_auth.status_code == 401

        # Garbage token → 401.
        bad = await client.get("/api/me", headers={"Authorization": "Bearer not-a-jwt"})
        assert bad.status_code == 401

        # Real token → 200 and correct identity.
        await client.post(
            "/api/auth/register",
            json={
                "username": "carol",
                "password": "correct-horse-battery",
                "display_name": "Carol",
            },
        )
        login = await client.post(
            "/api/auth/login",
            json={"username": "carol", "password": "correct-horse-battery"},
        )
        access = login.json()["access_token"]
        me = await client.get("/api/me", headers={"Authorization": f"Bearer {access}"})
        assert me.status_code == 200
        assert me.json()["username"] == "carol"


@pytest.mark.asyncio
async def test_refresh_rotates() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/api/auth/register",
            json={
                "username": "dave",
                "password": "correct-horse-battery",
                "display_name": "Dave",
            },
        )
        login = await client.post(
            "/api/auth/login",
            json={"username": "dave", "password": "correct-horse-battery"},
        )
        first_refresh = login.json()["refresh_token"]

        rotated = await client.post("/api/auth/refresh", json={"refresh_token": first_refresh})
        assert rotated.status_code == 200
        second_refresh = rotated.json()["refresh_token"]
        assert second_refresh != first_refresh

        # Replay of the now-revoked original must 401.
        replay = await client.post("/api/auth/refresh", json={"refresh_token": first_refresh})
        assert replay.status_code == 401

        # And chain-revoke should have killed the successor too.
        successor_after_replay = await client.post(
            "/api/auth/refresh", json={"refresh_token": second_refresh}
        )
        assert successor_after_replay.status_code == 401
