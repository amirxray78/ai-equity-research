-- Generated review snapshot of revision 0001; do not apply separately from Alembic.
BEGIN;

SET LOCAL search_path TO public, extensions;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE SCHEMA IF NOT EXISTS extensions;

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;

CREATE TABLE source_documents (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    accession_number TEXT NOT NULL,
    ticker TEXT NOT NULL,
    company_name TEXT NOT NULL,
    cik TEXT NOT NULL,
    form TEXT NOT NULL,
    filing_date DATE NOT NULL,
    report_date DATE,
    source_url TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_source_documents PRIMARY KEY (id),
    CONSTRAINT uq_source_documents_accession_number UNIQUE (accession_number)
);

CREATE INDEX ix_source_documents_ticker_filing_date ON source_documents (ticker, filing_date);

CREATE TABLE users (
    id UUID NOT NULL,
    display_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT fk_users_id_users FOREIGN KEY(id) REFERENCES auth.users (id) ON DELETE CASCADE
);

CREATE TABLE chat_threads (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    user_id UUID NOT NULL,
    title TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_chat_threads PRIMARY KEY (id),
    CONSTRAINT fk_chat_threads_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_chat_threads_user_id_created_at ON chat_threads (user_id, created_at);

CREATE TABLE document_chunks (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    source_document_id UUID NOT NULL,
    position INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER NOT NULL,
    section TEXT,
    anchor TEXT,
    embedding VECTOR(1536) NOT NULL,
    search_vector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english'::regconfig, content)) STORED NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_document_chunks PRIMARY KEY (id),
    CONSTRAINT ck_document_chunks_nonnegative_position CHECK (position >= 0),
    CONSTRAINT ck_document_chunks_positive_token_count CHECK (token_count > 0),
    CONSTRAINT fk_document_chunks_source_document_id_source_documents FOREIGN KEY(source_document_id) REFERENCES source_documents (id) ON DELETE CASCADE,
    CONSTRAINT uq_document_chunks_source_document_id UNIQUE (source_document_id, position)
);

CREATE INDEX ix_document_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX ix_document_chunks_search_vector_gin ON document_chunks USING gin (search_vector);

CREATE TABLE chat_messages (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    thread_id UUID NOT NULL,
    position INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    model TEXT,
    usage JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT pk_chat_messages PRIMARY KEY (id),
    CONSTRAINT ck_chat_messages_valid_role CHECK (role IN ('user', 'assistant')),
    CONSTRAINT ck_chat_messages_nonnegative_position CHECK (position >= 0),
    CONSTRAINT fk_chat_messages_thread_id_chat_threads FOREIGN KEY(thread_id) REFERENCES chat_threads (id) ON DELETE CASCADE,
    CONSTRAINT uq_chat_messages_thread_id UNIQUE (thread_id, position)
);

CREATE TABLE message_citations (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    message_id UUID NOT NULL,
    chunk_id UUID NOT NULL,
    citation_number INTEGER NOT NULL,
    quote TEXT NOT NULL,
    section TEXT,
    anchor TEXT,
    CONSTRAINT pk_message_citations PRIMARY KEY (id),
    CONSTRAINT ck_message_citations_positive_citation_number CHECK (citation_number > 0),
    CONSTRAINT fk_message_citations_chunk_id_document_chunks FOREIGN KEY(chunk_id) REFERENCES document_chunks (id) ON DELETE RESTRICT,
    CONSTRAINT fk_message_citations_message_id_chat_messages FOREIGN KEY(message_id) REFERENCES chat_messages (id) ON DELETE CASCADE,
    CONSTRAINT uq_message_citations_message_id UNIQUE (message_id, citation_number)
);

CREATE INDEX ix_message_citations_chunk_id ON message_citations (chunk_id);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.users FROM PUBLIC, anon, authenticated;

GRANT ALL ON TABLE public.users TO service_role;

GRANT SELECT ON TABLE public.users TO authenticated;

ALTER TABLE public.source_documents ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.source_documents FROM PUBLIC, anon, authenticated;

GRANT ALL ON TABLE public.source_documents TO service_role;

GRANT SELECT ON TABLE public.source_documents TO authenticated;

ALTER TABLE public.document_chunks ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.document_chunks FROM PUBLIC, anon, authenticated;

GRANT ALL ON TABLE public.document_chunks TO service_role;

GRANT SELECT ON TABLE public.document_chunks TO authenticated;

ALTER TABLE public.chat_threads ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.chat_threads FROM PUBLIC, anon, authenticated;

GRANT ALL ON TABLE public.chat_threads TO service_role;

GRANT SELECT ON TABLE public.chat_threads TO authenticated;

ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.chat_messages FROM PUBLIC, anon, authenticated;

GRANT ALL ON TABLE public.chat_messages TO service_role;

GRANT SELECT ON TABLE public.chat_messages TO authenticated;

ALTER TABLE public.message_citations ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.message_citations FROM PUBLIC, anon, authenticated;

GRANT ALL ON TABLE public.message_citations TO service_role;

GRANT SELECT ON TABLE public.message_citations TO authenticated;

GRANT USAGE ON SCHEMA public TO authenticated, service_role;

GRANT INSERT, UPDATE, DELETE ON TABLE public.users, public.chat_threads TO authenticated;

REVOKE ALL ON TABLE public.alembic_version FROM PUBLIC, anon, authenticated;

CREATE POLICY users_manage_own ON public.users
        FOR ALL TO authenticated
        USING (id = (SELECT auth.uid()))
        WITH CHECK (id = (SELECT auth.uid()));

CREATE POLICY threads_manage_own ON public.chat_threads
        FOR ALL TO authenticated
        USING (user_id = (SELECT auth.uid()))
        WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY messages_read_own ON public.chat_messages
        FOR SELECT TO authenticated
        USING (EXISTS (
            SELECT 1 FROM public.chat_threads AS thread
            WHERE thread.id = chat_messages.thread_id
              AND thread.user_id = (SELECT auth.uid())
        ));

CREATE POLICY citations_read_own ON public.message_citations
        FOR SELECT TO authenticated
        USING (EXISTS (
            SELECT 1 FROM public.chat_messages AS message
            JOIN public.chat_threads AS thread ON thread.id = message.thread_id
            WHERE message.id = message_citations.message_id
              AND thread.user_id = (SELECT auth.uid())
        ));

CREATE POLICY documents_read_authenticated ON public.source_documents
        FOR SELECT TO authenticated USING (true);

CREATE POLICY chunks_read_authenticated ON public.document_chunks
        FOR SELECT TO authenticated USING (true);

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

COMMIT;
