from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logger import get_logger
from app.models.user import User

logger = get_logger(__name__)


async def get_user_by_clerk_id(db: AsyncSession, clerk_id: str) -> User | None:
    """Retrieve a user by their Clerk ID."""
    query = select(User).where(User.clerk_id == clerk_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, clerk_id: str, email: str) -> User:
    """Create a new user in the database."""
    try:
        async with db.begin_nested():
            user = User(clerk_id=clerk_id, email=email)
            db.add(user)
            await db.flush()
        logger.info("User created — clerk_id=%s email=%s", clerk_id, email)
    except IntegrityError:
        query = select(User).where(User.clerk_id == clerk_id)
        result = await db.execute(query)
        user = result.scalar_one()
        user.email = email
        await db.flush()
        logger.debug("User already exists on create — clerk_id=%s (IntegrityError resolved)", clerk_id)
    return user


async def update_user_email(db: AsyncSession, user: User, email: str) -> User:
    """Update a user's email."""
    user.email = email
    await db.flush()
    logger.info("User email updated — clerk_id=%s email=%s", user.clerk_id, email)
    return user


async def delete_user_by_clerk_id(db: AsyncSession, clerk_id: str) -> bool:
    """Delete a user from the database by their Clerk ID."""
    query = delete(User).where(User.clerk_id == clerk_id)
    result = await db.execute(query)
    deleted = result.rowcount > 0
    if deleted:
        logger.info("User deleted — clerk_id=%s", clerk_id)
    else:
        logger.warning("Delete user no-op — clerk_id=%s not found", clerk_id)
    return deleted
