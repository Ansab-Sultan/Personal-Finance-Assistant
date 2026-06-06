from fastapi import HTTPException, Request, status
import httpx
from clerk_backend_api.security.types import AuthStatus
from app.core.security import verify_clerk_token
from app.core.database import get_db

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
