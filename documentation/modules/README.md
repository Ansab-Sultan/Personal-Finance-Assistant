# Modules — Build Order

This folder breaks the [project plan](../personal_finance_assistant_plan.md) into modules you build
in sequence. Each module is self-contained: a goal, what it touches (DB / backend / frontend), an
implementation checklist, the edge cases it owns, what to build vs. stub, and a "done when" bar.

**The Assistant is deliberately last** — every other module produces the data and endpoints it
orchestrates, and its routing shape is still being designed.

## Order & dependencies

| # | Module | Depends on | Brief mapping |
|---|--------|-----------|---------------|
| 01 | [Setup & Authentication (Clerk)](./01-setup-and-auth.md) | — | §2 Accounts & sign-in, multi-user |
| 02 | [Data Ingestion & Transaction CRUD](./02-data-ingestion.md) | 01 | §2 Financial data; §5 dirty data; transaction CRUD |
| 03 | [Budget Tracking](./03-budget-tracking.md) | 01, 02 | §3.6 Track a budget |
| 04 | [User Memory / Preferences](./04-user-memory.md) | 01 | §3.10 Remember user context |
| 05 | [Chat History](./05-chat-history.md) | 01 | §2 conversational assistant (persistence) |
| 06 | [Assistant (LangGraph)](./06-assistant.md) | 01–05 | §3 all capabilities — **routing under design** |

```
01 Setup & Auth
   ├── 02 Data Ingestion ──┐
   ├── 03 Budget Tracking ─┤  (03 also reads 02's transactions/rollups)
   ├── 04 User Memory ─────┤
   └── 05 Chat History ────┤
                           └──► 06 Assistant (orchestrates all of the above)
```

## How to read a module doc

Each file has the same shape:

- **Goal** — one sentence.
- **Depends on** — modules that must exist first.
- **Data** — DB models/columns this module owns or adds.
- **Backend** — services + endpoints.
- **Frontend** — pages + components.
- **Edge cases** — the slice of brief §5 this module is responsible for.
- **Build vs. stub** — honest scoping for the 6-hour budget.
- **Done when** — the acceptance bar before moving on.

Shared cross-cutting concerns (safety/prompt-injection, correctness eval, large-context strategy)
live in the [main plan](../personal_finance_assistant_plan.md) and are referenced where relevant.
