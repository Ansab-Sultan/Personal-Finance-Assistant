# Module 02 — Data Ingestion

> **Goal:** Get a user's transaction history into one clean, deduplicated `transactions` table —
> from both a CSV upload and the mock bank endpoint — and keep the `monthly_category_rollups` table
> current so later queries stay cheap at scale.
>
> **Depends on:** [01 Setup & Auth](./01-setup-and-auth.md) (needs `user_id` + DB).

This is the data path the entire assistant reads from. If ingestion is sloppy, every answer is
wrong. It is also where brief **§5 "dirty data"** is handled.

---

## Data

```sql
transactions (
  id, user_id, date, amount, currency, merchant, raw_description,
  category, source, hash, created_at
)
monthly_category_rollups (id, user_id, month, category, total_amount, txn_count, updated_at)

-- indexes
transactions:  (user_id, date), (user_id, category, date), unique(user_id, hash)
rollups:       unique(user_id, month, category)
```

- `hash` = SHA256(user_id + date + amount + merchant) → **unique constraint** makes re-ingesting the
  same file idempotent.
- `source` = `"csv"` | `"bank_api"` — for auditability and cross-source reconciliation.
- `raw_description` = original untrusted string, kept separate from cleaned `merchant`
  (see Safety & Data Trust in the main plan).
- `currency` stored as-is, never converted.

---

## Backend

| File | Responsibility |
|------|----------------|
| `services/ingestion.py` | CSV parser + mock-bank fetcher → raw rows |
| `services/normalizer.py` | raw rows → normalized `Transaction` schema (one shape for both sources) |
| `services/deduplication.py` | compute `hash`, drop exact dupes before insert |
| `services/tasks.py` | ARQ tasks: `process_csv_upload`, `fetch_mock_bank_data`, `refresh_monthly_rollups` |
| `api/v1/transactions.py` | `POST /upload-csv`, `GET /transactions` (paginated) |

### Flow

```
CSV file / bank fetch
   → parse              (tolerant: skip junk rows, don't crash the batch)
   → normalize          (dates, amounts, sign convention, category mapping)
   → dedup (hash)       (exact dupes dropped; unique constraint is the backstop)
   → bulk insert
   → refresh_monthly_rollups  (ARQ, after insert)
```

CSV upload returns fast: accept the file, enqueue `process_csv_upload` (ARQ), respond
`202 Accepted` with a job/status reference. A multi-year file must not block the HTTP response.

### Normalization decisions (write these in the README)

- **Date formats** — accept a few common ones; unparseable date → row quarantined, not guessed.
- **Amount sign** — pick one convention (e.g. expenses negative) and coerce both sources to it.
- **Category** — map provided categories to a canonical set; unknown → `"uncategorized"`
  (never silently dropped).
- **Both sources land in the same schema** — the assistant never knows or cares where a row came from.

---

## Edge cases (brief §5 — this module owns the data half)

| Messy input | Handling |
|-------------|----------|
| Duplicate rows | `hash` + unique constraint; idempotent re-upload |
| Missing fields | required-field check; partial rows quarantined with a reason, not inserted blind |
| Malformed dates / amounts | tolerant parse; unparseable → quarantine, surfaced in upload summary |
| Junk rows / bad encoding | skip-and-count; one bad row never fails the whole file |
| **Cross-source duplicates** | same purchase from CSV *and* bank: exact dupes caught by hash; **near-dupes** (same amount+merchant within ±2 days, different `source`) flagged as *suspected duplicate*, prefer bank source, note the assumption |

The upload response includes a summary: `{inserted, duplicates_skipped, quarantined, suspected_dupes}`
— honesty over a silent "success."

---

## Frontend

- `app/(dashboard)/transactions/page.tsx` — transaction list (paginated, server-fetched).
- `components/transactions/CsvUploader.tsx` — drag/drop upload → shows the ingestion summary.
- `components/transactions/TransactionTable.tsx` — list with date/category/amount.

Keep it functional, not fancy — this is a data surface, not the headline feature.

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
| Rollup refresh (ARQ) | Fully working — the scale story |
| Async upload via ARQ | Working; if time-boxed, process inline and note it |
| Near-duplicate reconciliation | Basic heuristic, documented |
| Quarantine review UI | Skip — return counts in the API response, note in README |

---

## Done when

- [ ] A sample CSV ingests; duplicates are dropped; junk rows are skipped without failing the batch.
- [ ] Re-uploading the same CSV inserts nothing new (idempotent).
- [ ] Mock bank data lands in the same `transactions` shape.
- [ ] `monthly_category_rollups` reflects the ingested data and refreshes after new ingests.
- [ ] `GET /transactions` is paginated and `user_id`-scoped.
