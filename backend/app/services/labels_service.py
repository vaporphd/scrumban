"""Labels business logic.

Skeleton only — bodies land with the Phase 2 endpoint issues.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.label import Label
from app.db.models.user import User
from app.domain.labels import LabelCreate, LabelUpdate


class LabelError(Exception):
    """Domain-level label failure. Routers map to HTTP 403/404/409."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


async def create_label(
    session: AsyncSession, *, actor: User, board_id: int, payload: LabelCreate
) -> Label:
    raise NotImplementedError("create_label lands with the labels endpoint issue")


async def list_labels(session: AsyncSession, *, actor: User, board_id: int) -> list[Label]:
    raise NotImplementedError("list_labels lands with the labels endpoint issue")


async def update_label(
    session: AsyncSession, *, actor: User, label_id: int, payload: LabelUpdate
) -> Label:
    raise NotImplementedError("update_label lands with the labels endpoint issue")


async def delete_label(session: AsyncSession, *, actor: User, label_id: int) -> None:
    raise NotImplementedError("delete_label lands with the labels endpoint issue")
