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
  id, user_id,
  role       message_role NOT NULL,
  content    TEXT         NOT NULL,
  created_at TIMESTAMPTZ
)
-- index (user_id, created_at)  → fast recent-history fetch, newest-first
```

- `system` is included in the ENUM even though system messages are not user-facing — they may be
  persisted for debugging/auditing the running summary. Only `user` and `assistant` rows are
  returned to the frontend.

*(Optional if multi-conversation is in scope: add a `conversations` table and `conversation_id`.
For 6 hours, a single rolling thread per user is fine — note the simplification.)*

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
        + last N raw turns                 (recent verbatim)
        + the new user message
```

- Keep the **last N turns verbatim** (recency matters most).
- Maintain a **running summary** of everything older — refresh it when the tail grows past a
  threshold. This caps context size (and cost) regardless of how long the conversation gets.
- Persist **both** the user message and the assistant reply after each turn.

> This is the chat-history half of the main plan's "Large Context Handling." The transaction-history
> half is solved separately by SQL + rollups (Module 02) — the model never ingests raw transactions.

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
| Running summary of old turns | Working; if time-boxed, cap to last-N only and note it |
| Multiple named conversations | Skip — single rolling thread per user, note in README |

---

## Done when

- [ ] Every user/assistant turn is persisted and `user_id`-scoped.
- [ ] A new message is answered with prior context available (the assistant "remembers" the thread).
- [ ] Responses stream token-by-token over SSE.
- [ ] A long conversation does not grow context unbounded (summary + window in effect).
