from datetime import date
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.logger import get_logger
from app.models.transaction import Transaction, DetectedSubscription

logger = get_logger(__name__)


async def detect_and_save_subscriptions(session: AsyncSession, user_id: UUID) -> None:
    """Analyze transaction history to detect monthly subscription patterns and persist them."""
    from app.models.user import User
    await session.execute(
        select(User.id).where(User.id == user_id).with_for_update()
    )
    query = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.amount < 0
    ).order_by(Transaction.date.asc())

    result = await session.execute(query)
    txns = list(result.scalars().all())

    by_merchant = {}
    for t in txns:
        m_clean = t.merchant.strip().lower()
        by_merchant.setdefault(m_clean, []).append(t)

    await session.execute(delete(DetectedSubscription).where(DetectedSubscription.user_id == user_id))
    await session.flush()

    detected_count = 0
    for merchant_name, merchant_txns in by_merchant.items():
        if len(merchant_txns) < 2:
            continue

        intervals = []
        for i in range(len(merchant_txns) - 1):
            diff = (merchant_txns[i+1].date - merchant_txns[i].date).days
            intervals.append(diff)

        monthly_intervals = [d for d in intervals if 27 <= d <= 33]
        if len(monthly_intervals) >= 1:
            avg_amount = sum(abs(float(t.amount)) for t in merchant_txns) / len(merchant_txns)
            cadence = 30
            last_seen = merchant_txns[-1].date
            confidence = len(monthly_intervals) / len(intervals)

            sub = DetectedSubscription(
                id=uuid4(),
                user_id=user_id,
                merchant=merchant_txns[0].merchant,
                amount=avg_amount,
                cadence_days=cadence,
                last_seen=last_seen,
                confidence=confidence
            )
            session.add(sub)
            detected_count += 1

    await session.flush()
    logger.info(
        "Subscription detection complete — user_id=%s txns_scanned=%d subs_detected=%d",
        user_id, len(txns), detected_count
    )


async def get_detected_subscriptions(session: AsyncSession, user_id: UUID) -> list[DetectedSubscription]:
    """Fetch precomputed subscription records for the given user."""
    logger.debug("Fetching detected subscriptions — user_id=%s", user_id)
    query = select(DetectedSubscription).where(DetectedSubscription.user_id == user_id)
    res = await session.execute(query)
    return list(res.scalars().all())
