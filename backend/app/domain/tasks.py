from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.task import TaskPriority


class TaskCreate(BaseModel):
    column_id: int
    title: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=32_768)
    assignee_id: int | None = None
    priority: TaskPriority = TaskPriority.MED
    due_at: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=32_768)
    assignee_id: int | None = None
    priority: TaskPriority | None = None
    due_at: datetime | None = None
    completed_at: datetime | None = None


class TaskMove(BaseModel):
    """Payload for `POST /api/tasks/{id}/move` (endpoint lands in a later issue).

    `column_id` stays the same for intra-column reorder; changes for
    cross-column moves. `position` follows ADR-0004 — client may send the
    computed `(prev + next) / 2`, server re-validates and may override.
    """

    column_id: int
    position: float


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    column_id: int
    title: str
    description: str | None
    creator_id: int | None
    assignee_id: int | None
    priority: TaskPriority
    due_at: datetime | None
    completed_at: datetime | None
    position: float
    created_at: datetime
    updated_at: datetime
