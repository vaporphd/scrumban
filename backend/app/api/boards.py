"""Boards REST router.

Mounted at `/api/boards` from `app.main_api`. Per ADR-0001 the router
stays thin: parse request, delegate to `boards_service`, serialize
response. All business logic + transaction boundaries live in the
service.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.domain.boards import BoardCreate, BoardRead
from app.services import boards_service

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
