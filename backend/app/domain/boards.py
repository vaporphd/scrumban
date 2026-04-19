from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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
