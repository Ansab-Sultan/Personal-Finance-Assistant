from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.chat import ChatMessage, MessageRole
from app.core.logger import get_logger
from app.services.llm import GeminiClient, llm_client
from app.services.memory import get_preferences

logger = get_logger(__name__)

RECENT_TURNS = 20
SUMMARIZE_THRESHOLD = 40

async def save_message(
    session: AsyncSession,
    user_id: UUID,
    role: MessageRole,
    content: str,
    is_summarized: bool = False
) -> ChatMessage:
    """Save a chat message or summary turn to the database."""
    msg = ChatMessage(
        user_id=user_id,
        role=role,
        content=content,
        is_summarized=is_summarized
    )
    session.add(msg)
    await session.flush()
    logger.debug("Message saved — user_id=%s role=%s content_len=%d", user_id, role, len(content))
    return msg

async def count_unsummarized(session: AsyncSession, user_id: UUID) -> int:
    """Count user and assistant turns that have not been summarized yet."""
    query = select(func.count(ChatMessage.id)).where(
        ChatMessage.user_id == user_id,
        ChatMessage.role.in_([MessageRole.user, MessageRole.assistant]),
        ChatMessage.is_summarized == False
    )
    result = await session.execute(query)
    return result.scalar_one()

async def get_recent_messages(
    session: AsyncSession,
    user_id: UUID,
    n: int = RECENT_TURNS
) -> List[ChatMessage]:
    """Retrieve the last n unsummarized user and assistant messages in chronological order."""
    query = select(ChatMessage).where(
        ChatMessage.user_id == user_id,
        ChatMessage.role.in_([MessageRole.user, MessageRole.assistant]),
        ChatMessage.is_summarized == False
    ).order_by(ChatMessage.created_at.desc()).limit(n)
    
    result = await session.execute(query)
    messages = list(result.scalars().all())
    messages.reverse()
    return messages

async def get_summary_row(session: AsyncSession, user_id: UUID) -> Optional[ChatMessage]:
    """Retrieve the single system message row containing the user's running summary."""
    query = select(ChatMessage).where(
        ChatMessage.user_id == user_id,
        ChatMessage.role == MessageRole.system
    ).order_by(ChatMessage.created_at.desc())
    result = await session.execute(query)
    return result.scalars().first()

async def upsert_summary(session: AsyncSession, user_id: UUID, content: str) -> ChatMessage:
    """Insert a running summary row or update it if it already exists."""
    summary_row = await get_summary_row(session, user_id)
    if summary_row:
        summary_row.content = content
        await session.execute(
            delete(ChatMessage).where(
                ChatMessage.user_id == user_id,
                ChatMessage.role == MessageRole.system,
                ChatMessage.id != summary_row.id
            )
        )
    else:
        summary_row = ChatMessage(
            user_id=user_id,
            role=MessageRole.system,
            content=content,
            is_summarized=True
        )
        session.add(summary_row)
    await session.flush()
    return summary_row

async def mark_messages_as_summarized(session: AsyncSession, message_ids: List[UUID]) -> None:
    """Mark a list of chat message IDs as summarized."""
    if not message_ids:
        return
    query = update(ChatMessage).where(ChatMessage.id.in_(message_ids)).values(is_summarized=True)
    await session.execute(query)

async def maybe_refresh_summary(
    session: AsyncSession,
    user_id: UUID,
    llm: GeminiClient
) -> Optional[str]:
    """Check unsummarized count and trigger a summary consolidation if the threshold is crossed."""
    unsummarized_count = await count_unsummarized(session, user_id)
    summary_row = await get_summary_row(session, user_id)
    existing_summary = summary_row.content if summary_row else ""

    if unsummarized_count <= SUMMARIZE_THRESHOLD:
        logger.debug(
            "Summary not refreshed — user_id=%s unsummarized_count=%d (threshold=%d)",
            user_id, unsummarized_count, SUMMARIZE_THRESHOLD
        )
        return existing_summary if existing_summary else None
        
    query = select(ChatMessage).where(
        ChatMessage.user_id == user_id,
        ChatMessage.role.in_([MessageRole.user, MessageRole.assistant]),
        ChatMessage.is_summarized == False
    ).order_by(ChatMessage.created_at.asc())
    
    result = await session.execute(query)
    all_unsummarized = list(result.scalars().all())
    
    if len(all_unsummarized) <= RECENT_TURNS:
        return existing_summary if existing_summary else None
        
    turns_to_summarize = all_unsummarized[:-RECENT_TURNS]

    logger.info(
        "Refreshing conversation summary — user_id=%s turns_to_summarize=%d",
        user_id, len(turns_to_summarize)
    )
    new_summary = await llm.summarize(
        existing_summary=existing_summary,
        old_turns=[
            {"role": t.role.value, "content": t.content}
            for t in turns_to_summarize
        ]
    )

    await upsert_summary(session, user_id, new_summary)
    await mark_messages_as_summarized(session, [t.id for t in turns_to_summarize])
    logger.debug("Summary committed — user_id=%s", user_id)

    return new_summary

async def get_chat_context(
    session: AsyncSession,
    user_id: UUID
) -> tuple[List[Dict[str, str]], str]:
    """Fetch user preferences, system instructions, running summaries, and recent messages for the LLM context."""
    summary = await maybe_refresh_summary(session, user_id, llm_client)
    prefs = await get_preferences(session, user_id)
    prefs_str = "\n".join([f"- {p.key}: {p.value}" for p in prefs])
    
    system_instruction = (
        "You are Personal Finance Assistant, a premium personal finance assistant. "
        "A user is chatting with you to get financial insights. "
        "Be concise, direct, helpful, and wowed by clean financial design.\n\n"
    )
    if prefs_str:
        system_instruction += f"User Preferences:\n{prefs_str}\n\n"
    if summary:
        system_instruction += f"Summary of earlier conversation:\n{summary}\n\n"
        
    recent = await get_recent_messages(session, user_id)
    messages = [{"role": r.role.value, "content": r.content} for r in recent]
    
    return messages, system_instruction

async def get_unsummarized_history(
    session: AsyncSession,
    user_id: UUID
) -> List[ChatMessage]:
    """Retrieve all unsummarized user and assistant messages in chronological order."""
    query = select(ChatMessage).where(
        ChatMessage.user_id == user_id,
        ChatMessage.role.in_([MessageRole.user, MessageRole.assistant]),
        ChatMessage.is_summarized == False
    ).order_by(ChatMessage.created_at.asc())
    result = await session.execute(query)
    return list(result.scalars().all())


