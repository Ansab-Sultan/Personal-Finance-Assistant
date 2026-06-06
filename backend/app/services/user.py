from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.user import User

async def get_user_by_clerk_id(db: AsyncSession, clerk_id: str) -> User | None:
    """Retrieve a user by their Clerk ID."""
    query = select(User).where(User.clerk_id == clerk_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, clerk_id: str, email: str) -> User:
    """Create a new user in the database."""
    user = User(clerk_id=clerk_id, email=email)
    db.add(user)
    await db.flush()
    return user

async def update_user_email(db: AsyncSession, user: User, email: str) -> User:
    """Update a user's email."""
    user.email = email
    await db.flush()
    return user

async def delete_user_by_clerk_id(db: AsyncSession, clerk_id: str) -> bool:
    """Delete a user from the database by their Clerk ID."""
    query = delete(User).where(User.clerk_id == clerk_id)
    result = await db.execute(query)
    return result.rowcount > 0
