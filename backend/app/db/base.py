"""SQLAlchemy Declarative Base definition.

All database models in future milestones will inherit from this Base class.
No domain business models are defined in Milestone 1.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy 2.x models."""

    pass
