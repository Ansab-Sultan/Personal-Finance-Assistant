import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from app.core.config import settings

clerk = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)

def verify_clerk_token(request: httpx.Request):
    """Verify the Clerk session token from the request headers."""
    state = clerk.authenticate_request(
        request,
        AuthenticateRequestOptions(
            authorized_parties=settings.CLERK_AUTHORIZED_PARTIES,
        ),
    )
    return state
