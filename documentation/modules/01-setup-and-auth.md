# Module 01 — Setup & Authentication (Clerk)

> **Goal:** A running monorepo (FastAPI + Next.js) where a user can sign up, sign in, and every
> backend request is tied to a verified `user_id`. This is the foundation every other module
> stands on — get data isolation right here, once.
>
> **Depends on:** nothing. Build this first.
>
> Clerk is **commodity work** — do not build auth yourself. Spend the saved time on the assistant.

---

## Scope

Two things:

1. **Setup** — repo layout, environment config, Postgres + Redis, FastAPI skeleton, Next.js skeleton.
2. **Clerk** — sign-up / sign-in on the frontend, token verification on the backend, webhook sync
   of users into our own DB, and **multi-tenancy enforced at the query level**.

> Clerk is already installed in the Next.js app. This module still documents the full wiring so the
> frontend and backend halves line up and nothing is assumed.

---

## Infrastructure

| Service | Local | Managed option |
|---------|-------|----------------|
| Postgres | `docker compose` (postgres:16) | Neon / Supabase Postgres |
| Redis | `docker compose` (redis:7) | Upstash |
| Clerk | — | Clerk dashboard (hosted) |

A minimal `docker-compose.yml` with `postgres` + `redis` is enough for local dev. Managed services
are a fine call for the submission — note whichever you pick in the README.

### Environment variables

**Backend (`.env`)**
```
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/finance
REDIS_URL=redis://localhost:6379/0
CLERK_SECRET_KEY=sk_test_...
CLERK_WEBHOOK_SIGNING_SECRET=whsec_...      # from Clerk dashboard → Webhooks
CLERK_AUTHORIZED_PARTIES=http://localhost:3000
GEMINI_API_KEY=...                          # used later by the assistant
```

**Frontend (`.env.local`)**
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
```

All backend env vars are loaded once via `core/config.py` (pydantic-settings). Nothing reads
`os.environ` directly.

---

## Backend skeleton (FastAPI)

Build the `core/` package first — it is shared by every later module:

| File | Responsibility |
|------|----------------|
| `core/config.py` | `Settings(BaseSettings)` — all env vars in one typed object |
| `core/database.py` | async SQLAlchemy engine + `async_session` factory |
| `core/dependencies.py` | `get_db`, `get_current_user` |
| `core/security.py` | Clerk token verification |
| `core/exceptions.py` | global exception handlers (auth errors → 401, validation → 422) |
| `main.py` | app factory, CORS (allow the frontend origin), router registration |

Use **async SQLAlchemy + asyncpg** and **Alembic** for migrations (the `users` table ships in this
module's first migration).

---

## Clerk — Frontend (Next.js App Router)

Clerk's middleware API is `clerkMiddleware()` + `createRouteMatcher` (the older `authMiddleware`
is deprecated — do not use it).

**1. Wrap the app** — `app/layout.tsx`:
```tsx
import { ClerkProvider } from '@clerk/nextjs'

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ClerkProvider>{children}</ClerkProvider>
      </body>
    </html>
  )
}
```

**2. Protect routes** — `middleware.ts` at the project root. Everything is private *except*
sign-in / sign-up:
```tsx
import { clerkMiddleware, createRouteMatcher } from '@clerk/nextjs/server'

const isPublicRoute = createRouteMatcher(['/sign-in(.*)', '/sign-up(.*)'])

export default clerkMiddleware(async (auth, req) => {
  if (!isPublicRoute(req)) {
    await auth.protect()
  }
})

export const config = {
  matcher: [
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    '/(api|trpc)(.*)',
  ],
}
```

**3. Sign-in / sign-up pages** — catch-all routes already scaffolded:
`app/(auth)/sign-in/[[...sign-in]]/page.tsx` → `<SignIn />`, and the matching `<SignUp />`.

**4. Call the backend with the session token.** The frontend never sends a raw `user_id` — it
sends the Clerk session token; the backend derives the user from it.
```tsx
// client component
import { useAuth } from '@clerk/nextjs'

