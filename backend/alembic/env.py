"""Alembic configuration for the application's Supabase Postgres tables."""

from logging.config import fileConfig
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

from alembic import context
from app.config import settings
from app.database.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata
database_url = make_url(str(settings.DATABASE_URL)).set(drivername="postgresql+psycopg")
if database_url.port == 6543 or database_url.query.get("pgbouncer") == "true":
    raise ValueError(
        "Alembic requires a direct/session connection, not transaction pooling"
    )


def include_name(name: str | None, type_: str, parent_names: dict[str, Any]) -> bool:
    """Keep Supabase-managed and unrelated tables out of autogenerate."""
    if type_ == "table":
        return name in target_metadata.tables
    return True


def render_item(type_: str, obj: Any, autogen_context: Any) -> str | bool:
    if type_ == "type" and isinstance(obj, Vector):
        autogen_context.imports.add("from pgvector.sqlalchemy import Vector")
        return f"Vector({obj.dim})"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=include_name,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.execute("SET LOCAL search_path TO public, extensions")
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url, poolclass=pool.NullPool, hide_parameters=True)
    with engine.connect() as connection:
        # Both extension locations are supported by Supabase projects.
        connection.exec_driver_sql("SET SESSION search_path TO public, extensions")
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_name=include_name,
            render_item=render_item,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
