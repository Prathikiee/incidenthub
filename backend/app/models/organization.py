"""Organization domain model."""

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.membership import OrganizationMembership
    from app.models.service import Service, ServiceDependency
    from app.models.team import Team


class Organization(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Organization entity representing the primary tenant boundary."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    # Relationships
    memberships: Mapped[list["OrganizationMembership"]] = relationship(
        "OrganizationMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    teams: Mapped[list["Team"]] = relationship(
        "Team",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    services: Mapped[list["Service"]] = relationship(
        "Service",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    service_dependencies: Mapped[list["ServiceDependency"]] = relationship(
        "ServiceDependency",
        back_populates="organization",
        cascade="all, delete-orphan",
        overlaps="dependencies_as_source,dependencies_as_target,organization,service_dependencies,source_service,target_service",
    )
