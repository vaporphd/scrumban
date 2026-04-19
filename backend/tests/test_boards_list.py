"""Integration tests for `GET /api/boards` (issue #70).

Covers:
- 200 with empty list when no boards exist.
- 200 returns only non-archived boards by default.
- 200 with `?include_archived=true` returns every board.
- 401 without `Authorization` header.
- 200 returns boards in `created_at desc` order (newest first).

Per `implementer.md`: 3+ pytest integration cases. We add five —
the empty-state and ordering cases are cheap to lock and prevent
common regressions when the repo query is later touched.

The archived-board scenario is seeded directly via the repo +
`archived_at = datetime.now(UTC)` because `POST /api/boards/{id}/archive`
(issue #73) hasn't shipped yet. Once #73 lands, a follow-up may
prefer to drive archive via the endpoint here, but the direct-row
approach keeps this test independent of the archive endpoint's PR
order.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import board_repo, user_repo


@pytest.mark.asyncio
async def test_list_boards_empty_200(client: AsyncClient, auth_pair: tuple[str, str, str]) -> None:
    _, access, _ = auth_pair

    response = await client.get(
        "/api/boards",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_boards_excludes_archived_by_default_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Seed 1 active + 1 archived board; default response holds only the active one."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    active = await board_repo.create(
        db_session, name="Active board", description=None, created_by=user.id
    )
    archived = await board_repo.create(
        db_session, name="Archived board", description=None, created_by=user.id
    )
    archived.archived_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.get(
        "/api/boards",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == active.id
    assert body[0]["name"] == "Active board"
    assert body[0]["archived_at"] is None


@pytest.mark.asyncio
async def test_list_boards_include_archived_returns_all_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """`?include_archived=true` returns every board including archived."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    active = await board_repo.create(
        db_session, name="Active board", description=None, created_by=user.id
    )
    archived = await board_repo.create(
        db_session, name="Archived board", description=None, created_by=user.id
    )
    archived.archived_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.get(
        "/api/boards?include_archived=true",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    ids = {row["id"] for row in body}
    assert ids == {active.id, archived.id}
    # Archived row carries a non-null `archived_at`; active stays null.
    by_id = {row["id"]: row for row in body}
    assert by_id[active.id]["archived_at"] is None
    assert by_id[archived.id]["archived_at"] is not None


@pytest.mark.asyncio
async def test_list_boards_no_auth_401(client: AsyncClient) -> None:
    response = await client.get("/api/boards")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_list_boards_newest_first_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Two boards created in order — response is newest first (`created_at desc`)."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    first = await board_repo.create(
        db_session, name="First board", description=None, created_by=user.id
    )
    second = await board_repo.create(
        db_session, name="Second board", description=None, created_by=user.id
    )
    await db_session.commit()

    response = await client.get(
        "/api/boards",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert [row["id"] for row in body] == [second.id, first.id]
