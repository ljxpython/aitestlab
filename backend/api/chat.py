import json
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from backend.models.chat import ChatRequest, ChatResponse, StreamChunk
from backend.services.autogen_service import autogen_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """流式聊天接口"""
    conversation_id = request.conversation_id or str(uuid.uuid4())
    logger.info(
        f"收到流式聊天请求 | 对话ID: {conversation_id} | 消息: {request.message[:50]}..."
    )

    try:

        async def generate():
            try:
                logger.debug(f"开始生成流式响应 | 对话ID: {conversation_id}")
                chunk_count = 0

                async for chunk in autogen_service.chat_stream(
                    message=request.message,
                    conversation_id=conversation_id,
                    system_message=request.system_message or "你是一个有用的AI助手",
                ):
                    chunk_count += 1
                    logger.debug(
                        f"生成第 {chunk_count} 个数据块 | 内容长度: {len(chunk)}"
                    )

                    # 发送内容块
                    chunk_data = StreamChunk(
                        content=chunk,
                        is_complete=False,
                        conversation_id=conversation_id,
                    )
                    yield f"data: {chunk_data.model_dump_json()}\n\n"

                # 发送完成信号
                final_chunk = StreamChunk(
                    content="", is_complete=True, conversation_id=conversation_id
                )
                yield f"data: {final_chunk.model_dump_json()}\n\n"
                logger.success(
                    f"流式响应完成 | 对话ID: {conversation_id} | 总块数: {chunk_count}"
                )

            except Exception as e:
                logger.error(
                    f"流式响应生成失败 | 对话ID: {conversation_id} | 错误: {e}"
                )
                error_chunk = StreamChunk(
                    content=f"错误: {str(e)}",
                    is_complete=True,
                    conversation_id=conversation_id,
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            },
        )

    except Exception as e:
        logger.error(f"流式聊天接口异常 | 对话ID: {conversation_id} | 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """普通聊天接口"""
    conversation_id = request.conversation_id or str(uuid.uuid4())
    logger.info(
        f"收到普通聊天请求 | 对话ID: {conversation_id} | 消息: {request.message[:50]}..."
    )

    try:
        response_message, conv_id = await autogen_service.chat(
            message=request.message,
            conversation_id=conversation_id,
            system_message=request.system_message,
        )

        logger.success(
            f"普通聊天响应完成 | 对话ID: {conv_id} | 响应长度: {len(response_message)}"
        )

        return ChatResponse(
            message=response_message, conversation_id=conv_id, timestamp=datetime.now()
        )

    except Exception as e:
        logger.error(f"普通聊天接口异常 | 对话ID: {conversation_id} | 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversation/{conversation_id}")
async def clear_conversation(conversation_id: str):
    """清除对话历史"""
    logger.info(f"收到清除对话请求 | 对话ID: {conversation_id}")

    try:
        autogen_service.clear_conversation(conversation_id)
        logger.success(f"对话清除成功 | 对话ID: {conversation_id}")
        return {"message": "对话已清除", "conversation_id": conversation_id}
    except Exception as e:
        logger.error(f"清除对话失败 | 对话ID: {conversation_id} | 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_agent_stats():
    """获取 Agent 统计信息"""
    logger.debug("收到 Agent 统计信息请求")

    try:
        stats = autogen_service.get_agent_stats()
        logger.debug(f"Agent 统计信息: {stats}")
        return stats
    except Exception as e:
        logger.error(f"获取 Agent 统计信息失败 | 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def force_cleanup():
    """强制清理过期的 Agent"""
    logger.info("收到强制清理请求")

    try:
        autogen_service.force_cleanup()
        stats = autogen_service.get_agent_stats()
        logger.success("强制清理完成")
        return {"message": "清理完成", "stats": stats}
    except Exception as e:
        logger.error(f"强制清理失败 | 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
