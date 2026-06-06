# Module 04 — User Memory / Preferences

> **Goal:** Persist stated user context ("I get paid on the 1st", "don't count rent in my food
> budget") and apply it automatically later, without the user repeating themselves.
>
> **Depends on:** [01 Setup & Auth](./01-setup-and-auth.md).
>
> Brief mapping: **§3.10 Remember user context** — the evaluators will test this explicitly. It's
> small, but a visible "it remembered" moment is high signal.

---

## Data

```sql
user_preferences (id, user_id, key, value, updated_at)
-- unique(user_id, key)  → upsert on write
```

A flat key-value store is deliberate: it's open-ended (the user can state anything) and trivial to
read on each request. Examples:

| key | value | meaning |
|-----|-------|---------|
| `pay_date` | `"1"` | gets paid on the 1st → drives "this pay cycle" framing |
| `exclude_from_food` | `"rent"` | exclude rent from the food budget figure |
| `currency_display` | `"PKR"` | how to format money back to the user |

> Keep keys to a **small known vocabulary** the assistant writes to (not free-form per message), so
> reads are predictable and applying them is deterministic. Document the vocabulary.

---

## Backend

| File | Responsibility |
|------|----------------|
| `services/memory.py` | read all prefs for a user; upsert a pref; delete a pref |
| `api/v1/users.py` | `GET/PATCH` profile + preferences |

- **Read path:** preferences are fetched from the DB on each assistant request (cheap, indexed by
  `user_id`) and injected into context — **never** stored in the LLM context across turns.
- **Write path:** the assistant's `user_memory_tool` calls `services/memory.py` to persist a stated
  preference. Writing is a first-class action, not a side effect of chatting.

---

## How other modules consume it

- **[03 Budget Tracking](./03-budget-tracking.md):** `exclude_from_food: rent` removes rent from the
  food spend figure before comparing to the limit.
- **Assistant (06):** `pay_date` reframes "this month" as "this pay cycle"; `currency_display`
  formats output. Preferences are part of the prompt context the assistant always has.

---

## Edge cases

| Case | Handling |
|------|----------|
| Conflicting preferences stated over time | upsert by `key` → latest wins; surface the change ("got it, updating that") |
| Vague preference ("I don't spend much on coffee") | only persist if it maps to a known key; otherwise acknowledge without storing junk |
| Preference references unknown category | validate against the user's categories before storing |
| User asks "what do you know about me?" | read back the stored preferences in plain English |

---

## Build vs. stub

| Item | Call |
|------|------|
| KV store + read/upsert/delete | Fully working — explicitly tested |
| Known-key vocabulary + validation | Fully working — keeps application deterministic |
| Apply `exclude_from_food` in budget/spend | Working — concrete, demonstrable |
| Free-form semantic memory / embeddings | Skip — over-engineered for 6 hours, note in README |

---

## Done when

- [ ] Stating a preference in chat persists it (assistant → `user_memory_tool` → DB).
- [ ] A later query reflects it without the user restating it (e.g. food spend excludes rent).
- [ ] "What do you know about me?" reads the preferences back.
- [ ] All preferences are `user_id`-scoped.
