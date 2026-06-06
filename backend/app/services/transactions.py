import calendar
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import and_, desc, select, update, delete, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import DuplicateTransactionError
from app.core.logger import get_logger
from app.models.transaction import Transaction, MonthlyCategoryRollup
from app.services.deduplication import compute_transaction_hash

logger = get_logger(__name__)


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
        try:
            async with session.begin_nested():
                rollup = MonthlyCategoryRollup(
                    user_id=user_id,
                    month=month,
                    category=category,
                    total_amount=amount_delta,
                    txn_count=count_delta
                )
                session.add(rollup)
                await session.flush()
        except IntegrityError:
            result = await session.execute(query)
            rollup = result.scalar_one()
            rollup.total_amount = float(rollup.total_amount) + amount_delta
            rollup.txn_count += count_delta
            if rollup.txn_count <= 0:
                await session.delete(rollup)
            await session.flush()
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
    logger.debug(
        "Transaction created — user_id=%s merchant=%s amount=%s category=%s",
        user_id, merchant, amount, category
    )

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

    # Detection recompute is enqueued by the API layer after commit (see recompute_detections_task).
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
        logger.warning("Delete transaction — not found: txn_id=%s user_id=%s", txn_id, user_id)
        return False

    old_date = txn.date
    old_amount = float(txn.amount)
    old_category = txn.category

    await session.delete(txn)
    logger.info("Transaction deleted — txn_id=%s user_id=%s", txn_id, user_id)

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
                    try:
                        async with session.begin_nested():
                            rollup = MonthlyCategoryRollup(
                                user_id=user_id,
                                month=month,
                                category=category,
                                total_amount=total,
                                txn_count=count
                            )
                            session.add(rollup)
                            await session.flush()
                    except IntegrityError:
                        res_exist = await session.execute(q_exist)
                        rollup = res_exist.scalar_one()
                        rollup.total_amount = total
                        rollup.txn_count = count
                else:
                    rollup.total_amount = total
                    rollup.txn_count = count
            else:
                if rollup:
                    await session.delete(rollup)

async def get_transaction(
    session: AsyncSession,
    user_id: UUID,
    txn_id: UUID
) -> Optional[Transaction]:
    """Fetch a single transaction scoped to the user."""
    query = select(Transaction).where(
        Transaction.id == txn_id,
        Transaction.user_id == user_id
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()

async def list_transactions(
    session: AsyncSession,
    user_id: UUID,
    page: int,
    size: int,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category: Optional[str] = None,
    merchant: Optional[str] = None
) -> tuple[List[Transaction], int]:
    """Retrieve filtered and paginated transactions for a user, along with the total count."""

    conditions = [Transaction.user_id == user_id]
    if start_date:
        conditions.append(Transaction.date >= start_date)
    if end_date:
        conditions.append(Transaction.date <= end_date)
    if category:
        conditions.append(Transaction.category == category.lower())
    if merchant:
        conditions.append(Transaction.merchant.ilike(f"%{merchant}%"))
        
    where_clause = and_(*conditions)
    
    count_query = select(func.count()).select_from(Transaction).where(where_clause)
    count_result = await session.execute(count_query)
    total = count_result.scalar_one()
    
    query = select(Transaction).where(where_clause).order_by(desc(Transaction.date)).offset((page - 1) * size).limit(size)
    result = await session.execute(query)
    items = list(result.scalars().all())
    
    return items, total

async def create_manual_transaction(
    session: AsyncSession,
    user_id: UUID,
    txn_data: Dict[str, Any],
    force: bool
) -> Transaction:
    """Create a manual transaction with duplicate validation checking."""

    txn_dict = dict(txn_data)
    txn_dict["source"] = "manual"
    
    h = compute_transaction_hash(user_id, txn_dict["date"], txn_dict["amount"], txn_dict["merchant"])
    
    if not force:
        query = select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.hash == h
        )
        result = await session.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            raise DuplicateTransactionError(existing)
    else:
        txn_dict["merchant"] = f"{txn_dict['merchant']} (duplicate)"
        
    return await create_transaction(session, user_id, txn_dict)

