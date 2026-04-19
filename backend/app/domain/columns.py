from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ColumnCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    wip_limit: int | None = Field(default=None, ge=1, le=1000)


class ColumnUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    # Explicit `None` on an optional wip_limit means "clear it"; absence means
    # "leave as-is". Endpoints handle the two cases via `model_fields_set`.
    wip_limit: int | None = Field(default=None, ge=1, le=1000)


class ColumnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    name: str
    position: int
    wip_limit: int | None
    created_at: datetime
    updated_at: datetime
