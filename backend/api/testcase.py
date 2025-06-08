"""
AI测试用例生成API路由
"""

import base64
import json
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from backend.models.chat import (
    AgentMessage,
    AgentType,
    FileUpload,
    TestCaseRequest,
    TestCaseResponse,
    TestCaseStreamChunk,
)
from backend.services.testcase_service import testcase_service

router = APIRouter(prefix="/api/testcase", tags=["testcase"])


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


@router.post("/generate/stream")
async def generate_testcase_stream(request: TestCaseRequest):
    """流式生成测试用例"""
    conversation_id = request.conversation_id or str(uuid.uuid4())
    logger.info(
        f"收到流式测试用例生成请求 | 对话ID: {conversation_id} | 轮次: {request.round_number}"
    )

    try:

        async def generate():
            try:
                logger.debug(f"开始生成流式测试用例 | 对话ID: {conversation_id}")
                chunk_count = 0

                async for chunk in testcase_service.generate_testcase_stream(request):
                    chunk_count += 1
                    logger.debug(
                        f"生成第 {chunk_count} 个数据块 | 智能体: {chunk.agent_name} | 内容长度: {len(chunk.content)}"
                    )

                    # 发送数据块
                    yield f"data: {chunk.model_dump_json()}\n\n"

                logger.success(
                    f"流式测试用例生成完成 | 对话ID: {conversation_id} | 总块数: {chunk_count}"
                )

            except Exception as e:
                logger.error(
                    f"流式生成过程中出错 | 对话ID: {conversation_id} | 错误: {e}"
                )
                error_chunk = TestCaseStreamChunk(
                    content=f"生成过程中出错: {str(e)}",
                    agent_type=AgentType.USER_PROXY,
                    agent_name="system",
                    conversation_id=conversation_id,
                    round_number=request.round_number,
                    is_complete=True,
                    timestamp=datetime.now(),
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"

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

    except Exception as e:
        logger.error(
            f"流式测试用例生成接口异常 | 对话ID: {conversation_id} | 错误: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate", response_model=TestCaseResponse)
async def generate_testcase(request: TestCaseRequest):
    """普通测试用例生成接口"""
    conversation_id = request.conversation_id or str(uuid.uuid4())
    logger.info(
        f"收到普通测试用例生成请求 | 对话ID: {conversation_id} | 轮次: {request.round_number}"
    )

    try:
        agent_messages = []

        # 收集所有流式响应
        async for chunk in testcase_service.generate_testcase_stream(request):
            if chunk.content and not chunk.is_complete:
                agent_message = AgentMessage(
                    id=str(uuid.uuid4()),
                    content=chunk.content,
                    agent_type=chunk.agent_type,
                    agent_name=chunk.agent_name,
                    timestamp=chunk.timestamp or datetime.now(),
                    conversation_id=conversation_id,
                    round_number=chunk.round_number,
                )
                agent_messages.append(agent_message)

        logger.success(
            f"普通测试用例生成完成 | 对话ID: {conversation_id} | 消息数: {len(agent_messages)}"
        )

        # 判断是否完成（达到最大轮次或用户满意）
        is_complete = request.round_number >= testcase_service.max_rounds

        return TestCaseResponse(
            conversation_id=conversation_id,
            agent_messages=agent_messages,
            is_complete=is_complete,
            round_number=request.round_number,
            max_rounds=testcase_service.max_rounds,
        )

    except Exception as e:
        logger.error(
            f"普通测试用例生成接口异常 | 对话ID: {conversation_id} | 错误: {e}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback")
async def submit_feedback(conversation_id: str, feedback: str, round_number: int):
    """提交用户反馈"""
    logger.info(f"收到用户反馈 | 对话ID: {conversation_id} | 轮次: {round_number}")

    try:
        # 创建反馈请求
        request = TestCaseRequest(
            conversation_id=conversation_id,
            user_feedback=feedback,
            round_number=round_number + 1,
        )

        # 检查是否超过最大轮次
        if request.round_number > testcase_service.max_rounds:
            return {
                "message": "已达到最大交互轮次",
                "max_rounds_reached": True,
                "conversation_id": conversation_id,
            }

        return {
            "message": "反馈提交成功",
            "conversation_id": conversation_id,
            "next_round": request.round_number,
            "max_rounds_reached": False,
        }

    except Exception as e:
        logger.error(f"提交反馈失败 | 对话ID: {conversation_id} | 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str):
    """获取对话历史"""
    logger.info(f"获取对话历史 | 对话ID: {conversation_id}")

    try:
        conversation_state = testcase_service.active_conversations.get(conversation_id)

        if not conversation_state:
            raise HTTPException(status_code=404, detail="对话不存在")

        return {
            "conversation_id": conversation_id,
            "messages": conversation_state.get("messages", []),
            "last_testcases": conversation_state.get("last_testcases", ""),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取对话历史失败 | 对话ID: {conversation_id} | 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversation/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """删除对话"""
    logger.info(f"删除对话 | 对话ID: {conversation_id}")

    try:
        if conversation_id in testcase_service.active_conversations:
            del testcase_service.active_conversations[conversation_id]
            return {"message": "对话删除成功", "conversation_id": conversation_id}
        else:
            raise HTTPException(status_code=404, detail="对话不存在")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除对话失败 | 对话ID: {conversation_id} | 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_testcase_stats():
    """获取测试用例生成统计信息"""
    logger.debug("收到测试用例统计信息请求")

    try:
        active_conversations = len(testcase_service.active_conversations)

        return {
            "active_conversations": active_conversations,
            "max_rounds": testcase_service.max_rounds,
            "service_status": "running",
        }

    except Exception as e:
        logger.error(f"获取统计信息失败 | 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
