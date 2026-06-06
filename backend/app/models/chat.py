import enum
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Index, func, Text, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base

class MessageRole(str, enum.Enum):
    """Enumeration representing the sender of a chat message."""
    user = "user"
    assistant = "assistant"
    system = "system"

class ChatMessage(Base):
    """ChatMessage ORM model representing conversation turns and running summaries."""
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(
        Enum(MessageRole, name="message_role", create_type=False),
        nullable=False
    )
    content = Column(Text, nullable=False)
    is_summarized = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="chat_messages")

    __table_args__ = (
        Index("idx_chat_messages_user_created", "user_id", "created_at"),
        Index("idx_chat_messages_user_summarized", "user_id", "is_summarized"),
    )
