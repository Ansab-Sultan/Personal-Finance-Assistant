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
            
    if category == TransactionCategory.restaurants:
        from app.services.memory import get_preference_by_key
        exclude_cat_name = await get_preference_by_key(session, user_id, "exclude_from_food")
        if exclude_cat_name:
            try:
                exclude_cat = TransactionCategory(exclude_cat_name)
                exclude_spent = 0.0
                if period == BudgetPeriod.monthly:
                    current_month = date.today().strftime("%Y-%m")
                    eq = select(MonthlyCategoryRollup.total_amount).where(
                        MonthlyCategoryRollup.user_id == user_id,
                        MonthlyCategoryRollup.month == current_month,
                        MonthlyCategoryRollup.category == exclude_cat
                    )
                    eres = await session.execute(eq)
                    eval_val = eres.scalar_one_or_none()
                    if eval_val is not None:
                        exclude_spent = abs(float(eval_val))
                elif period == BudgetPeriod.yearly:
                    current_year = str(date.today().year)
                    eq = select(func.sum(MonthlyCategoryRollup.total_amount)).where(
                        MonthlyCategoryRollup.user_id == user_id,
                        MonthlyCategoryRollup.category == exclude_cat,
                        MonthlyCategoryRollup.month.like(f"{current_year}-%")
                    )
                    eres = await session.execute(eq)
                    eval_val = eres.scalar_one_or_none()
                    if eval_val is not None:
                        exclude_spent = abs(float(eval_val))
                spent_sum = max(0.0, spent_sum - exclude_spent)
            except ValueError:
                pass
                
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
    from sqlalchemy.exc import IntegrityError
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
        try:
            budget = Budget(
                user_id=user_id,
                category=category,
                limit_amount=limit_amount,
                period=period
            )
            session.add(budget)
            await session.flush()
        except IntegrityError:
            await session.rollback()
            result = await session.execute(query)
            budget = result.scalar_one()
            budget.limit_amount = limit_amount
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

async def update_budget(
    session: AsyncSession,
    user_id: UUID,
    budget_id: UUID,
    update_data: Dict[str, Any]
) -> Optional[Budget]:
    """Update configured fields of a budget."""
    budget = await get_budget(session, user_id, budget_id)
    if not budget:
        return None
    for key, value in update_data.items():
        setattr(budget, key, value)
    await session.flush()
    return budget

async def get_budget_limit(
    session: AsyncSession,
    user_id: UUID,
    category: TransactionCategory,
    period: BudgetPeriod
) -> float:
    """Calculate budget limit for a specific category and period, returning 0.0 if not configured."""
    query = select(Budget.limit_amount).where(
        Budget.user_id == user_id,
        Budget.category == category,
        Budget.period == period
    )
    res = await session.execute(query)
    limit_val = res.scalar_one_or_none()
    return float(limit_val) if limit_val is not None else 0.0

