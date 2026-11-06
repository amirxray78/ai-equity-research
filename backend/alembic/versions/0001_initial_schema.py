"""Create the application schema, retrieval indexes, and access policies.

Revision ID: 0001
Revises: None
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS extensions")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions")
    op.create_table(
        "source_documents",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("accession_number", sa.Text(), nullable=False),
        sa.Column("ticker", sa.Text(), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("cik", sa.Text(), nullable=False),
        sa.Column("form", sa.Text(), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_documents")),
        sa.UniqueConstraint(
            "accession_number", name=op.f("uq_source_documents_accession_number")
        ),
    )
    op.create_index(
        "ix_source_documents_ticker_filing_date",
        "source_documents",
        ["ticker", "filing_date"],
        unique=False,
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["id"],
            ["auth.users.id"],
            name=op.f("fk_users_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_table(
        "chat_threads",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_threads_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_threads")),
    )
    op.create_index(
        "ix_chat_threads_user_id_created_at",
        "chat_threads",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "document_chunks",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("source_document_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("anchor", sa.Text(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english'::regconfig, content)", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_document_chunks_nonnegative_position")
        ),
        sa.CheckConstraint(
            "token_count > 0", name=op.f("ck_document_chunks_positive_token_count")
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["source_documents.id"],
            name=op.f("fk_document_chunks_source_document_id_source_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_chunks")),
        sa.UniqueConstraint(
            "source_document_id",
            "position",
            name=op.f("uq_document_chunks_source_document_id"),
        ),
    )
    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index(
        "ix_document_chunks_search_vector_gin",
        "document_chunks",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_table(
        "chat_messages",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')", name=op.f("ck_chat_messages_valid_role")
        ),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_chat_messages_nonnegative_position")
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["chat_threads.id"],
            name=op.f("fk_chat_messages_thread_id_chat_threads"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_messages")),
        sa.UniqueConstraint(
            "thread_id", "position", name=op.f("uq_chat_messages_thread_id")
        ),
    )
    op.create_table(
        "message_citations",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_id", sa.Uuid(), nullable=False),
        sa.Column("citation_number", sa.Integer(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("anchor", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "citation_number > 0",
            name=op.f("ck_message_citations_positive_citation_number"),
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"],
            ["document_chunks.id"],
            name=op.f("fk_message_citations_chunk_id_document_chunks"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["chat_messages.id"],
            name=op.f("fk_message_citations_message_id_chat_messages"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_citations")),
        sa.UniqueConstraint(
            "message_id",
            "citation_number",
            name=op.f("uq_message_citations_message_id"),
        ),
    )
    op.create_index(
        op.f("ix_message_citations_chunk_id"),
        "message_citations",
        ["chunk_id"],
        unique=False,
    )

    # Explicit grants avoid depending on a project's default API privileges.
    for table in (
        "users",
        "source_documents",
        "document_chunks",
        "chat_threads",
        "chat_messages",
        "message_citations",
    ):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"REVOKE ALL ON TABLE public.{table} FROM PUBLIC, anon, authenticated"
        )
        op.execute(f"GRANT ALL ON TABLE public.{table} TO service_role")
        op.execute(f"GRANT SELECT ON TABLE public.{table} TO authenticated")

    op.execute("GRANT USAGE ON SCHEMA public TO authenticated, service_role")
    op.execute(
        "GRANT INSERT, UPDATE, DELETE ON TABLE public.users, public.chat_threads TO authenticated"
    )
    op.execute(
        "REVOKE ALL ON TABLE public.alembic_version FROM PUBLIC, anon, authenticated"
    )

    op.execute("""
        CREATE POLICY users_manage_own ON public.users
        FOR ALL TO authenticated
        USING (id = (SELECT auth.uid()))
        WITH CHECK (id = (SELECT auth.uid()))
    """)
    op.execute("""
        CREATE POLICY threads_manage_own ON public.chat_threads
        FOR ALL TO authenticated
        USING (user_id = (SELECT auth.uid()))
        WITH CHECK (user_id = (SELECT auth.uid()))
    """)
    op.execute("""
        CREATE POLICY messages_read_own ON public.chat_messages
        FOR SELECT TO authenticated
        USING (EXISTS (
            SELECT 1 FROM public.chat_threads AS thread
            WHERE thread.id = chat_messages.thread_id
              AND thread.user_id = (SELECT auth.uid())
        ))
    """)
    op.execute("""
        CREATE POLICY citations_read_own ON public.message_citations
        FOR SELECT TO authenticated
        USING (EXISTS (
            SELECT 1 FROM public.chat_messages AS message
            JOIN public.chat_threads AS thread ON thread.id = message.thread_id
            WHERE message.id = message_citations.message_id
              AND thread.user_id = (SELECT auth.uid())
        ))
    """)
    op.execute("""
        CREATE POLICY documents_read_authenticated ON public.source_documents
        FOR SELECT TO authenticated USING (true)
    """)
    op.execute("""
        CREATE POLICY chunks_read_authenticated ON public.document_chunks
        FOR SELECT TO authenticated USING (true)
    """)


def downgrade() -> None:
    # Dropping tables also drops their policies and indexes. Keep shared extensions.
    op.drop_table("message_citations")
    op.drop_table("chat_messages")
    op.drop_table("document_chunks")
    op.drop_table("chat_threads")
    op.drop_table("users")
    op.drop_table("source_documents")
