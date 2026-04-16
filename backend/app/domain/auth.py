from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.user import UserRole


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: UserRole
    # Defaults so call sites that build UserRead without these fields stay
    # green; in practice `from_attributes=True` reads them off the User ORM
    # row, which always has the columns.
    tg_user_id: int | None = None
    tg_username: str | None = None


class TgLinkCodeResponse(BaseModel):
    """One-time Telegram link code (ADR-0003).

    `bot_username` is included so the frontend can render the
    `t.me/<bot>?start=<code>` deep link in a single round-trip; when the
    env isn't configured the field is null and the UI falls back to plain
    `/start <code>` instructions.
    """

    code: str = Field(min_length=6, max_length=6)
    expires_at: datetime
    bot_username: str | None = None
