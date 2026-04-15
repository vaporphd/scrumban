from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.tg_link_code import TgLinkCode


class UserRole(StrEnum):
    OWNER = "owner"
    MEMBER = "member"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Stored lowercased. Display-preserving casing is not supported — the
    # display_name column is what users see; username is a stable handle.
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)

    # Telegram linkage. `tg_user_id` is the authoritative identity, nullable
    # until the user completes /start with a valid code (ADR-0003).
    tg_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True)
    tg_username: Mapped[str | None] = mapped_column(String(64), nullable=True)

    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
        default=UserRole.MEMBER,
    )

    link_codes: Mapped[list[TgLinkCode]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
