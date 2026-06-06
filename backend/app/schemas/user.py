from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class UserBase(BaseModel):
    """Base Pydantic schema for User properties."""
    email: str

class UserCreate(UserBase):
    """Pydantic schema for creating a user (e.g. from webhooks)."""
    clerk_id: str

class UserRead(UserBase):
    """Pydantic schema for reading user data."""
    id: UUID
    clerk_id: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
