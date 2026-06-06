from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_db_user_id
from app.models.transaction import TransactionCategory
from app.models.budget import BudgetPeriod
from app.schemas.budget import BudgetRead, BudgetCreate, BudgetUpdate, BudgetStatusRead
from app.services import budget as budget_service

router = APIRouter(prefix="/api/v1/budgets", tags=["budgets"])

@router.post("", response_model=BudgetRead, status_code=status.HTTP_201_CREATED)
async def create_or_update_user_budget(
    payload: BudgetCreate,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Create a new budget or update an existing one if the category and period match."""
    budget = await budget_service.create_or_update_budget(
        session=db,
        user_id=user_id,
        category=payload.category,
        limit_amount=payload.limit_amount,
        period=payload.period
    )
    await db.commit()
    return budget

@router.get("", response_model=List[BudgetRead])
async def list_user_budgets(
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """List all budgets configured by the current user."""
    budgets = await budget_service.list_budgets(db, user_id)
    return budgets

@router.get("/status", response_model=List[BudgetStatusRead])
async def get_all_budgets_status(
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve spent status for all configured budgets of the user."""
    statuses = await budget_service.get_all_budget_statuses(db, user_id)
    return statuses

@router.get("/status/{category}/{period}", response_model=BudgetStatusRead)
async def get_specific_budget_status(
    category: TransactionCategory,
    period: BudgetPeriod,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Calculate and retrieve budget spent status for a specific category and period, even if no budget is set.
    
    If no budget is set, limit will default to 0.0, and status will indicate no budget configuration.
    """
    limit = 0.0
    
    from sqlalchemy import select
    from app.models.budget import Budget
    
    query = select(Budget.limit_amount).where(
        Budget.user_id == user_id,
        Budget.category == category,
        Budget.period == period
    )
    res = await db.execute(query)
    limit_val = res.scalar_one_or_none()
    if limit_val is not None:
        limit = float(limit_val)
        
    status_details = await budget_service.compute_budget_status(
        session=db,
        user_id=user_id,
        category=category,
        period=period,
        limit_amount=limit
    )
    return status_details

@router.get("/{id}", response_model=BudgetRead)
async def read_user_budget(
    id: UUID,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Read a specific budget details, scoped to the current user."""
    budget = await budget_service.get_budget(db, user_id, id)
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    return budget

@router.patch("/{id}", response_model=BudgetRead)
async def update_user_budget(
    id: UUID,
    payload: BudgetUpdate,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Update configured fields of a budget."""
    budget = await budget_service.get_budget(db, user_id, id)
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
        
    update_dict = payload.model_dump(exclude_unset=True)
    for key, value in update_dict.items():
        setattr(budget, key, value)
        
    await db.commit()
    return budget

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_budget(
    id: UUID,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Delete a budget configuration."""
    deleted = await budget_service.delete_budget(db, user_id, id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    await db.commit()
    return None
