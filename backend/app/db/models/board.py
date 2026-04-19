from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.column import Column
    from app.db.models.label import Label
    from app.db.models.user import User


class Board(Base, TimestampMixin):
    """A kanban board owned by one user; tasks + columns + labels live under it.

    Single-organization product (see `tasks/todo.md` section 1): there is no
    "organization" row above a board. The board's creator is stamped in
    `created_by` for audit and owner-only actions (ADR-level RBAC is Phase 7,
    but the column is needed from day one).

    `archived_at` implements soft-delete: archiving a board hides it from
    board listings but preserves the whole tree (columns, tasks, labels) so
    activity history and search stay intact. Hard-delete is out of scope for
    Phase 2 — if a user truly needs to purge a board, that's a separate
    issue and requires cascade decisions per table.
    """

    __tablename__ = "boards"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # `created_by` per `tasks/todo.md` section 3 — matches the plan's column
    # name so migration diffs don't surprise the reviewer. Nullable=False:
    # every board has a creator; if that user is later deleted, SET NULL
    # lets the board survive without a dangling FK.
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    creator: Mapped[User | None] = relationship("User")
    columns: Mapped[list[Column]] = relationship(
        back_populates="board",
        cascade="all, delete-orphan",
        order_by="Column.position",
    )
    labels: Mapped[list[Label]] = relationship(
        back_populates="board",
        cascade="all, delete-orphan",
    )
    # Tasks don't FK directly to board — they FK to column. Board-level
    # task queries go through the columns relationship + filters. No
    # back_populates to `Task` here, intentionally.

    def __repr__(self) -> str:
        return f"Board(id={self.id!r}, name={self.name!r})"
