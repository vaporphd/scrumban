"""Columns REST router.

Mounted at `/api` from `app.main_api`. Routes nest under `/boards/{board_id}/columns`
because column creation is a sub-resource of a board (you can only add
a column *to* a board). Future per-column verbs (PATCH / DELETE /
reorder — issues #78, #79, #80) will use a flat `/columns/{column_id}`
shape because once a column exists its identity is global; the parent
board is reachable via the row's `board_id`. Keeping both shapes in this
file means the columns surface stays in one place.

Per ADR-0001 the router stays thin: parse request, delegate to
`columns_service`, serialize response. All business logic + transaction
boundaries live in the service.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.domain.columns import ColumnCreate, ColumnRead
from app.services import columns_service
from app.services.boards_service import BoardError

router = APIRouter(tags=["columns"])


@router.post(
    "/boards/{board_id}/columns",
    response_model=ColumnRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_column(
    board_id: int,
    payload: ColumnCreate,
    user: CurrentUser,
    session: SessionDep,
) -> ColumnRead:
    """Append a new column to `board_id`.

    Returns the created `ColumnRead` with the server-assigned `id` and
    `position`. 404 on unknown board id and on archived boards (archived
    = read-only — see `columns_service.create_column`). 422 on invalid
    `name` (empty / >64) or `wip_limit` (<1 / >1000) is handled by
    FastAPI from the pydantic schema. 401 (no token / bad token) is
    handled by the `CurrentUser` dependency.
    """
    try:
        column = await columns_service.create_column(
            session, actor=user, board_id=board_id, payload=payload
        )
    except BoardError as exc:
        if exc.code == "board_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
        raise
    return ColumnRead.model_validate(column)
