import enum
import re
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, model_validator, Field
from app.models.transaction import TransactionCategory

class PreferenceKey(str, enum.Enum):
    """Enumeration representing valid user preference keys."""
    pay_date = "pay_date"
    exclude_from_food = "exclude_from_food"
    currency_display = "currency_display"
    pay_cycle_start = "pay_cycle_start"

class PreferenceUpsert(BaseModel):
    """Pydantic schema for creating or updating a user preference."""
    key: PreferenceKey
    value: str

    @model_validator(mode="after")
    def validate_value_by_key(self) -> "PreferenceUpsert":
        """Validate the format of value depending on the preference key type."""
        val = self.value.strip()
        if self.key == PreferenceKey.pay_date:
            try:
                day = int(val)
                if not (1 <= day <= 31):
                    raise ValueError("pay_date must be an integer between 1 and 31")
            except ValueError:
                raise ValueError("pay_date must be a valid integer string")
                
        elif self.key == PreferenceKey.currency_display:
            if not re.match(r"^[A-Z]{3}$", val.upper()):
                raise ValueError("currency_display must be a 3-letter currency code")
                
        elif self.key == PreferenceKey.pay_cycle_start:
            try:
                datetime.strptime(val, "%Y-%m-%d")
            except ValueError:
                raise ValueError("pay_cycle_start must be in YYYY-MM-DD format")
                
        elif self.key == PreferenceKey.exclude_from_food:
            try:
                TransactionCategory(val.lower())
            except ValueError:
                raise ValueError("exclude_from_food must be a valid transaction category name")
                
        return self

class PreferenceRead(BaseModel):
    """Pydantic schema for reading stored user preference details."""
    id: UUID
    user_id: UUID
    key: PreferenceKey
    value: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
