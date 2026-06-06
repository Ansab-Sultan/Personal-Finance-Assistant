from datetime import date as date_type, datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.transaction import TransactionCategory, TransactionSource

class TransactionBase(BaseModel):
    """Base Pydantic schema for Transaction properties."""
    date: date_type
    amount: float
    currency: str = Field(default="USD", min_length=3, max_length=3, pattern="^[A-Z]{3}$")
    merchant: str
    raw_description: str
    category: TransactionCategory = TransactionCategory.uncategorized
    source: TransactionSource

class TransactionCreate(TransactionBase):
    """Pydantic schema for creating a transaction."""
    pass

class TransactionUpdate(BaseModel):
    """Pydantic schema for updating a transaction."""
    date: Optional[date_type] = None
    amount: Optional[float] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3, pattern="^[A-Z]{3}$")
    merchant: Optional[str] = None
    category: Optional[TransactionCategory] = None

class TransactionRead(TransactionBase):
    """Pydantic schema for reading a transaction."""
    id: UUID
    user_id: UUID
    hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TransactionPaginated(BaseModel):
    """Paginated list of transactions."""
    items: List[TransactionRead]
    total: int
    page: int
    size: int
