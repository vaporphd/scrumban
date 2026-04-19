"""Integration tests for `PATCH /api/boards/{id}` (issue #72).

Covers:
- 200 update of `name` only — DB persists the change, `description`
  untouched.
- 200 update of `description` only — DB persists, `name` untouched.
- 200 update of both fields at once.
- 200 explicit `description: null` clears a previously-set description
  (this is the `exclude_unset` vs `exclude_none` behavior the service
  documents — sending null is "clear", omitting is "leave alone").
- 200 empty body `{}` is a no-op — same row returned, `updated_at` may
  or may not bump (we don't assert it; the no-op contract is "fields
  unchanged", not "no UPDATE issued").
- 422 on empty `name`.
- 422 on `name` over the 128-char schema cap.
- 404 on unknown id.
- 404 on archived board (archived = read-only by default — same model
  as `get_board`).
- 401 without `Authorization` header.

Per `implementer.md`: 3+ pytest integration cases. We ship ten —
covers each branch (each-field-only, both, null-clears, no-op, two 422
shapes, two 404 shapes, 401) so a future router refactor can't quietly
regress any of them.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import board_repo, user_repo


@pytest.mark.asyncio
async def test_update_board_name_only_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """PATCH `name` only — `description` stays untouched."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="Old name", description="Original description", created_by=user.id
    )
    await db_session.commit()

    response = await client.patch(
        f"/api/boards/{board.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "New name"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == board.id
    assert body["name"] == "New name"
    # description unchanged because the client didn't send it.
    assert body["description"] == "Original description"

    # Persisted in DB.
    # Re-fetch via the test session. Since the row is already in the
    # test session's identity map (we created it above), refresh to
    # pull what the API session committed.
    await db_session.refresh(board)
    row = board
    assert row is not None
    assert row.name == "New name"
    assert row.description == "Original description"


@pytest.mark.asyncio
async def test_update_board_description_only_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """PATCH `description` only — `name` stays untouched."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="Stable name", description="Old description", created_by=user.id
    )
    await db_session.commit()

    response = await client.patch(
        f"/api/boards/{board.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"description": "New description"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Stable name"
    assert body["description"] == "New description"


@pytest.mark.asyncio
async def test_update_board_both_fields_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """PATCH both fields in one request."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="Original", description="Original desc", created_by=user.id
    )
    await db_session.commit()

    response = await client.patch(
        f"/api/boards/{board.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Renamed", "description": "Reworded"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["description"] == "Reworded"


@pytest.mark.asyncio
async def test_update_board_null_description_clears_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Explicit `description: null` clears a previously-set description.

    This is the `exclude_unset` semantics documented in the service:
    sending JSON null means "clear this field"; omitting means "leave
    it alone". `exclude_none` would conflate these.
    """
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="With desc", description="To be cleared", created_by=user.id
    )
    await db_session.commit()

    response = await client.patch(
        f"/api/boards/{board.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"description": None},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["description"] is None
    # Persisted as NULL.
    # Re-fetch via the test session. Since the row is already in the
    # test session's identity map (we created it above), refresh to
    # pull what the API session committed.
    await db_session.refresh(board)
    row = board
    assert row is not None
    assert row.description is None


@pytest.mark.asyncio
async def test_update_board_empty_body_is_noop_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """PATCH with empty body returns the current row unchanged."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="Untouched", description="Unchanged", created_by=user.id
    )
    await db_session.commit()

    response = await client.patch(
        f"/api/boards/{board.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Untouched"
    assert body["description"] == "Unchanged"


@pytest.mark.asyncio
async def test_update_board_empty_name_422(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """`name=""` violates the 1-char minimum on `BoardUpdate.name`."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="Original", description=None, created_by=user.id
    )
    await db_session.commit()

    response = await client.patch(
        f"/api/boards/{board.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": ""},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_board_oversized_name_422(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """`name` over the 128-char cap is rejected by pydantic."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="Original", description=None, created_by=user.id
    )
    await db_session.commit()

    response = await client.patch(
        f"/api/boards/{board.id}",
        headers={"Authorization": f"Bearer {access}"},
        # 129 chars — one past the cap.
        json={"name": "x" * 129},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_board_unknown_id_404(
    client: AsyncClient, auth_pair: tuple[str, str, str]
) -> None:
    _, access, _ = auth_pair
    response = await client.patch(
        "/api/boards/9999999",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Anything"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_board_archived_404(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Archived boards are read-only — PATCH returns 404 (same model as GET)."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="Archived", description=None, created_by=user.id
    )
    board.archived_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.patch(
        f"/api/boards/{board.id}",
        headers={"Authorization": f"Bearer {access}"},
        json={"name": "Renamed?"},
    )
    assert response.status_code == 404

    # The DB row was not mutated (404 short-circuits before any flush).
    # Re-fetch via the test session. Since the row is already in the
    # test session's identity map (we created it above), refresh to
    # pull what the API session committed.
    await db_session.refresh(board)
    row = board
    assert row is not None
    assert row.name == "Archived"


@pytest.mark.asyncio
async def test_update_board_no_auth_401(client: AsyncClient) -> None:
    response = await client.patch("/api/boards/1", json={"name": "nope"})
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
