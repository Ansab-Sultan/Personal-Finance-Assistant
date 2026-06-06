from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.transaction import Transaction, MonthlyCategoryRollup, DetectedSubscription, FlaggedAnomaly, TransactionCategory
from app.models.budget import Budget, BudgetPeriod
from app.services import budget as budget_service
from app.services import memory as memory_service
from app.services.receipt import parse_receipt_image

async def spending_query_tool(
    db: AsyncSession,
    user_id: UUID,
    categories: List[str],
    period: str = "monthly"
) -> Dict[str, Any]:
    """Calculate the total spending in specific categories for a given period."""
    cleaned_categories = [c.strip().lower() for c in categories]
    
    total = 0.0
    category_breakdown = {}
    
    if period == "monthly":
        month_str = date.today().strftime("%Y-%m")
        query = select(MonthlyCategoryRollup).where(
            MonthlyCategoryRollup.user_id == user_id,
            MonthlyCategoryRollup.month == month_str,
            MonthlyCategoryRollup.category.in_(cleaned_categories)
        )
        res = await db.execute(query)
        rows = res.scalars().all()
        for r in rows:
            val = abs(float(r.total_amount))
            category_breakdown[r.category.value] = val
            total += val
    else:
        year_str = str(date.today().year)
        query = select(
            MonthlyCategoryRollup.category,
            func.sum(MonthlyCategoryRollup.total_amount)
        ).where(
            MonthlyCategoryRollup.user_id == user_id,
            MonthlyCategoryRollup.month.like(f"{year_str}-%"),
            MonthlyCategoryRollup.category.in_(cleaned_categories)
        ).group_by(MonthlyCategoryRollup.category)
        
        res = await db.execute(query)
        rows = res.all()
        for cat, val in rows:
            if val is not None:
                val_abs = abs(float(val))
                category_breakdown[cat.value] = val_abs
                total += val_abs
                
    return {
        "period": period,
        "categories_queried": categories,
        "total_spent": total,
        "breakdown": category_breakdown
    }

async def transactions_list_tool(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 5
) -> Dict[str, Any]:
    """Fetch the most recent transactions for a user, up to the given limit."""
    query = select(Transaction).where(
        Transaction.user_id == user_id
    ).order_by(Transaction.date.desc()).limit(limit)
    res = await db.execute(query)
    txns = res.scalars().all()
    return {
        "count": len(txns),
        "transactions": [
            {
                "date": t.date.isoformat(),
                "merchant": t.merchant,
                "category": t.category.value,
                "amount": float(t.amount),
                "currency": t.currency
            }
            for t in txns
        ]
    }

async def budget_tracker_tool(
    db: AsyncSession,
    user_id: UUID,
    category: str,
    period: str = "monthly"
) -> Dict[str, Any]:
    """Compare current spending against the user's budget limits for a category."""
    cat_enum = TransactionCategory(category.strip().lower())
    period_enum = BudgetPeriod(period.strip().lower())
    
    limit = await budget_service.get_budget_limit(db, user_id, cat_enum, period_enum)
    status = await budget_service.compute_budget_status(db, user_id, cat_enum, period_enum, limit)
    return status

async def user_memory_tool(
    db: AsyncSession,
    user_id: UUID,
    action: str,
    key: str,
    value: Optional[str] = None
) -> Dict[str, Any]:
    """Read, create, or update user financial preferences/memory keys in the database."""
    action_clean = action.strip().lower()
    
    if action_clean == "read":
        if key:
            val = await memory_service.get_preference_by_key(db, user_id, key)
            return {key: val}
        else:
            prefs = await memory_service.get_preferences(db, user_id)
            return {p.key: p.value for p in prefs}
            
    elif action_clean == "write":
        if not key or value is None:
            return {"error": "Missing key or value for preference write"}
        pref = await memory_service.upsert_preference(db, user_id, key, value)
        await db.commit()
        return {"success": True, "key": pref.key, "value": pref.value}
        
    elif action_clean == "delete":
        if not key:
            return {"error": "Missing key for preference delete"}
        deleted = await memory_service.delete_preference(db, user_id, key)
        await db.commit()
        return {"success": deleted}
        
    return {"error": f"Invalid action: {action}"}

async def finance_summary_tool(
    db: AsyncSession,
    user_id: UUID,
    period: str = "monthly"
) -> Dict[str, Any]:
    """Generate a category-wise summary of all spending and incomes for the current period."""
    total_spending = 0.0
    total_income = 0.0
    breakdown = {}
    
    if period == "monthly":
        month_str = date.today().strftime("%Y-%m")
        query = select(MonthlyCategoryRollup).where(
            MonthlyCategoryRollup.user_id == user_id,
            MonthlyCategoryRollup.month == month_str
        )
        res = await db.execute(query)
        rows = res.scalars().all()
        for r in rows:
            val = float(r.total_amount)
            if r.category == TransactionCategory.income:
                total_income += val
            else:
                val_abs = abs(val)
                breakdown[r.category.value] = val_abs
                total_spending += val_abs
    else:
        year_str = str(date.today().year)
        query = select(
            MonthlyCategoryRollup.category,
            func.sum(MonthlyCategoryRollup.total_amount)
        ).where(
            MonthlyCategoryRollup.user_id == user_id,
            MonthlyCategoryRollup.month.like(f"{year_str}-%")
        ).group_by(MonthlyCategoryRollup.category)
        
        res = await db.execute(query)
        rows = res.all()
        for cat, val in rows:
            if val is not None:
                val_float = float(val)
                if cat == TransactionCategory.income:
                    total_income += val_float
                else:
                    val_abs = abs(val_float)
                    breakdown[cat.value] = val_abs
                    total_spending += val_abs
                    
    return {
        "period": period,
        "total_spending": total_spending,
        "total_income": total_income,
        "category_spends": breakdown
    }

