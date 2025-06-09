from fastapi import APIRouter

from .api import router as api_router
from .chat import router as chat_router
from .performance import router as performance_router
from .requirements import router as requirements_router
from .testcase import router as testcase_router

agent_router = APIRouter()
agent_router.include_router(requirements_router, tags=["智能体"])
agent_router.include_router(testcase_router, tags=["智能体"])
agent_router.include_router(chat_router, prefix="/chat", tags=["聊天"])
agent_router.include_router(api_router, prefix="/api", tags=["API自动化测试"])
agent_router.include_router(performance_router, tags=["性能测试"])
__all__ = ["agent_router"]
