import uuid
from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base

class User(Base):
    """User ORM model representing users synced from Clerk."""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clerk_id = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    monthly_category_rollups = relationship("MonthlyCategoryRollup", back_populates="user", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    detected_subscriptions = relationship("DetectedSubscription", back_populates="user", cascade="all, delete-orphan")
    flagged_anomalies = relationship("FlaggedAnomaly", back_populates="user", cascade="all, delete-orphan")

