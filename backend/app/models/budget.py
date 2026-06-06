import enum
import uuid
from sqlalchemy import Column, DateTime, Numeric, ForeignKey, Index, func, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from app.models.transaction import TransactionCategory

class BudgetPeriod(str, enum.Enum):
    """Enumeration representing the frequency/period of a budget."""
    monthly = "monthly"
    yearly = "yearly"

class Budget(Base):
    """Budget ORM model representing user budget targets per category and period."""
    __tablename__ = "budgets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(
        Enum(TransactionCategory, name="transaction_category", create_type=False),
        nullable=False
    )
    limit_amount = Column(Numeric(12, 2), nullable=False)
    period = Column(
        Enum(BudgetPeriod, name="budget_period", create_type=False),
        nullable=False,
        default=BudgetPeriod.monthly
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="budgets")

    __table_args__ = (
        Index("idx_budgets_user_category_period", "user_id", "category", "period", unique=True),
    )
