# Document Copilot — Build Checklist

Working checklist for the full build. Update it as we go.

**Status:** `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` blocked

**Guiding rule:** build the risky spine first — **corpus → retrieval → grounded citations** — and the UI last. A polished chat box over weak retrieval fails the client's trust bar ("a wrong but confident answer is worse than no answer").

---

## Critical path

```text
foundations → Supabase → backend skeleton → schema/migrations
   → ingestion (parse → chunk → embed → store)
   → retrieval (vector + FTS + RRF)
   → grounded answer + citation validation
   → API + auth + streaming
   → frontend
   → hardening → deploy → pilot acceptance
```

Anything that blocks the path is done first. Anything cosmetic waits.

---

## Phase 0 — Foundations

Goal: every machine and account needed to build exists.

- [x] Python 3.12+, uv, Node 20+, pnpm verified
- [x] `data/download.py` `USER_AGENT` set to a real contact email (SEC requirement)
- [x] Run `uv run data/download.py`; confirm `data/downloads/manifest.json` + 25 files
- [] Supabase account + project created (see `docs/guides/supabase-setup.md`)
- [ ] OpenAI account + API key created
- [ ] Railway account created (needed only at deploy time)

**Exit:** sample corpus downloaded locally; credentials in hand.

---

## Phase 1 — Supabase + environment config

Goal: one hosted Postgres/Auth project wired to both services, secrets never committed.

- [ ] Collect: project URL, anon key, service_role key, direct connection string, DB password
- [ ] Enable **Email** auth; for dev, disable "Confirm email"
- [ ] Create `backend/.env` from `backend/.env.example` and fill every value
- [ ] Create `frontend/.env` from `frontend/.env.example` and fill `VITE_*` values
- [ ] Confirm `.env` is gitignored and `service_role` never appears in frontend code
- [ ] Backend `app/config.py` validates required vars and fails fast at startup

**Exit:** `backend/` can read settings; a bad/missing var crashes immediately with a clear message.

---

## Phase 2 — Backend skeleton

Goal: a running FastAPI service with health check, settings, logging, and test runner.

- [ ] `cd backend && uv sync`
- [ ] `uv add fastapi uvicorn pydantic pydantic-settings httpx structlog openai supabase pydantic-ai sqlalchemy alembic "psycopg[binary]" pgvector`
- [ ] `uv add --dev pytest ruff`
- [ ] Create `app/main.py` (app factory, routers, CORS from `ALLOWED_ORIGINS`)
- [ ] Create `app/config.py` (pydantic-settings, single source of truth)
- [ ] Add `GET /health` returning service + version
- [ ] Configure `ruff` and `pytest` in `pyproject.toml`
- [ ] `uv run uvicorn app.main:app --reload` → `/health` returns 200

**Exit:** `GET /health` works; `uv run pytest` collects (even if zero tests); `uv run ruff check .` passes.

---

## Phase 3 — Database schema + migrations

Goal: every table, extension, index, and RLS policy exists, managed only by Alembic.

- [ ] `uv run alembic init alembic`
- [ ] `alembic/env.py`: import SQLAlchemy metadata; read `settings.DATABASE_URL`
- [ ] Use the **direct/session** connection string, never the transaction pooler
- [x] Models in `app/database/models/` (one model per file):
  - [x] `users` (keyed by `auth.users.id`)
  - [x] `chat_threads`
  - [x] `chat_messages`
  - [x] `message_citations`
  - [x] `source_documents`
  - [x] `document_chunks`
- [ ] First migration with explicit SQL:
  - [ ] `create extension if not exists vector`
  - [ ] `vector(1536)` embedding column
  - [ ] generated `tsvector` column for full-text search
  - [ ] HNSW index on embeddings
  - [ ] GIN index on `tsvector` (+ metadata JSON if needed)
  - [ ] RLS enabled + policies on user-owned tables
