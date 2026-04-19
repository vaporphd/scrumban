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


class ColumnsReorderRequest(BaseModel):
    """Body schema for `POST /api/boards/{board_id}/columns/reorder`.

    `ordered_column_ids` is the *complete* desired order — every column on
    the board must be present exactly once. The service validates set
    equality and rejects partial / extra / duplicate / unknown ids with
    a single `400 invalid_reorder` (see `columns_service.reorder_columns`
    for the exact validation policy and the rationale for collapsing
    those four shapes onto one error code).

    `min_length=1` blocks an empty list at the schema layer (422). The
    service-level set-equality check would also catch this for any
    non-empty board, but a board with zero columns + an empty request is
    a degenerate case we'd rather reject as malformed input than as a
    domain error.
    """

    ordered_column_ids: list[int] = Field(min_length=1)
