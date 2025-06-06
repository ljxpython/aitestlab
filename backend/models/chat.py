from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """聊天消息模型"""

    id: Optional[str] = None
    content: str
    role: str = "user"  # user, assistant, system
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    """聊天请求模型"""

    message: str
    conversation_id: Optional[str] = None
    system_message: Optional[str] = "你是一个有用的AI助手"


class ChatResponse(BaseModel):
    """聊天响应模型"""

    message: str
    conversation_id: str
    timestamp: datetime


class StreamChunk(BaseModel):
    """流式响应块"""

    content: str
    is_complete: bool = False
    conversation_id: Optional[str] = None
