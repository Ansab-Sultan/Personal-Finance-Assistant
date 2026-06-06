from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.preference import UserPreference

async def get_preferences(session: AsyncSession, user_id: UUID) -> List[UserPreference]:
    """Retrieve all preferences configured for a user."""
    query = select(UserPreference).where(UserPreference.user_id == user_id)
    result = await session.execute(query)
    return list(result.scalars().all())

async def get_preference_by_key(
    session: AsyncSession,
    user_id: UUID,
    key: str
) -> Optional[str]:
    """Retrieve the value of a specific preference key for a user."""
    query = select(UserPreference.value).where(
        UserPreference.user_id == user_id,
        UserPreference.key == key
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()

async def upsert_preference(
    session: AsyncSession,
    user_id: UUID,
    key: str,
    value: str
) -> UserPreference:
    """Create or update a user preference (upsert)."""
    from sqlalchemy.exc import IntegrityError
    query = select(UserPreference).where(
        UserPreference.user_id == user_id,
        UserPreference.key == key
    )
    result = await session.execute(query)
    pref = result.scalar_one_or_none()
    
    if pref:
        pref.value = value
    else:
        try:
            async with session.begin_nested():
                pref = UserPreference(
                    user_id=user_id,
                    key=key,
                    value=value
                )
                session.add(pref)
                await session.flush()
        except IntegrityError:
            result = await session.execute(query)
            pref = result.scalar_one()
            pref.value = value
            await session.flush()
            
    return pref

async def delete_preference(
    session: AsyncSession,
    user_id: UUID,
    key: str
) -> bool:
    """Delete a user preference key, returning True if it existed and was deleted."""
    query = select(UserPreference).where(
        UserPreference.user_id == user_id,
        UserPreference.key == key
    )
    result = await session.execute(query)
    pref = result.scalar_one_or_none()
    
    if pref:
        await session.delete(pref)
        return True
    return False
