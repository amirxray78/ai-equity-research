"""Offline migration checks: no credentials, network, or database required."""

import re
import sys
from io import StringIO
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from alembic.config import Config
from sqlalchemy.dialects.postgresql import dialect
from sqlalchemy.schema import CreateIndex, CreateTable

from alembic import command
from app.database.models import Base

BACKEND = Path(__file__).resolve().parents[2]


@pytest.fixture
def migration_config(monkeypatch: pytest.MonkeyPatch) -> Config:
    config_module = ModuleType("app.config")
    config_module.settings = SimpleNamespace(  # type: ignore[attr-defined]
        DATABASE_URL="postgresql://postgres:offline%25password@localhost:5432/postgres"
    )
    monkeypatch.setitem(sys.modules, "app.config", config_module)

    def forbid_connection(*args: object, **kwargs: object) -> None:
        raise AssertionError("Offline migration checks must never create an engine")

    monkeypatch.setattr("sqlalchemy.create_engine", forbid_connection)
    return Config(str(BACKEND / "alembic.ini"), output_buffer=StringIO())


def upgrade_sql(config: Config) -> str:
    command.upgrade(config, "head", sql=True)
    return config.output_buffer.getvalue()


def normalize(sql: str) -> str:
    return " ".join(sql.split())


def test_initial_migration_matches_all_model_tables_and_indexes(
    migration_config: Config,
) -> None:
    raw_sql = upgrade_sql(migration_config)
    sql = normalize(raw_sql)
    for table in Base.metadata.sorted_tables:
        expected = str(CreateTable(table).compile(dialect=dialect()))
        actual = re.search(
            rf"CREATE TABLE {table.name} \(\n(.*?)\n\);", raw_sql, re.DOTALL
        )
        assert actual is not None
        expected_body = expected.split("(\n", 1)[1].rsplit("\n)", 1)[0]
        # Constraint order can differ between metadata and Alembic rendering.
        assert sorted(
            line.strip().rstrip(",") for line in actual[1].splitlines()
        ) == sorted(line.strip().rstrip(",") for line in expected_body.splitlines())
        for index in table.indexes:
            assert normalize(str(CreateIndex(index).compile(dialect=dialect()))) in sql
    assert (
        sql.count("CREATE TABLE ") == 7
    )  # Six app tables plus Alembic's version table.
    assert "CREATE TABLE auth.users" not in sql


def test_retrieval_schema_and_atomic_upgrade(migration_config: Config) -> None:
    sql = upgrade_sql(migration_config)
    assert sql.startswith("BEGIN;")
    assert sql.rstrip().endswith("COMMIT;")
    assert sql.index("CREATE EXTENSION IF NOT EXISTS vector") < sql.index(
        "VECTOR(1536)"
    )
    assert (
        "GENERATED ALWAYS AS (to_tsvector('english'::regconfig, content)) STORED" in sql
    )
    assert "USING hnsw (embedding vector_cosine_ops)" in sql
    assert "USING gin (search_vector)" in sql


def test_all_app_tables_have_explicit_rls_and_grants(migration_config: Config) -> None:
    sql = upgrade_sql(migration_config)
    for table in Base.metadata.tables:
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in sql
        assert (
            f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC, anon, authenticated"
            in sql
        )
        assert f"GRANT SELECT ON TABLE public.{table} TO authenticated" in sql
        assert f"GRANT ALL ON TABLE public.{table} TO service_role" in sql
    assert (
        "REVOKE ALL ON TABLE public.alembic_version FROM PUBLIC, anon, authenticated"
        in sql
    )


def test_chat_read_policies_follow_thread_ownership(migration_config: Config) -> None:
    sql = normalize(upgrade_sql(migration_config))
    assert (
        "USING (id = (SELECT auth.uid())) WITH CHECK (id = (SELECT auth.uid()))" in sql
    )
    assert (
        "USING (user_id = (SELECT auth.uid())) WITH CHECK (user_id = (SELECT auth.uid()))"
        in sql
    )
    assert (
        "WHERE thread.id = chat_messages.thread_id AND thread.user_id = (SELECT auth.uid())"
        in sql
    )
    assert (
        "WHERE message.id = message_citations.message_id AND thread.user_id = (SELECT auth.uid())"
        in sql
    )
    assert (
        "CREATE POLICY messages_read_own ON public.chat_messages FOR SELECT TO authenticated"
        in sql
    )
    assert (
        "CREATE POLICY citations_read_own ON public.message_citations FOR SELECT TO authenticated"
        in sql
    )
    write_grants = [line for line in sql.split(";") if "GRANT INSERT" in line]
    assert len(write_grants) == 1
    assert (
        "ON TABLE public.users, public.chat_threads TO authenticated" in write_grants[0]
    )


def test_downgrade_removes_dependents_first_and_preserves_supabase(
    migration_config: Config,
) -> None:
    command.downgrade(migration_config, "0001:base", sql=True)
    sql = migration_config.output_buffer.getvalue()
    dropped = [
        line.strip() for line in sql.splitlines() if line.startswith("DROP TABLE")
    ]
    assert dropped == [
        "DROP TABLE message_citations;",
        "DROP TABLE chat_messages;",
        "DROP TABLE document_chunks;",
        "DROP TABLE chat_threads;",
        "DROP TABLE users;",
        "DROP TABLE source_documents;",
    ]
    assert "DROP EXTENSION" not in sql
    assert "DROP SCHEMA" not in sql
    assert "DROP TABLE auth." not in sql


def test_transaction_pooler_is_rejected_before_connecting(
    migration_config: Config,
) -> None:
    sys.modules["app.config"].settings.DATABASE_URL = (  # type: ignore[attr-defined]
        "postgresql://postgres:offline@localhost:6543/postgres"
    )
    with pytest.raises(ValueError, match="direct/session connection"):
        upgrade_sql(migration_config)
