# AI-Powered Personal Finance Assistant

A full-stack personal finance assistant that ingests transactions, tracks budgets, and answers
natural-language questions about a user's money through a LangGraph agent that **routes each query to
the cheapest level of effort that can answer it** — no LLM for clicks, one call for simple lookups,
a full reasoning loop only when the model must actually synthesize over the numbers.

> **Architecture & reasoning:** see [`documentation/design_note.md`](./documentation/design_note.md).
> Per-module specs live in [`documentation/modules/`](./documentation/modules/).

---

## Tech Stack

| Layer | Tools |
|-------|-------|
| **Backend** | FastAPI (async), LangGraph, SQLAlchemy 2.0 (async) + asyncpg, Alembic, ARQ (Redis-backed jobs), [uv](https://docs.astral.sh/uv/) |
| **AI** | Google Gemini 2.5 Flash via `google-genai` (chat, routing, summarization, **receipt vision OCR**) |
| **Frontend** | Next.js 16, React 19, Tailwind CSS 4 |
| **Auth** | Clerk (JWT verification + Svix webhooks for user sync) |
| **Data** | PostgreSQL 16, Redis 7 |

---

## Prerequisites

- **Docker** + Docker Compose (for the one-command path)
- **Node.js 20+** and **Python 3.12+** with **uv** (only for the run-locally path)
- API keys: a **Clerk** application (publishable + secret key) and a **Google Gemini API key**
  - *Both are optional for a quick look:* with a dummy `GEMINI_API_KEY` the backend runs in
    **mock mode** (deterministic canned LLM/receipt responses) so the whole app is explorable without
    a paid key. See [Additional Notes](#additional-notes).

---

## Environment Variables

**`backend/.env`**

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Async Postgres DSN, e.g. `postgresql+asyncpg://postgres:password@db:5432/finance` |
| `REDIS_URL` | Redis DSN for ARQ, e.g. `redis://redis:6379/0` |
| `CLERK_SECRET_KEY` | Clerk backend secret key (verifies session JWTs) |
| `CLERK_WEBHOOK_SIGNING_SECRET` | Svix signing secret for the Clerk user-sync webhook |
| `CLERK_AUTHORIZED_PARTIES` | Comma-separated allowed origins, e.g. `http://localhost:3000` (also used for CORS) |
| `GEMINI_API_KEY` | Google Gemini API key (use a `dummy...` value to force mock mode) |
| `MODEL` *(optional)* | Override the Gemini model (default `gemini-2.5-flash`) |
| `ROUTER_MAX_TOKENS`, `REACT_MAX_TOKENS`, `SYNTHESIZER_MAX_TOKENS`, `*_TEMPERATURE` *(optional)* | Per-tier LLM tuning (see `app/core/llm_config.py`) |

**`frontend/.env.local`**

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk publishable key |
| `CLERK_SECRET_KEY` | Clerk secret key |
| `NEXT_PUBLIC_BACKEND_URL` | Backend base URL, e.g. `http://localhost:8000` |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | e.g. `/sign-in` |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | e.g. `/sign-up` |

---

## Setup & Run

Install dependencies once (installs `uv` if missing, runs `uv sync` for the backend and `npm install`
for the frontend):

```bash
./setup.sh
```

### Option 1 — Run the whole system via Docker (recommended)

Starts everything: Postgres, Redis, backend, ARQ worker, and frontend. Migrations
(`alembic upgrade head`) run automatically on backend startup; no port edits are needed because
Compose handles internal routing.

```bash
# Ensure backend/.env and frontend/.env.local are populated, then:
sudo docker compose up --build -d

# Stop:
sudo docker compose down
```

App: **http://localhost:3000** · API docs: **http://localhost:8000/docs**

### Option 2 — DB/Redis in Docker, apps locally (dev mode)

Runs only Postgres and Redis in containers; backend, worker, and frontend run natively.

1. **Point `backend/.env` at the host-mapped ports** (`5435` and `6385`):
   ```ini
   DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5435/finance
   REDIS_URL=redis://localhost:6385/0
   ```
2. **Start the databases:**
   ```bash
   sudo docker compose up db redis -d
   ```
3. **Apply migrations** (Docker does this for you in Option 1; do it manually here):
   ```bash
   cd backend && uv run alembic upgrade head
   ```
4. **Run the backend (FastAPI):**
   ```bash
   cd backend && uv run uvicorn app.main:app --reload
   ```
5. **Run the worker (ARQ):**
   ```bash
   cd backend && uv run arq app.worker.WorkerSettings
   ```
6. **Run the frontend (Next.js):**
   ```bash
   cd frontend && npm run dev
   ```

> **First-time auth note:** users are provisioned into the local DB by a **Clerk webhook**. For local
> testing, expose the webhook with `ngrok` (point a Clerk `user.created` webhook at
> `<public-url>/api/v1/auth/webhook`), or insert a row manually. Without this, authenticated API calls
> return `401 "User not registered in local database"`. See [Additional Notes](#additional-notes).

---

## Project Structure

```
revonix/
├── backend/                 # FastAPI + LangGraph
│   └── app/
│       ├── agent/           # LangGraph graph, router/synthesizer nodes, state, tools
│       ├── api/v1/          # REST endpoints (auth, transactions, budget, chat, users)
│       ├── services/        # Business logic (ingestion, budget, receipt, subscriptions, anomalies, llm…)
│       ├── models/          # SQLAlchemy models
│       ├── schemas/         # Pydantic request/response models
│       ├── core/            # config, llm_config, db, security, deps
│       └── worker.py        # ARQ worker entrypoint
├── frontend/                # Next.js 16 (dashboard, chat, budgets, transactions)
├── documentation/           # design_note.md + per-module specs + the brief
├── docker-compose.yml
└── setup.sh
```

---

## API Overview

All routes are under `/api/v1`. Full interactive reference at **`/docs`** (Swagger). Highlights:

- `POST /transactions/upload-csv`, `POST /transactions/fetch-bank` — ingest (async via ARQ)
- `GET/POST/PATCH/DELETE /transactions` · `GET /transactions/subscriptions` · `GET /transactions/anomalies`
- `POST /transactions/receipts/parse` — receipt vision OCR (parse only; user confirms before write)
- `GET/POST/PATCH/DELETE /budget` · `GET /budget/status/{category}/{period}`
- `POST /chat` (SSE streaming) · `GET /chat/history`
- `GET/PATCH /users/me/preferences` — durable user memory
- `POST /auth/webhook` — Clerk user lifecycle sync
