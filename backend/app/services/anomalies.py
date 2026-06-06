from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.logger import get_logger
from app.models.transaction import Transaction, FlaggedAnomaly

logger = get_logger(__name__)


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
        logger.debug("detect_and_save_anomalies — no negative transactions for user_id=%s", user_id)
        return

    by_category = {}
    for t in txns:
        by_category.setdefault(t.category, []).append(abs(float(t.amount)))

    category_averages = {}
    for cat, amounts in by_category.items():
        category_averages[cat] = sum(amounts) / len(amounts)

    await session.execute(delete(FlaggedAnomaly).where(FlaggedAnomaly.user_id == user_id))
    await session.flush()

    flagged_count = 0
    for t in txns:
        val = abs(float(t.amount))
        cat_avg = category_averages.get(t.category, 0.0)
        if cat_avg > 0 and val > 2.0 * cat_avg:
            cur = t.currency or "USD"
            anomaly = FlaggedAnomaly(
                id=uuid4(),
                user_id=user_id,
                transaction_id=t.id,
                category=t.category,
                amount=val,
                currency=cur,
                reason=f"Transaction amount {cur} {val:.2f} is more than 2x the category average of {cur} {cat_avg:.2f}.",
                detected_at=datetime.now()
            )
            session.add(anomaly)
            flagged_count += 1

    await session.flush()
    logger.info(
        "Anomaly detection complete — user_id=%s scanned=%d flagged=%d",
        user_id, len(txns), flagged_count
    )


async def get_flagged_anomalies(session: AsyncSession, user_id: UUID) -> list[FlaggedAnomaly]:
    """Fetch precomputed flagged anomalies for the given user."""
    logger.debug("Fetching flagged anomalies — user_id=%s", user_id)
    query = select(FlaggedAnomaly).where(FlaggedAnomaly.user_id == user_id)
    res = await session.execute(query)
    return list(res.scalars().all())
