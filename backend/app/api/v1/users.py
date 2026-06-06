from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_db_user_id
from app.schemas.user import UserRead
from app.schemas.preference import PreferenceRead, PreferenceUpsert, PreferenceKey
from app.services import memory as memory_service
from app.services import user as user_service

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserRead)
async def get_my_profile(
    clerk_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve the current user's profile based on verified Clerk JWT token."""
    user = await user_service.get_user_by_clerk_id(db, clerk_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found in database",
        )
    return user

@router.get("/me/preferences", response_model=List[PreferenceRead])
async def get_my_preferences(
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve all preferences configured for the current user."""
    return await memory_service.get_preferences(db, user_id)

@router.patch("/me/preferences", response_model=PreferenceRead)
async def upsert_my_preference(
    payload: PreferenceUpsert,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Create or update a preference for the current user, checking value formatting constraints."""
    pref = await memory_service.upsert_preference(db, user_id, payload.key, payload.value)
    await db.commit()
    return pref

@router.delete("/me/preferences/{key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_preference(
    key: PreferenceKey,
    user_id: UUID = Depends(get_db_user_id),
    db: AsyncSession = Depends(get_db)
):
    """Delete a preference key for the current user."""
    deleted = await memory_service.delete_preference(db, user_id, key)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preference key not found"
        )
    await db.commit()
    return None
