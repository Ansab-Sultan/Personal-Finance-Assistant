from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.transaction import Transaction, FlaggedAnomaly

async def detect_and_save_anomalies(session: AsyncSession, user_id: UUID) -> None:
    """Scan transactions to flag expenses exceeding 2x the category average."""
    from app.models.user import User
    await session.execute(
        select(User.id).where(User.id == user_id).with_for_update()
    )
    query = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.amount < 0
    )
    result = await session.execute(query)
    txns = list(result.scalars().all())
    
    if not txns:
        return
        
    by_category = {}
    for t in txns:
        by_category.setdefault(t.category, []).append(abs(float(t.amount)))
        
    category_averages = {}
    for cat, amounts in by_category.items():
        category_averages[cat] = sum(amounts) / len(amounts)
        
    await session.execute(delete(FlaggedAnomaly).where(FlaggedAnomaly.user_id == user_id))
    await session.flush()
    
    for t in txns:
        val = abs(float(t.amount))
        cat_avg = category_averages.get(t.category, 0.0)
        if cat_avg > 0 and val > 2.0 * cat_avg:
            anomaly = FlaggedAnomaly(
                id=uuid4(),
                user_id=user_id,
                transaction_id=t.id,
                category=t.category,
                amount=val,
                reason=f"Transaction amount ${val:.2f} is more than 2x the category average of ${cat_avg:.2f}.",
                detected_at=datetime.now()
            )
            session.add(anomaly)
            
    await session.flush()

async def get_flagged_anomalies(session: AsyncSession, user_id: UUID) -> list[FlaggedAnomaly]:
    """Fetch precomputed flagged anomalies for the given user."""
    query = select(FlaggedAnomaly).where(FlaggedAnomaly.user_id == user_id)
    res = await session.execute(query)
    return list(res.scalars().all())

