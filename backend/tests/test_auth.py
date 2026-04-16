"""Full auth test suite for the Phase 1 backend (issue #4).

Builds on the sanity subset that shipped with #2 — register happy
path, login returns a pair, `/me` requires Bearer, refresh rotates +
chain-revoke on replay — and fills the gaps called out in the issue:

- Login 401 paths: wrong password AND unknown user, with timing parity
  so we do not leak "this username exists".
- Register 409 on duplicate username (both the pre-check and the
  IntegrityError race branch).
- Access-token expiry: forge a token with past `exp` rather than
  freezing time; deterministic, no asyncio clock trickery.
- Refresh 401 on invalid garbage and on an expired row.
- Concurrent refresh race: two in-flight calls with the same token;
  exactly one wins, per ADR-0005 transactional rotation.

Coverage gate for `app/services/auth_service.py` is ≥ 90%; see the
`pytest --cov=app.services.auth_service --cov-report=term-missing`
output in the PR.
"""

from __future__ import annotations

import asyncio
import secrets
import statistics
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from jose import jwt
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import generate_refresh_token, hash_refresh_token
from app.db.models.refresh_token import RefreshToken
from app.db.models.user import User
from app.repositories import user_repo

# ---------------------------------------------------------------------------
# Sanity subset (kept from #2 — these prove the happy paths)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_happy_path(client: AsyncClient) -> None:
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
async def test_login_returns_tokens(client: AsyncClient) -> None:
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
async def test_me_requires_auth(client: AsyncClient) -> None:
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
async def test_refresh_rotates(client: AsyncClient) -> None:
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


