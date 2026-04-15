from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.domain.auth import UserRead

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
