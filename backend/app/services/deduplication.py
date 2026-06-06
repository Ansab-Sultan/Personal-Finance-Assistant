import hashlib
from datetime import date, timedelta
from typing import Any, Dict, List, Set, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from app.models.transaction import Transaction

def compute_transaction_hash(user_id: UUID, date_val: date, amount: float, merchant: str) -> str:
    """Compute the SHA256 hash of a transaction to uniquely identify it for idempotency."""
    formatted_amount = f"{float(amount):.2f}"
    raw_str = f"{str(user_id)}|{date_val.isoformat()}|{formatted_amount}|{merchant.strip().lower()}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

async def find_existing_hashes(session: AsyncSession, user_id: UUID, hashes: Set[str]) -> Set[str]:
    """Find which of the given hashes already exist in the database for the user."""
    if not hashes:
        return set()
    query = select(Transaction.hash).where(
        and_(
            Transaction.user_id == user_id,
            Transaction.hash.in_(list(hashes))
        )
    )
    result = await session.execute(query)
    return set(result.scalars().all())

async def find_near_duplicates(
    session: AsyncSession,
    user_id: UUID,
    transactions_to_check: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Find existing transactions in the database that are near-duplicates of the new transactions.
    
    A near-duplicate has the same amount and merchant (case-insensitive)
    with a date within a +/- 2-day window, but a different source.
    """
    if not transactions_to_check:
        return []
        
    conditions = []
    for txn in transactions_to_check:
        date_val = txn["date"]
        min_date = date_val - timedelta(days=2)
        max_date = date_val + timedelta(days=2)
        conditions.append(
            and_(
                func.lower(Transaction.merchant) == txn["merchant"].strip().lower(),
                Transaction.amount == txn["amount"],
                Transaction.date.between(min_date, max_date),
                Transaction.source != txn["source"]
            )
        )
        
    if not conditions:
        return []
        
    query = select(Transaction).where(
        and_(
            Transaction.user_id == user_id,
            or_(*conditions)
        )
    )
    result = await session.execute(query)
    return list(result.scalars().all())
