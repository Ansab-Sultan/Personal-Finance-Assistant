from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, AsyncSessionLocal
from app.core.dependencies import get_db_user_id
from app.core.logger import get_logger
from app.models.chat import MessageRole
from app.schemas.chat import ChatMessageRead, ChatRequest
from app.services import chat as chat_service
from app.services.llm import llm_client

from app.agent.agent import compiled_agent
import asyncio

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/history", response_model=List[ChatMessageRead])
async def get_chat_history(
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve raw unsummarized chat messages for the current user's active thread."""
    logger.debug("Fetching chat history — user_id=%s", user_id)
    return await chat_service.get_unsummarized_history(db, user_id)


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_chat_history(
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Permanently delete all chat messages and summaries for the current user."""
    logger.info("Clearing chat history — user_id=%s", user_id)
    from app.models.chat import ChatMessage
    await db.execute(delete(ChatMessage).where(ChatMessage.user_id == user_id))
    await db.commit()
    return None


@router.post("")
async def stream_chat(
    payload: ChatRequest,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Stream assistant response over Server-Sent Events (SSE), maintaining memory and summaries."""
    message_content = payload.message.strip()
    if not message_content and not payload.image_base64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message content cannot be empty"
        )

    has_image = bool(payload.image_base64)
    logger.info(
        "Chat request — user_id=%s message_len=%d has_image=%s",
        user_id, len(message_content), has_image
    )

    await chat_service.save_message(db, user_id, MessageRole.user, message_content)
    await db.commit()

    messages, system_instruction = await chat_service.get_chat_context(db, user_id)

    initial_state = {
        "user_id": str(user_id),
        "message": message_content,
        "image_base64": payload.image_base64,
        "image_name": payload.image_name,
        "system_instruction": system_instruction,
        "messages": messages,
        "route": "",
        "intent": "",
        "tool_parameters": {},
        "tool_results": {},
        "response": ""
    }

    logger.debug("Invoking agent — user_id=%s", user_id)
    final_state = await compiled_agent.ainvoke(initial_state)
    reply_text = final_state.get("response") or "I was unable to construct a response."
    logger.info(
        "Agent response ready — user_id=%s route=%s intent=%s reply_len=%d",
        user_id,
        final_state.get("route", "?"),
        final_state.get("intent", "?"),
        len(reply_text),
    )

    async def event_generator():
        words = reply_text.split(" ")
        for i, word in enumerate(words):
            token = f" {word}" if i > 0 else word
            yield f"data: {token}\n\n"
            await asyncio.sleep(0.03)

        async with AsyncSessionLocal() as session:
            await chat_service.save_message(
                session=session,
                user_id=user_id,
                role=MessageRole.assistant,
                content=reply_text
            )
            await session.commit()
        logger.debug("Assistant message persisted — user_id=%s", user_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
