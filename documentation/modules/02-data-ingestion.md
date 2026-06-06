# Module 02 — Data Ingestion & Transaction CRUD

> **Goal:** Get a user's transaction history into one clean, deduplicated `transactions` table —
> from a CSV upload, the mock bank endpoint, *and* manual entry — give the user **full CRUD** over
> individual transactions, and keep the `monthly_category_rollups` table consistent on every change
> so later queries stay cheap at scale.
>
> **Depends on:** [01 Setup & Auth](./01-setup-and-auth.md) (needs `user_id` + DB).

This is the data path the entire assistant reads from. If ingestion is sloppy, every answer is
wrong. It is also where brief **§5 "dirty data"** is handled.

---

## Data

```sql
-- ENUMs (defined once, reused across tables)
CREATE TYPE transaction_source   AS ENUM ('csv', 'bank_api', 'manual', 'receipt');
CREATE TYPE transaction_category AS ENUM (
  'groceries', 'restaurants', 'transport', 'fuel',
  'utilities', 'rent', 'health', 'entertainment',
  'shopping', 'subscriptions', 'travel', 'education',
  'income', 'transfer', 'uncategorized'
);

transactions (
  id, user_id,
  date          DATE,
  amount        NUMERIC(12,2),
  currency      VARCHAR(3),          -- ISO 4217; CHECK (currency ~ '^[A-Z]{3}$')
  merchant      TEXT,
  raw_description TEXT,
  category      transaction_category NOT NULL DEFAULT 'uncategorized',
  source        transaction_source   NOT NULL,
  hash          TEXT,
  created_at    TIMESTAMPTZ
)
monthly_category_rollups (id, user_id, month, category transaction_category, total_amount, txn_count, updated_at)

-- indexes
transactions:  (user_id, date), (user_id, category, date), unique(user_id, hash)
rollups:       unique(user_id, month, category)
```

- `hash` = SHA256(user_id + date + amount + merchant) → **unique constraint** makes re-ingesting the
  same file idempotent.
- `source` — ENUM: `csv | bank_api | manual | receipt`. System-set, never client-supplied.
- `category` — ENUM of 15 canonical categories + `uncategorized`. Unknown/unmapped input → `uncategorized`
  (never dropped). Adding a new category requires an Alembic migration — document this as a scoping
  decision; user-defined categories are a future feature.
- `currency` — VARCHAR(3) with a CHECK constraint (`^[A-Z]{3}$`). Not a Postgres ENUM because
  ISO 4217 has ~170 currencies; a CHECK is the right level of validation here. Stored as-is, never
  converted.
- `raw_description` = original untrusted string, kept separate from cleaned `merchant`
  (see Safety & Data Trust in the main plan).

---

## Backend

| File | Responsibility |
|------|----------------|
| `services/ingestion.py` | CSV parser + mock-bank fetcher → raw rows |
| `services/normalizer.py` | raw rows → normalized `Transaction` schema (one shape for both sources) |
| `services/deduplication.py` | compute `hash`, drop exact dupes before insert |
| `services/tasks.py` | ARQ tasks: `process_csv_upload`, `fetch_mock_bank_data_task`, `recompute_detections_task` |
| `services/transactions.py` | single-row CRUD + **rollup sync** (recompute affected month/category buckets) |
| `api/v1/transactions.py` | ingestion (`POST /upload-csv`) + full transaction CRUD (see below) |

### Flow

```
CSV file / bank fetch
   → parse              (tolerant: skip junk rows, don't crash the batch)
   → normalize          (dates, amounts, sign convention, category mapping)
   → dedup (hash)       (exact dupes dropped; unique constraint is the backstop)
   → bulk insert
   → rollup sync + subscription/anomaly detect  (inline within the ARQ ingest job, once per batch)
```

CSV upload returns fast: accept the file, enqueue `process_csv_upload` (ARQ), respond
`202 Accepted` with a job/status reference. A multi-year file must not block the HTTP response.

