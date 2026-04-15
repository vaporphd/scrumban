from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class TgLinkCode(Base):
    """One-time code a user sends as `/start <code>` to link Telegram to their
    app account (ADR-0003).

    Invariant: at most one non-consumed code per user. Enforced in two layers:
    - DB: partial unique index `WHERE consumed_at IS NULL` (below).
    - Service: `issue_link_code` marks any existing active code as consumed
      before inserting the new one, inside a single transaction.

    Expiration is checked in the service, not the index, because Postgres
    requires partial-index predicates to be immutable (NOW() is not).
    """

    __tablename__ = "tg_link_codes"
    __table_args__ = (
        Index(
            "uq_active_link_code_per_user",
            "user_id",
            unique=True,
            postgresql_where="consumed_at IS NULL",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # Six ASCII digits; stored as fixed-length string to avoid leading-zero
    # issues and to keep the value easy to read in Postgres directly.
    code: Mapped[str] = mapped_column(String(6), nullable=False)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="link_codes")
