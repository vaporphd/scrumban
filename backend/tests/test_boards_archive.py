"""Integration tests for `POST /api/boards/{id}/archive` (issue #73).

Covers:
- 200 on first call — `archived_at IS NOT NULL` after.
- 200 on repeat call — `archived_at` is unchanged from first call
  (idempotent semantics per the issue: re-archive does not refresh
  the timestamp).
- 200 archive then default `GET /api/boards` excludes the archived row.
- 200 archive then `GET /api/boards?include_archived=true` includes it.
- 404 on unknown id.
- 401 without `Authorization` header.
- 200 archive of a board with columns + labels — soft-delete does not
  cascade (rows survive on the underlying tables; archived board still
  reachable via `?include_archived=true` with relations intact).

Per `implementer.md`: 3+ pytest integration cases. We ship seven —
covers each branch the acceptance criteria + idempotency contract calls
out, plus the cascade-safety invariant from the `Board.archived_at`
docstring on the model.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.column import Column as BoardColumn
from app.db.models.label import Label
from app.repositories import board_repo, user_repo


@pytest.mark.asyncio
async def test_archive_board_first_call_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """First archive call returns 200 and stamps `archived_at`."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="To archive", description=None, created_by=user.id
    )
    await db_session.commit()
    assert board.archived_at is None

    response = await client.post(
        f"/api/boards/{board.id}/archive",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == board.id
    assert body["name"] == "To archive"
    assert body["archived_at"] is not None

    # Persisted in DB.
    await db_session.refresh(board)
    assert board.archived_at is not None


@pytest.mark.asyncio
async def test_archive_board_idempotent_preserves_timestamp_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Repeat archive call returns 200 and does NOT refresh `archived_at`.

    The issue's acceptance criterion is "200 no-op on repeat" — we
    interpret that strictly as preserve-original-timestamp (rather than
    refresh-on-every-call) because the stamp records *when* the board
    first left active circulation, and overwriting it loses audit value.
    """
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="Twice-archived", description=None, created_by=user.id
    )
    await db_session.commit()

    auth = {"Authorization": f"Bearer {access}"}

    first = await client.post(f"/api/boards/{board.id}/archive", headers=auth)
    assert first.status_code == 200
    first_archived_at = first.json()["archived_at"]
    first_updated_at = first.json()["updated_at"]
    assert first_archived_at is not None

    second = await client.post(f"/api/boards/{board.id}/archive", headers=auth)
    assert second.status_code == 200
    second_archived_at = second.json()["archived_at"]
    second_updated_at = second.json()["updated_at"]

    # Idempotency: the timestamp returned the second time is the same
    # one the first call stamped.
    assert second_archived_at == first_archived_at
    # And `updated_at` must not drift either — the no-op repeat call
    # must not bump the row's updated_at, otherwise a future refactor
    # could silently turn idempotent re-archive into a write.
    assert second_updated_at == first_updated_at


@pytest.mark.asyncio
async def test_archive_board_then_default_list_excludes_it_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """After archive, the default `GET /api/boards` no longer returns it."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    keep = await board_repo.create(
        db_session, name="Stay visible", description=None, created_by=user.id
    )
    archive_target = await board_repo.create(
        db_session, name="To archive", description=None, created_by=user.id
    )
    await db_session.commit()

    auth = {"Authorization": f"Bearer {access}"}

    archive_resp = await client.post(f"/api/boards/{archive_target.id}/archive", headers=auth)
    assert archive_resp.status_code == 200

    list_resp = await client.get("/api/boards", headers=auth)
    assert list_resp.status_code == 200
    body = list_resp.json()
    ids = {row["id"] for row in body}
    assert keep.id in ids
    assert archive_target.id not in ids


@pytest.mark.asyncio
async def test_archive_board_then_include_archived_returns_it_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """After archive, `?include_archived=true` still returns the row."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    archive_target = await board_repo.create(
        db_session, name="Archived but listed", description=None, created_by=user.id
    )
    await db_session.commit()

    auth = {"Authorization": f"Bearer {access}"}

    archive_resp = await client.post(f"/api/boards/{archive_target.id}/archive", headers=auth)
    assert archive_resp.status_code == 200

    list_resp = await client.get("/api/boards?include_archived=true", headers=auth)
    assert list_resp.status_code == 200
    body = list_resp.json()
    by_id = {row["id"]: row for row in body}
    assert archive_target.id in by_id
    assert by_id[archive_target.id]["archived_at"] is not None


@pytest.mark.asyncio
async def test_archive_board_unknown_id_404(
    client: AsyncClient, auth_pair: tuple[str, str, str]
) -> None:
    _, access, _ = auth_pair
    response = await client.post(
        "/api/boards/9999999/archive",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_archive_board_no_auth_401(client: AsyncClient) -> None:
    response = await client.post("/api/boards/1/archive")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_archive_board_does_not_cascade_columns_or_labels_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Archive is soft-delete: columns + labels stay attached to the row.

    The model docstring on `Board.archived_at` calls this out:
    "archiving a board hides it from board listings but preserves the
    whole tree (columns, tasks, labels) so activity history and search
    stay intact." This test locks that contract — a future "archive
    cascades to columns" change has to update this test deliberately.
    """
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="With children", description=None, created_by=user.id
    )
    await db_session.flush()
    db_session.add(BoardColumn(board_id=board.id, name="To do", position=0))
    db_session.add(Label(board_id=board.id, name="bug", color="#ef4444"))
    await db_session.commit()

    auth = {"Authorization": f"Bearer {access}"}
    archive_resp = await client.post(f"/api/boards/{board.id}/archive", headers=auth)
    assert archive_resp.status_code == 200

    # Detail GET with include_archived=true must return the board with
    # columns + labels still present — proves no cascade happened.
    detail_resp = await client.get(f"/api/boards/{board.id}?include_archived=true", headers=auth)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == board.id
    assert detail["archived_at"] is not None
    assert len(detail["columns"]) == 1
    assert detail["columns"][0]["name"] == "To do"
    assert len(detail["labels"]) == 1
    assert detail["labels"][0]["name"] == "bug"
