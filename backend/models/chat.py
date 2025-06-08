from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

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


# AI用例模块相关模型


class AgentType(str, Enum):
    """智能体类型"""

    REQUIREMENT_AGENT = "requirement_agent"
    TESTCASE_AGENT = "testcase_agent"
    USER_PROXY = "user_proxy"


class AgentMessage(BaseModel):
    """智能体消息模型"""

    id: Optional[str] = None
    content: str
    agent_type: AgentType
    agent_name: str
    timestamp: datetime
    conversation_id: str
    round_number: int = 1  # 交互轮次


class FileUpload(BaseModel):
    """文件上传模型"""

    filename: str
    content_type: str
    size: int
    content: str  # base64编码的文件内容或文本内容


class TestCaseRequest(BaseModel):
    """测试用例生成请求"""

    conversation_id: Optional[str] = None
    files: Optional[List[FileUpload]] = None
    text_content: Optional[str] = None
    user_feedback: Optional[str] = None  # 用户反馈
    round_number: int = 1  # 当前交互轮次


class TestCaseResponse(BaseModel):
    """测试用例生成响应"""

    conversation_id: str
    agent_messages: List[AgentMessage]
    is_complete: bool = False
    round_number: int
    max_rounds: int = 3


class TestCaseStreamChunk(BaseModel):
    """测试用例流式响应块"""

    content: str
    agent_type: AgentType
    agent_name: str
    conversation_id: str
    round_number: int
    is_complete: bool = False
    timestamp: Optional[datetime] = None
