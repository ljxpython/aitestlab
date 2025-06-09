"""
AI测试用例生成API路由
"""

import base64
import json
import uuid
from datetime import datetime
from typing import List, Optional

from autogen_core import CancellationToken, ClosureContext, MessageContext
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from loguru import logger
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.models.chat import FileUpload, TestCaseRequest
from backend.services.testcase_service import (
    RequirementMessage,
    ResponseMessage,
    start_runtime,
    testcase_service,
)

router = APIRouter(prefix="/api/testcase", tags=["testcase"])


class FeedbackRequest(BaseModel):
    """用户反馈请求模型"""

    conversation_id: str
    feedback: str
    round_number: int


@router.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    text_content: Optional[str] = Form(None),
    conversation_id: Optional[str] = Form(None),
):
    """文件上传接口"""
    conversation_id = conversation_id or str(uuid.uuid4())
    logger.info(
        f"收到文件上传请求 | 对话ID: {conversation_id} | 文件数量: {len(files)}"
    )

    try:
        uploaded_files = []

        for file in files:
            # 读取文件内容
            content = await file.read()

            # 检查文件大小（限制为10MB）
            if len(content) > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=413, detail=f"文件 {file.filename} 过大，最大支持10MB"
                )

            # 编码文件内容
            encoded_content = base64.b64encode(content).decode("utf-8")

            file_upload = FileUpload(
                filename=file.filename or "unknown",
                content_type=file.content_type or "application/octet-stream",
                size=len(content),
                content=encoded_content,
            )
            uploaded_files.append(file_upload)

            logger.debug(f"文件上传成功: {file.filename} ({len(content)} bytes)")

        logger.success(f"所有文件上传完成 | 对话ID: {conversation_id}")

        return {
            "conversation_id": conversation_id,
            "files": [
                {"filename": f.filename, "content_type": f.content_type, "size": f.size}
                for f in uploaded_files
            ],
            "text_content": text_content,
            "message": "文件上传成功",
        }

    except Exception as e:
        logger.error(f"文件上传失败 | 对话ID: {conversation_id} | 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generate/sse")
async def generate_testcase_sse(
    conversation_id: Optional[str] = Query(None, description="对话ID"),
    text_content: Optional[str] = Query(None, description="文本内容"),
    round_number: int = Query(1, description="轮次"),
    user_feedback: Optional[str] = Query(None, description="用户反馈"),
):
    """SSE流式生成测试用例 - 仿照examples/agent/testcase.py实现"""
    conversation_id = conversation_id or str(uuid.uuid4())
    logger.info(
        f"收到SSE流式测试用例生成请求 | 对话ID: {conversation_id} | 轮次: {round_number}"
    )

    # 用户输入队列，用于模拟用户交互
    user_input_queue = []
    if user_feedback:
        user_input_queue.append(user_feedback)

    # 前端发送任何智能体执行的结果
    # 将收到的消息发送给前端（浏览器）
    async def collect_result(
        _agent: ClosureContext, message: ResponseMessage, ctx: MessageContext
    ) -> None:
        msg = message.model_dump()
        logger.info(f"[SSE收集] 返回的消息: {msg}")
        # 将消息添加到队列中，稍后发送给前端
        if not hasattr(collect_result, "messages"):
            collect_result.messages = []
        collect_result.messages.append(msg)

    async def _user_input(
        prompt: str, cancellation_token: Optional[CancellationToken] = None
    ) -> str:
        """用户输入函数 - 模拟用户交互"""
        logger.info(f"[SSE用户输入] 收到提示: {prompt}")

        # 如果有预设的用户反馈，返回它
        if user_input_queue:
            user_response = user_input_queue.pop(0)
            logger.info(f"[SSE用户输入] 返回预设反馈: {user_response}")
            return user_response

        # 默认同意
        default_response = "同意"
        logger.info(f"[SSE用户输入] 返回默认响应: {default_response}")
        return default_response

    async def generate():
        try:
            logger.debug(f"开始SSE流式测试用例生成 | 对话ID: {conversation_id}")

            # 初始化消息队列
            collect_result.messages = []

            # 准备需求消息
            requirement = RequirementMessage(
                text_content=text_content or "",
                files=[],  # GET请求不支持文件上传
                conversation_id=conversation_id,
                round_number=round_number,
                user_feedback=user_feedback,
            )

            logger.info(f"[SSE需求] 验证后的消息: {requirement}")

            # 启动运行时
            await start_runtime(
                requirement=requirement,
                collect_result=collect_result,
                user_input_func=_user_input,
            )

            # 发送收集到的所有消息
            for msg in collect_result.messages:
                logger.debug(f"[SSE发送] 消息: {msg}")
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"

            logger.success(
                f"SSE流式测试用例生成完成 | 对话ID: {conversation_id} | 消息数: {len(collect_result.messages)}"
            )

        except Exception as e:
            logger.error(
                f"SSE流式生成过程中出错 | 对话ID: {conversation_id} | 错误: {e}"
            )

            # 发送错误消息
            error_message = {
                "type": "error",
                "content": f"Error: {str(e)}",
                "source": "system",
                "is_final": True,
            }
            yield f"data: {json.dumps(error_message, ensure_ascii=False)}\n\n"

    return EventSourceResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


# 已删除 /generate/stream 接口 - 已被 /generate/sse 接口替代


# 已删除 /generate 接口 - 前端未使用，已被 /generate/sse 接口替代


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """提交用户反馈"""
    logger.info(
        f"收到用户反馈 | 对话ID: {request.conversation_id} | 轮次: {request.round_number}"
    )
    logger.debug(f"反馈内容: {request.feedback}")

    try:
        # 创建测试用例请求
        testcase_request = TestCaseRequest(
            conversation_id=request.conversation_id,
            user_feedback=request.feedback,
            round_number=request.round_number + 1,
        )

        # 检查是否超过最大轮次
        if testcase_request.round_number > testcase_service.max_rounds:
            logger.info(
                f"达到最大轮次 | 对话ID: {request.conversation_id} | 当前轮次: {testcase_request.round_number}"
            )
            return {
                "message": "已达到最大交互轮次",
                "max_rounds_reached": True,
                "conversation_id": request.conversation_id,
                "next_round": testcase_request.round_number,
            }

        logger.success(
            f"反馈提交成功 | 对话ID: {request.conversation_id} | 下一轮次: {testcase_request.round_number}"
        )
        return {
            "message": "反馈提交成功",
            "conversation_id": request.conversation_id,
            "next_round": testcase_request.round_number,
            "max_rounds_reached": False,
        }

    except Exception as e:
        logger.error(f"提交反馈失败 | 对话ID: {request.conversation_id} | 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 已删除 /conversation/{id} GET 接口 - 前端未使用


# 已删除 /conversation/{id} DELETE 接口 - 前端未使用


# 已删除 /stats 接口 - 前端未使用
