"""Shared SQLAlchemy declarative base for all ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Single declarative base for the entire project.

    All ORM model classes must inherit from this Base so that
    Base.metadata contains every table for Alembic autogenerate.
    """
