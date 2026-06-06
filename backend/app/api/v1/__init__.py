"""Version 1 API Router bundling all sub-routers under a unified /api/v1 prefix."""

from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.budget import router as budget_router
from app.api.v1.chat import router as chat_router
from app.api.v1.transactions import router as transactions_router
from app.api.v1.users import router as users_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(budget_router)
router.include_router(chat_router)
router.include_router(transactions_router)
router.include_router(users_router)
