from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.board import Board
    from app.db.models.task import Task


class Column(Base, TimestampMixin):
    """A column inside a board (e.g. "To do", "In progress", "Done").

    Columns are ordered within the board by `position`. Unlike tasks, column
    reorders are much rarer (once-at-setup, occasional polish) so an integer
    position is fine — we don't need ADR-0004's float scheme here. Reorder
    endpoints rewrite positions in a transaction.

    `wip_limit` is nullable — an unset limit means no cap. The limit is
    advisory at the domain layer; enforcement (block vs warn) is a Phase 2
    service-level decision.
    """

    __tablename__ = "columns"

    id: Mapped[int] = mapped_column(primary_key=True)
    board_id: Mapped[int] = mapped_column(
        ForeignKey("boards.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    # Integer per the Phase 2 plan. ADR-0004's float scheme is task-only —
    # column reorders are rare enough that cascading integer shifts are fine.
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    wip_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    board: Mapped[Board] = relationship(back_populates="columns")
    tasks: Mapped[list[Task]] = relationship(
        back_populates="column",
        cascade="all, delete-orphan",
        order_by="Task.position",
    )

    def __repr__(self) -> str:
        return f"Column(id={self.id!r}, board_id={self.board_id!r}, name={self.name!r})"
