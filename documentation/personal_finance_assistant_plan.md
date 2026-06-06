# Revonix — Personal Finance Assistant: Project Plan

---

## Out of Scope

The brief describes a **user-facing product only** — no admin roles, platform management, or
content moderation are mentioned anywhere. The README will state these as deliberate scoping calls:

- **Admin panel / back-office** — nothing in the brief is evaluated through it.
- **Real bank integration (Plaid etc.)** — we consume the provided mock bank endpoint instead.
- **Multi-currency conversion** — we record a transaction's currency as-is; we do not convert
  between currencies (see the receipt edge-case note).

Ship the user app, nothing else.

---

## Core Requirements

These are the things that must exist for the submission to be credible:

### 1. Authentication & Multi-Tenancy (Clerk)
- Sign up, sign in, session management via Clerk
- Every DB row — transactions, budgets, chat history, preferences — is scoped to `user_id`
- Enforce data isolation at the **query level**, not just the route level
- Clerk webhooks to sync user creation/deletion into your own DB

### 2. Financial Data Ingestion
- **CSV upload**: parse, validate, normalize, deduplicate, store
- **Mock bank endpoint**: fetch, normalize into the same schema
- Both flow into a single `transactions` table with a consistent structure
- Must handle: duplicate rows, missing fields, malformed dates, junk rows

### 3. Conversational AI Assistant (LangGraph + Gemini 2.5 Flash-Lite)
The core of the product. Full detail in the Agent section below.

### 4. Budget Tracking
- Users set a budget per category (e.g., food: PKR 15,000/month)
- Assistant reads current spend against budget and warns when close

### 5. User Memory / Preferences
- Persist stated user context: "I get paid on the 1st", "don't count rent in food budget"
- Applied automatically in future queries without the user repeating themselves

### 6. Chat History
- Full conversation history per user, persisted in DB
- Sent to agent as context on each new message (summarized if long)

---

## LangGraph Agent Design

> ⚠️ **Routing shape under active design (being decided together).** Whether this is a *single*
> agent or a *supervisor + sub-agent* split is the open question. What is already settled and not
> changing: the tool set below, the **LLM-never-writes-SQL** rule, and the large-context strategy.

### Agent Flow

```
User Message + Chat History
          ↓
  [Orchestrator Node]       ← LLM interprets natural language intent
          ↓
  [Tool Call with Parameters] ← LLM fills typed parameters (e.g. categories, date_range, period)
          ↓                     Tool internally constructs safe parameterized SQL — LLM never writes SQL
  [Tool Execution]          ← one or more tools run (in sequence or parallel)
          ↓
  [Response Synthesizer]    ← Gemini 2.5 Flash-Lite narrates the tool result in plain English
          ↓
     User Response
```

The orchestrator runs on Gemini 2.5 Flash-Lite. It always interprets the user's natural language
first — this is what handles ambiguity ("eating out" → categories: restaurants, dining, food).
It then decides whether to:
- Call a single tool with the interpreted parameters
- Compose a multi-step plan (e.g., fetch data → detect anomaly → explain)

**The LLM never writes raw SQL.** It fills tool parameters. The tool owns the query.
This keeps the DB safe from prompt injection and keeps hallucinated column names out of your queries.

### Tools

| Tool | What It Does | Query Type |
|------|-------------|------------|
| `spending_query_tool` | SQL aggregations — "how much on groceries last month?" | Simple / Fast |
| `budget_tracker_tool` | Compare current spend to budget limits per category | Simple / Fast |
| `user_memory_tool` | Read and write user preferences and stated context | Simple / Fast |
| `finance_summary_tool` | Category-wise aggregation → plain English summary | Medium |
| `temporal_comparison_tool` | This month vs. last month / same period last year | Medium |
| `subscription_detector_tool` | Identify repeating charges at regular intervals | Medium |
| `anomaly_detector_tool` | Flag charges out-of-pattern using threshold heuristics | Medium |
| `receipt_ocr_tool` | Accept image, extract merchant/amount/date via Gemini vision, record transaction | High |
| `cutback_suggestion_tool` | Analyze category spend, produce numbered suggestions with real figures | Medium |
| `merchant_lookup_tool` | Web search for unrecognized merchant names | External Call |