> **Detection placement.** Subscription/anomaly recompute runs **once per batch inside the ingest
> job** here (already off the request path). Single-row CRUD instead enqueues a separate
> `recompute_detections_task` after commit, so a one-row write never blocks on a full rescan. It's
> event-driven, not a cron — see [06 Assistant](./06-assistant.md#subscriptions--anomalies--precomputed-read-only-at-query-time).

### Normalization decisions (write these in the README)

- **Date formats** — accept a few common ones; unparseable date → row quarantined, not guessed.
- **Amount sign** — pick one convention (e.g. expenses negative) and coerce both sources to it.
- **Category** — map provided categories to a canonical set; unknown → `"uncategorized"`
  (never silently dropped).
- **Both sources land in the same schema** — the assistant never knows or cares where a row came from.

---

## Transaction CRUD

Beyond bulk ingestion, the user has full control over individual transactions — to fix an OCR
mistake, remove a slipped-through duplicate, or add a cash expense the bank never saw.

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/transactions` | Create one transaction manually (`source = "manual"`) |
| `GET` | `/transactions` | List — paginated + filterable (date range, category), `user_id`-scoped |
| `GET` | `/transactions/{id}` | Read one |
| `PATCH` | `/transactions/{id}` | Update fields (amount, date, category, merchant, …) |
| `DELETE` | `/transactions/{id}` | Delete one |

All routes go through `get_current_user`; every query is filtered by `user_id`, and `{id}` is
verified to belong to the caller. A user can never touch another user's row — return **404, not
403**, so you don't leak whether the id exists.

### Keeping rollups consistent (the part that matters)

Manual mutations must not let `monthly_category_rollups` drift, or every later answer goes wrong.
Each single-row change updates only the affected bucket(s) — cheap and exact, no full rebuild:

- **Create** → increment the `(user_id, month, category)` bucket by the amount; `txn_count += 1`.
- **Delete** → decrement that bucket; `txn_count -= 1`.
- **Update** → if `amount`, `date` (month), or `category` changed, **decrement the old bucket and
  increment the new one** (they may be the same). Edits to other fields don't touch rollups.

`services/transactions.py` owns this so an endpoint can't forget it, and it runs in the **same DB
transaction** as the row change so a row and its rollup never disagree.

### Manual create vs. the dedup constraint

A manually entered transaction still gets a `hash` and `source = "manual"`. If it collides with the
`unique(user_id, hash)` constraint (same date + amount + merchant as an existing row — e.g. two
identical coffees), **don't silently swallow it**: return `409 Conflict` with the existing row so the
UI can ask *"looks like a duplicate — add anyway?"* and, on confirm, insert with a tie-breaker. This
matches the module's reconciliation philosophy: surface conflicts, don't guess.

---

## Edge cases (brief §5 — this module owns the data half)

| Messy input | Handling |
|-------------|----------|
| Duplicate rows | `hash` + unique constraint; idempotent re-upload |
| Missing fields | required-field check; partial rows quarantined with a reason, not inserted blind |
| Malformed dates / amounts | tolerant parse; unparseable → quarantine, surfaced in upload summary |
| Junk rows / bad encoding | skip-and-count; one bad row never fails the whole file |
| **Cross-source duplicates** | same purchase from CSV *and* bank: exact dupes caught by hash; **near-dupes** (same amount+merchant within ±2 days, different `source`) flagged as *suspected duplicate*, prefer bank source, note the assumption |
| Manual entry duplicates an existing row | `409 Conflict` + the existing row returned; user confirms to add with a tie-breaker (see Transaction CRUD) |
| Edit / delete drifting the rollups | bucket-level rollup sync inside the same DB transaction (see Transaction CRUD) |

The upload response includes a summary: `{inserted, duplicates_skipped, quarantined, suspected_dupes}`
— honesty over a silent "success."

---

## Frontend

- `app/(dashboard)/transactions/page.tsx` — transaction list (paginated, server-fetched).
- `components/transactions/CsvUploader.tsx` — drag/drop upload → shows the ingestion summary.
- `components/transactions/TransactionTable.tsx` — list with date/category/amount + **row actions
  (edit / delete)**.
- `components/transactions/TransactionForm.tsx` — add/edit a single transaction (used for both
  manual create and `PATCH`), with the duplicate-confirm prompt on `409`.

Keep it functional, not fancy — this is a data surface, not the headline feature. Optimistic UI on
edit/delete is fine; reconcile against the API response.

---

## Scale note (why rollups live here)

`refresh_monthly_rollups` runs after every ingest and maintains per-user, per-month, per-category
totals. Multi-month / multi-year questions later read a few hundred rollup rows instead of scanning
millions of raw transactions — this is the module that makes "holds up at 10×–100× data" true.
Raw rows are only read for drill-downs.

---

## Build vs. stub

| Item | Call |
|------|------|
| CSV parse + normalize + dedup + store | Fully working — core data path |
| Mock bank fetch → same schema | Fully working |
| **Transaction CRUD (create / read / update / delete)** | Fully working — the user controls their own data |
| **Rollup sync on single-row CRUD** | Fully working — correctness of every later answer depends on it |
| Rollup refresh (ARQ) | Fully working — the scale story |
| Async upload via ARQ | Working; if time-boxed, process inline and note it |
| Near-duplicate reconciliation | Basic heuristic, documented |
| Manual-duplicate `409` confirm flow | Working; if time-boxed, just block with a clear error and note it |
| Quarantine review UI | Skip — return counts in the API response, note in README |

---

## Done when

- [ ] A sample CSV ingests; duplicates are dropped; junk rows are skipped without failing the batch.
- [ ] Re-uploading the same CSV inserts nothing new (idempotent).
- [ ] Mock bank data lands in the same `transactions` shape.
- [ ] A user can create, read, update, and delete an individual transaction.
- [ ] Editing or deleting a transaction keeps `monthly_category_rollups` correct (bucket sync).
- [ ] A user cannot read or mutate another user's transaction (404 on a foreign `{id}`).
- [ ] `monthly_category_rollups` reflects ingested data and refreshes after new ingests.
- [ ] `GET /transactions` is paginated, filterable, and `user_id`-scoped.