const { getToken } = useAuth()
const token = await getToken()
await fetch(`${process.env.NEXT_PUBLIC_BACKEND_URL}/api/v1/transactions`, {
  headers: { Authorization: `Bearer ${token}` },
})
```
(Server components / route handlers use `auth()` from `@clerk/nextjs/server` and `getToken()` there.)

---

## Clerk — Backend (FastAPI verification)

Install `clerk-backend-api`. Verify the incoming session token with `authenticate_request`, which
does **networkless** verification and returns the JWT payload (its `sub` claim is the Clerk user id).

`core/security.py`:
```python
import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from core.config import settings

clerk = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)

def verify_clerk_token(request: httpx.Request):
    state = clerk.authenticate_request(
        request,
        AuthenticateRequestOptions(
            authorized_parties=settings.CLERK_AUTHORIZED_PARTIES,  # e.g. ["http://localhost:3000"]
        ),
    )
    return state  # state.is_signed_in, state.payload (claims incl. "sub")
```

`core/dependencies.py` — turn that into the `get_current_user` dependency every protected route uses:
```python
from fastapi import Depends, HTTPException, Request
import httpx

async def get_current_user(request: Request) -> str:
    # rebuild an httpx.Request from the incoming headers for the Clerk SDK
    httpx_req = httpx.Request(method=request.method, url=str(request.url),
                              headers=request.headers.raw)
    state = verify_clerk_token(httpx_req)
    if not state.is_signed_in:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return state.payload["sub"]  # Clerk user id → maps to users.clerk_id
```

> **Rule:** `user_id` always comes from this verified token. It is **never** read from a request
> body, query param, or header the client controls. This single rule is the multi-tenancy boundary.

---

## Webhook sync (users into our DB)

Clerk owns identity; we keep a thin `users` row for foreign keys and cascade deletes. Sync on
`user.created` and `user.deleted`.

**Recommended:** receive the webhook **directly on FastAPI** and verify the Svix signature with the
`svix` Python package + `CLERK_WEBHOOK_SIGNING_SECRET` — one less hop than bouncing through Next.js.
Endpoint: `POST /api/v1/auth/webhook` (mark it public — no `get_current_user`).

- `user.created` → upsert `users(clerk_id, email)`
- `user.deleted` → delete the `users` row; `ON DELETE CASCADE` removes their transactions, budgets,
  chat, preferences (data isolation includes the right to be forgotten)

> The plan's structure also lists a Next.js `app/api/webhooks/clerk/route.ts`. If you route through
> the frontend instead, verify with `verifyWebhook` from `@clerk/nextjs/webhooks` and forward the
> event to the backend. Pick **one** path and document it — don't wire both.

---

## Data

```sql
users (id, clerk_id UNIQUE, email, created_at)
```
Other tables reference `users.id` with `ON DELETE CASCADE`. Ships in this module's first Alembic
migration.

---

## Multi-tenancy enforcement

- Every query in every later module is filtered by the `user_id` from `get_current_user`.
- Centralize it: a small helper / base query pattern that injects `WHERE user_id = :uid` so an
  individual endpoint can't forget it.
- *(Optional, defense-in-depth, mention-in-README-if-skipped):* Postgres Row-Level Security.

---

## Build vs. stub

| Item | Call |
|------|------|
| Clerk sign-in/up, session, token verify | Fully working — commodity |
| `get_current_user` dependency | Fully working — it's the security boundary |
| Webhook user sync | Working (created + deleted) |
| Row-Level Security | Skip; enforce at query level, note in README |
| docker-compose vs managed services | Either; document the choice |

---

## Done when

- [ ] A new user can sign up and sign in via Clerk on the frontend.
- [ ] A protected backend route returns 401 without a token and the correct `user_id` with one.
- [ ] `user.created` lands a row in `users`; `user.deleted` removes it.
- [ ] No endpoint trusts a client-supplied `user_id`.
- [ ] One Alembic migration creates `users`; `core/` package is in place for later modules.
