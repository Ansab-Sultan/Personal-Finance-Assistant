# Design Note — AI-Powered Personal Finance Assistant

## 1. Features Covered & Completion Level

All ten brief capabilities are implemented and reachable from chat; each is also a tool the agent owns.

| # | Capability | Status | Notes |
|---|------------|--------|-------|
| 1 | Spending queries ("how much on groceries last month?") | ✅ Done | SQL over monthly rollups |
| 2 | Track a budget + warn near limit | ✅ Done | 80% warning / over states; monthly & yearly |
| 3 | Summarize finances | ✅ Done | category rollup + light narration |
| 4 | Compare across time | ✅ Done | period-vs-period delta |
| 5 | Suggest where to cut back | 🔧 Partial | heuristic (15% on discretionary categories > $100) + LLM narration; not personalized ML |
| 6 | Surface recurring subscriptions | ✅ Done | ~30-day cadence detection, precomputed on ingest |
| 7 | Flag unusual activity | ✅ Done | charge > 2× category average, precomputed on ingest |
| 8 | Read a receipt from a photo | ✅ Done | Gemini vision → parse → user confirms → write |
| 9 | "What is this charge?" / merchant lookup | 🔧 Partial | local heuristic dictionary + LLM; no live web search (see §4) |
| 10 | Remember user context | ✅ Done | durable KV preferences applied automatically |

Plus: CSV + mock-bank ingestion with dedup, streaming chat with rolling-summary memory, Clerk auth,
and a Next.js dashboard (transactions, budgets, chat).

## 2. Key Architectural & Technical Decisions

**Routing as the headline — three cost tiers.** The single most important design choice is matching
effort to the task instead of running the heaviest path on everything:

- **No LLM (0 calls):** structured UI actions (budget card, transaction table, subscriptions/anomalies
  feeds, CSV upload) hit REST directly. A click never touches a model.
- **Fast lane (exactly 1 call):** a cheap router classifies intent + extracts typed params, then a
  **deterministic template** renders the answer. Used for single-intent lookups (spending query,
  budget check, memory write, temporal compare, reading subs/anomalies). No second narration call.
- **Reasoning / ReAct (2+ calls):** only when the model must *synthesize over the figures* — cut-back
  advice, merchant explanation, multi-part or ambiguous asks. A ReAct loop plans → calls tool(s) →
  observes → replans, then a synthesizer narrates.

The deciding rule is explicit: **not "how many tools" but "can a template render the result, or must
the LLM reason over the numbers?"** The math is *always* SQL; the LLM is only ever a language adapter.

**Graph shape (LangGraph):** `router → {fast_lane | react_agent} → (synthesizer) → END`. One router
(supervisor) + a deterministic fast lane + **one** ReAct agent holding all ten tools. I deliberately
**rejected N specialist sub-agents**: a tool already does CRUD via its service, so extra agents add
graph-wiring and context cost with no payoff in a 6-hour build and read as over-engineering.

**Build once, expose twice.** Each capability is a service in `services/`, exposed both as a REST
endpoint (deterministic UI) and a LangGraph tool (chat). Shared logic, zero duplication.

**Handling large transaction history.** This is structural, not a patch: the LLM **never sees raw
transaction rows.** Spending math runs as SQL aggregates over a `monthly_category_rollups` table;
multi-month/yearly queries sum ≤12 precomputed rows; drill-downs are paginated. So "years of data"
cannot overflow the context window — interpreted intent goes in, an aggregated number comes out.
Chat history is bounded separately: last-N turns verbatim + a rolling LLM summary of older turns.

**Async processing.** Heavy ingestion (CSV parse, normalize, dedup, rollup + subscription/anomaly
recompute) runs on an **ARQ** worker over Redis; the upload endpoint returns `202` with a job id, so
the request stays fast. Subscriptions and anomalies are **precomputed into result tables** and only
*read* at query time — instant, and it carries the 10×–100× scale story. Detection is **event-driven,
not a cron**: bulk ingest recomputes once per batch inside the worker job, and a single manual write
commits then enqueues a fire-and-forget recompute (so a one-row write never blocks on a full rescan).
I avoided a scheduled job deliberately — detection is local SQL with no external rate limit, so a
timer would only add staleness and rescan idle users for no benefit.

