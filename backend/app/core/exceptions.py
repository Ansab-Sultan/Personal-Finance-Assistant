from fastapi import Request, status
from fastapi.responses import JSONResponse
from app.core.logger import get_logger

logger = get_logger(__name__)


class AuthException(Exception):
    """Custom exception raised when authentication fails."""
    def __init__(self, detail: str = "Not authenticated"):
        self.detail = detail


async def auth_exception_handler(request: Request, exc: AuthException):
    """Handle custom AuthException and return 401 response."""
    logger.warning("AuthException on %s %s — %s", request.method, request.url.path, exc.detail)
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": exc.detail},
    )


class DuplicateTransactionError(Exception):
    """Raised when attempting to create a duplicate transaction."""
    def __init__(self, existing_transaction) -> None:
        self.existing_transaction = existing_transaction
