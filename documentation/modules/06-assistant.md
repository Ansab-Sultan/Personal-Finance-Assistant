# Module 06 — Assistant (LangGraph)

> **Goal:** The conversational core. Turn natural language (and receipt images) into the right
> action over the user's data — routing cheaply, reasoning deeply only when needed, recovering from
> failures, and narrating results in plain English.
>
> **Depends on:** every other module (01–05). Build it **last** — it orchestrates the data and
> endpoints they produce.
>
> Brief mapping: **all of §3** (the 10 capabilities), and the §7 grading axes
> (routing & model selection, multi-step reasoning, large context, edge cases).

---

## The one signal that matters

§7's headline axis is **routing & model selection** — *"match the right level of effort to each
task… rather than applying the heaviest approach to everything."* The §3 intro says it plainly:
the ten capabilities *"are not all the same kind of work"* — some are near-instant lookups, some
need multi-step reasoning, some an image, some years of data — and *"how you handle that difference
is a large part of the signal."*

So the design is built around **three cost tiers**, and the assistant's first job on every message
is to pick the cheapest tier that can answer correctly.

---

## Three cost tiers

| Tier | LLM calls | When | Examples |
|------|-----------|------|----------|
| **No LLM** | 0 | User *clicked* — a structured UI action hits REST directly | budgets page, transactions list, subscriptions feed, anomalies feed, CSV upload, receipt-parse button |
| **Fast lane** | exactly **1** (the router) | Natural-language **single-intent lookup** whose answer a deterministic **template** can render | "how much on groceries last month?", "am I on budget?", "remember I get paid on the 1st" |
| **Reasoning (ReAct)** | **2+** | The LLM must reason/narrate over figures, chain tools, or recover from a step | "where can I cut back?", "what is this charge?", "compare *and explain why*", ambiguous/multi-part |

**The deciding rule is not "how many tools."** It is:

> **Can a deterministic template render the result, or must the LLM synthesize over the numbers?**

The arithmetic is **always SQL over `monthly_category_rollups`** (Module 02) — the LLM never counts
rows or computes a ratio. In the fast lane the single LLM call is the **router itself**: it only
translates natural language into typed tool parameters (`category`, `period`, `categories[]`); the
tool runs the parameterized query and a template prints the answer, with **no second narration
call**. On a click, even that one call is skipped.

---

## Graph shape — router + fast lane + one ReAct agent

```
message (+ optional image)
        ↓
[Router node]   ← 1 cheap Flash-Lite call: classify intent + extract typed params
        ↓
   ┌────┴───────────────────────────┐
   ↓                                ↓
[Fast lane]                   [ReAct agent]   ← ONE agent, holds all tools
 single tool →                 plan → call tool(s) → observe →
 deterministic template         recover/replan → decide it has enough
 (NO 2nd LLM call)                     ↓
   └─────────────┬──────────────────────┘
                 ↓
         [Synthesizer]  ← narrate to plain English (skipped when the fast lane templated)
```

This is a **supervisor (the router) + one heavy sub-agent + a deterministic fast lane** — not a mesh
of specialist sub-agents.

> **Why not supervisor + N specialist sub-agents?** A tool already does CRUD by calling its service;
> it does not need a sub-agent wrapper. Sub-agents earn their cost only when you need *separate
> reasoning loops with their own context* — not to group tools by domain. N specialist agents is
> graph-wiring cost with more failure surface and reads as over-engineered for a 6-hour build. One
> ReAct agent holding all tools lets the model pick the tool; that is all we need. (State this
> trade-off in the README — §7 rewards being able to defend the call.)

| File | Responsibility |
|------|----------------|
| `agent/agent.py` | LangGraph graph definition + compiled agent (router → branch → synthesizer) |
| `agent/nodes.py` | router (classify + extract), fast-lane dispatch, synthesizer |
| `agent/state.py` | `AgentState`: message, image?, `user_id`, prefs, recent turns, route, tool results |
| `agent/tools/*` | the ten tools, each wrapping a `services/` function (see below) |

---

## §3 capability → lane mapping

- **Fast lane (1 call, templated):** spending query, budget check, user-memory write, simple
  temporal delta ("up 18% vs last month").
