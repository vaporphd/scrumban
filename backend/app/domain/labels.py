from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# Hex color pattern: `#` followed by 3 or 6 hex digits. Strict regex validation
# so the DB never sees "red" or "rgb(…)"; the frontend picks from a swatch.
HEX_COLOR_PATTERN = r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"


class LabelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str = Field(pattern=HEX_COLOR_PATTERN, max_length=16)


class LabelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    color: str | None = Field(default=None, pattern=HEX_COLOR_PATTERN, max_length=16)


class LabelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    name: str
    color: str
    created_at: datetime
    updated_at: datetime
