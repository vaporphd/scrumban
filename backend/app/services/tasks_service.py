"""Tasks business logic.

Skeleton only — bodies land with the Phase 2 endpoint issues. The
surface is declared here so router PRs can import cleanly.

`move_task` is called out explicitly because ADR-0004 requires it to
run inside a single transaction that reads neighbour positions and
writes column_id + position together.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.task import Task
from app.db.models.user import User
from app.domain.tasks import TaskCreate, TaskMove, TaskUpdate


class TaskError(Exception):
    """Domain-level task failure. Routers map to HTTP 403/404/409."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def create_task(session: AsyncSession, *, creator: User, payload: TaskCreate) -> Task:
    raise NotImplementedError("create_task lands with the task-create endpoint issue")


async def get_task(session: AsyncSession, *, actor: User, task_id: int) -> Task:
    raise NotImplementedError("get_task lands with the task-detail endpoint issue")


async def update_task(
    session: AsyncSession, *, actor: User, task_id: int, payload: TaskUpdate
) -> Task:
    raise NotImplementedError("update_task lands with the task-update endpoint issue")


async def delete_task(session: AsyncSession, *, actor: User, task_id: int) -> None:
    raise NotImplementedError("delete_task lands with the task-delete endpoint issue")


async def move_task(session: AsyncSession, *, actor: User, task_id: int, payload: TaskMove) -> Task:
    """Transactional task move per ADR-0004.

    Reads neighbour positions, writes (column_id, position) in one
    transaction. Body lands with `/api/tasks/{id}/move`.
    """
    raise NotImplementedError("move_task lands with the task-move endpoint issue (ADR-0004)")