async def temporal_comparison_tool(
    db: AsyncSession,
    user_id: UUID,
    category: str,
    period_a: str,
    period_b: str
) -> Dict[str, Any]:
    """Compare spending in a category between two months."""
    cat_enum = TransactionCategory(category.strip().lower())
    
    query_a = select(MonthlyCategoryRollup.total_amount).where(
        MonthlyCategoryRollup.user_id == user_id,
        MonthlyCategoryRollup.month == period_a,
        MonthlyCategoryRollup.category == cat_enum
    )
    res_a = await db.execute(query_a)
    val_a = res_a.scalar_one_or_none()
    amount_a = abs(float(val_a)) if val_a is not None else 0.0
    
    query_b = select(MonthlyCategoryRollup.total_amount).where(
        MonthlyCategoryRollup.user_id == user_id,
        MonthlyCategoryRollup.month == period_b,
        MonthlyCategoryRollup.category == cat_enum
    )
    res_b = await db.execute(query_b)
    val_b = res_b.scalar_one_or_none()
    amount_b = abs(float(val_b)) if val_b is not None else 0.0
    
    difference = amount_b - amount_a
    pct_change = (difference / amount_a * 100.0) if amount_a > 0 else 0.0
    
    return {
        "category": category,
        "period_a": period_a,
        "amount_a": amount_a,
        "period_b": period_b,
        "amount_b": amount_b,
        "difference": difference,
        "percentage_change": pct_change
    }

async def subscription_detector_tool(db: AsyncSession, user_id: UUID) -> Dict[str, Any]:
    """Read precomputed detected recurring subscription charges from the database."""
    query = select(DetectedSubscription).where(DetectedSubscription.user_id == user_id)
    res = await db.execute(query)
    subs = res.scalars().all()
    
    return {
        "subscriptions": [
            {
                "merchant": s.merchant,
                "amount": float(s.amount),
                "cadence_days": s.cadence_days,
                "last_seen": s.last_seen.isoformat(),
                "confidence": float(s.confidence)
            }
            for s in subs
        ]
    }

async def anomaly_detector_tool(db: AsyncSession, user_id: UUID) -> Dict[str, Any]:
    """Read precomputed flagged transaction anomalies from the database."""
    query = select(FlaggedAnomaly).where(FlaggedAnomaly.user_id == user_id)
    res = await db.execute(query)
    anoms = res.scalars().all()
    
    return {
        "anomalies": [
            {
                "transaction_id": str(a.transaction_id),
                "category": a.category.value,
                "amount": float(a.amount),
                "reason": a.reason,
                "detected_at": a.detected_at.isoformat()
            }
            for a in anoms
        ]
    }

async def receipt_ocr_tool(
    db: AsyncSession,
    user_id: UUID,
    image_base64: str,
    image_name: str
) -> Dict[str, Any]:
    """OCR parse an uploaded receipt image using Gemini Vision."""
    try:
        parsed = await parse_receipt_image(image_base64)
        return {
            "success": True,
            "image_name": image_name,
            "parsed_data": parsed
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc)
        }

async def cutback_suggestion_tool(db: AsyncSession, user_id: UUID) -> Dict[str, Any]:
    """Analyze current spending categories to offer cutback suggestions."""
    summary = await finance_summary_tool(db, user_id, "monthly")
    category_spends = summary["category_spends"]
    
    suggestions = []
    for cat, val in category_spends.items():
        if cat in ["groceries", "restaurants", "shopping", "entertainment"] and val > 100.0:
            potential_savings = val * 0.15
            suggestions.append({
                "category": cat,
                "current_spending": val,
                "target_reduction_pct": 15.0,
                "potential_savings": potential_savings,
                "advice": f"Reducing spending on {cat} by 15% would save ${potential_savings:.2f}."
            })
            
    return {
        "current_month": date.today().strftime("%Y-%m"),
        "total_spending": summary["total_spending"],
        "suggestions": suggestions
    }

async def merchant_lookup_tool(merchant: str) -> Dict[str, Any]:
    """Stub/mock lookup helper for unrecognized merchants."""
    merchant_clean = merchant.strip().lower()
    
    if "starbucks" in merchant_clean:
        details = "Starbucks is a multinational chain of coffeehouses and roastery reserves."
    elif "uber" in merchant_clean:
        details = "Uber is a ride-sharing and food delivery service app."
    elif "netflix" in merchant_clean:
        details = "Netflix is an entertainment subscription service for streaming movies and TV shows."
    else:
        details = f"Details for {merchant} are not locally indexed. A standard web search would classify this merchant as retail/services."
        
    return {
        "query": merchant,
        "details": details
    }
