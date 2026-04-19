from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.column import Column
    from app.db.models.label import Label
    from app.db.models.user import User


class TaskPriority(StrEnum):
    """Priority levels for a task.

    Chose ENUM over String: this is a small, stable, product-level set
    (low / med / high / urgent per `tasks/todo.md` section 3). An ENUM
    gets the DB-level constraint for free — no "someone-types-'hgh'"
    silent data drift — and the UI renders a fixed dropdown either way.
    Adding a value later is a one-line Alembic `ALTER TYPE ... ADD VALUE`
    migration; cheap enough that the extensibility concern doesn't flip
    the trade-off. Mirrors the existing `UserRole` pattern in
    `app/db/models/user.py`.
    """

    LOW = "low"
    MED = "med"
    HIGH = "high"
    URGENT = "urgent"


class Task(Base, TimestampMixin):
    """A kanban task, owned by a column.

    Two indexes per `tasks/todo.md` section 3:

    - `(column_id, position)` — the hot path for rendering a column
      (ORDER BY position) and required by ADR-0004 so ordered reads don't
      degenerate to a seqscan.
    - `(assignee_id, due_at)` — supports "my tasks", "my overdue tasks",
      and the APScheduler reminder job (Phase 6) that scans for
      `due_at - now < reminder_window AND assignee.tg_user_id IS NOT NULL`.

    `position` is `Float` per ADR-0004 — insert between neighbours as
    `(prev + next) / 2`, rebalance when gaps close to `1e-6`.

    `creator_id` and `assignee_id` are `SET NULL` on user delete so a
    task survives a user being removed from the system (Phase 7 RBAC).
    The task loses its assignee but stays on the board.
    """

    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_column_id_position", "column_id", "position"),
        Index("ix_tasks_assignee_id_due_at", "assignee_id", "due_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    column_id: Mapped[int] = mapped_column(
        ForeignKey("columns.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    creator_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    priority: Mapped[TaskPriority] = mapped_column(
        Enum(
            TaskPriority,
            name="task_priority",
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
        default=TaskPriority.MED,
    )

    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Float per ADR-0004. `double precision` in Postgres via SQLAlchemy's
    # Float type (no precision argument = DOUBLE PRECISION).
    position: Mapped[float] = mapped_column(Float, nullable=False)

    column: Mapped[Column] = relationship(back_populates="tasks")
    creator: Mapped[User | None] = relationship("User", foreign_keys=[creator_id])
    assignee: Mapped[User | None] = relationship("User", foreign_keys=[assignee_id])
    labels: Mapped[list[Label]] = relationship(
        secondary="task_labels",
        back_populates="tasks",
    )

    def __repr__(self) -> str:
        return f"Task(id={self.id!r}, column_id={self.column_id!r}, title={self.title!r})"
