from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TaskLabel(Base):
    """m2m link row between `tasks` and `labels`.

    Uses a composite primary key `(task_id, label_id)` so the pair is
    unique without an extra unique index, and the row itself carries no
    state beyond the association. Declared as a full model (vs. a bare
    `Table`) so SQLAlchemy's typed `Mapped[...]` style stays consistent
    across the codebase and future additions (e.g. `created_at`,
    `added_by_id`) are one-line changes.

    Both FKs `ON DELETE CASCADE` — when a task or a label is deleted, the
    association rows go with it.
    """

    __tablename__ = "task_labels"

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True
    )
    label_id: Mapped[int] = mapped_column(
        ForeignKey("labels.id", ondelete="CASCADE"), primary_key=True
    )

    def __repr__(self) -> str:
        return f"TaskLabel(task_id={self.task_id!r}, label_id={self.label_id!r})"
