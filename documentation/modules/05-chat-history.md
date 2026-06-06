# Module 05 — Chat History

> **Goal:** Persist every conversation turn per user, and feed prior context to the assistant on
> each new message — summarized when the history gets long, so context never blows up.
>
> **Depends on:** [01 Setup & Auth](./01-setup-and-auth.md).
>
> This module is the assistant's short-term memory. It's separate from [04 User Memory](./04-user-memory.md):
> Module 04 stores **durable facts** ("I get paid on the 1st"); this stores the **conversation**.

---

## Data

```sql
CREATE TYPE message_role AS ENUM ('user', 'assistant', 'system');

chat_messages (
  id           UUID PRIMARY KEY,
  user_id      TEXT         NOT NULL,
  role         message_role NOT NULL,
  content      TEXT         NOT NULL,
  is_summarized BOOLEAN     NOT NULL DEFAULT FALSE,  -- TRUE once this turn is folded into the summary
  created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
)
-- index (user_id, created_at)         → fast recent-history fetch, newest-first
-- index (user_id, is_summarized)      → fast count of unsummarized turns
```

- `system` rows hold the **running summary** — one row per user, overwritten each time the summary
  is refreshed. Only `user` and `assistant` rows are returned to the frontend.
- `is_summarized = TRUE` marks turns that have already been folded into the summary row — they are
  never sent verbatim to the LLM again.

*(Single rolling thread per user — no `conversations` table. Note the simplification in README.)*

---

## Backend

| File | Responsibility |
|------|----------------|
| `schemas/chat.py` | `ChatMessage`, `ChatRequest`, `ChatResponse` |
| `api/v1/chat.py` | `POST /chat` (SSE streaming response) + persists both turns |

### Context strategy (the part that matters at scale)

Never send the entire history to the model. On each new message:

```
context = system prompt
        + user preferences (from Module 04)
        + running summary of older turns   (if history is long)
        + last N raw turns verbatim        (recency matters most)
        + the new user message
```

#### Constants

```python
RECENT_TURNS       = 20   # always sent verbatim; never summarized away
SUMMARIZE_THRESHOLD = 40  # trigger a summary refresh when unsummarized turns exceed this
```

#### Summarization trigger (runs before the main agent call)

```python
async def maybe_refresh_summary(user_id: str, db: AsyncSession) -> str | None:
    unsummarized_count = await count_unsummarized(user_id, db)

    if unsummarized_count <= SUMMARIZE_THRESHOLD:
        return await get_existing_summary(user_id, db)  # None if first time

    # turns to fold in = all unsummarized EXCEPT the most recent RECENT_TURNS
    old_turns = await get_turns_to_summarize(user_id, exclude_recent=RECENT_TURNS, db=db)
    existing  = await get_existing_summary(user_id, db) or ""

    new_summary = await llm.summarize(existing, old_turns)  # cheap, short prompt

    await upsert_summary_row(user_id, new_summary, db)       # role='system', overwrites previous
    await mark_as_summarized(old_turns, db)                  # is_summarized = TRUE

    return new_summary
```

- The summarization call is a **separate LLM call with a short compression prompt** — it runs
  once per threshold crossing, not on every message.
- `upsert_summary_row` keeps exactly one `role='system'` row per user — no accumulation.
- `mark_as_summarized` sets `is_summarized = TRUE` on the folded turns — they are never sent
  verbatim again, but remain in the DB for audit/debugging.

#### Building context for the agent

```python
summary  = await maybe_refresh_summary(user_id, db)
recent   = await get_last_n_turns(user_id, n=RECENT_TURNS, db=db)

context_messages = [system_prompt]
if summary:
    context_messages.append({"role": "system", "content": f"Summary of earlier conversation:\n{summary}"})
context_messages += recent          # verbatim last-N turns
context_messages.append(new_message)
```

- Persist **both** the user message and the assistant reply after each turn.
- On the very first message: no summary exists, no recent turns — just system prompt + preferences
  + message. No special case needed; the code handles it naturally.

> This is the chat-history half of the main plan's "Large Context Handling." The transaction-history
> half is solved by SQL + rollups (Module 02) — the model never ingests raw transactions.

---

## Streaming

`POST /chat` streams the response over **SSE**. Even when the assistant does real work, first tokens
arrive fast — this is the "feel fast" constraint from the brief. The frontend renders tokens as they
arrive.

---

## Frontend

- `app/(dashboard)/chat/page.tsx` — main chat UI with message history.
- `components/chat/ChatWindow.tsx`, `MessageBubble.tsx` — render the streamed thread.
- `components/chat/ReceiptUpload.tsx` — image upload into the chat (consumed by the assistant's
  receipt tool in Module 06).
- `lib/hooks/useChat.ts` — manages the SSE stream + optimistic user message.

---

## Edge cases

| Case | Handling |
|------|----------|
| Very long history | running summary + last-N window; context size stays bounded |
| First message (empty history) | summary section omitted; just system + prefs + message |
| Streaming connection drops | persist the user turn immediately; reconcile/retry the assistant turn |
| Empty / whitespace message | reject client-side and server-side |

---

## Build vs. stub

| Item | Call |
|------|------|
| Persist turns + recent-window fetch | Fully working — assistant depends on it |
| SSE streaming | Working — directly serves the "fast" constraint |
| `is_summarized` column + summary row schema | Fully working — schema is the foundation |
| Summarization trigger + `maybe_refresh_summary` | Fully working — ~30 lines, high evaluator signal |
| Multiple named conversations | Skip — single rolling thread per user, note in README |

---

## Done when

- [ ] Every user/assistant turn is persisted and `user_id`-scoped.
- [ ] A new message is answered with prior context available (the assistant "remembers" the thread).
- [ ] Responses stream token-by-token over SSE.
- [ ] A long conversation does not grow context unbounded — summary triggers when unsummarized turns exceed `SUMMARIZE_THRESHOLD`.
- [ ] The summary row is a single `role='system'` row per user, overwritten on each refresh.
- [ ] Summarized turns are marked `is_summarized = TRUE` and never re-sent verbatim.
- [ ] First message works with no summary and no history (no special case needed).
