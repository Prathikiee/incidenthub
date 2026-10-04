"""Service and ServiceDependency domain models."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class Service(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Service entity representing an operational software component or system."""

    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_services_org_slug",
        ),
        # Unique constraint on (id, organization_id) enables composite foreign keys
        # from service_dependencies, guaranteeing tenant-isolated graph edges at DB level.
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_services_id_org",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="services",
    )
    dependencies_as_source: Mapped[list["ServiceDependency"]] = relationship(
        "ServiceDependency",
        primaryjoin="and_(Service.id == ServiceDependency.source_service_id, "
        "Service.organization_id == ServiceDependency.organization_id)",
        back_populates="source_service",
        cascade="all, delete-orphan",
        overlaps="dependencies_as_source,dependencies_as_target,service_dependencies,organization,source_service,target_service",
    )
    dependencies_as_target: Mapped[list["ServiceDependency"]] = relationship(
        "ServiceDependency",
        primaryjoin="and_(Service.id == ServiceDependency.target_service_id, "
        "Service.organization_id == ServiceDependency.organization_id)",
        back_populates="target_service",
        cascade="all, delete-orphan",
        overlaps="dependencies_as_source,dependencies_as_target,service_dependencies,organization,source_service,target_service",
    )


class ServiceDependency(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """Directed dependency relationship between two services within an organization.

    Interpretation:
        source_service_id depends on target_service_id
        (e.g., Checkout API -> Payment Service)
    """

    __tablename__ = "service_dependencies"
    __table_args__ = (
        # Disallow self-dependency
        CheckConstraint(
            "source_service_id != target_service_id",
            name="ck_service_dependencies_no_self_dependency",
        ),
        # Disallow duplicate dependencies between same source and target
        UniqueConstraint(
            "source_service_id",
            "target_service_id",
            name="uq_service_dependencies_source_target",
        ),
        # Composite foreign keys guaranteeing both services belong to the same organization
        ForeignKeyConstraint(
            ["source_service_id", "organization_id"],
            ["services.id", "services.organization_id"],
            name="fk_service_dep_source_service_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["target_service_id", "organization_id"],
            ["services.id", "services.organization_id"],
            name="fk_service_dep_target_service_org",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_service_dep_organization",
            ondelete="CASCADE",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    source_service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    target_service_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="service_dependencies",
        overlaps="dependencies_as_source,dependencies_as_target,service_dependencies,source_service,target_service",
    )
    source_service: Mapped["Service"] = relationship(
        "Service",
        primaryjoin="and_(ServiceDependency.source_service_id == Service.id, "
        "ServiceDependency.organization_id == Service.organization_id)",
        back_populates="dependencies_as_source",
        overlaps="dependencies_as_source,dependencies_as_target,service_dependencies,organization,target_service",
    )
    target_service: Mapped["Service"] = relationship(
        "Service",
        primaryjoin="and_(ServiceDependency.target_service_id == Service.id, "
        "ServiceDependency.organization_id == Service.organization_id)",
        back_populates="dependencies_as_target",
        overlaps="dependencies_as_source,dependencies_as_target,service_dependencies,organization,source_service",
    )
