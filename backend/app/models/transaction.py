import enum
import uuid
from sqlalchemy import Column, DateTime, String, Numeric, ForeignKey, Index, func, Integer, Date, Enum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base

class TransactionSource(str, enum.Enum):
    """Enumeration representing the source from which a transaction was ingested."""
    csv = "csv"
    bank_api = "bank_api"
    manual = "manual"
    receipt = "receipt"

class TransactionCategory(str, enum.Enum):
    """Enumeration representing the financial category of a transaction."""
    groceries = "groceries"
    restaurants = "restaurants"
    transport = "transport"
    fuel = "fuel"
    utilities = "utilities"
    rent = "rent"
    health = "health"
    entertainment = "entertainment"
    shopping = "shopping"
    subscriptions = "subscriptions"
    travel = "travel"
    education = "education"
    income = "income"
    transfer = "transfer"
    uncategorized = "uncategorized"

class Transaction(Base):
    """Transaction ORM model representing individual financial transactions."""
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD")
    merchant = Column(String, nullable=False)
    raw_description = Column(String, nullable=False)
    category = Column(
        Enum(TransactionCategory, name="transaction_category", create_type=False),
        nullable=False,
        default=TransactionCategory.uncategorized,
        index=True
    )
    source = Column(
        Enum(TransactionSource, name="transaction_source", create_type=False),
        nullable=False
    )
    hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="transactions")

    __table_args__ = (
        Index("idx_transactions_user_date", "user_id", "date"),
        Index("idx_transactions_user_category_date", "user_id", "category", "date"),
        Index("idx_transactions_user_hash", "user_id", "hash", unique=True),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="ck_transactions_currency_format"),
    )


class MonthlyCategoryRollup(Base):
    """ORM model representing monthly aggregated transaction totals per user and category."""
    __tablename__ = "monthly_category_rollups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month = Column(String(7), nullable=False, index=True)
    category = Column(
        Enum(TransactionCategory, name="transaction_category", create_type=False),
        nullable=False,
        index=True
    )
    total_amount = Column(Numeric(12, 2), nullable=False, default=0.0)
    txn_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="monthly_category_rollups")

    __table_args__ = (
        Index("idx_rollups_user_month_category", "user_id", "month", "category", unique=True),
    )


class DetectedSubscription(Base):
    """ORM model representing monthly recurring transactions detected by heuristics."""
    __tablename__ = "detected_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    merchant = Column(String, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD", server_default="USD")
    cadence_days = Column(Integer, nullable=False)
    last_seen = Column(Date, nullable=False)
    confidence = Column(Numeric(4, 2), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="detected_subscriptions")


class FlaggedAnomaly(Base):
    """ORM model representing anomalous transaction amounts flagged by heuristics."""
    __tablename__ = "flagged_anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(
        Enum(TransactionCategory, name="transaction_category", create_type=False),
        nullable=False
    )
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="USD", server_default="USD")
    reason = Column(String, nullable=False)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="flagged_anomalies")
    transaction = relationship("Transaction")

