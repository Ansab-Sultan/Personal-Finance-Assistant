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

> 🚧 **This module is under active design — do not implement yet.**
>
> The routing shape (single LangGraph agent vs. supervisor + sub-agent, where the escalation line
> sits, one heavy sub-agent vs. several specialists, and the model tiering) is being decided in
> discussion. This file is a stub so the module set is complete; it will be filled in once we lock
> the design.

---

## What is already settled (will not change)

These hold regardless of the final routing shape:

- **The LLM never writes SQL.** It fills typed tool parameters; each tool owns its parameterized
  query. (Injection-safe, no hallucinated columns.)
- **The tool set** — see the [main plan](../personal_finance_assistant_plan.md#tools):
  `spending_query`, `budget_tracker`, `user_memory`, `finance_summary`, `temporal_comparison`,
  `subscription_detector`, `anomaly_detector`, `receipt_ocr`, `cutback_suggestion`, `merchant_lookup`.
- **Large-context strategy** — the model never ingests raw transaction history; aggregation happens
  in SQL over `monthly_category_rollups`; chat history is summarized + windowed (Module 05).
- **Safety** — untrusted text (`raw_description`, OCR output) is delimited and labelled, never
  treated as instructions.
- **Tools reuse existing services** — e.g. `budget_tracker` calls Module 03's budget-status service;
  `user_memory` calls Module 04's service. The assistant is an orchestration layer, not a
  reimplementation.

---

## Open questions (being decided together)

1. **Single agent vs. supervisor + sub-agent.** Leaning supervisor (cheap router) + one heavy
   ReAct sub-agent + a deterministic fast lane — but not finalized.
2. **Escalation line** — when does the supervisor answer directly vs. hand off? (Proposed: >1 tool
   call or any reasoning over results → sub-agent.)
3. **One heavy sub-agent vs. several specialists** — leaning one, to avoid N-agent wiring in 6 hours.
4. **Model tiering** — cheap model for routing/narration, heavier model only on the hard path.

See the [main plan's LangGraph Agent Design section](../personal_finance_assistant_plan.md#langgraph-agent-design)
for the current draft of the flow, tools, and routing table.

---

## Cross-cutting (owned here, defined in the main plan)

- **Routing & model selection** — the §7 headline signal.
- **Multi-step / agentic reasoning with recovery** — failed/empty tool result → retry, replan, or
  degrade gracefully; "decide when it has enough."
- **"Cannot answer" / contradictions / bad receipts** — see *Handling the Unexpected* in the main plan.
- **Correctness eval** — the ~10-case harness asserts the assistant's tool outputs against
  independently computed answers.

---

## Done when (to be finalized with the design)

- [ ] _Routing design locked (open questions above resolved)._
- [ ] Simple lookups answered on the cheap/fast path; heavy reasoning only escalates when needed.
- [ ] Multi-step requests decompose, gather, and recover from a failed step without being told to.
- [ ] Receipt upload → extract → confirm → record works end to end.
- [ ] The correctness harness passes, including the unanswerable and ambiguous cases.
