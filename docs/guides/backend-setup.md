# Backend setup

This project uses a separate Python + FastAPI backend because the server is responsible for AI and document-processing work, not just basic web CRUD. Python gives us the strongest ecosystem for ingestion, chunking, embeddings, retrieval, evaluation, and LLM workflows. Keeping this logic behind a dedicated API also keeps the frontend focused on the user experience while the backend owns data access, orchestration, and grounding.

## Init (from empty `backend/`)

```bash
cd backend
uv sync
uv add fastapi uvicorn pydantic pydantic-settings httpx structlog openai supabase pydantic-ai sqlalchemy alembic "psycopg[binary]" pgvector
uv add --dev pytest ruff
```

## Database migrations

Alembic owns database schema changes for this project. SQLAlchemy models describe the app tables, and Alembic migrations apply those changes to Supabase Postgres.

Alembic is initialized in this repository. Run commands from `backend/`.
Inspect the revision chain and generate SQL without a database connection:

```bash
uv run alembic heads
uv run alembic history
uv run alembic upgrade head --sql
```

`alembic/env.py` imports all models through `app.database.models` and reads
`settings.DATABASE_URL`. It selects the installed psycopg driver without storing
credentials in `alembic.ini`. Use the direct/session Supabase database connection;
the standard transaction-pooler port (6543) is rejected before connecting.
The search path includes `public` and `extensions`, supporting Supabase's usual
vector extension locations. Autogenerate only considers application table names,
so Supabase-managed tables are excluded. When deliberately removing an application
model, write the corresponding `drop_table` operation explicitly.

The initial revision `0001` creates all six application tables, `vector(1536)`,
the generated English search vector, cosine HNSW and GIN indexes, explicit grants,
and RLS policies. It assumes Supabase's `auth.users`, `auth.uid()`, and API roles
already exist. It creates no Auth users or application users and ingests no data.

Access rules:

| Table | Authenticated access |
| --- | --- |
| `users` | Read/create/update/delete own application user |
| `chat_threads` | Read/create/update/delete own threads |
| `chat_messages` | Read messages belonging to own threads |
| `message_citations` | Read citations belonging to own threads |
| `source_documents`, `document_chunks` | Read shared corpus |

All tables have RLS enabled. Anonymous access is revoked. The backend service
role can write messages, citations, and corpus data; since it bypasses RLS,
request handlers must enforce thread ownership and grounding validation.
Application user creation after signup remains an application responsibility.
These rules follow [Supabase's RLS and grant model](https://supabase.com/docs/guides/database/postgres/row-level-security).

Generate review SQL on demand with `uv run alembic upgrade head --sql` rather than
keeping a duplicate SQL snapshot. Alembic revisions are the schema source of truth.
Offline tests compare the
migration's tables and indexes against model metadata and check emitted policies,
grants, and rollback order. Live execution and RLS behavior still need verification
against Supabase after approval.

Create a migration after changing SQLAlchemy models:

```bash
uv run alembic revision --autogenerate -m "add document tables"
```

Always review the generated migration. Add explicit operations for Supabase/Postgres features that autogenerate cannot reliably infer:

- `create extension if not exists vector`
- `vector(1536)` columns
- generated `tsvector` columns
- HNSW and GIN indexes
- RLS enablement and policies

After reviewing the SQL and approving changes to the target database, apply:

```bash
uv run alembic upgrade head
```

Then verify with `uv run alembic current` and `uv run alembic check` (both connect
to the database). Supabase-specific policies and grants still need separate review;
autogenerate does not compare them. `uv run alembic downgrade base` drops all six
application tables and their data, preserving Supabase Auth, shared extensions,
and schemas. Use downgrade only when that data loss is intended.

## Run

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Imports (`from app...`)

`backend/app` is installed as an editable package by `uv sync`, so `from app...` imports work from uvicorn, direct Python execution, tests, and Jupyter kernels that use the backend venv.

The `[build-system]` and `[tool.hatch.build.targets.wheel]` sections in `backend/pyproject.toml` tell uv how to install the local `app/` package. Without that package install, imports depend on the current working directory or a manually configured `PYTHONPATH`, which is fragile in notebooks and IDE run buttons.

Preferred API server command:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Direct file execution also works:

```bash
cd backend
uv run python app/main.py
```

For Jupyter, install and select the backend kernel:

```bash
cd backend
uv run python -m ipykernel install --user --name document-copilot-backend --display-name "Document Copilot Backend"
```

Then notebooks can import backend modules:

```python
from app.config import settings
```

## Sample SEC data

From the repo root (stdlib-only script, no backend env needed):

```bash
uv run data/download.py
```
