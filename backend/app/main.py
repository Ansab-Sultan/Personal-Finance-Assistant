import os
import sys

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.exceptions import AuthException, auth_exception_handler
from app.api.v1 import router as api_v1_router

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Revonix Personal Finance Assistant API",
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
    
    @app.get("/health")
    async def health_check():
        """Unprotected health check route."""
        return {"status": "ok"}
        
    return app

app = create_app()
