from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.board import Board
    from app.db.models.task import Task


class Label(Base, TimestampMixin):
    """A colored tag that can be applied to tasks inside a board.

    Labels are board-scoped (not global) so each board maintains its own
    vocabulary. Unique-per-board name prevents duplicates in the UI.

    `color` is stored as a hex string (e.g. "#ef4444"). Validation of the
    color format lives in the pydantic schema, not the DB column — the
    DB just holds the string.
    """

    __tablename__ = "labels"
    __table_args__ = (UniqueConstraint("board_id", "name", name="uq_labels_board_id_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=False)

    board: Mapped[Board] = relationship(back_populates="labels")
    tasks: Mapped[list[Task]] = relationship(
        secondary="task_labels",
        back_populates="labels",
    )

    def __repr__(self) -> str:
        return f"Label(id={self.id!r}, board_id={self.board_id!r}, name={self.name!r})"
