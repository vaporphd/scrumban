from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CHAR, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class RefreshToken(Base):
    """Opaque, rotating refresh token (ADR-0005).

    The plaintext value is generated with `secrets.token_urlsafe(32)` and
    returned to the client exactly once — only the SHA-256 hex hash is
    stored. Rotation is enforced by the auth service: on every refresh we
    mark this row `revoked_at = now()`, insert a successor, and set
    `replaced_by_id` to point at it. A reuse of an already-revoked token
    triggers chain revocation for the whole user.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Hex SHA-256 of the plaintext token. Fixed-width so the unique index
    # is a clean CHAR(64) comparison.
    token_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False, unique=True, index=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Self-referential FK. Populated when rotation swaps this token for a
    # successor. Lets us walk the replacement chain if we ever need to.
    replaced_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped[User] = relationship("User")
