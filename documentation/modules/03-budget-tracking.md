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
budgets (id, user_id, category, limit_amount, period, created_at)
-- period: enum 'monthly' (start with this) — extensible to weekly/custom later
-- unique(user_id, category, period)  → one budget per category per period
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
  spent   = current-period spend for category  (read from monthly_category_rollups)
  limit   = budgets.limit_amount
  ratio   = spent / limit
  state   = ok (<80%) | warning (80–100%) | over (>100%)
  →  { category, spent, limit, remaining, ratio, state }
```

- Read **spend from `monthly_category_rollups`**, not by scanning raw transactions — stays cheap.
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
| Category typo / unknown category | validate against the user's known categories on write |
| Mid-period budget change | status always reflects the current `limit_amount`; no historical recompute |

---

## Build vs. stub

| Item | Call |
|------|------|
| Budget CRUD | Fully working — simple, high signal |
| Budget-status service | Fully working — reused by the assistant tool |
| Monthly period | Fully working |
| Weekly / custom periods | Skip; design the `period` column to allow it, note in README |
| Preference-aware exclusions | Hook now, wire when Module 04 exists |

---

## Done when

- [ ] A user can create, read, update, delete a budget for a category.
- [ ] Budget status returns spent / limit / remaining / state, reading from rollups.
- [ ] The 80% warning and over-limit states are correct against the sample data.
- [ ] All budget rows are `user_id`-scoped.
