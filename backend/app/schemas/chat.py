from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field
from app.models.chat import MessageRole


class ChatMessageBase(BaseModel):
    """Base Pydantic schema for ChatMessage properties."""
    role: MessageRole
    content: str = Field(..., min_length=1)

class ChatMessageRead(ChatMessageBase):
    """Pydantic schema for reading stored chat messages."""
    id: UUID
    user_id: UUID
    is_summarized: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ChatRequest(BaseModel):
    """Pydantic schema for chat query requests."""
    message: str = Field(..., min_length=1)
    image_base64: Optional[str] = None
    image_name: Optional[str] = None

class ChatResponse(BaseModel):
    """Pydantic schema for chat completions response."""
    reply: str

