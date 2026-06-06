from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.transaction import TransactionCategory
from app.models.budget import BudgetPeriod

class BudgetBase(BaseModel):
    """Base Pydantic schema for Budget properties."""
    category: TransactionCategory
    limit_amount: float = Field(..., gt=0)
    period: BudgetPeriod = BudgetPeriod.monthly

class BudgetCreate(BudgetBase):
    """Pydantic schema for creating a new budget."""
    pass

class BudgetUpdate(BaseModel):
    """Pydantic schema for updating an existing budget."""
    limit_amount: Optional[float] = Field(None, gt=0)
    period: Optional[BudgetPeriod] = None

class BudgetRead(BudgetBase):
    """Pydantic schema for reading budget details."""
    id: UUID
    user_id: UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class BudgetStatusRead(BaseModel):
    """Pydantic schema representing the spend status relative to a budget limit."""
    id: Optional[UUID] = None
    category: TransactionCategory
    period: BudgetPeriod
    spent: float
    limit: float
    remaining: float
    ratio: float
    state: str
