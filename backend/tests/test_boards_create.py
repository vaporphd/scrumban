"""Integration tests for `POST /api/boards` (issue #69).

Covers:
- 201 happy path with auth — body matches `BoardRead`, row in DB carries
  `created_by = authenticated user`.
- 401 without `Authorization` header.
- 401 with garbage Bearer token.
- 422 on empty `name`.
- 422 on `name` over the 128-char schema cap.
- 201 with `description` omitted (optional field).

Per `implementer.md`: 3+ pytest integration cases. We exceed that to
also lock the optional-description path and the bad-bearer 401, both of
which are easy regressions in router refactors.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.board import Board
from app.repositories import user_repo


@pytest.mark.asyncio
async def test_create_board_happy_path_201(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    username, access, _ = auth_pair

    response = await client.post(
        "/api/boards",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Roadmap", "description": "Q3 plan"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Roadmap"
    assert body["description"] == "Q3 plan"
    assert isinstance(body["id"], int)
    assert body["archived_at"] is None
    assert "created_at" in body
    assert "updated_at" in body
    # `created_by` is the FK to the authenticated user.
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    assert body["created_by"] == user.id

    # Row is actually persisted with the right owner.
    row = await db_session.get(Board, body["id"])
    assert row is not None
    assert row.name == "Roadmap"
    assert row.created_by == user.id


@pytest.mark.asyncio
async def test_create_board_without_description_201(
    client: AsyncClient, auth_pair: tuple[str, str, str]
) -> None:
    """`description` is optional — omitting it is a valid 201."""
    _, access, _ = auth_pair

    response = await client.post(
        "/api/boards",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Solo board"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Solo board"
    assert body["description"] is None


@pytest.mark.asyncio
async def test_create_board_no_auth_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/boards",
        json={"name": "Nope", "description": "no token"},
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_create_board_bad_bearer_401(client: AsyncClient) -> None:
    """Garbage token must 401, not 500 — locks the deps.current_user branch."""
    response = await client.post(
        "/api/boards",
        headers={"Authorization": "Bearer not-a-jwt"},
        json={"name": "Whatever"},
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_create_board_empty_name_422(
    client: AsyncClient, auth_pair: tuple[str, str, str]
) -> None:
    _, access, _ = auth_pair
    response = await client.post(
        "/api/boards",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "", "description": "empty name"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_board_oversized_name_422(
    client: AsyncClient, auth_pair: tuple[str, str, str]
) -> None:
    """`name` is capped at 128 chars by the BoardCreate schema."""
    _, access, _ = auth_pair
    response = await client.post(
        "/api/boards",
        headers={"Authorization": f"Bearer {access}"},
        # 129 chars — one past the cap.
        json={"name": "x" * 129},
    )
    assert response.status_code == 422
