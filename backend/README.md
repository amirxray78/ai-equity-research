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

Database migrations are not initialized yet; see the
[backend setup guide](../docs/guides/backend-setup.md) when adding them.

SQLAlchemy models live in `app/database/models.py`:

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

These definitions do not create tables. The next schema step is an Alembic
migration with the vector extension, generated search column, HNSW/GIN indexes,
and RLS policies before exposing database access. Citation validation must enforce
that only assistant messages cite retrieved evidence.
