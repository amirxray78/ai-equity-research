"""User database model."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, auth_users

if TYPE_CHECKING:
    from .chat_thread import ChatThread


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        ForeignKey(auth_users.c.id, ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    threads: Mapped[list["ChatThread"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
