"""Integration tests for `POST /api/boards/{board_id}/columns/reorder` (issue #80).

Covers:
- 200 happy path: 3 columns A/B/C reversed to C/B/A → response in new
  order with positions 1000/2000/3000; DB rows match.
- 200 idempotent: passing the *current* order still rewrites positions
  and returns 200 (the rewrite is a no-op semantically but exercises
  the same flush path).
- 400 partial list (subset of board's columns) → no DB mutation.
- 400 extra ids (column id from another board mixed in) → no mutation.
- 400 duplicate ids `[A, A, B]` → no mutation.
- 400 unknown id (id that doesn't exist anywhere) → no mutation.
- 404 unknown board id.
- 404 archived parent board (read-only obscurity contract — same as
  PATCH/DELETE).
- 422 empty `ordered_column_ids` (pydantic `min_length=1`).
- 401 without `Authorization` header.

Per `implementer.md`: 3+ pytest cases; we ship ten so each
validation flavor is locked against a future router refactor (the
service collapses partial / extra / duplicate / unknown onto one
`invalid_reorder` code, but each input shape gets its own test so a
regression in one branch can't hide behind another).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.board import Board
from app.db.models.column import Column
from app.repositories import board_repo, column_repo, user_repo


async def _make_board_with_three_columns(
    db_session: AsyncSession, user_id: int
) -> tuple[Board, Column, Column, Column]:
    """Test helper: board + columns A/B/C at positions 1000/2000/3000."""
    board = await board_repo.create(
        db_session, name="Roadmap", description=None, created_by=user_id
    )
    a = await column_repo.create(
        db_session, board_id=board.id, name="A", position=1000, wip_limit=None
    )
    b = await column_repo.create(
        db_session, board_id=board.id, name="B", position=2000, wip_limit=None
    )
    c = await column_repo.create(
        db_session, board_id=board.id, name="C", position=3000, wip_limit=None
    )
    await db_session.commit()
    return board, a, b, c


@pytest.mark.asyncio
async def test_reorder_columns_reverse_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """3 columns A/B/C reversed to C/B/A → positions 1000/2000/3000 with C first."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board, a, b, c = await _make_board_with_three_columns(db_session, user.id)

    response = await client.post(
        f"/api/boards/{board.id}/columns/reorder",
        headers={"Authorization": f"Bearer {access}"},
        json={"ordered_column_ids": [c.id, b.id, a.id]},
    )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 3
    # Response is in the new display order — C at slot 0, A at slot 2.
    assert [row["id"] for row in body] == [c.id, b.id, a.id]
    # Positions rewritten to the canonical 1000/2000/3000 spread.
    assert [row["position"] for row in body] == [1000, 2000, 3000]
    # Names follow ids — sanity that we didn't accidentally rename anything.
    assert [row["name"] for row in body] == ["C", "B", "A"]

    # DB rows match. Snapshot the ids before expire_all per the
    # MissingGreenlet trap pattern — `column.id` would lazy-load
    # against the closed transaction otherwise.
    a_id, b_id, c_id = a.id, b.id, c.id
    db_session.expire_all()
    fresh_a = await db_session.get(Column, a_id)
    fresh_b = await db_session.get(Column, b_id)
    fresh_c = await db_session.get(Column, c_id)
    assert fresh_a is not None and fresh_a.position == 3000
    assert fresh_b is not None and fresh_b.position == 2000
    assert fresh_c is not None and fresh_c.position == 1000


