import os
import sys
import time

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.exceptions import AuthException, auth_exception_handler
from app.core.logger import get_logger
from app.api.v1 import router as api_v1_router

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Personal Finance Assistant API",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CLERK_AUTHORIZED_PARTIES or ["http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(AuthException, auth_exception_handler)

    app.include_router(api_v1_router)

    @app.on_event("startup")
    async def on_startup() -> None:
        """Log application startup."""
        logger.info("Personal Finance Assistant API starting up — version 0.1.0")

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        """Log application shutdown."""
        logger.info("Personal Finance Assistant API shutting down")

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log each incoming HTTP request and its response status and duration."""
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s → %s (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response

    @app.get("/health")
    async def health_check():
        """Unprotected health check route."""
        logger.debug("Health check requested")
        return {"status": "ok"}

    return app


app = create_app()
