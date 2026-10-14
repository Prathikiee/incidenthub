"""Refresh token domain model."""

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """RefreshToken entity for persisting and rotating refresh tokens."""

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default=None,
    )

    # Relationship to user
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (Index("ix_refresh_tokens_user_id_token_hash", "user_id", "token_hash"),)

    @property
    def is_revoked(self) -> bool:
        """Check if token has been revoked."""
        return self.revoked_at is not None

    @property
    def is_expired(self) -> bool:
        """Check if token expiration timestamp has passed."""
        now = datetime.now(UTC)
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        return exp <= now

    @property
    def is_active(self) -> bool:
        """Check if token is neither revoked nor expired."""
        return not self.is_revoked and not self.is_expired
