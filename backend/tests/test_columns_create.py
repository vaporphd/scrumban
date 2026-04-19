"""Integration tests for `POST /api/boards/{board_id}/columns` (issue #77).

Covers:
- 201 happy path: first column on a fresh board → `position == 1000`,
  body matches `ColumnRead`, row persisted with the right `board_id`.
- 201 second column on the same board → `position == 2000`
  (max + COLUMN_POSITION_STEP — append semantics).
- 201 with `wip_limit` omitted (optional field).
- 404 on unknown board id.
- 404 on archived board (archived = read-only — same model as the
  boards PATCH endpoint).
- 422 on empty `name`.
- 422 on `name` over the 64-char schema cap.
- 422 on `wip_limit == 0` (schema requires `>= 1`).
- 401 without `Authorization` header.

Per `implementer.md`: 3+ pytest integration cases. We ship nine —
covers each branch (happy path twice for position math, optional
field, both 404 shapes, both 422 shapes for name + the wip_limit
boundary, 401) so a future router refactor can't quietly regress any
of them.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.column import Column
from app.repositories import board_repo, user_repo


@pytest.mark.asyncio
async def test_create_column_happy_path_201(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board = await board_repo.create(
        db_session, name="Roadmap", description=None, created_by=user.id
    )
    await db_session.commit()

    response = await client.post(
        f"/api/boards/{board.id}/columns",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "To do", "wip_limit": 5},
    )

    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["id"], int)
    assert body["board_id"] == board.id
    assert body["name"] == "To do"
    assert body["position"] == 1000
    assert body["wip_limit"] == 5
    assert "created_at" in body
    assert "updated_at" in body

    # Row is actually persisted — re-read on a fresh session view.
    row = await db_session.get(Column, body["id"])
    assert row is not None
    assert row.board_id == board.id
    assert row.name == "To do"
    assert row.position == 1000
    assert row.wip_limit == 5


@pytest.mark.asyncio
async def test_create_column_second_column_appends_at_max_plus_step(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Second column on the same board lands at `MAX(position) + 1000`."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board = await board_repo.create(
        db_session, name="Roadmap", description=None, created_by=user.id
    )
    await db_session.commit()

    first = await client.post(
        f"/api/boards/{board.id}/columns",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "To do"},
    )
    assert first.status_code == 201
    assert first.json()["position"] == 1000

    second = await client.post(
        f"/api/boards/{board.id}/columns",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Done"},
    )
    assert second.status_code == 201
    assert second.json()["position"] == 2000


@pytest.mark.asyncio
async def test_create_column_without_wip_limit_201(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """`wip_limit` is optional — omitting it returns 201 with `wip_limit=null`."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board = await board_repo.create(
        db_session, name="Roadmap", description=None, created_by=user.id
    )
    await db_session.commit()

    response = await client.post(
        f"/api/boards/{board.id}/columns",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Backlog"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Backlog"
    assert body["wip_limit"] is None


@pytest.mark.asyncio
async def test_create_column_unknown_board_404(
    client: AsyncClient, auth_pair: tuple[str, str, str]
) -> None:
    _, access, _ = auth_pair
    response = await client.post(
        "/api/boards/9999999/columns",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Nope"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_column_archived_board_404(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Archived boards are read-only — adding columns 404s, not 403s.

    Same archived = read-only model as `boards_service.update_board`.
    """
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board = await board_repo.create(db_session, name="Old", description=None, created_by=user.id)
    board.archived_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.post(
        f"/api/boards/{board.id}/columns",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Cannot add"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_column_empty_name_422(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board = await board_repo.create(
        db_session, name="Roadmap", description=None, created_by=user.id
    )
    await db_session.commit()

    response = await client.post(
        f"/api/boards/{board.id}/columns",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_column_oversized_name_422(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """`name` is capped at 64 chars by the ColumnCreate schema."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board = await board_repo.create(
        db_session, name="Roadmap", description=None, created_by=user.id
    )
    await db_session.commit()

    response = await client.post(
        f"/api/boards/{board.id}/columns",
        headers={"Authorization": f"Bearer {access}"},
        # 65 chars — one past the cap.
        json={"name": "x" * 65},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_column_wip_limit_zero_422(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """`wip_limit` schema requires `>= 1` — zero must 422."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board = await board_repo.create(
        db_session, name="Roadmap", description=None, created_by=user.id
    )
    await db_session.commit()

    response = await client.post(
        f"/api/boards/{board.id}/columns",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "WIP", "wip_limit": 0},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_column_no_auth_401(client: AsyncClient) -> None:
    """No bearer → 401 before we even reach the board lookup."""
    response = await client.post(
        "/api/boards/1/columns",
        json={"name": "No auth"},
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