- [ ] Review the generated migration line by line
- [ ] `uv run alembic upgrade head`
- [ ] Verify tables/indexes in Supabase SQL editor

**Exit:** schema exists in Supabase; `alembic upgrade head` is repeatable; no manual dashboard edits needed.

---

## Phase 4 — Ingestion pipeline

Goal: raw HTML → normalized Markdown → chunks → embeddings → Supabase.

- [ ] Decide HTML→Markdown tool (decision D1) and add it
- [ ] `ingest/` script: parse downloaded filings into normalized Markdown
- [ ] Preserve provenance: ticker, company, form, filing date, report date, accession, section
- [ ] Implement chunking (decision D2) with token count + overlap
- [ ] Batch-embed chunks with OpenAI (decision D3)
- [ ] Upsert `source_documents` and `document_chunks` keyed by accession number
- [ ] Make re-runs idempotent (no duplicate documents/chunks)
- [ ] Unit tests: extraction, chunk boundaries, metadata mapping
- [ ] Run against the full sample corpus; record row counts

**Exit:** 25 filings in `source_documents`; chunks + embeddings in `document_chunks`; a second run creates no duplicates.

---

## Phase 5 — Retrieval

Goal: query text → ranked, relevant source passages.

- [ ] `retrieval/queries.py`: pgvector semantic query
- [ ] `retrieval/queries.py`: Postgres full-text query
- [ ] `retrieval/fusion.py`: Reciprocal Rank Fusion in Python
- [ ] `retrieval/retriever.py`: orchestrate → bounded `SourcePassage` list
- [ ] Neighbor lookup (`read_chunk`, `read_surrounding_chunks`)
- [ ] Unit tests with fixed fixtures (no network, no live DB)
- [ ] Manual sanity check: the 10 brief questions retrieve the right companies/sections

**Exit:** every example question returns chunks from the correct ticker and relevant section.

---

## Phase 6 — Grounded answer + citation validation

Goal: typed answer that can only cite retrieved evidence.

- [ ] `assistant/outputs.py`: `GroundedAnswer`, `Citation`, `SourcePassage`
- [ ] `assistant/deps.py`: `DocumentAgentDeps` (user, thread, retriever, validator)
- [ ] `assistant/instructions.md`: product contract (answer only from passages; cite every claim; refuse when insufficient; no stock picks)
- [ ] `assistant/agent.py`: PydanticAI agent with bounded tools
- [ ] `grounding/validator.py`:
  - [ ] every citation maps to a retrieved passage
  - [ ] at least one citation unless "insufficient evidence"
  - [ ] cannot cite documents not retrieved this turn
  - [ ] failure returns a controlled error, not prose
- [ ] Unit tests: citation extraction + grounding enforcement (mock LLM, still test the contract)

**Exit:** invalid citations are rejected in tests; an out-of-corpus question yields an explicit refusal.

---

## Phase 7 — API, auth, streaming, persistence

Goal: authenticated chat turn end-to-end over HTTP.

- [ ] `auth/dependencies.py`: verify `Authorization: Bearer <supabase jwt>`; `get_current_user`
- [ ] Reject unauthenticated requests before retrieval/LLM work
- [ ] `chat/messages.py`: AI SDK wire format ↔ internal models
- [ ] `chat/orchestrator.py`: one turn lifecycle
- [ ] `chat/streaming.py`: AI SDK-compatible streaming parts
- [ ] `api/chat.py`:
  - [ ] `POST /chat/stream`
  - [ ] `GET /threads`
  - [ ] `GET /threads/{id}/messages`