@pytest.mark.asyncio
async def test_reorder_columns_idempotent_same_order_200(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Reorder to current order returns 200 with positions unchanged.

    Tests that the rewrite is well-defined even when the new order
    equals the old order — a no-op semantically but the same flush
    path runs. Locks idempotency for clients that POST a full snapshot
    after every drag.
    """
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board, a, b, c = await _make_board_with_three_columns(db_session, user.id)

    response = await client.post(
        f"/api/boards/{board.id}/columns/reorder",
        headers={"Authorization": f"Bearer {access}"},
        json={"ordered_column_ids": [a.id, b.id, c.id]},
    )

    assert response.status_code == 200
    body = response.json()
    assert [row["id"] for row in body] == [a.id, b.id, c.id]
    assert [row["position"] for row in body] == [1000, 2000, 3000]


@pytest.mark.asyncio
async def test_reorder_columns_partial_list_400(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Partial list (subset of board's columns) → 400 + no mutation.

    The acceptance criterion calls this out explicitly: the body must
    name the *complete* desired order. A board with {A, B, C} that
    receives `[A, B]` is missing C and must fail.
    """
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board, a, b, c = await _make_board_with_three_columns(db_session, user.id)

    a_id, b_id, c_id = a.id, b.id, c.id
    response = await client.post(
        f"/api/boards/{board.id}/columns/reorder",
        headers={"Authorization": f"Bearer {access}"},
        json={"ordered_column_ids": [a_id, b_id]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_reorder"

    # No mutation — original positions still in place.
    db_session.expire_all()
    fresh_a = await db_session.get(Column, a_id)
    fresh_b = await db_session.get(Column, b_id)
    fresh_c = await db_session.get(Column, c_id)
    assert fresh_a is not None and fresh_a.position == 1000
    assert fresh_b is not None and fresh_b.position == 2000
    assert fresh_c is not None and fresh_c.position == 3000


@pytest.mark.asyncio
async def test_reorder_columns_extra_id_from_other_board_400(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Extra id (a column from another board) → 400 + no mutation.

    A request that names ids beyond the target board's set must fail —
    even if every named id exists *somewhere*. This is the
    cross-board-leak guard: a drag-handler bug that posted ids from a
    different board would otherwise silently rewrite positions across
    board boundaries.
    """
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board, a, b, c = await _make_board_with_three_columns(db_session, user.id)

    # Create a second board with one column — its id is an "extra"
    # from the target board's perspective.
    other_board = await board_repo.create(
        db_session, name="Other", description=None, created_by=user.id
    )
    other_col = await column_repo.create(
        db_session, board_id=other_board.id, name="X", position=1000, wip_limit=None
    )
    await db_session.commit()

    a_id, b_id, c_id, other_id = a.id, b.id, c.id, other_col.id
    response = await client.post(
        f"/api/boards/{board.id}/columns/reorder",
        headers={"Authorization": f"Bearer {access}"},
        json={"ordered_column_ids": [a_id, b_id, c_id, other_id]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_reorder"

    # No mutation on either board.
    db_session.expire_all()
    fresh_a = await db_session.get(Column, a_id)
    fresh_b = await db_session.get(Column, b_id)
    fresh_c = await db_session.get(Column, c_id)
    fresh_other = await db_session.get(Column, other_id)
    assert fresh_a is not None and fresh_a.position == 1000
    assert fresh_b is not None and fresh_b.position == 2000
    assert fresh_c is not None and fresh_c.position == 3000
    assert fresh_other is not None and fresh_other.position == 1000


@pytest.mark.asyncio
async def test_reorder_columns_duplicate_ids_400(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Duplicate ids `[A, A, B]` → 400 + no mutation.

    Even when the multiset coincidentally matches the board's set
    (here `[A, A, B]` has set `{A, B}` != `{A, B, C}` — caught by
    set-equality), the explicit `len(list) != len(set)` branch
    guarantees rejection independent of the board's contents. Tests
    the duplicate-rejection guarantee per service docstring.
    """
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board, a, b, c = await _make_board_with_three_columns(db_session, user.id)

    a_id, b_id, c_id = a.id, b.id, c.id
    response = await client.post(
        f"/api/boards/{board.id}/columns/reorder",
        headers={"Authorization": f"Bearer {access}"},
        json={"ordered_column_ids": [a_id, a_id, b_id]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_reorder"

    db_session.expire_all()
    fresh_a = await db_session.get(Column, a_id)
    fresh_b = await db_session.get(Column, b_id)
    fresh_c = await db_session.get(Column, c_id)
    assert fresh_a is not None and fresh_a.position == 1000
    assert fresh_b is not None and fresh_b.position == 2000
    assert fresh_c is not None and fresh_c.position == 3000


@pytest.mark.asyncio
async def test_reorder_columns_unknown_id_400(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Unknown id (id that doesn't exist anywhere) → 400 + no mutation."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board, a, b, c = await _make_board_with_three_columns(db_session, user.id)

    a_id, b_id, c_id = a.id, b.id, c.id
    response = await client.post(
        f"/api/boards/{board.id}/columns/reorder",
        headers={"Authorization": f"Bearer {access}"},
        json={"ordered_column_ids": [a_id, b_id, 9_999_999]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "invalid_reorder"

    db_session.expire_all()
    fresh_a = await db_session.get(Column, a_id)
    fresh_b = await db_session.get(Column, b_id)
    fresh_c = await db_session.get(Column, c_id)
    assert fresh_a is not None and fresh_a.position == 1000
    assert fresh_b is not None and fresh_b.position == 2000
    assert fresh_c is not None and fresh_c.position == 3000


@pytest.mark.asyncio
async def test_reorder_columns_unknown_board_404(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
) -> None:
    """Unknown board id → 404."""
    _, access, _ = auth_pair
    response = await client.post(
        "/api/boards/9999999/columns/reorder",
        headers={"Authorization": f"Bearer {access}"},
        json={"ordered_column_ids": [1, 2, 3]},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_reorder_columns_archived_board_404(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Archived parent board → 404 (read-only obscurity contract)."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board, a, b, c = await _make_board_with_three_columns(db_session, user.id)
    board.archived_at = datetime.now(UTC)
    await db_session.commit()

    a_id, b_id, c_id = a.id, b.id, c.id
    response = await client.post(
        f"/api/boards/{board.id}/columns/reorder",
        headers={"Authorization": f"Bearer {access}"},
        json={"ordered_column_ids": [c_id, b_id, a_id]},
    )
    assert response.status_code == 404

    # Belt-and-suspenders: 404 short-circuits before any mutation.
    db_session.expire_all()
    fresh_a = await db_session.get(Column, a_id)
    fresh_b = await db_session.get(Column, b_id)
    fresh_c = await db_session.get(Column, c_id)
    assert fresh_a is not None and fresh_a.position == 1000
    assert fresh_b is not None and fresh_b.position == 2000
    assert fresh_c is not None and fresh_c.position == 3000


@pytest.mark.asyncio
async def test_reorder_columns_empty_list_422(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Empty `ordered_column_ids` → 422 (pydantic `min_length=1`).

    Schema rejects this before the service runs — a board with zero
    columns + an empty request is a degenerate case we'd rather
    surface as malformed input than as a 200-on-empty domain success.
    """
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board, _, _, _ = await _make_board_with_three_columns(db_session, user.id)

    response = await client.post(
        f"/api/boards/{board.id}/columns/reorder",
        headers={"Authorization": f"Bearer {access}"},
        json={"ordered_column_ids": []},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reorder_columns_no_auth_401(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Missing `Authorization` → 401 (handled by `CurrentUser` dep)."""
    # No need to seed a board — the dep fires before the handler runs.
    response = await client.post(
        "/api/boards/1/columns/reorder",
        json={"ordered_column_ids": [1, 2, 3]},
    )
    assert response.status_code == 401
