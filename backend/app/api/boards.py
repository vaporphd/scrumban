"""Boards REST router.

Mounted at `/api/boards` from `app.main_api`. Per ADR-0001 the router
stays thin: parse request, delegate to `boards_service`, serialize
response. All business logic + transaction boundaries live in the
service.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.domain.boards import BoardCreate, BoardDetailRead, BoardRead, BoardUpdate
from app.services import boards_service
from app.services.boards_service import BoardError

router = APIRouter(prefix="/boards", tags=["boards"])


@router.post(
    "",
    response_model=BoardRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_board(
    payload: BoardCreate,
    user: CurrentUser,
    session: SessionDep,
) -> BoardRead:
    """Create a board owned by the authenticated user.

    422 on invalid `name` / `description` is handled automatically by
    FastAPI from the pydantic schema. 401 (no token / bad token) is
    handled by the `CurrentUser` dependency.
    """
    board = await boards_service.create_board(session, creator=user, payload=payload)
    return BoardRead.model_validate(board)


@router.get(
    "",
    response_model=list[BoardRead],
)
async def list_boards(
    user: CurrentUser,
    session: SessionDep,
    include_archived: bool = False,
) -> list[BoardRead]:
    """List boards, newest first.

    By default excludes archived boards (the common UI case). Pass
    `?include_archived=true` to include them. 401 on missing/bad token
    is handled by the `CurrentUser` dependency.
    """
    boards = await boards_service.list_boards(
        session, actor=user, include_archived=include_archived
    )
    return [BoardRead.model_validate(b) for b in boards]


@router.get(
    "/{board_id}",
    response_model=BoardDetailRead,
)
async def get_board(
    board_id: int,
    user: CurrentUser,
    session: SessionDep,
    include_archived: bool = False,
) -> BoardDetailRead:
    """Return one board with embedded columns (ordered by position) + labels.

    404 on unknown id. Archived boards 404 by default — pass
    `?include_archived=true` to fetch one. 401 (no token / bad token)
    is handled by the `CurrentUser` dependency. Eager-loaded in 3
    SELECTs total via `selectinload`; see
    `board_repo.get_by_id_with_relations` for the rationale.
    """
    try:
        board = await boards_service.get_board(
            session, actor=user, board_id=board_id, include_archived=include_archived
        )
    except BoardError as exc:
        if exc.code == "board_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
        raise
    return BoardDetailRead.model_validate(board)


@router.patch(
    "/{board_id}",
    response_model=BoardRead,
)
async def update_board(
    board_id: int,
    payload: BoardUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> BoardRead:
    """Partially update `name` and/or `description` on board `board_id`.

    Returns the updated `BoardRead`. 404 on unknown id and on archived
    boards (archived = read-only — see `boards_service.update_board`).
    422 on invalid `name` (empty / >128) or `description` (>4096) is
    handled by FastAPI from the pydantic schema. 401 (no token / bad
    token) is handled by the `CurrentUser` dependency. Empty `{}` body
    is a valid no-op and returns the current row unchanged — see the
    service docstring for the rationale.
    """
    try:
        board = await boards_service.update_board(
            session, actor=user, board_id=board_id, payload=payload
        )
    except BoardError as exc:
        if exc.code == "board_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
        raise
    return BoardRead.model_validate(board)


@router.post(
    "/{board_id}/archive",
    response_model=BoardRead,
)
async def archive_board(
    board_id: int,
    user: CurrentUser,
    session: SessionDep,
) -> BoardRead:
    """Soft-archive board `board_id`. Idempotent.

    First call stamps `archived_at = now()`; repeat calls are 200 no-ops
    that preserve the original timestamp (see
    `boards_service.archive_board` for the rationale). Returns the
    `BoardRead` for the archived board so clients can refresh local
    state without a follow-up GET. 404 on unknown id. 401 (no token /
    bad token) is handled by the `CurrentUser` dependency.
    """
    try:
        board = await boards_service.archive_board(session, actor=user, board_id=board_id)
    except BoardError as exc:
        if exc.code == "board_not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from exc
        raise
    return BoardRead.model_validate(board)
