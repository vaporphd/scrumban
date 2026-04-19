"""Integration tests for `GET /api/boards/{id}` (issue #71).

Covers:
- 200 happy path on a board with no columns + no labels — `columns: []`,
  `labels: []`.
- 200 with seeded columns + labels — columns are returned ordered by
  `position`; labels are present.
- 404 on a numeric id that doesn't exist.
- 404 on an archived board with the default filter.
- 200 on an archived board with `?include_archived=true`.
- 401 without `Authorization` header.
- N+1 assertion: hitting the endpoint with N=5 columns + N=5 labels
  issues at most 3 SELECT statements against the `boards` / `columns` /
  `labels` tables (board + 1 selectin per relationship). The auth
  middleware adds its own SELECTs (user lookup, etc.); we count only
  the queries against the three relevant tables to keep the assertion
  honest about the eager-load shape.

Per `implementer.md`: 3+ pytest integration cases. We ship seven —
the empty-relations and ordering cases lock common regressions cheaply,
and the N+1 case is the load-bearing assertion called out in the issue.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.column import Column
from app.db.models.label import Label
from app.db.session import engine
from app.repositories import board_repo, user_repo


@pytest.mark.asyncio
async def test_get_board_empty_relations_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Board with no columns + no labels comes back with both as empty lists."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="Empty board", description=None, created_by=user.id
    )
    await db_session.commit()

    response = await client.get(
        f"/api/boards/{board.id}",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == board.id
    assert body["name"] == "Empty board"
    assert body["columns"] == []
    assert body["labels"] == []
    # BoardDetailRead extends BoardRead — base fields still present.
    assert body["created_by"] == user.id
    assert body["archived_at"] is None


@pytest.mark.asyncio
async def test_get_board_columns_ordered_by_position_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Columns come back in `position` order regardless of insert order."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="Ordered", description=None, created_by=user.id
    )
    # Insert in the wrong order to prove the loader sorts (not insert order).
    db_session.add_all(
        [
            Column(board_id=board.id, name="Done", position=2),
            Column(board_id=board.id, name="Todo", position=0),
            Column(board_id=board.id, name="Doing", position=1),
        ]
    )
    db_session.add_all(
        [
            Label(board_id=board.id, name="bug", color="#ef4444"),
            Label(board_id=board.id, name="feat", color="#22c55e"),
        ]
    )
    await db_session.commit()

    response = await client.get(
        f"/api/boards/{board.id}",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert [c["name"] for c in body["columns"]] == ["Todo", "Doing", "Done"]
    assert [c["position"] for c in body["columns"]] == [0, 1, 2]
    # Labels: shape check; order is not contractual (no `order_by` on the
    # relationship) so just assert the set.
    assert {label["name"] for label in body["labels"]} == {"bug", "feat"}


@pytest.mark.asyncio
async def test_get_board_unknown_id_404(
    client: AsyncClient, auth_pair: tuple[str, str, str]
) -> None:
    _, access, _ = auth_pair
    response = await client.get(
        "/api/boards/9999999",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_board_archived_default_404(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Archived board is 404 under the default filter."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="Archived", description=None, created_by=user.id
    )
    board.archived_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.get(
        f"/api/boards/{board.id}",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_board_archived_include_archived_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """`?include_archived=true` returns the archived board."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(
        db_session, name="Archived but visible", description=None, created_by=user.id
    )
    board.archived_at = datetime.now(UTC)
    await db_session.commit()

    response = await client.get(
        f"/api/boards/{board.id}?include_archived=true",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == board.id
    assert body["archived_at"] is not None
    assert body["columns"] == []
    assert body["labels"] == []


@pytest.mark.asyncio
async def test_get_board_no_auth_401(client: AsyncClient) -> None:
    response = await client.get("/api/boards/1")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.asyncio
async def test_get_board_no_n_plus_1(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """With N=5 columns + N=5 labels, the endpoint issues at most 3 selects
    against `boards` / `columns` / `labels`.

    The `selectinload` strategy guarantees one extra SELECT per
    relationship regardless of N; if a future refactor re-introduces
    lazy-loading per row, the count climbs to 1 + N + N (= 11 for N=5)
    and this test fails fast. Auth middleware queries on the `users`
    table are excluded so the assertion stays on the eager-load shape,
    not on unrelated middleware churn.
    """
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None

    board = await board_repo.create(db_session, name="Many", description=None, created_by=user.id)
    db_session.add_all([Column(board_id=board.id, name=f"Col {i}", position=i) for i in range(5)])
    db_session.add_all([Label(board_id=board.id, name=f"l{i}", color="#abcdef") for i in range(5)])
    await db_session.commit()

    queries: list[str] = []

    def _capture(
        _conn: Any,
        _cursor: Any,
        statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        # Only count SELECTs against the three relevant tables. The
        # auth dependency hits `users` / `refresh_tokens`; counting
        # those would conflate eager-load efficiency with auth churn.
        lower = statement.lower()
        if not lower.lstrip().startswith("select"):
            return
        if " from boards" in lower or " from columns" in lower or " from labels" in lower:
            queries.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _capture)
    try:
        response = await client.get(
            f"/api/boards/{board.id}",
            headers={"Authorization": f"Bearer {access}"},
        )
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _capture)

    assert response.status_code == 200
    body = response.json()
    assert len(body["columns"]) == 5
    assert len(body["labels"]) == 5
    # 1 board SELECT + 1 selectin SELECT per relationship = 3.
    assert len(queries) <= 3, (
        f"Expected ≤3 SELECTs against boards/columns/labels, got {len(queries)}:\n"
        + "\n".join(queries)
    )
