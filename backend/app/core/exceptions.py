from fastapi import Request, status
from fastapi.responses import JSONResponse

class AuthException(Exception):
    """Custom exception raised when authentication fails."""
    def __init__(self, detail: str = "Not authenticated"):
        self.detail = detail

async def auth_exception_handler(request: Request, exc: AuthException):
    """Handle custom AuthException and return 401 response."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": exc.detail},
    )
