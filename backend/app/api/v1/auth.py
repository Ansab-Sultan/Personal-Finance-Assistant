from fastapi import APIRouter, Header, HTTPException, Request, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError
from app.core.config import settings
from app.core.database import get_db
from app.services import user as user_service

router = APIRouter(prefix="/auth", tags=["auth"])

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
            
        user = await user_service.get_user_by_clerk_id(db, clerk_id)
        if not user:
            await user_service.create_user(db, clerk_id, email)
        else:
            await user_service.update_user_email(db, user, email)
            
        await db.commit()
        return {"status": "user synced successfully"}
        
    elif event_type == "user.deleted":
        clerk_id = data.get("id")
        if not clerk_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user deletion payload",
            )
            
        await user_service.delete_user_by_clerk_id(db, clerk_id)
        await db.commit()
        return {"status": "user deleted successfully"}
        
    return {"status": f"unhandled event type: {event_type}"}
