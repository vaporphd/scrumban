from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.core.config import get_settings
from app.domain.auth import TgLinkCodeResponse, UserRead
from app.services import tg_link_service

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.post(
    "/me/tg-link-code",
    response_model=TgLinkCodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue_my_link_code(user: CurrentUser, session: SessionDep) -> TgLinkCodeResponse:
    """Issue a fresh 6-digit Telegram link code for the current user.

    Per ADR-0003, hitting this endpoint a second time invalidates the prior
    active code and returns a new one. The code is single-use and expires
    after `TELEGRAM__LINK_CODE_TTL_MINUTES`.
    """
    code = await tg_link_service.issue_link_code(session, user)
    settings = get_settings()
    return TgLinkCodeResponse(
        code=code.code,
        expires_at=code.expires_at,
        bot_username=settings.telegram.bot_username,
    )