### Routing Logic — The Signal They Are Grading

Do **not** route every query through the same depth of reasoning. That is the mistake they are watching for.

| Query Type | LLM Interprets | Tool Called With | Tool Runs |
|-----------|---------------|-----------------|-----------|
| "How much did I spend on eating out?" | maps "eating out" → categories, extracts period | `spending_query_tool(categories=[...], period=...)` | parameterized SQL |
| "Am I on budget?" | identifies relevant category + current period | `budget_tracker_tool(category=..., period=...)` | DB comparison |
| "Summarize my finances" | identifies scope (this month, all time) | `finance_summary_tool(period=...)` | SQL GROUP BY per category |
| "Am I spending more this month?" | identifies two periods to compare | `temporal_comparison_tool(period_a=..., period_b=...)` | two SQL queries |
| "What is this charge?" | extracts merchant name from message | `merchant_lookup_tool(merchant=...)` | web search |
| Receipt image upload | detects image input | `receipt_ocr_tool(image=...)` | Gemini vision |
| "Where can I cut back?" | identifies user's categories and history scope | `cutback_suggestion_tool(period=...)` | SQL aggregation |
| Ambiguous / multi-part | breaks into sub-intents | multiple tool calls in sequence | each tool handles its own query |

**The rule**: The LLM always interprets intent and translates natural language into typed tool
parameters. It never touches SQL directly. The tool owns the query, the LLM owns the interpretation.

### Large Context Handling
- Never load a user's full transaction history into the LLM context
- Use **SQL GROUP BY** for aggregations — that is what a database is for
- **Pre-aggregated rollups for scale.** A `monthly_category_rollups` table (refreshed by an ARQ
  task on every ingest) holds per-user, per-month, per-category totals. Queries that span years
  ("am I spending more than usual?", "summarize my finances", "compare to last year") read a few
  hundred rollup rows instead of scanning millions of raw transactions. Raw rows are only touched
  for drill-downs (e.g. "show me those grocery transactions"). This is the direct answer to the
  brief's "must hold up at 10×–100× data."
- **Composite indexes** on `(user_id, date)` and `(user_id, category, date)` so even raw-row
  queries stay range-scoped — never a full-table scan.
- For temporal queries, fetch only the relevant date ranges
- Summarize long chat histories before passing to context (keep last N turns + a running summary)
- User preferences are fetched from DB on each request, not stored in context

---

## Handling the Unexpected (Brief §5)

Real inputs are messy, and the evaluators say they may inject a new input mid-session. Explicit
strategy for each situation the brief names:

### "I genuinely cannot answer that"
- Every data tool returns a structured `no_data` / `out_of_range` signal. An empty result is
  **never** silently narrated as "you spent 0."
