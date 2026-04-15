from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep
from app.domain.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from app.services import auth_service
from app.services.auth_service import AuthError

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: SessionDep) -> UserRead:
    try:
        user = await auth_service.register(
            session,
            username=payload.username,
            password=payload.password,
            display_name=payload.display_name,
        )
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message) from exc
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    try:
        user = await auth_service.authenticate(
            session, username=payload.username, password=payload.password
        )
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    pair = await auth_service.issue_tokens(session, user)
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, session: SessionDep) -> TokenResponse:
    try:
        pair = await auth_service.refresh(session, refresh_token=payload.refresh_token)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token)
