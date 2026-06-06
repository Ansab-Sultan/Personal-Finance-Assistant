from fastapi import APIRouter, Header, HTTPException, Request, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from svix.webhooks import Webhook, WebhookVerificationError
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def clerk_webhook(
    request: Request,
    svix_id: str = Header(..., alias="svix-id"),
    svix_timestamp: str = Header(..., alias="svix-timestamp"),
    svix_signature: str = Header(..., alias="svix-signature"),
    db: AsyncSession = Depends(get_db)
):
    """Handle Clerk user lifecycle webhooks (user.created, user.deleted)."""
    payload = await request.body()
    payload_str = payload.decode("utf-8")
    
    try:
        wh = Webhook(settings.CLERK_WEBHOOK_SIGNING_SECRET)
        headers = {
            "svix-id": svix_id,
            "svix-timestamp": svix_timestamp,
            "svix-signature": svix_signature,
        }
        event = wh.verify(payload_str, headers)
    except WebhookVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook verification failed: {str(exc)}",
        )
    
    event_type = event.get("type")
    data = event.get("data", {})
    
    if event_type == "user.created":
        clerk_id = data.get("id")
        email_addresses = data.get("email_addresses", [])
        email = email_addresses[0].get("email_address") if email_addresses else ""
        
        if not clerk_id or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user creation payload",
            )
            
        query = select(User).where(User.clerk_id == clerk_id)
        result = await db.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(clerk_id=clerk_id, email=email)
            db.add(user)
        else:
            user.email = email
            
        await db.commit()
        return {"status": "user synced successfully"}
        
    elif event_type == "user.deleted":
        clerk_id = data.get("id")
        if not clerk_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user deletion payload",
            )
            
        query = delete(User).where(User.clerk_id == clerk_id)
        await db.execute(query)
        await db.commit()
        return {"status": "user deleted successfully"}
        
    return {"status": f"unhandled event type: {event_type}"}