- The assistant states what it does *not* have ("your history starts in March 2024, so I can't
  compare to last year") and offers the nearest answerable question — it never fabricates a number.
- Out-of-domain questions ("what's the weather?") are declined politely and steered back to finance.

### Contradicting / duplicate sources
- The same purchase can arrive from **both** the CSV and the mock bank feed, or a **receipt upload
  can double-count a card charge already in the data.** Exact duplicates are caught by the `hash`
  unique constraint (idempotent re-ingest).
- **Near-duplicates** (same amount + merchant within a ±2-day window across different `source`s)
  are flagged as *suspected duplicates* rather than blindly merged. The assistant surfaces the
  conflict, prefers the bank/authoritative source, and notes the assumption.
- On receipt upload we look for a matching existing transaction before inserting; if found, we
  **enrich** it (attach line items) instead of creating a second expense.

### Bad receipt photos
- `receipt_ocr_tool` returns **confidence + extracted fields**, not a blind write.
- Low confidence, rotated, partial, or unreadable → the assistant **asks the user to confirm or
  correct** merchant/amount/date before recording, instead of saving wrong data.
- Foreign-language / foreign-currency receipts: capture the **currency as printed** and store it
  (no conversion); translate field labels for display only.

---

## Safety & Data Trust

- **The LLM never writes SQL** — it fills typed tool parameters; tools own parameterized queries.
  This stops injection and hallucinated column names at the source.
- **Untrusted text is data, not instructions.** Merchant strings, CSV description columns, and
  receipt OCR output can carry prompt-injection payloads ("ignore previous instructions…"). Any
  such text placed in a model prompt is wrapped in explicit delimiters and labelled untrusted; the
  system prompt states that content inside those delimiters is never an instruction. This is why
  `raw_description` is stored separately from the cleaned `merchant`.
- **Tool inputs are validated/whitelisted** before any query runs — `category` against the user's
  known categories, `period` against an allowed enum, date ranges bounded.

---

## Correctness Check (cheap, high-signal)

Finance users trust numbers — a wrong figure is worse than "I don't know." A tiny eval harness:
- ~8–10 canned questions over the sample dataset whose answers are computed independently (plain
  SQL/pandas) and asserted against the assistant's tool output (e.g. "groceries in March" = X).
- Includes at least one **unanswerable** question (asserts a graceful decline) and one **ambiguous**
  one (asserts it interprets sensibly or asks).
- Runs in seconds. Proves the SQL tools return *correct* numbers and that routing picks the right
  tool — directly demonstrable to the evaluators.

---

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Auth | Clerk | Commodity — do not build this |
| Backend | FastAPI | Async-native, fits ARQ + LangGraph well |
| AI Agent | LangGraph | Controllable, auditable, agentic loop |
| LLM | Gemini 2.5 Flash-Lite | Fast, cheap, vision-capable |
| Database | PostgreSQL | Financial data is relational, SQL is the right tool |
| ORM | SQLAlchemy (async) | Works natively with FastAPI async |
| Migrations | Alembic | Standard PostgreSQL migration tooling |
| Cache / Broker | Redis | Dual purpose: caching + ARQ task queue |
| Background Tasks | ARQ | Lightweight, async-native, simpler than Celery for this scale |
| Frontend | Next.js | App router, Clerk integration, good DX |

---

## Project Structure

### Backend (FastAPI)

```
backend/
├── core/
│   ├── config.py             # Pydantic Settings — all env vars in one place
│   ├── database.py           # SQLAlchemy async engine + session factory
│   ├── dependencies.py       # FastAPI deps: get_db, get_current_user
│   ├── security.py           # Clerk JWT verification middleware
│   └── exceptions.py         # Global exception handlers
│
├── agent/
│   ├── agent.py              # LangGraph graph definition + compiled agent
│   ├── nodes.py              # Orchestrator, planner, synthesizer nodes
│   ├── state.py              # LangGraph AgentState definition
│   └── tools/
│       ├── spending.py       # spending_query_tool — interprets category intent, runs parameterized SQL
│       ├── budget.py         # budget_tracker_tool
│       ├── summary.py        # finance_summary_tool
│       ├── temporal.py       # temporal_comparison_tool
│       ├── subscriptions.py  # subscription_detector_tool
│       ├── anomaly.py        # anomaly_detector_tool
│       ├── receipt_ocr.py    # receipt_ocr_tool — Gemini vision
│       ├── merchant_lookup.py# merchant_lookup_tool — web search
│       ├── cutback.py        # cutback_suggestion_tool
│       └── memory.py         # user_memory_tool
│
├── services/
│   ├── ingestion.py          # CSV parser + mock bank endpoint fetcher
│   ├── normalizer.py         # Raw rows → normalized Transaction schema
│   ├── deduplication.py      # Hash-based dedup before insert
│   ├── budget.py             # Budget CRUD logic
│   ├── memory.py             # User preferences read/write
│   └── tasks.py              # ARQ background task functions
│
├── api/
│   └── v1/
│       ├── auth.py           # Clerk webhook: user.created, user.deleted
│       ├── transactions.py   # POST /upload-csv, GET /transactions
│       ├── chat.py           # POST /chat (SSE streaming response)
│       ├── budget.py         # CRUD for budgets
│       └── users.py          # GET/PATCH user profile + preferences
│
├── schemas/
│   ├── transaction.py        # TransactionCreate, TransactionRead
│   ├── chat.py               # ChatMessage, ChatRequest, ChatResponse
│   ├── budget.py             # BudgetCreate, BudgetRead
│   └── user.py               # UserRead, UserPreference
│
├── models/                   # SQLAlchemy ORM models
│   ├── user.py
│   ├── transaction.py
│   ├── budget.py
│   ├── chat_message.py
│   └── user_preference.py
│
├── worker.py                 # ARQ worker entry point
├── main.py                   # FastAPI app factory, router registration
└── alembic/                  # DB migrations
    └── versions/
```

### Frontend (Next.js)

```
frontend/
├── app/
│   ├── (auth)/
│   │   ├── sign-in/[[...sign-in]]/page.tsx
│   │   └── sign-up/[[...sign-up]]/page.tsx
│   │
│   ├── (dashboard)/
│   │   ├── layout.tsx         # Sidebar, auth guard, Clerk provider
│   │   ├── page.tsx           # Dashboard overview — spending snapshot
│   │   ├── chat/
│   │   │   └── page.tsx       # Main chat UI with message history
│   │   ├── transactions/
│   │   │   └── page.tsx       # Transaction list + CSV upload
│   │   ├── budgets/
│   │   │   └── page.tsx       # Set/view/edit budgets per category
│   │   └── settings/
│   │       └── page.tsx       # User preferences (pay date, exclusions)
│   │
│   └── api/
│       └── webhooks/
│           └── clerk/route.ts  # Clerk webhook receiver → forward to backend
│
├── components/
│   ├── chat/
│   │   ├── ChatWindow.tsx
│   │   ├── MessageBubble.tsx
│   │   └── ReceiptUpload.tsx
│   ├── transactions/
│   │   ├── TransactionTable.tsx
│   │   └── CsvUploader.tsx
│   └── budget/
│       └── BudgetCard.tsx
│
└── lib/
    ├── api.ts                 # Typed API client (fetch wrapper)
    └── hooks/
        ├── useChat.ts
        └── useTransactions.ts
```

---

## Background Tasks (ARQ + Redis)

| Task | Trigger | Why Not Inline |
|------|---------|---------------|
| `process_csv_upload` | After CSV file received | File can be large — don't block the HTTP response |
| `fetch_mock_bank_data` | On-demand or scheduled | External network call, unknown latency |
| `run_subscription_detection` | After new data ingested | Batch scan, expensive to run per-request |
| `run_anomaly_detection` | After new data ingested | Same — batch, not per-query |
| `refresh_monthly_rollups` | After new data ingested | Keeps the pre-aggregated rollup table current so multi-month/year queries stay cheap |

Worker entry point: `worker.py` — registered with Redis via ARQ.

---

## Database Schema (High Level)

```sql
users                    (id, clerk_id, email, created_at)
transactions             (id, user_id, date, amount, currency, merchant, raw_description,
                          category, source, hash, created_at)
budgets                  (id, user_id, category, limit_amount, period, created_at)
chat_messages            (id, user_id, role, content, created_at)
user_preferences         (id, user_id, key, value, updated_at)
monthly_category_rollups (id, user_id, month, category, total_amount, txn_count, updated_at)

-- indexes
transactions:  (user_id, date), (user_id, category, date), unique(user_id, hash)
rollups:       unique(user_id, month, category)
```

- `transactions.hash` — SHA256 of (user_id + date + amount + merchant); a **unique constraint** so
  re-ingesting the same CSV is idempotent (exact-duplicate dedup)
- `transactions.source` — `"csv"` or `"bank_api"`, for auditability and cross-source reconciliation
- `transactions.raw_description` — the original, **untrusted** merchant/description string, kept
  separate from the cleaned `merchant` field (see Safety & Data Trust — never treated as instructions)
- `transactions.currency` — stored, not converted (multi-currency conversion is out of scope)
- `monthly_category_rollups` — pre-aggregated totals; the read path for any multi-month question
- `user_preferences` — flat key-value store (e.g. `pay_date: "1"`, `exclude_from_food: "rent"`)

---

## What to Build vs. Stub

Be honest about this in the README. The evaluators read Section 7 carefully.

| Feature | Call | Reason |
|---------|------|--------|
| Clerk auth | Fully working | Commodity — one day of setup max |
| CSV ingestion | Fully working | Core data path — must work |
| Spending queries | Fully working | Core assistant capability, high signal |
| Budget tracking | Fully working | Simple, high signal for evaluators |
| Finance summary | Fully working | Core assistant capability |
| User memory | Fully working | They will test this explicitly |
| Temporal comparison | Fully working | Core reasoning, shows multi-step thinking |
| Receipt OCR | Working (Gemini vision) | High signal, Gemini makes it relatively easy |
| Subscription detection | Basic heuristic (same merchant + ~30-day interval) | Acceptable stub with honest note |
| Anomaly detection | Threshold-based (charge > 2× category average) | Acceptable stub with honest note |
| Cut-back suggestions | SQL aggregation + LLM narration | Rule-based is fine for 6 hours |
| Merchant lookup | Web search tool — stub if time runs out | Low priority, mention in README |
| Pre-aggregated rollups | Fully working | Direct answer to "holds up at 100× data" — high signal |
| Cross-source reconciliation | Basic near-duplicate flagging | Honest heuristic, documented |
| "Cannot answer" handling | Fully working | Cheap; directly tested by §5 |
| Correctness eval harness | Small (~10 cases) | Proves the numbers are right; minutes to write |

---

## Constraints — How We Address Them

| Constraint | Approach |
|-----------|----------|
| **Fast responses** | Two fast-path mechanisms: (1) **structured UI actions** (clicking a budget card, opening transactions) hit the API directly and never touch an LLM; (2) for natural-language lookups, the model interprets intent once, the tool runs, and a **deterministic template** renders single-value results — no second LLM narration call. SSE streaming keeps anything heavier feeling responsive. |
| **Economical** | No full transaction history in context. Single-value results are templated, not narrated, to skip a 2nd LLM call. Heavy reasoning fires only on queries that need it (*how we escalate is the open agent-routing question we're settling*). **Cache** in Redis: merchant lookups globally (merchant identity isn't user-specific) + recent per-user summaries. |
| **Large data** | Pre-aggregated `monthly_category_rollups` for multi-month questions; raw-row queries are index-scoped and date-filtered. All aggregation in SQL (GROUP BY/SUM/AVG) — the LLM narrates, never counts rows. |
| **Many concurrent users** | Stateless async FastAPI + ARQ workers scale horizontally. Redis handles shared state and caching. |

---

## What They Are Actually Grading (Re-read Section 7)

They are not counting features. The real signals:

1. **You did not send everything through one big LLM call** — you routed intelligently by query complexity
2. **The LLM interprets intent, the tool runs the query** — LLM fills typed parameters, never writes raw SQL. Handles ambiguity without opening injection vectors.
3. **You used off-the-shelf where it made sense** — Clerk, ARQ, not custom auth or custom queues
4. **Your README is honest** — what you built, what you stubbed, why you made each call
5. **Your architecture survives real load** — async, stateless, no per-request full-table scans

The **design note is worth as much as the code.** A clean, honest README explaining your
trade-offs is part of the deliverable, not an afterthought.