# ---------------------------------------------------------------------------
# Login 401 paths (wrong password, unknown user, response parity)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_wrong_password_401(client: AsyncClient) -> None:
    await client.post(
        "/api/auth/register",
        json={
            "username": "eve",
            "password": "correct-horse-battery",
            "display_name": "Eve",
        },
    )

    response = await client.post(
        "/api/auth/login",
        json={"username": "eve", "password": "wrong-horse-battery"},
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json() == {"detail": "Invalid username or password."}


@pytest.mark.asyncio
async def test_login_unknown_user_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/auth/login",
        json={"username": "ghost", "password": "anything-goes-here"},
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json() == {"detail": "Invalid username or password."}


@pytest.mark.asyncio
async def test_login_response_parity_wrong_vs_unknown(client: AsyncClient) -> None:
    """Unknown-user and wrong-password 401s must be indistinguishable.

    Asserts two things in one test:

    1. HTTP-shape parity — same status, same body, same `WWW-Authenticate`
       header. The response itself does not leak "this username exists".
    2. Wall-time parity — the unknown-user path runs a dummy argon2 verify
       (see `auth_service._DUMMY_PASSWORD_HASH`) so its latency tracks the
       wrong-password path. Without the dummy verify, locally measured
       wrong-password ≈ 30 ms vs unknown-user ≈ 4 ms (~7x), enabling
       username enumeration. Locks the fix from #23.

    Method: N=10 samples per branch, compare medians (mean is too sensitive
    to argon2's fat right tail from GC pauses and scheduler jitter). The
    30% tolerance is wide enough to absorb noise on a busy CI runner but
    tight enough to catch a regression — argon2 dominates wall-time at
    ~25-30ms, so anything else (DB lookup, JSON parse) is well under 30%
    of the dominant term.
    """
    await client.post(
        "/api/auth/register",
        json={
            "username": "frank",
            "password": "correct-horse-battery",
            "display_name": "Frank",
        },
    )

    # Warm up argon2: the very first verify in a process is slower (lazy
    # memory alloc inside the C extension). Two warmup pairs is enough to
    # take that off the table for the median calculation.
    for _ in range(2):
        await client.post(
            "/api/auth/login",
            json={"username": "frank", "password": "wrong"},
        )
        await client.post(
            "/api/auth/login",
            json={"username": "warmup-ghost", "password": "wrong"},
        )

    n = 10
    wrong_samples: list[float] = []
    unknown_samples: list[float] = []
    last_wrong = None
    last_unknown = None
    for _ in range(n):
        t0 = time.perf_counter()
        last_wrong = await client.post(
            "/api/auth/login",
            json={"username": "frank", "password": "wrong-horse-battery"},
        )
        wrong_samples.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        # Randomize unknown username per sample so we don't accidentally hit
        # any caching path the DB might add later.
        last_unknown = await client.post(
            "/api/auth/login",
            json={"username": f"ghost-{secrets.token_hex(4)}", "password": "any"},
        )
        unknown_samples.append(time.perf_counter() - t0)

    assert last_wrong is not None
    assert last_unknown is not None

    # Response-shape parity (carried over from the original assertion).
    assert last_wrong.status_code == 401
    assert last_unknown.status_code == 401
    assert last_wrong.json() == last_unknown.json()
    assert last_wrong.headers.get("www-authenticate") == last_unknown.headers.get(
        "www-authenticate"
    )
    assert last_wrong.headers.get("www-authenticate") == "Bearer"

    # Timing parity. Median, not mean — argon2's tail latency from the odd
    # GC pause skews means upward asymmetrically.
    median_wrong = statistics.median(wrong_samples)
    median_unknown = statistics.median(unknown_samples)
    delta = abs(median_wrong - median_unknown) / max(median_wrong, median_unknown)
    assert delta < 0.30, (
        f"timing-leak regression: wrong-password median={median_wrong * 1000:.2f}ms vs "
        f"unknown-user median={median_unknown * 1000:.2f}ms (delta={delta * 100:.1f}%, "
        "tolerance=30%). The unknown-user branch in auth_service.authenticate must run "
        "a dummy argon2 verify to keep wall-time comparable; see #23."
    )


# ---------------------------------------------------------------------------
# Register 409 paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_username_taken_409(client: AsyncClient) -> None:
    payload = {
        "username": "grace",
        "password": "correct-horse-battery",
        "display_name": "Grace",
    }
    first = await client.post("/api/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/auth/register", json=payload)
    assert second.status_code == 409
    assert second.json() == {"detail": "Username is already taken."}

    # Usernames are normalised to lowercase — "GRACE" is the same user.
    third = await client.post(
        "/api/auth/register",
        json={**payload, "username": "GRACE"},
    )
    assert third.status_code == 409


@pytest.mark.asyncio
async def test_register_integrity_error_409(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Covers the `IntegrityError` branch of `auth_service.register`.

    The pre-check is racy: two parallel registrations with the same
    username both pass `get_by_username is None`, then the DB's unique
    constraint catches one of them on insert. We simulate by making
    `user_repo.create` raise `IntegrityError` directly; the service
    must roll back and surface the same 409 as the pre-check branch.
    """

    async def boom(*args: Any, **kwargs: Any) -> User:
        raise IntegrityError("stmt", {}, Exception("duplicate key"))

    monkeypatch.setattr(user_repo, "create", boom)

    response = await client.post(
        "/api/auth/register",
        json={
            "username": "heidi",
            "password": "correct-horse-battery",
            "display_name": "Heidi",
        },
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Username is already taken."}


# ---------------------------------------------------------------------------
# Access token expiry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_access_token_expired_401(client: AsyncClient) -> None:
    """Forge a token with past `exp` instead of freezing time.

    Freezing time in asyncio is fragile (event loop timers, DB clock vs
    process clock, etc). Signing a JWT with `exp = now - 60s` using the
    same secret/algorithm as `app.core.security.issue_access_token`
    gives us a deterministic expired-but-otherwise-valid token.

    No user fixture needed: `jose.jwt.decode` raises
    `ExpiredSignatureError` before any DB lookup happens, so `sub`
    pointing at a non-existent id is fine.
    """
    settings = get_settings()
    now = datetime.now(tz=UTC)
    expired = jwt.encode(
        {
            "sub": "1",
            "iat": int((now - timedelta(minutes=30)).timestamp()),
            "exp": int((now - timedelta(seconds=60)).timestamp()),
        },
        settings.jwt.secret,
        algorithm=settings.jwt.algorithm,
    )

    response = await client.get("/api/me", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_access_token_bad_signature_401(client: AsyncClient) -> None:
    """A token signed with the wrong secret must 401.

    Locks in that `decode_access_token` actually verifies the
    signature — not just parses the payload.
    """
    now = datetime.now(tz=UTC)
    forged = jwt.encode(
        {
            "sub": "1",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
        },
        "definitely-not-the-real-secret",
        algorithm="HS256",
    )

    response = await client.get("/api/me", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_access_token_non_integer_sub_401(client: AsyncClient) -> None:
    """`sub` must be a stringified int; anything else → 401.

    Covers the `ValueError` branch of `decode_access_token`.
    """
    settings = get_settings()
    now = datetime.now(tz=UTC)
    weird = jwt.encode(
        {
            "sub": "not-a-number",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
        },
        settings.jwt.secret,
        algorithm=settings.jwt.algorithm,
    )

    response = await client.get("/api/me", headers={"Authorization": f"Bearer {weird}"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_access_token_unknown_user_401(client: AsyncClient) -> None:
    """Valid signature, valid `sub`, but the user was deleted → 401.

    Covers the `user is None` branch at the tail of
    `load_user_from_access_token`.
    """
    settings = get_settings()
    now = datetime.now(tz=UTC)
    token = jwt.encode(
        {
            "sub": "9999999",  # no such user; table is truncated per-test
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
        },
        settings.jwt.secret,
        algorithm=settings.jwt.algorithm,
    )

    response = await client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Refresh-token 401 paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_invalid_401(client: AsyncClient) -> None:
    """Random garbage refresh token → 401, not 500."""
    response = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": generate_refresh_token()},  # valid shape, no matching row
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.json() == {"detail": "Invalid refresh token."}


@pytest.mark.asyncio
async def test_refresh_expired_401(client: AsyncClient, db_session: AsyncSession) -> None:
    """A live (non-revoked) refresh token past its `expires_at` → 401.

    Covers the `expires_at <= now` branch of `auth_service.refresh`.
    We insert the row directly at the model level so we can backdate
    `expires_at` without faking the clock.
    """
    await client.post(
        "/api/auth/register",
        json={
            "username": "ivan",
            "password": "correct-horse-battery",
            "display_name": "Ivan",
        },
    )
    user = await user_repo.get_by_username(db_session, "ivan")
    assert user is not None

    plain = generate_refresh_token()
    expired_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(plain),
        expires_at=datetime.now(tz=UTC) - timedelta(seconds=1),
    )
    db_session.add(expired_row)
    await db_session.commit()

    response = await client.post("/api/auth/refresh", json={"refresh_token": plain})
    assert response.status_code == 401
    assert response.json() == {"detail": "Refresh token has expired."}


@pytest.mark.asyncio
async def test_refresh_concurrent_race_single_winner(
    client: AsyncClient, auth_pair: tuple[str, str, str], db_session: AsyncSession
) -> None:
    """Smoke-test that two in-flight refresh calls never both succeed.

    Two `asyncio.gather`'d POSTs over `httpx.AsyncClient` /
    `ASGITransport` may genuinely interleave at await points or run
    effectively sequentially — both produce 1x200 + 1x401 (the second
    case via the replay branch already locked in by
    `test_refresh_rotates`). So this test does NOT directly observe
    the `SELECT ... FOR UPDATE` serialization invariant from ADR-0005;
    truly exercising the FOR UPDATE path would require injecting a
    barrier mid-transaction, which is out of scope here.

    What we do assert at the HTTP / DB layer: exactly one 200, exactly
    one 401, and at most one live (non-revoked) refresh row left.
    """
    _, _, refresh_token = auth_pair

    results = await asyncio.gather(
        client.post("/api/auth/refresh", json={"refresh_token": refresh_token}),
        client.post("/api/auth/refresh", json={"refresh_token": refresh_token}),
    )
    statuses = sorted(r.status_code for r in results)

    # Exactly one winner. The loser hits either the "revoked_at set"
    # replay branch or the "row no longer matches FOR UPDATE snapshot"
    # branch — both surface as 401 at the HTTP layer.
    assert statuses.count(200) == 1, f"expected 1 winner, got statuses={statuses}"
    assert statuses.count(401) == 1, f"expected 1 loser, got statuses={statuses}"

    # The winning pair must be usable; the loser must have triggered
    # chain-revoke if it was the replay branch. Either way, the
    # post-race DB state has at most one live (non-revoked,
    # non-expired) refresh token — the successor from the winning
    # rotation. If the loser hit the replay branch, even that successor
    # got chain-revoked and we see zero live tokens. The invariant is
    # "not more than one live row", which captures both.
    live_tokens = (
        (await db_session.execute(select(RefreshToken).where(RefreshToken.revoked_at.is_(None))))
        .scalars()
        .all()
    )
    assert len(live_tokens) <= 1, f"expected at most 1 live refresh row, got {len(live_tokens)}"