- **Reasoning (2+ calls, narrated):** cut-back suggestions, merchant lookup, "compare *and explain
  why*", finance summary (light narration), any ambiguous or multi-part request.
- **No LLM (REST):** subscriptions feed, anomalies feed, budget card, transaction table, CSV upload.
- **Receipt path:** parse (Gemini vision) → confirm/edit → write.

Worked example — **"Suggest where to cut back" → reasoning lane**, not fast lane: the
`cutback_suggestion_tool` returns raw figures, but turning them into *"you're spending ~40% above
your usual on eating out; dropping from 4 to 2 visits a week saves ~PKR 3,000"* is synthesis a
template can't produce. Router call → tool(s) → synthesizer = 2+ calls.

---

## Build once, expose twice (the shared-service pattern)

Each capability is a **service** in `services/`, exposed **twice**:

- a plain **REST endpoint** — deterministic, no LLM, for UI buttons and pages;
- a LangGraph **tool** — for when the user asks the same thing in chat.

Both call the same service, so there is no duplicated logic and no second source of truth. The
assistant is an **orchestration layer, not a reimplementation**: `budget_tracker_tool` calls Module
03's budget-status service, `user_memory_tool` calls Module 04's service, the receipt and spending
tools call Module 02's transaction services.

---

## Tools

