from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.columns import ColumnRead
from app.domain.labels import LabelRead


class BoardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4096)


class BoardUpdate(BaseModel):
    """Partial update — every field optional. Endpoint applies present fields only."""

    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4096)


class BoardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class BoardDetailRead(BoardRead):
    """Board + eager-loaded columns (ordered by position) + labels.

    Returned by `GET /api/boards/{id}` (issue #71). The list endpoint
    (`GET /api/boards`) intentionally stays on the lighter `BoardRead`
    shape — embedding columns + labels in every list row would be a
    payload regression for the common UI case (sidebar + board picker).
    Detail view is the right place to hydrate.

    `columns` is sorted by `Column.position` via the relationship's
    `order_by` clause on the model — see `app/db/models/board.py`.
    """

    columns: list[ColumnRead]
    labels: list[LabelRead]
