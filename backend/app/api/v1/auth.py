from fastapi import APIRouter, Header, HTTPException, Request, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError
from app.core.config import settings
from app.core.database import get_db
from app.core.logger import get_logger
from app.services import user as user_service

logger = get_logger(__name__)

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
        logger.warning("Clerk webhook verification failed — svix_id=%s: %s", svix_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Webhook verification failed: {str(exc)}",
        )

    event_type = event.get("type")
    data = event.get("data", {})
    logger.info("Clerk webhook received — event_type=%s svix_id=%s", event_type, svix_id)

    if event_type == "user.created":
        clerk_id = data.get("id")
        email_addresses = data.get("email_addresses", [])
        email = email_addresses[0].get("email_address") if email_addresses else ""

        if not clerk_id or not email:
            logger.warning("Invalid user.created payload — clerk_id=%s email=%s", clerk_id, email)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user creation payload",
            )

        user = await user_service.get_user_by_clerk_id(db, clerk_id)
        if not user:
            await user_service.create_user(db, clerk_id, email)
            logger.info("Created user — clerk_id=%s email=%s", clerk_id, email)
        else:
            await user_service.update_user_email(db, user, email)
            logger.info("Updated email for existing user — clerk_id=%s email=%s", clerk_id, email)

        await db.commit()
        return {"status": "user synced successfully"}

    elif event_type == "user.deleted":
        clerk_id = data.get("id")
        if not clerk_id:
            logger.warning("Invalid user.deleted payload — missing clerk_id")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user deletion payload",
            )

        await user_service.delete_user_by_clerk_id(db, clerk_id)
        await db.commit()
        logger.info("Deleted user — clerk_id=%s", clerk_id)
        return {"status": "user deleted successfully"}

    logger.debug("Unhandled webhook event_type=%s", event_type)
    return {"status": f"unhandled event type: {event_type}"}
