"""API 路由。"""

from fastapi import APIRouter

from backend.api.channel import router as channel_router
from backend.api.chat import router as chat_router
from backend.api.sessions import router as sessions_router
from backend.api.skills import router as skills_router

router = APIRouter()
router.include_router(chat_router, prefix="/chat", tags=["chat"])
router.include_router(sessions_router, prefix="/sessions", tags=["sessions"])
router.include_router(skills_router, prefix="/skills", tags=["skills"])
router.include_router(channel_router, prefix="/channels", tags=["channels"])
