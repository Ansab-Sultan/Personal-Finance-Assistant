# Module 03 — Budget Tracking

> **Goal:** A user can set a budget per category and period, and the system can report current spend
> against that budget and warn when they are close to or over the limit.
>
> **Depends on:** [01 Setup & Auth](./01-setup-and-auth.md), [02 Data Ingestion](./02-data-ingestion.md)
> (budget status compares against real spend).
>
> Brief mapping: **§3.6 Track a budget** — "let a user set a budget and have the assistant track it
> and warn when they are close to the limit."

This is a small, high-signal module: simple to build, and the assistant gets a clean tool out of it.

---

## Data

```sql
CREATE TYPE budget_period AS ENUM ('monthly', 'yearly');

budgets (
  id, user_id,
  category      transaction_category NOT NULL,   -- reuses the ENUM from Module 02
  limit_amount  NUMERIC(12,2)        NOT NULL,
  period        budget_period        NOT NULL DEFAULT 'monthly',
  created_at    TIMESTAMPTZ
)
-- unique(user_id, category, period)  → one budget per category per period type
-- e.g. a user can have BOTH a monthly AND yearly budget for 'travel'
```

---

## Backend

| File | Responsibility |
|------|----------------|
| `services/budget.py` | budget CRUD + **budget-status computation** (spend vs. limit) |
| `api/v1/budget.py` | CRUD endpoints for budgets |

### Budget status computation

The reusable piece (the assistant's `budget_tracker_tool` calls the same service):

```
status(category, period) →
  spent   = period spend for category:
              monthly → read from monthly_category_rollups for current month
              yearly  → SUM monthly_category_rollups for current calendar year (12 rows max)
  limit   = budgets.limit_amount
  ratio   = spent / limit
  state   = ok (<80%) | warning (80–100%) | over (>100%)
  →  { category, period, spent, limit, remaining, ratio, state }
```

- **Monthly** spend: single rollup row read — O(1).
- **Yearly** spend: SUM of up to 12 rollup rows for the current year — still O(1) in practice,
  never scans raw transactions.
- Read **spend from `monthly_category_rollups`** in both cases — stays cheap.
- Respects user preferences from [04 User Memory](./04-user-memory.md) (e.g. "don't count rent in
  food budget") when that module exists: exclusions are applied to the spend figure. Until then,
  compute the raw figure and leave a hook.
- The 80% warning threshold is a product decision — state it in the README.

---

## Frontend

- `app/(dashboard)/budgets/page.tsx` — set / view / edit budgets per category.
- `components/budget/BudgetCard.tsx` — shows spent / limit / remaining with an `ok|warning|over`
  visual state. **This card is a "structured UI action"** — it hits the API directly and never
  touches an LLM (the fast path from the main plan's constraints table).

---

## Edge cases

| Case | Handling |
|------|----------|
| Budget set for a category with no spend yet | `spent = 0`, `state = ok` — valid, not an error |
| Spend exists but no budget set | status returns "no budget for this category" — don't invent one |
| Category not in ENUM | rejected at the schema level — Postgres raises a type error before it hits the service |
| Mid-period budget change | status always reflects the current `limit_amount`; no historical recompute |
| User has both monthly AND yearly budget for same category | both are valid — return both statuses; the assistant surfaces whichever is most relevant to the question |
| Yearly budget queried in January | only 1 month of rollups exist — `spent` is accurate for what has elapsed, not fabricated |

---

## Build vs. stub

| Item | Call |
|------|------|
| Budget CRUD | Fully working — simple, high signal |
| Budget-status service | Fully working — reused by the assistant tool |
| Monthly period | Fully working |
| Yearly period | Fully working — SUM of rollup rows, stays cheap |
| Weekly / custom periods | Skip; ENUM is designed to extend, note in README |
| Preference-aware exclusions | Hook now, wire when Module 04 exists |

---

## Done when

- [ ] A user can create, read, update, delete a budget for a category.
- [ ] Both `monthly` and `yearly` periods work; yearly correctly sums rollup rows for the year.
- [ ] A user can hold both a monthly and yearly budget for the same category simultaneously.
- [ ] Budget status returns spent / limit / remaining / state, reading from rollups only.
- [ ] The 80% warning and over-limit states are correct against the sample data.
- [ ] Invalid category values are rejected at the DB level (ENUM constraint).
- [ ] All budget rows are `user_id`-scoped.
