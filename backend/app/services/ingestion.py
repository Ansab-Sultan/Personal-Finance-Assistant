import csv
import io
import uuid
from datetime import date
from typing import Any, Dict, List, Tuple, Set
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.transaction import Transaction
from app.services.normalizer import normalize_transaction_data, parse_date, parse_amount
from app.services.deduplication import compute_transaction_hash, find_existing_hashes, find_near_duplicates
from app.services.transactions import create_transaction, refresh_monthly_rollups, get_month_str

async def parse_csv_stream(csv_content: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parse CSV text content, returning normalized rows and quarantined rows."""
    normalized_rows = []
    quarantined_rows = []
    
    f = io.StringIO(csv_content)
    reader = csv.DictReader(f)
    
    if not reader.fieldnames:
        raise ValueError("CSV file has no headers")
        
    field_map = {}
    for col in reader.fieldnames:
        col_lower = col.strip().lower()
        if "date" in col_lower:
            field_map["date"] = col
        elif "amount" in col_lower or "value" in col_lower:
            field_map["amount"] = col
        elif "merchant" in col_lower or "payee" in col_lower:
            field_map["merchant"] = col
        elif "description" in col_lower or "memo" in col_lower:
            field_map["description"] = col
        elif "category" in col_lower:
            field_map["category"] = col
        elif "currency" in col_lower:
            field_map["currency"] = col

    for row_idx, row in enumerate(reader, start=1):
        try:
            raw_date = row.get(field_map.get("date", "date"))
            raw_amount = row.get(field_map.get("amount", "amount"))
            raw_merchant = row.get(field_map.get("merchant", "merchant"))
            raw_desc = row.get(field_map.get("description", "description"))
            raw_category = row.get(field_map.get("category", "category"))
            raw_currency = row.get(field_map.get("currency", "currency"))
            
            if not raw_date or not raw_amount:
                raise ValueError("Missing required fields: date or amount")
                
            raw_record = {
                "date": raw_date,
                "amount": raw_amount,
                "merchant": raw_merchant or "",
                "description": raw_desc or "",
                "category": raw_category or "",
                "currency": raw_currency or "USD"
            }
            
            normalized = normalize_transaction_data(raw_record, source="csv")
            normalized_rows.append(normalized)
            
        except Exception as exc:
            quarantined_rows.append({
                "row_number": row_idx,
                "raw_data": row,
                "reason": str(exc)
            })
            
    return normalized_rows, quarantined_rows

async def fetch_mock_bank_data() -> List[Dict[str, Any]]:
    """Fetch transactions from a simulated mock bank endpoint."""
    return [
        {
            "date": "2026-06-01",
            "amount": "-1500.00",
            "merchant": "Apartment Rental",
            "description": "Monthly rent payment",
            "category": "rent",
            "currency": "USD"
        },
        {
            "date": "2026-06-02",
            "amount": "-45.50",
            "merchant": "Whole Foods",
            "description": "Weekly groceries",
            "category": "grocery",
            "currency": "USD"
        },
        {
            "date": "2026-06-03",
            "amount": "-12.99",
            "merchant": "Netflix",
            "description": "Subscription",
            "category": "entertainment",
            "currency": "USD"
        },
        {
            "date": "2026-06-04",
            "amount": "2500.00",
            "merchant": "Employer Corp",
            "description": "Salary payout",
            "category": "income",
            "currency": "USD"
        }
    ]

async def ingest_transactions(
    session: AsyncSession,
    user_id: UUID,
    normalized_txns: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Ingest, deduplicate, and record normalized transactions for the user."""
    if not normalized_txns:
        return {
            "inserted": 0,
            "duplicates_skipped": 0,
            "suspected_duplicates": []
        }
        
    hashes_to_check = set()
    unique_txns = []
    seen_hashes_in_batch = set()
    
    for txn in normalized_txns:
        h = compute_transaction_hash(
            user_id=user_id,
            date_val=txn["date"],
            amount=txn["amount"],
            merchant=txn["merchant"]
        )
        txn["hash"] = h
        
        if h in seen_hashes_in_batch:
            continue
        seen_hashes_in_batch.add(h)
        hashes_to_check.add(h)
        unique_txns.append(txn)
        
    existing_hashes = await find_existing_hashes(session, user_id, hashes_to_check)
    
    to_insert = []
    duplicates_skipped = 0
    
    for txn in unique_txns:
        if txn["hash"] in existing_hashes:
            duplicates_skipped += 1
        else:
            to_insert.append(txn)
            
    near_dupes = await find_near_duplicates(session, user_id, to_insert)
    near_dupe_details = [
        {
            "id": str(d.id),
            "date": d.date.isoformat(),
            "amount": float(d.amount),
            "merchant": d.merchant,
            "source": d.source
        }
        for d in near_dupes
    ]
    

    db_txns = []
    affected_buckets = set()
    for txn in to_insert:
        db_txn = Transaction(
            id=uuid.uuid4(),
            user_id=user_id,
            date=txn["date"],
            amount=txn["amount"],
            currency=txn.get("currency", "USD"),
            merchant=txn["merchant"],
            raw_description=txn.get("raw_description", txn["merchant"]),
            category=txn["category"],
            source=txn["source"],
            hash=txn["hash"]
        )
        db_txns.append(db_txn)
        affected_buckets.add((get_month_str(txn["date"]), txn["category"]))
        
    session.add_all(db_txns)
    await session.flush()
    
    if affected_buckets:
        await refresh_monthly_rollups(session, user_id, list(affected_buckets))
        from app.services.subscriptions import detect_and_save_subscriptions
        from app.services.anomalies import detect_and_save_anomalies
        await detect_and_save_subscriptions(session, user_id)
        await detect_and_save_anomalies(session, user_id)
        
    inserted_count = len(db_txns)
        
    return {
        "inserted": inserted_count,
        "duplicates_skipped": duplicates_skipped,
        "suspected_duplicates": near_dupe_details
    }