**Data model.** Postgres with a category ENUM, `transactions` (hash-deduped), `monthly_category_rollups`
(the aggregation backbone), `budgets`, `user_preferences` (CHECK-constrained KV), `chat_messages`
(with a single rolling-summary row), and lightweight `detected_subscriptions` / `flagged_anomalies`.
Everything is `user_id`-scoped; foreign resources return 404, not 403.

**Pragmatic build-vs-buy.** Clerk for auth (JWT verify + Svix webhook for user sync) so engineering
time went to the hard AI parts. Gemini 2.5 Flash everywhere — I **tier the effort, not the model**
(tiny router prompt + low token cap; templated fast lane skips the second call; full tool schemas
only on the ReAct path). The ReAct path *could* swap to a stronger model; Flash is the cheap default.

## 3. Assumptions, Trade-offs & Limitations

- **Single rolling chat thread per user** — no multi-conversation table; simplest thing that meets the
  brief.
- **Known-key preference vocabulary** (`pay_date`, `exclude_from_food`, `currency_display`, …) enforced
  by a CHECK constraint — open-ended free-text memory was out of scope; unmappable preferences are
  acknowledged but not stored as junk.
- **Budgets are per-category**, monthly or yearly; weekly/custom periods are designed-for (ENUM extends)
  but not built.
- **80% budget-warning threshold** is a product decision, stated here and in the README.
- **No rate limiting / quotas** on the API yet.
- **Cut-back logic is heuristic**, not learned — a deliberate trade-off (see §5).

## 4. Intentionally Skipped or Stubbed

- **Live merchant lookup (#9)** — implemented as a small local heuristic + the model's own knowledge,
  **not** a live web/Google search. *Why:* a real search integration means an external API key,
  rate-limit handling, and untrusted-content parsing — high cost for a feature whose AI-engineering
  signal (intent routing + grounded answer) is already demonstrated. The seam is a single tool, so
  swapping in a search API later is trivial.
- **LangGraph checkpointer for receipt confirmation** — *deliberately not added.* The receipt
  confirm-then-write step spans turns, but the parsed fields already live in the prior assistant
  message in chat history, so cross-turn state is free. A Postgres checkpointer would be machinery
  with no benefit here.
- **Free-form semantic memory / embeddings**, multi-named conversations, weekly budgets — skipped as
  over-engineering for the time box; each is noted as an extension point.

## 5. Challenges & How I Handled Them

- **Context-window risk with large histories** — solved at the architecture level: SQL does all math
  and the model never ingests raw rows (see §2), plus summarize-and-window for chat. The model size of
  the data is decoupled from the prompt size.
- **Receipts are messy** (#5 of the brief — "expect the unexpected) — the parser returns a
  `confidence` score and never writes directly; low-confidence, blurry, or foreign-currency reads are
  surfaced for the user to confirm or correct before a transaction is created.
- **Dirty / duplicate imports** — ingestion normalizes rows, quarantines unparseable ones (reported
  back, not silently dropped), and hash-dedupes; exact duplicates `409` with the existing row, near
  ones are flagged.
- **Not narrating empty data as a real answer** — tools return structured `no_data` / `out_of_range`
  signals; the assistant states what's missing and offers the nearest answerable question rather than
  saying "you spent 0."
- **Prompt-injection surface** — the LLM never writes SQL (typed params only); untrusted text
  (`raw_description`, OCR output) is delimited and labelled as data, never instructions.

## 6. Thinking Process & Prioritization

I built bottom-up: data ingestion + rollups → budgets → memory → chat history → the agent last, so the
agent composes already-correct, already-tested services. I front-loaded the three things the brief
weights most — **routing & model selection, large-context handling, and multi-step reasoning with
recovery** — because they show AI-engineering judgment, and consciously kept CRUD-like features (budget
UI, simple lookups) thin since they don't demonstrate that judgment. Every place I spent a model call,
I can say *why a cheaper path wouldn't answer the question* — that trade-off, made explicit, is the
core of the design.
