from fastapi import Depends, HTTPException, Request, status
import httpx
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from clerk_backend_api.security.types import AuthStatus
from arq import create_pool
from arq.connections import RedisSettings
from app.core.security import verify_clerk_token
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User

async def get_current_user(request: Request) -> str:
    """Validate Clerk token and extract the user's Clerk ID."""
    httpx_req = httpx.Request(
        method=request.method,
        url=str(request.url),
        headers=request.headers.raw,
    )
    try:
        state = verify_clerk_token(httpx_req)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(exc)}",
        )
    if state.status != AuthStatus.SIGNED_IN or not state.payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    clerk_id = state.payload.get("sub")
    if not clerk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user identity",
        )
    return clerk_id

async def get_db_user_id(
    clerk_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> UUID:
    """Dependency to look up the DB internal UUID for the authenticated user."""
    query = select(User.id).where(User.clerk_id == clerk_id)
    result = await db.execute(query)
    user_id = result.scalar_one_or_none()
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not registered in local database",
        )
    return user_id

async def get_redis_pool():
    """Create and yield a Redis pool for arq job enqueuing."""
    pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    try:
        yield pool
    finally:
        await pool.close()