The full set (see the [main plan](../personal_finance_assistant_plan.md#tools)):
`spending_query`, `budget_tracker`, `user_memory`, `finance_summary`, `temporal_comparison`,
`subscription_detector`, `anomaly_detector`, `receipt_ocr`, `cutback_suggestion`, `merchant_lookup`.

Settled rules (hold regardless of routing):

- **The LLM never writes SQL.** It fills typed tool parameters; each tool owns its parameterized
  query. (Injection-safe, no hallucinated columns.)
- **Tool inputs are validated/whitelisted** before any query runs — `category` against the user's
  known categories, `period` against an allowed enum, date ranges bounded.
- **Large-context strategy** — the model never ingests raw transaction history; aggregation happens
  in SQL over `monthly_category_rollups`; chat history is summarized + windowed (Module 05).

---

## Subscriptions & anomalies — precomputed, read-only at query time

These are **precomputed detections, not per-request scans**, written to two small
`user_id`-scoped tables:

```sql
detected_subscriptions (id, user_id, merchant, amount, cadence_days, last_seen, confidence, updated_at)
flagged_anomalies       (id, user_id, transaction_id, category, amount, reason, detected_at)
```

Detection is **event-driven, not scheduled** — it recomputes when a user's data actually changes,
never on a timer:

- **Bulk ingest** (CSV / mock-bank): detection runs **inline, once per batch, inside the ARQ ingest
  job** (`detect_and_save_subscriptions` / `detect_and_save_anomalies` in `services/`). It's already
  off the request path and amortized over the whole import.
- **Single-row writes** (manual create / update / delete): the API commits, then **enqueues a
  fire-and-forget `recompute_detections_task`** so a one-row write never blocks on a full rescan.

> **Why event-driven, not cron.** Detection is pure local SQL/Python — no external API and no rate
> limit to smooth out, so a timer buys nothing. A cron would only add **staleness** (new data wouldn't
> surface until the next tick) and would either rescan *every* user each tick (wasteful — against the
> brief's "economical" ask) or need dirty-user tracking. Triggering on the ingest event runs exactly
> when — and only for the user whose — data changed. Cron would be the right tool for a periodic
> digest or a throttled external call; neither applies here.

Both the REST feed **and** the `subscription_detector_tool` / `anomaly_detector_tool` only **read**
these tables — instant and cheap, and it carries the brief's 10×–100× scale story (no expensive
scan on the hot path). Heuristics: same merchant at a regular ~30-day interval; a charge > 2× the
category average. (Acceptable starting heuristics, noted honestly in README.)

---

## Receipt flow — REST confirm *and* in-chat, one shared service, no checkpointer

`services/receipt.py` does the Gemini-vision parse → `{merchant, amount, date, currency,
confidence}` and **never writes**. Two entry points reuse it:

- **Deterministic (UI button):** `POST /receipts/parse` returns the extracted fields + confidence →
  the frontend shows a confirm/edit card → on accept it writes via the existing `POST /transactions`
  (`source = 'receipt'`; the Module 02 dedup / `409` rules apply, so a receipt can't double-count a
  card charge already in the data).
- **Conversational (image dropped into chat):** the agent detects the image → `receipt_ocr_tool`
  calls the same parse service → the assistant replies *"I read Starbucks, PKR 1,240, 3 Jun — record
  it?"* → on the user's confirm or correction **next turn**, it calls transaction create.

**Why no `langgraph-checkpoint-postgres`:** the confirm spans two turns, but the parsed fields live
in the assistant's prior message, which is already in the **chat history (Module 05)** sent on the
next turn. The checkpointer solves mid-*run* pauses (human-in-the-loop inside a single graph
execution); our pause is *between* runs, where chat history already is the memory. Adding the
checkpointer here would be machinery we don't need — note this deliberate call in the README.

Low confidence, blurry, rotated, partial, or foreign-currency receipts → **ask the user to confirm
or correct before writing**, never a blind write (brief §5). Currency is captured **as printed**,
no conversion.

---

## Handling the unexpected (brief §5)

- **"I genuinely cannot answer that."** Every data tool returns a structured `no_data` /
  `out_of_range` signal; an empty result is **never** narrated as "you spent 0." The assistant
  states what it lacks ("your history starts in March 2024, so I can't compare to last year") and
  offers the nearest answerable question. Out-of-domain questions are declined and steered back to
  finance.
- **Contradicting / duplicate sources.** Exact dupes are caught by the `hash` unique constraint;
  near-dupes are surfaced, not merged (Module 02). A receipt matching an existing charge **enriches**
  it rather than creating a second expense.
- **Untrusted text is data, not instructions.** `raw_description` and OCR output can carry
  injection payloads; any such text in a prompt is wrapped in explicit delimiters and labelled
  untrusted — the system prompt states content inside those delimiters is never an instruction.
- **Multi-step recovery.** A failed or empty tool result → retry, replan, or degrade gracefully;
  the agent decides when it has enough rather than looping forever.

---

## Model tiering

Gemini 2.5 Flash-Lite everywhere; tier the **effort**, not the model:

- Router: tiny prompt + low `max_tokens` — classify and extract only.
- Fast lane: skips the second LLM call entirely (deterministic template).
- ReAct path: the full system prompt + tool schemas, only when escalation is warranted.

The ReAct path *could* swap to a stronger model later, but Flash-Lite is the cheap, defensible
default for a finance assistant where the SQL tools — not the model — own correctness.

### LLM configuration — `core/llm_config.py`

All model params are centralised in one config class so per-role tuning is a single-line change,
not a hunt through node files:

```python
# core/llm_config.py
from pydantic_settings import BaseSettings

class LLMConfig(BaseSettings):
    model: str = "gemini-2.5-flash-lite"       # override via MODEL= in .env
    # NOTE: max_tokens caps the model's OUTPUT only. Input (summary + history +
    # tool results) is bounded by the ~1M-token context window, NOT by these.
    router_max_tokens: int  = 256              # classify + extract — tiny JSON, keep it small
    react_max_tokens:  int  = 8192             # generous: multi-step reasoning + tool args
    synthesizer_max_tokens: int = 8192         # generous: long narrated summaries / cut-back lists
    router_temperature:     float = 0.0        # deterministic classification
    react_temperature:      float = 0.1
    synthesizer_temperature: float = 0.3

llm_config = LLMConfig()
```

> **Why these sizes.** `max_tokens` limits the **reply length**, not the context the model reads —
> the chat summary, prior turns, and tool results are *input* and live in the ~1M-token context
> window. The router output is a tiny classification, so it stays small (cheap + fast). The ReAct
> and synthesizer outputs can be long — a finance summary or a numbered cut-back list with figures —
> so they get generous headroom to avoid a truncated reply. All three are env-overridable, so if a
> reply ever clips you raise `REACT_MAX_TOKENS` without a code change.

Used in `agent/nodes.py`:

```python
from core.llm_config import llm_config
from langchain_google_genai import ChatGoogleGenerativeAI

router_llm = ChatGoogleGenerativeAI(
    model=llm_config.model,
    max_tokens=llm_config.router_max_tokens,
    temperature=llm_config.router_temperature,
)
react_llm = ChatGoogleGenerativeAI(
    model=llm_config.model,
    max_tokens=llm_config.react_max_tokens,
    temperature=llm_config.react_temperature,
).bind_tools(tools)
synthesizer_llm = ChatGoogleGenerativeAI(
    model=llm_config.model,
    max_tokens=llm_config.synthesizer_max_tokens,
    temperature=llm_config.synthesizer_temperature,
)
```

Because `LLMConfig` extends Pydantic `BaseSettings`, every field is overridable via environment
variable (`MODEL=gemini-2.0-flash`, `REACT_MAX_TOKENS=4096`, etc.) with no code change — the
right place for a production tuning knob.

---

## Response style

The assistant answers **to the point and well formatted** — this is part of the "feel fast" and
"plain English" goals, and it's a system-prompt rule for both the fast-lane template and the
synthesizer:

- **Lead with the answer.** Give the number or result first, then a short reason if it adds value —
  never a paragraph of preamble before the figure.
- **No filler.** Skip "Great question!", restating the question, and apologetic hedging. A simple
  lookup gets one or two sentences, not an essay.
- **Format for scanning.** Use markdown where it helps — **bold** the key figure, bullets for
  multiple items (e.g. a category breakdown or numbered cut-back suggestions), a compact table only
  when comparing rows. Money is always rendered with the user's `currency_display` (Module 04).
- **Match depth to the question.** Fast-lane answers stay terse; reasoning-lane answers may be
  longer but stay structured — short intro line, then bullets, no rambling.

This is enforced in the prompt, not the token cap — `max_tokens` bounds length, the style rules
bound *shape*.

---

## Streaming

`POST /chat` (Module 05) streams over **SSE**. Even when the assistant does real work, first tokens
arrive fast — the "feel fast" constraint. The fast lane's templated answers return almost
immediately; the ReAct path streams the synthesizer's narration as it's produced.

---

## Correctness eval

A small (~10-case) harness over the sample dataset asserts:

- tool outputs against **independently computed** answers (plain SQL/pandas) — proves the numbers
  are right;
- at least one **unanswerable** case (graceful decline) and one **ambiguous** case (sensible
  interpretation or a clarifying question);
- that the **router selects the right lane/tool** for a fixed set of prompts.

Runs in seconds; directly demonstrable to evaluators.

---

## Build vs. stub

| Item | Call |
|------|------|
| Router + fast lane + one ReAct agent | Fully working — the §7 headline signal |
| Shared service behind REST endpoint + tool | Fully working — the "build once, expose twice" pattern |
| Spending / budget / summary / temporal / memory tools | Fully working — core, high signal |
| Receipt: parse → confirm → write (REST + in-chat) | Working — Gemini vision; never blind-writes |
| Subscriptions & anomalies (event-driven recompute → tables, read-only feeds) | Working — basic heuristics, honest note |
| Cut-back suggestions | Working — SQL aggregation + LLM narration |
| Merchant lookup (web search) | Stub if time runs out — low priority, note in README |
| "Cannot answer" / injection-safe untrusted text | Fully working — cheap, directly tested by §5 |
| Correctness harness | Small (~10 cases) — proves numbers + routing |
| Supervisor + N specialist sub-agents | Skip — over-engineered for 6h; one ReAct agent suffices |
| LangGraph postgres checkpointer | Skip — chat history is the between-turn memory; note why |

---

## Done when

- [ ] A click-driven action (budget card, transactions, subscriptions/anomalies feed) returns with
      **zero** LLM calls.
- [ ] A natural-language single-intent lookup is answered on the **fast lane** with exactly one LLM
      call and a templated result (no second narration call).
- [ ] A multi-step / ambiguous request escalates to the **ReAct agent**, decomposes, gathers, and
      recovers from a failed step without being told to.
- [ ] Every §3 capability maps to exactly one lane, and the router picks it correctly in the harness.
- [ ] Receipt upload → extract → **confirm/edit** → record works end to end via both the REST path
      and an in-chat image, sharing `services/receipt.py`, with no checkpointer.
- [ ] Subscriptions & anomalies are read from precomputed tables, not scanned per request.
- [ ] The LLM never emits SQL; untrusted text is delimited and never treated as instructions.
- [ ] Unanswerable questions are declined gracefully; empty results are never narrated as "0."
- [ ] The correctness harness passes, including the unanswerable and ambiguous cases.
