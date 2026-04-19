"""Sanity tests for Phase 2 models + schemas (issue #36).

Not endpoint tests — those land with the endpoint issues. This file just
proves:
  1. Every new model round-trips through the DB (insert + re-select) so
     FKs, defaults, and the ENUM type are wired correctly.
  2. The pydantic schemas accept the ORM rows via `from_attributes=True`
     so the endpoint issues don't hit schema surprises on day one.
  3. The cascade deletes hold (board → columns → tasks; task ↔ labels).

Per `implementer.md`: "Write a minimum-viable sanity test for every new
endpoint, service method, or bot handler, even when a separate test
ticket exists." The endpoint test issues (#108+) replace this file with
their own coverage.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.board import Board
from app.db.models.column import Column
from app.db.models.label import Label
from app.db.models.task import Task, TaskPriority
from app.db.models.task_label import TaskLabel
from app.db.models.user import User, UserRole
from app.domain.boards import BoardRead
from app.domain.columns import ColumnRead
from app.domain.labels import LabelRead
from app.domain.tasks import TaskRead


async def _make_user(session: AsyncSession, username: str = "phase2-user") -> User:
    user = User(
        username=username,
        password_hash="$argon2id$fake",
        display_name="Phase2",
        role=UserRole.MEMBER,
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_board_column_task_roundtrip(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    board = Board(name="Roadmap", description="Q3 plan", created_by=user.id)
    db_session.add(board)
    await db_session.flush()

    col = Column(board_id=board.id, name="To do", position=0, wip_limit=10)
    db_session.add(col)
    await db_session.flush()

    task = Task(
        column_id=col.id,
        title="Ship Phase 2",
        description="first real features",
        creator_id=user.id,
        assignee_id=user.id,
        priority=TaskPriority.HIGH,
        position=0.0,
    )
    db_session.add(task)
    await db_session.commit()

    got = await db_session.get(Task, task.id)
    assert got is not None
    # ENUM `values_callable` stores the value not the name (CLAUDE.md gotcha).
    assert got.priority is TaskPriority.HIGH
    assert got.priority.value == "high"
    # Float position per ADR-0004.
    assert isinstance(got.position, float)

    # Schemas accept ORM rows.
    BoardRead.model_validate(board)
    ColumnRead.model_validate(col)
    TaskRead.model_validate(got)


@pytest.mark.asyncio
async def test_label_and_task_label_m2m(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, username="phase2-labels")
    board = Board(name="Labels board", created_by=user.id)
    db_session.add(board)
    await db_session.flush()

    col = Column(board_id=board.id, name="Todo", position=0)
    db_session.add(col)
    await db_session.flush()

    task = Task(
        column_id=col.id,
        title="Has a label",
        creator_id=user.id,
        priority=TaskPriority.MED,
        position=0.0,
    )
    label = Label(board_id=board.id, name="bug", color="#ef4444")
    db_session.add_all([task, label])
    await db_session.flush()

    db_session.add(TaskLabel(task_id=task.id, label_id=label.id))
    await db_session.commit()

    # Relationship loads the linked label through the secondary table.
    await db_session.refresh(task, attribute_names=["labels"])
    assert [label.id for label in task.labels] == [label.id]

    LabelRead.model_validate(label)


@pytest.mark.asyncio
async def test_label_unique_name_per_board(db_session: AsyncSession) -> None:
    """`uq_labels_board_id_name` prevents duplicate label names inside one board."""
    from sqlalchemy.exc import IntegrityError

    user = await _make_user(db_session, username="phase2-uniq")
    board = Board(name="Uniq", created_by=user.id)
    db_session.add(board)
    await db_session.flush()

    db_session.add(Label(board_id=board.id, name="bug", color="#ef4444"))
    await db_session.commit()

    db_session.add(Label(board_id=board.id, name="bug", color="#ff0000"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_board_delete_cascades_to_columns_and_tasks(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, username="phase2-cascade")
    board = Board(name="To be deleted", created_by=user.id)
    db_session.add(board)
    await db_session.flush()
    col = Column(board_id=board.id, name="Todo", position=0)
    db_session.add(col)
    await db_session.flush()
    task = Task(
        column_id=col.id,
        title="orphan-me-not",
        creator_id=user.id,
        priority=TaskPriority.LOW,
        position=0.0,
    )
    db_session.add(task)
    await db_session.commit()

    board_id = board.id
    col_id = col.id
    task_id = task.id

    await db_session.delete(board)
    await db_session.commit()

    assert await db_session.get(Board, board_id) is None
    assert await db_session.get(Column, col_id) is None
    assert await db_session.get(Task, task_id) is None


@pytest.mark.asyncio
async def test_task_delete_cascades_to_task_labels(db_session: AsyncSession) -> None:
    user = await _make_user(db_session, username="phase2-tl-cascade")
    board = Board(name="TL", created_by=user.id)
    db_session.add(board)
    await db_session.flush()
    col = Column(board_id=board.id, name="Todo", position=0)
    db_session.add(col)
    await db_session.flush()
    task = Task(
        column_id=col.id,
        title="t",
        creator_id=user.id,
        priority=TaskPriority.MED,
        position=0.0,
    )
    label = Label(board_id=board.id, name="l", color="#aaa")
    db_session.add_all([task, label])
    await db_session.flush()
    db_session.add(TaskLabel(task_id=task.id, label_id=label.id))
    await db_session.commit()

    label_id = label.id

    await db_session.delete(task)
    await db_session.commit()

    # Label survives…
    assert await db_session.get(Label, label_id) is not None
    # …but the association row is gone.
    result = await db_session.execute(select(TaskLabel).where(TaskLabel.label_id == label_id))
    assert result.scalar_one_or_none() is None
