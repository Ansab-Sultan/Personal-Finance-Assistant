import uuid
from sqlalchemy import Column, DateTime, String, ForeignKey, Index, func, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base

class UserPreference(Base):
    """UserPreference ORM model representing user-stated key-value memory/preferences."""
    __tablename__ = "user_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(Text, nullable=False)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="preferences")

    __table_args__ = (
        Index("idx_user_preferences_user_key", "user_id", "key", unique=True),
        CheckConstraint(
            "key IN ('pay_date', 'exclude_from_food', 'currency_display', 'pay_cycle_start')",
            name="ck_user_preferences_key_values"
        ),
    )
