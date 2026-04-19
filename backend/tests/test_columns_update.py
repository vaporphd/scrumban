"""Integration tests for `PATCH /api/columns/{id}` (issue #78).

Covers:
- 200 update of `name` only — DB persists, `wip_limit` untouched.
- 200 update of `wip_limit` only — DB persists, `name` untouched.
- 200 update of both fields at once.
- 200 explicit `wip_limit: null` clears a previously-set limit
  (`exclude_unset` semantics: sending null = clear; omitting = leave
  alone — same model the boards PATCH service documents).
- 200 empty body `{}` is a no-op — same row returned.
- 422 on empty `name`.
- 422 on `name` over the 64-char schema cap.
- 422 on `wip_limit == 0` (schema requires `>= 1`).
- 422 on `wip_limit > 1000` (schema requires `<= 1000`).
- 404 on unknown column id.
- 404 on column whose parent board is archived (read-only model).
- 401 without `Authorization` header.

Per `implementer.md`: 3+ pytest integration cases. We ship twelve so
each branch (each-field-only, both, null-clears, no-op, both 422 name
shapes, both 422 wip_limit shapes, both 404 shapes, 401) is locked
against a future router refactor.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.board import Board
from app.db.models.column import Column
from app.repositories import board_repo, column_repo, user_repo


async def _make_board_and_column(
    db_session: AsyncSession,
    user_id: int,
    *,
    column_name: str = "Original",
    wip_limit: int | None = 5,
) -> tuple[Board, Column]:
    """Test helper: create a board + a single column owned by `user_id`."""
    board = await board_repo.create(
        db_session, name="Roadmap", description=None, created_by=user_id
    )
    column = await column_repo.create(
        db_session,
        board_id=board.id,
        name=column_name,
        position=1000,
        wip_limit=wip_limit,
    )
    await db_session.commit()
    return board, column


@pytest.mark.asyncio
async def test_update_column_name_only_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """PATCH `name` only — `wip_limit` stays untouched."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    _, column = await _make_board_and_column(db_session, user.id, wip_limit=5)

    response = await client.patch(
        f"/api/columns/{column.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Renamed"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == column.id
    assert body["name"] == "Renamed"
    # wip_limit unchanged because the client didn't send it.
    assert body["wip_limit"] == 5

    await db_session.refresh(column)
    assert column.name == "Renamed"
    assert column.wip_limit == 5


@pytest.mark.asyncio
async def test_update_column_wip_limit_only_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """PATCH `wip_limit` only — `name` stays untouched."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    _, column = await _make_board_and_column(db_session, user.id, column_name="Stable", wip_limit=3)

    response = await client.patch(
        f"/api/columns/{column.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"wip_limit": 7},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Stable"
    assert body["wip_limit"] == 7

    await db_session.refresh(column)
    assert column.name == "Stable"
    assert column.wip_limit == 7


@pytest.mark.asyncio
async def test_update_column_both_fields_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """PATCH both fields in one request."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    _, column = await _make_board_and_column(db_session, user.id, wip_limit=5)

    response = await client.patch(
        f"/api/columns/{column.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Renamed", "wip_limit": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["wip_limit"] == 10


@pytest.mark.asyncio
async def test_update_column_null_wip_limit_clears_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Explicit `wip_limit: null` clears a previously-set limit.

    `exclude_unset` semantics: sending JSON null means "clear this
    field"; omitting means "leave it alone". Mirrors the boards PATCH
    behavior — see `boards_service.update_board` docstring.
    """
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    _, column = await _make_board_and_column(db_session, user.id, wip_limit=5)

    response = await client.patch(
        f"/api/columns/{column.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"wip_limit": None},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["wip_limit"] is None

    await db_session.refresh(column)
    assert column.wip_limit is None


@pytest.mark.asyncio
async def test_update_column_empty_body_is_noop_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """PATCH with empty body returns the current row unchanged."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    _, column = await _make_board_and_column(
        db_session, user.id, column_name="Untouched", wip_limit=4
    )

    response = await client.patch(
        f"/api/columns/{column.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Untouched"
    assert body["wip_limit"] == 4


@pytest.mark.asyncio
async def test_update_column_empty_name_422(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """`name=""` violates the 1-char minimum on `ColumnUpdate.name`."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    _, column = await _make_board_and_column(db_session, user.id)

    response = await client.patch(
        f"/api/columns/{column.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_column_oversized_name_422(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """`name` over the 64-char cap is rejected by pydantic."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    _, column = await _make_board_and_column(db_session, user.id)

    response = await client.patch(
        f"/api/columns/{column.id}",
        headers={"Authorization": f"Bearer {access}"},
        # 65 chars — one past the cap.
        json={"name": "x" * 65},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_column_wip_limit_zero_422(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """`wip_limit` schema requires `>= 1` — zero must 422."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    _, column = await _make_board_and_column(db_session, user.id)

    response = await client.patch(
        f"/api/columns/{column.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"wip_limit": 0},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_column_wip_limit_over_cap_422(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """`wip_limit` schema requires `<= 1000` — 1001 must 422."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    _, column = await _make_board_and_column(db_session, user.id)

    response = await client.patch(
        f"/api/columns/{column.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"wip_limit": 1001},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_column_unknown_id_404(
    client: AsyncClient, auth_pair: tuple[str, str, str]
) -> None:
    _, access, _ = auth_pair
    response = await client.patch(
        "/api/columns/9999999",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Anything"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_column_archived_board_404(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Column on an archived board is not patchable — 404 (read-only model)."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board, column = await _make_board_and_column(db_session, user.id)
    board.archived_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.patch(
        f"/api/columns/{column.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Renamed?"},
    )
    assert response.status_code == 404

    # The DB row was not mutated (404 short-circuits before any flush).
    await db_session.refresh(column)
    assert column.name == "Original"


@pytest.mark.asyncio
async def test_update_column_no_auth_401(client: AsyncClient) -> None:
    response = await client.patch("/api/columns/1", json={"name": "nope"})
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
