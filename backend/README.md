# FastAPI backend

Requires Python 3.12+ and `uv`. Run commands from `backend/`.

```powershell
uv sync
Copy-Item .env.example .env  # First setup only; then fill in your credentials.
uv run uvicorn app.main:app --reload
```

Configuration lives in `.env`, loaded by `app/config.py`. Fill in the Supabase,
database, and OpenAI values; set `ALLOWED_ORIGINS` to your frontend origin.

- API docs: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/health>
- Stop: `Ctrl+C`. Development reloads automatically when code changes.
- Update installed dependencies: `uv sync` after pulling changes.
- Lint: `uv run ruff check .`
- Production: `uv run uvicorn app.main:app --host 0.0.0.0 --port <PORT>`
  (replace `<PORT>` with the hosting service's assigned port).

Alembic is configured in `alembic.ini` and `alembic/env.py`. The initial revision
is `alembic/versions/0001_initial_schema.py`; it has not been applied to Supabase.
See the [backend setup guide](../docs/guides/backend-setup.md) for the review and
apply workflow.

SQLAlchemy models live in `app/database/models/`, with one model per file:

```text
models/
├── __init__.py         # Registers and exports all models
├── base.py             # Shared metadata and Supabase Auth reference
├── user.py
├── source_document.py
├── document_chunk.py
├── chat_thread.py
├── chat_message.py
└── message_citation.py
```

Import models and the complete migration metadata with
`from app.database.models import Base, User`.

- `users`: application user keyed by the existing Supabase Auth user ID.
  Create an application user after signup before creating its first thread.
- `source_documents`: SEC filing provenance, unique by accession number.
- `document_chunks`: ordered passages within a source document, with text, token
  count, optional section/HTML anchor, a 1536-dimensional embedding, and a generated
  English full-text search vector. Positions are unique and zero-based per document.
  Ingestion must use an embedding model that outputs 1536 dimensions.
- `chat_threads`: conversations owned by an application user.
- `chat_messages`: ordered user/assistant messages with optional model and usage data.
  Assign a unique, zero-based position within each thread when saving a message.
- `message_citations`: numbered references to document chunks, preserving the
  quoted passage and optional section/HTML anchor.

Deleting an application user cascades through its threads, messages, and citations.
Deleting a source document cascades to its chunks; cited chunks are protected from
deletion, so deleting their source document is also blocked. Auth credentials stay in Supabase;
`auth.users` is excluded from the application's SQLAlchemy metadata.

The prepared migration creates the vector extension, generated search column,
HNSW cosine and GIN indexes, and RLS policies. Authenticated users can manage
their own application user and threads, read their own messages/citations, and
read the shared corpus. Message, citation, and corpus writes require the backend
service role. Anonymous access is revoked. The backend must still verify ownership
and validate citations when using the service role, which bypasses RLS.

Preview SQL without connecting to the database:

```powershell
uv run alembic upgrade head --sql
```

After review and explicit approval, apply from `backend/` with
`uv run alembic upgrade head`. The initial migration creates empty tables; it
does not ingest filings or populate application users for existing Auth accounts.
