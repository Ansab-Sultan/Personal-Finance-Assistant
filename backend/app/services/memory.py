from typing import List, Optional
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logger import get_logger
from app.models.preference import UserPreference

logger = get_logger(__name__)


async def get_preferences(session: AsyncSession, user_id: UUID) -> List[UserPreference]:
    """Retrieve all preferences configured for a user."""
    query = select(UserPreference).where(UserPreference.user_id == user_id)
    result = await session.execute(query)
    prefs = list(result.scalars().all())
    logger.debug("Fetched %d preferences — user_id=%s", len(prefs), user_id)
    return prefs


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
    val = result.scalar_one_or_none()
    logger.debug("Preference get — user_id=%s key=%s found=%s", user_id, key, val is not None)
    return val


async def upsert_preference(
    session: AsyncSession,
    user_id: UUID,
    key: str,
    value: str
) -> UserPreference:
    """Create or update a user preference (upsert)."""
    query = select(UserPreference).where(
        UserPreference.user_id == user_id,
        UserPreference.key == key
    )
    result = await session.execute(query)
    pref = result.scalar_one_or_none()

    if pref:
        pref.value = value
        logger.debug("Preference updated — user_id=%s key=%s", user_id, key)
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
            logger.info("Preference created — user_id=%s key=%s", user_id, key)
        except IntegrityError:
            result = await session.execute(query)
            pref = result.scalar_one()
            pref.value = value
            await session.flush()
            logger.debug("Preference IntegrityError resolved — user_id=%s key=%s", user_id, key)

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
        logger.info("Preference deleted — user_id=%s key=%s", user_id, key)
        return True
    logger.warning("Preference delete no-op — user_id=%s key=%s not found", user_id, key)
    return False
