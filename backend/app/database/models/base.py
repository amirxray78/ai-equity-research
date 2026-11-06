"""Shared SQLAlchemy metadata and Supabase Auth reference."""

from sqlalchemy import Column, MetaData, Table, Uuid
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


# Supabase owns auth.users; exclude it from application migration metadata.
auth_users = Table(
    "users", MetaData(), Column("id", Uuid, primary_key=True), schema="auth"
)
