"""Columns REST router.

Mounted at `/api` from `app.main_api`. Routes split into two shapes:

  * Sub-resource shape `/boards/{board_id}/columns` — used for column
    *creation*, because you can only add a column *to* a board (the
    parent must exist; new column has no id yet).
  * Flat shape `/columns/{column_id}` — used for per-column verbs
    (PATCH, DELETE here, reorder coming with issue #80) because once
    a column exists its identity is global; the parent board is
    reachable via the row's `board_id`.

Keeping both shapes in this file means the columns surface stays in
one place.

Per ADR-0001 the router stays thin: parse request, delegate to
`columns_service`, serialize response. All business logic + transaction
boundaries live in the service.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUser, SessionDep
from app.domain.columns import ColumnCreate, ColumnRead, ColumnUpdate
from app.services import columns_service
from app.services.boards_service import BoardError
from app.services.columns_service import ColumnError

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


@router.patch(
    "/columns/{column_id}",
    response_model=ColumnRead,
)
async def update_column(
    column_id: int,
    payload: ColumnUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> ColumnRead:
    """Partially update `name` and/or `wip_limit` on column `column_id`.

    Column id is at the root (`/columns/{column_id}`) — not nested under
    its board — because once a column exists its identity is global; the
    parent board is reachable via the row's `board_id`. This is the
    flat-shape branch the module-level docstring describes.

    Returns the updated `ColumnRead`. 404 on unknown column id and on
    columns whose parent board is archived (archived = read-only — see
    `columns_service.update_column`). 422 on invalid `name` (empty /
    >64) or `wip_limit` (<1 / >1000) is handled by FastAPI from the
    pydantic schema. 401 (no token / bad token) is handled by the
    `CurrentUser` dependency. Empty `{}` body is a valid no-op and
    returns the current row unchanged — see the service docstring.
    """
    try:
        column = await columns_service.update_column(
            session, actor=user, column_id=column_id, payload=payload
        )
    except (ColumnError, BoardError) as exc:
        # Both surface as 404 to keep the obscurity contract (see
        # service docstring). The DELETE branch below adds the 409
        # `column_has_tasks` shape; that code never reaches PATCH.
        if exc.code in {"column_not_found", "board_not_found"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
        raise
    return ColumnRead.model_validate(column)


@router.delete(
    "/columns/{column_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_column(
    column_id: int,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    """Delete column `column_id`, refusing if it still holds tasks.

    Per issue #79: 204 on empty column; 409 with body
    `{"detail": "column_has_tasks", "task_count": N}` if the column
    still contains one or more tasks; 404 on unknown column id and on
    columns whose parent board is archived (same obscurity contract as
    PATCH). 401 (no token / bad token) is handled by the `CurrentUser`
    dependency.

    Why a hand-built `JSONResponse` for the 409 branch rather than
    `HTTPException`: FastAPI's `HTTPException(detail={...})` would
    nest the structure as `{"detail": {"detail": "...",
    "task_count": N}}`, which doesn't match the issue's flat shape.
    Building the response directly is the only way to land
    `{"detail": <string>, "task_count": <int>}` at the top level
    while keeping the `Authorization` dependency, FastAPI's exception
    pipeline, and the OpenAPI schema all behaving normally for the
    other status codes.
    """
    try:
        await columns_service.delete_column(session, actor=user, column_id=column_id)
    except ColumnError as exc:
        if exc.code == "column_has_tasks":
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={"detail": "column_has_tasks", "task_count": exc.task_count},
            )
        if exc.code == "column_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
        raise
    except BoardError as exc:
        if exc.code == "board_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)
