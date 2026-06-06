from datetime import date
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.budget import Budget, BudgetPeriod
from app.models.transaction import TransactionCategory, MonthlyCategoryRollup

async def compute_budget_status(
    session: AsyncSession,
    user_id: UUID,
    category: TransactionCategory,
    period: BudgetPeriod,
    limit_amount: float
) -> Dict[str, Any]:
    """Compute current spent vs. limit status for a given category and period.
    
    Exclusions from Module 04 user preferences can be applied to the spent query here
    when that module is implemented.
    """
    spent_sum = 0.0
    
    if period == BudgetPeriod.monthly:
        current_month = date.today().strftime("%Y-%m")
        query = select(MonthlyCategoryRollup.total_amount).where(
            MonthlyCategoryRollup.user_id == user_id,
            MonthlyCategoryRollup.month == current_month,
            MonthlyCategoryRollup.category == category
        )
        res = await session.execute(query)
        val = res.scalar_one_or_none()
        if val is not None:
            spent_sum = abs(float(val))
            
    elif period == BudgetPeriod.yearly:
        current_year = str(date.today().year)
        query = select(func.sum(MonthlyCategoryRollup.total_amount)).where(
            MonthlyCategoryRollup.user_id == user_id,
            MonthlyCategoryRollup.category == category,
            MonthlyCategoryRollup.month.like(f"{current_year}-%")
        )
        res = await session.execute(query)
        val = res.scalar_one_or_none()
        if val is not None:
            spent_sum = abs(float(val))
            
    remaining = max(0.0, limit_amount - spent_sum)
    ratio = spent_sum / limit_amount if limit_amount > 0 else 0.0
    
    if ratio < 0.8:
        state = "ok"
    elif ratio <= 1.0:
        state = "warning"
    else:
        state = "over"
        
    return {
        "category": category,
        "period": period,
        "spent": spent_sum,
        "limit": limit_amount,
        "remaining": remaining,
        "ratio": ratio,
        "state": state
    }

async def create_or_update_budget(
    session: AsyncSession,
    user_id: UUID,
    category: TransactionCategory,
    limit_amount: float,
    period: BudgetPeriod
) -> Budget:
    """Create a new budget or update an existing one for the same user, category and period."""
    query = select(Budget).where(
        Budget.user_id == user_id,
        Budget.category == category,
        Budget.period == period
    )
    result = await session.execute(query)
    budget = result.scalar_one_or_none()
    
    if budget:
        budget.limit_amount = limit_amount
    else:
        budget = Budget(
            user_id=user_id,
            category=category,
            limit_amount=limit_amount,
            period=period
        )
        session.add(budget)
        
    await session.flush()
    return budget

async def get_budget(session: AsyncSession, user_id: UUID, budget_id: UUID) -> Optional[Budget]:
    """Retrieve details of a specific budget, ensuring user scope validation."""
    query = select(Budget).where(
        Budget.id == budget_id,
        Budget.user_id == user_id
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()

async def list_budgets(session: AsyncSession, user_id: UUID) -> List[Budget]:
    """List all budgets configured by a user."""
    query = select(Budget).where(Budget.user_id == user_id)
    result = await session.execute(query)
    return list(result.scalars().all())

async def delete_budget(session: AsyncSession, user_id: UUID, budget_id: UUID) -> bool:
    """Delete a budget, returning whether the budget existed and was deleted."""
    query = select(Budget).where(
        Budget.id == budget_id,
        Budget.user_id == user_id
    )
    result = await session.execute(query)
    budget = result.scalar_one_or_none()
    
    if budget:
        await session.delete(budget)
        return True
    return False

async def get_all_budget_statuses(session: AsyncSession, user_id: UUID) -> List[Dict[str, Any]]:
    """Retrieve spend statuses for all budgets configured by a user."""
    budgets = await list_budgets(session, user_id)
    statuses = []
    for b in budgets:
        status = await compute_budget_status(
            session=session,
            user_id=user_id,
            category=b.category,
            period=b.period,
            limit_amount=float(b.limit_amount)
        )
        status["id"] = b.id
        statuses.append(status)
    return statuses
