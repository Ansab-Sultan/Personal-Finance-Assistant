import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

clerk = Clerk(bearer_auth=settings.CLERK_SECRET_KEY)
logger.debug("Clerk SDK client initialized")


def verify_clerk_token(request: httpx.Request):
    """Verify the Clerk session token from the request headers."""
    logger.debug("Verifying Clerk token for %s %s", request.method, str(request.url))
    state = clerk.authenticate_request(
        request,
        AuthenticateRequestOptions(
            authorized_parties=settings.CLERK_AUTHORIZED_PARTIES,
        ),
    )
    return state
