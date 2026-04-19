"""Integration tests for `DELETE /api/columns/{id}` (issue #79).

Covers:
- 204 on empty column — DB row gone after the call.
- 204 leaves sibling columns on the same board untouched (defensive — a
  bug that swept the board's other columns into the cascade would still
  return 204 to the caller; this test catches it).
- 409 on a column with one task — body shape `{"detail":
  "column_has_tasks", "task_count": 1}`.
- 409 on a column with five tasks — `task_count: 5`.
- 409 short-circuits before any mutation — the column and its tasks
  are still present in the DB after the failed call.
- 404 on unknown column id.
- 404 on a column whose parent board is archived (same read-only
  obscurity contract as PATCH).
- 401 without `Authorization` header.

Per `implementer.md`: 3+ pytest integration cases. We ship eight so
each branch (204 happy path, 204 sibling-safety, two 409 task-count
echoes, 409 no-mutation, two 404 shapes, 401) is locked against a
future router refactor. Tasks are inserted directly via the model
(no public POST /api/tasks endpoint until issue #90) — see the
implementer's design note on the deferred 409 smoke scenario.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.board import Board
from app.db.models.column import Column
from app.db.models.task import Task, TaskPriority
from app.repositories import board_repo, column_repo, user_repo


async def _make_board_and_column(
    db_session: AsyncSession,
    user_id: int,
    *,
    column_name: str = "To do",
    position: int = 1000,
) -> tuple[Board, Column]:
    """Test helper: create a board + a single column owned by `user_id`."""
    board = await board_repo.create(
        db_session, name="Roadmap", description=None, created_by=user_id
    )
    column = await column_repo.create(
        db_session,
        board_id=board.id,
        name=column_name,
        position=position,
        wip_limit=None,
    )
    await db_session.commit()
    return board, column


async def _seed_tasks(db_session: AsyncSession, column_id: int, count: int) -> None:
    """Insert `count` minimal Task rows directly (no public endpoint yet).

    `POST /api/tasks` lands with issue #90; until then the test seeds
    the rows via the model + session.add(). Position values use the
    float scheme from ADR-0004 with comfortably wide gaps so the seed
    order stays stable regardless of insert order.
    """
    for i in range(count):
        task = Task(
            column_id=column_id,
            title=f"Seed task {i + 1}",
            description=None,
            creator_id=None,
            assignee_id=None,
            priority=TaskPriority.MED,
            due_at=None,
            completed_at=None,
            position=float((i + 1) * 1000),
        )
        db_session.add(task)
    await db_session.commit()


@pytest.mark.asyncio
async def test_delete_empty_column_204(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """DELETE on an empty column returns 204 and the row is gone."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    _, column = await _make_board_and_column(db_session, user.id)

    column_id = column.id
    response = await client.delete(
        f"/api/columns/{column_id}",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 204
    # 204 must not have a body.
    assert response.content == b""

    # Row is gone from the DB. Snapshot the id before expire_all so the
    # post-expire `get(Column, ...)` doesn't trip the lazy-load that
    # would re-resolve `column.id` against the closed transaction
    # (MissingGreenlet trap — same family as the boards PATCH fix).
    db_session.expire_all()
    gone = await db_session.get(Column, column_id)
    assert gone is None


@pytest.mark.asyncio
async def test_delete_empty_column_leaves_siblings_204(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Deleting one column does not touch siblings on the same board.

    Defensive: a bug that widened the delete (e.g. matched on board_id
    instead of column id) would still return 204, so we verify the
    other rows are still present afterwards.
    """
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board, doomed = await _make_board_and_column(db_session, user.id, column_name="Doomed")
    survivor_a = await column_repo.create(
        db_session, board_id=board.id, name="Survivor A", position=2000, wip_limit=None
    )
    survivor_b = await column_repo.create(
        db_session, board_id=board.id, name="Survivor B", position=3000, wip_limit=None
    )
    await db_session.commit()

    doomed_id = doomed.id
    survivor_a_id = survivor_a.id
    survivor_b_id = survivor_b.id

    response = await client.delete(
        f"/api/columns/{doomed_id}",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 204

    # Siblings still in the DB. Snapshot ids before expire_all per the
    # MissingGreenlet note in the empty-204 test above.
    db_session.expire_all()
    still_a = await db_session.get(Column, survivor_a_id)
    still_b = await db_session.get(Column, survivor_b_id)
    assert still_a is not None and still_a.name == "Survivor A"
    assert still_b is not None and still_b.name == "Survivor B"


@pytest.mark.asyncio
async def test_delete_column_with_one_task_409(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Column with a single task → 409 with task_count=1."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    _, column = await _make_board_and_column(db_session, user.id)
    await _seed_tasks(db_session, column.id, count=1)

    response = await client.delete(
        f"/api/columns/{column.id}",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 409
    body = response.json()
    # Issue spec body shape: top-level `detail` (string) + `task_count`.
    assert body == {"detail": "column_has_tasks", "task_count": 1}


@pytest.mark.asyncio
async def test_delete_column_with_five_tasks_409(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Column with five tasks → 409 echoes task_count=5."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    _, column = await _make_board_and_column(db_session, user.id)
    await _seed_tasks(db_session, column.id, count=5)

    response = await client.delete(
        f"/api/columns/{column.id}",
        headers={"Authorization": f"Bearer {access}"},
    )

    assert response.status_code == 409
    body = response.json()
    assert body == {"detail": "column_has_tasks", "task_count": 5}


@pytest.mark.asyncio
async def test_delete_column_409_does_not_mutate(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """A 409 must not mutate the column or its tasks.

    Belt-and-suspenders: the service raises before calling
    `column_repo.delete`, so a 409 path that somehow reached the
    delete would still surface as 204 to the client. Verify the row
    + the seeded tasks are still in the DB after the failed call.
    """
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    _, column = await _make_board_and_column(db_session, user.id)
    await _seed_tasks(db_session, column.id, count=3)

    column_id = column.id
    response = await client.delete(
        f"/api/columns/{column_id}",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 409

    db_session.expire_all()
    still = await db_session.get(Column, column_id)
    assert still is not None
    task_rows = await db_session.execute(select(Task).where(Task.column_id == column_id))
    assert len(list(task_rows.scalars().all())) == 3


@pytest.mark.asyncio
async def test_delete_column_unknown_id_404(
    client: AsyncClient, auth_pair: tuple[str, str, str]
) -> None:
    _, access, _ = auth_pair
    response = await client.delete(
        "/api/columns/9999999",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_column_archived_board_404(
    client: AsyncClient,
    auth_pair: tuple[str, str, str],
    db_session: AsyncSession,
) -> None:
    """Column on an archived board is not deletable — 404 (read-only model)."""
    username, access, _ = auth_pair
    user = await user_repo.get_by_username(db_session, username)
    assert user is not None
    board, column = await _make_board_and_column(db_session, user.id)
    board.archived_at = datetime.now(UTC)
    await db_session.commit()

    column_id = column.id
    response = await client.delete(
        f"/api/columns/{column_id}",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 404

    # Row was not deleted (404 short-circuits before any flush).
    db_session.expire_all()
    still = await db_session.get(Column, column_id)
    assert still is not None


@pytest.mark.asyncio
async def test_delete_column_no_auth_401(client: AsyncClient) -> None:
    response = await client.delete("/api/columns/1")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"
