from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/api/v1/users", tags=["users"])

@router.get("/me", response_model=UserRead)
async def get_my_profile(
    clerk_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve the current user's profile based on verified Clerk JWT token."""
    query = select(User).where(User.clerk_id == clerk_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found in database",
        )
        
    return user
