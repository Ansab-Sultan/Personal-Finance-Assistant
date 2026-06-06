from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from app.models.transaction import Transaction, MonthlyCategoryRollup
from app.services.deduplication import compute_transaction_hash

def get_month_str(date_val: date) -> str:
    """Get the YYYY-MM string representation of a date."""
    return date_val.strftime("%Y-%m")

async def adjust_rollup(
    session: AsyncSession,
    user_id: UUID,
    month: str,
    category: str,
    amount_delta: float,
    count_delta: int
) -> None:
    """Adjust the monthly category rollup bucket (increment or decrement)."""
    query = select(MonthlyCategoryRollup).where(
        MonthlyCategoryRollup.user_id == user_id,
        MonthlyCategoryRollup.month == month,
        MonthlyCategoryRollup.category == category
    )
    result = await session.execute(query)
    rollup = result.scalar_one_or_none()
    
    if not rollup:
        if count_delta <= 0:
            return
        rollup = MonthlyCategoryRollup(
            user_id=user_id,
            month=month,
            category=category,
            total_amount=amount_delta,
            txn_count=count_delta
        )
        session.add(rollup)
    else:
        rollup.total_amount = float(rollup.total_amount) + amount_delta
        rollup.txn_count += count_delta
        if rollup.txn_count <= 0:
            await session.delete(rollup)

async def create_transaction(
    session: AsyncSession,
    user_id: UUID,
    txn_data: Dict[str, Any]
) -> Transaction:
    """Create a new transaction and update the corresponding monthly category rollup."""
    date_val = txn_data["date"]
    amount = txn_data["amount"]
    merchant = txn_data["merchant"]
    category = txn_data.get("category", "uncategorized")
    
    txn_hash = compute_transaction_hash(user_id, date_val, amount, merchant)
    
    new_txn = Transaction(
        user_id=user_id,
        date=date_val,
        amount=amount,
        currency=txn_data.get("currency", "USD"),
        merchant=merchant,
        raw_description=txn_data.get("raw_description", merchant),
        category=category,
        source=txn_data.get("source", "manual"),
        hash=txn_hash
    )
    session.add(new_txn)
    
    month = get_month_str(date_val)
    await adjust_rollup(session, user_id, month, category, float(amount), 1)
    
    return new_txn

async def update_transaction(
    session: AsyncSession,
    user_id: UUID,
    txn_id: UUID,
    update_data: Dict[str, Any]
) -> Optional[Transaction]:
    """Update a transaction, syncing the old and new monthly category rollup buckets if needed."""
    query = select(Transaction).where(
        Transaction.id == txn_id,
        Transaction.user_id == user_id
    )
    result = await session.execute(query)
    txn = result.scalar_one_or_none()
    
    if not txn:
        return None
        
    old_date = txn.date
    old_amount = float(txn.amount)
    old_category = txn.category
    
    new_date = update_data.get("date", old_date)
    new_amount = update_data.get("amount", old_amount)
    new_category = update_data.get("category", old_category)
    
    for key, value in update_data.items():
        if hasattr(txn, key):
            setattr(txn, key, value)
            
    if new_date != old_date or new_amount != old_amount or new_category != old_category:
        txn.hash = compute_transaction_hash(user_id, new_date, new_amount, txn.merchant)
        
        old_month = get_month_str(old_date)
        new_month = get_month_str(new_date)
        
        await adjust_rollup(session, user_id, old_month, old_category, -old_amount, -1)
        await adjust_rollup(session, user_id, new_month, new_category, float(new_amount), 1)
        
    return txn

async def delete_transaction(
    session: AsyncSession,
    user_id: UUID,
    txn_id: UUID
) -> bool:
    """Delete a transaction and decrement its corresponding monthly category rollup bucket."""
    query = select(Transaction).where(
        Transaction.id == txn_id,
        Transaction.user_id == user_id
    )
    result = await session.execute(query)
    txn = result.scalar_one_or_none()
    
    if not txn:
        return False
        
    old_date = txn.date
    old_amount = float(txn.amount)
    old_category = txn.category
    
    await session.delete(txn)
    
    month = get_month_str(old_date)
    await adjust_rollup(session, user_id, month, old_category, -old_amount, -1)
    
    return True

async def refresh_monthly_rollups(
    session: AsyncSession,
    user_id: UUID,
    months_categories: Optional[List[tuple[str, str]]] = None
) -> None:
    """Recalculate and update the monthly category rollups for specific months and categories."""
    if months_categories is not None and not months_categories:
        return
        
    if months_categories:
        import calendar
        for month, category in months_categories:
            year = int(month[:4])
            m = int(month[5:7])
            _, last_day = calendar.monthrange(year, m)
            start_date = date(year, m, 1)
            end_date = date(year, m, last_day)
            
            q_sum = select(
                func.sum(Transaction.amount),
                func.count(Transaction.id)
            ).where(
                Transaction.user_id == user_id,
                Transaction.category == category,
                Transaction.date.between(start_date, end_date)
            )
            res = await session.execute(q_sum)
            total, count = res.all()[0]
            
            q_exist = select(MonthlyCategoryRollup).where(
                MonthlyCategoryRollup.user_id == user_id,
                MonthlyCategoryRollup.month == month,
                MonthlyCategoryRollup.category == category
            )
            res_exist = await session.execute(q_exist)
            rollup = res_exist.scalar_one_or_none()
            
            if count and count > 0:
                if not rollup:
                    rollup = MonthlyCategoryRollup(
                        user_id=user_id,
                        month=month,
                        category=category,
                        total_amount=total,
                        txn_count=count
                    )
                    session.add(rollup)
                else:
                    rollup.total_amount = total
                    rollup.txn_count = count
            else:
                if rollup:
                    await session.delete(rollup)
