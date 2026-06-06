from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_db_user_id
from app.core.logger import get_logger
from app.models.transaction import TransactionCategory
from app.models.budget import BudgetPeriod
from app.schemas.budget import BudgetRead, BudgetCreate, BudgetUpdate, BudgetStatusRead
from app.services import budget as budget_service

logger = get_logger(__name__)

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.post("", response_model=BudgetRead, status_code=status.HTTP_201_CREATED)
async def create_or_update_user_budget(
    payload: BudgetCreate,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Create a new budget or update an existing one if the category and period match."""
    logger.info(
        "Upserting budget — user_id=%s category=%s period=%s limit=%.2f",
        user_id, payload.category, payload.period, payload.limit_amount
    )
    budget = await budget_service.create_or_update_budget(
        session=db,
        user_id=user_id,
        category=payload.category,
        limit_amount=payload.limit_amount,
        period=payload.period
    )
    await db.commit()
    logger.debug("Budget upserted — budget_id=%s", budget.id)
    return budget


@router.get("", response_model=List[BudgetRead])
async def list_user_budgets(
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """List all budgets configured by the current user."""
    logger.debug("Listing budgets — user_id=%s", user_id)
    return await budget_service.list_budgets(db, user_id)


@router.get("/status", response_model=List[BudgetStatusRead])
async def get_all_budgets_status(
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve spent status for all configured budgets of the user."""
    logger.debug("Fetching all budget statuses — user_id=%s", user_id)
    return await budget_service.get_all_budget_statuses(db, user_id)


@router.get("/status/{category}/{period}", response_model=BudgetStatusRead)
async def get_specific_budget_status(
    category: TransactionCategory,
    period: BudgetPeriod,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Calculate and retrieve budget spent status for a specific category and period, even if no budget is set."""
    logger.debug(
        "Fetching budget status — user_id=%s category=%s period=%s",
        user_id, category, period
    )
    limit = await budget_service.get_budget_limit(db, user_id, category, period)
    return await budget_service.compute_budget_status(
        session=db,
        user_id=user_id,
        category=category,
        period=period,
        limit_amount=limit
    )


@router.get("/{id}", response_model=BudgetRead)
async def read_user_budget(
    id: UUID,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Read specific budget details, scoped to the current user."""
    logger.debug("Reading budget — user_id=%s budget_id=%s", user_id, id)
    budget = await budget_service.get_budget(db, user_id, id)
    if not budget:
        logger.warning("Budget not found — user_id=%s budget_id=%s", user_id, id)
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
    logger.info("Updating budget — user_id=%s budget_id=%s fields=%s", user_id, id, list(payload.model_dump(exclude_unset=True).keys()))
    update_dict = payload.model_dump(exclude_unset=True)
    budget = await budget_service.update_budget(db, user_id, id, update_dict)
    if not budget:
        logger.warning("Budget not found for update — user_id=%s budget_id=%s", user_id, id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    await db.commit()
    return budget


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_budget(
    id: UUID,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Delete a budget configuration."""
    logger.info("Deleting budget — user_id=%s budget_id=%s", user_id, id)
    deleted = await budget_service.delete_budget(db, user_id, id)
    if not deleted:
        logger.warning("Budget not found for deletion — user_id=%s budget_id=%s", user_id, id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    await db.commit()
    return None
