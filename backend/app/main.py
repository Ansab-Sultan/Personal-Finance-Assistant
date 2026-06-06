from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.exceptions import AuthException, auth_exception_handler
from app.routers import auth, users, transactions, budget

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
    
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(transactions.router)
    app.include_router(budget.router)
    
    @app.get("/health")
    async def health_check():
        """Unprotected health check route."""
        return {"status": "ok"}
        
    return app

app = create_app()