- [ ] Persist user message, assistant message, cited chunks, usage metadata
- [ ] Enforce thread ownership (403 on another user's thread)
- [ ] Error mapping: 401 / 403 / 404 / 422 / 502 / 500
- [ ] Verify with `curl` using a real access token

**Exit:** authenticated streaming works via `curl`; messages and citations persist and reload.

---

## Phase 8 — Frontend

Goal: analyst signs in, asks a question, sees a streamed cited answer.

- [ ] `cd frontend && pnpm create vite . --template react-ts`
- [ ] `pnpm install`
- [ ] `pnpm add react-router-dom @supabase/supabase-js`
- [ ] `pnpm add -D tailwindcss @tailwindcss/vite`
- [ ] `pnpm dlx shadcn@latest init`
- [ ] (optional) `corepack use pnpm@latest` to pin the version
- [ ] `src/lib/env.ts` — validate `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- [ ] `src/lib/supabase.ts`, `src/lib/http.ts`, `src/lib/api.ts`
- [ ] Email sign-in / sign-up pages + session guard
- [ ] Chat route using `useChat` + `DefaultChatTransport` → FastAPI
- [ ] Message list, streaming state, citation cards, source passage viewer
- [ ] Empty / loading / error states (network vs HTTP errors distinguishable)
- [ ] `pnpm tsc --noEmit && pnpm lint`

**Exit:** a real user can sign in, ask, watch the answer stream, and open a citation passage.

---

## Phase 9 — Hardening

- [ ] Fast suite green with no network/DB: `pytest -m "not integration"`
- [ ] Integration tests behind `@pytest.mark.integration`
- [ ] Structured logging with `structlog` (no secrets/PII)
- [ ] Timeouts on OpenAI + Supabase calls
- [ ] Security review: service_role never in browser, RLS correct, CORS allowlist tight
- [ ] Failure UX: 502 upstream, expired token, empty corpus
- [ ] Cost check: embedding + generation spend per question is sane

**Exit:** tests pass offline; a simulated upstream failure shows a clean error, not a stack trace.

---

## Phase 10 — Deploy (Railway)

- [ ] Create Railway project with two services (frontend, backend)
- [ ] Backend env vars set in Railway (never committed)
- [ ] Frontend build + `VITE_*` vars set
- [ ] Run `alembic upgrade head` against the hosted DB
- [ ] Set `ALLOWED_ORIGINS` to the deployed frontend domain
- [ ] Smoke test: sign in → ask → citations
- [ ] Write a short runbook (deploy, migrate, rollback)

**Exit:** production URL works end-to-end.

---

## Phase 11 — Client-brief acceptance

- [ ] All 10 example questions answer with correct citations
- [ ] Out-of-corpus question → explicit "not enough evidence"
- [ ] Citation click opens the underlying passage
- [ ] Users see only their own past conversations
- [ ] Email login works for Driftwood addresses
- [ ] Pilot: 5 senior analysts, 1 week, ≥3 hours saved per analyst per week

**Exit:** brief's definition of done met.

---

## Open decisions (resolve before the phase that needs them)

| # | Decision | Needed by | Options / notes |
|---|---|---|---|
| D1 | HTML → Markdown tool | Phase 4 | `selectolax`, `beautifulsoup4 + lxml`, `trafilatura`. Parsing is genuinely hard → a library is justified. |
| D2 | Chunk size + overlap | Phase 4 | Start ~800 tokens, 15% overlap; prefer section-aware splitting. |
| D3 | Embedding model + dimensions | Phases 3–4 | `text-embedding-3-small` (1536) vs `large` (3072). Dimension is baked into the migration. |
| D4 | "Page" citation semantics | Phases 3–6 | 10-K HTML has no fixed pages. Need section + paragraph anchor, or render to PDF. **Affects the trust requirement.** |
| D5 | RLS vs service-role queries | Phase 3 | User-scoped queries where possible; service_role only for privileged writes. |
| D6 | Streaming payload shape | Phase 7 | Must match the installed Vercel AI SDK version. |

## Scope notes (from the brief)

- Corpus target is 10-Ks **and 10-Qs** for S&P 500, 2020–2025; the current sample script only fetches 5 × 10-K. Decide whether to widen before Phase 4.
- Explicitly out of scope: trading recommendations, external/news data, multi-tenant, billing, mobile.
