"""
AI测试用例生成API路由 - 重新设计版本
实现两个核心接口：
1. /generate/sse - 启动需求分析和初步用例生成
2. /feedback - 处理用户反馈，支持优化和最终化
"""

import asyncio
import base64
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from loguru import logger
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.models.chat import FileUpload, TestCaseRequest
from backend.services.testcase_service import (
    FeedbackMessage,
    RequirementMessage,
    testcase_runtime,
    testcase_service,
)

router = APIRouter(prefix="/api/testcase", tags=["testcase"])


class FeedbackRequest(BaseModel):
    """用户反馈请求模型"""

    conversation_id: str
    feedback: str
    round_number: int
    previous_testcases: Optional[str] = ""


class GenerateRequest(BaseModel):
    """生成请求模型"""

    conversation_id: Optional[str] = None
    text_content: Optional[str] = None
    files: Optional[List[FileUpload]] = None
    round_number: int = 1


class StreamingGenerateRequest(BaseModel):
    """流式生成请求模型"""

    conversation_id: Optional[str] = None
    text_content: Optional[str] = None
    files: Optional[List[FileUpload]] = None
    file_paths: Optional[List[str]] = None  # 新增：支持文件路径列表
    round_number: int = 1
    enable_streaming: bool = True


@router.post("/upload")
async def upload_files(
    user_id: int = Query(default=1, description="用户ID"),
    files: List[UploadFile] = File(...),
):
    """
    文件上传接口 - 参考examples实现

    处理文件上传并返回存储路径，供后续文件解析使用
    """
    logger.info(
        f"📁 [文件上传] 收到文件上传请求 | 用户ID: {user_id} | 文件数量: {len(files)}"
    )

    try:
        from pathlib import Path

        import aiofiles

        uploaded_files = []

        # 创建用户专属上传目录
        upload_dir = Path("uploads") / str(user_id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"   📂 上传目录: {upload_dir}")

        for i, file in enumerate(files):
            logger.info(f"   📄 处理文件 {i+1}: {file.filename}")

            # 文件类型验证（可选，当前注释掉以支持更多格式）
            # ALLOWED_TYPES = [
            #     "application/pdf",
            #     "application/msword",
            #     "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            #     "text/plain"
            # ]
            # if file.content_type not in ALLOWED_TYPES:
            #     raise HTTPException(400, detail=f"不支持的文件类型: {file.content_type}")

            # 生成唯一文件名
            file_ext = Path(file.filename).suffix if file.filename else ""
            uuid_name = f"{uuid.uuid4().hex}{file_ext}"
            file_path = upload_dir / uuid_name
            logger.debug(f"   💾 文件保存路径: {file_path}")

            # 流式写入文件并控制大小
            max_size = 10 * 1024 * 1024  # 10MB
            total_size = 0

            async with aiofiles.open(file_path, "wb") as buffer:
                while chunk := await file.read(8192):
                    total_size += len(chunk)
                    if total_size > max_size:
                        await buffer.close()
                        file_path.unlink(missing_ok=True)
                        raise HTTPException(
                            413, detail=f"文件 {file.filename} 大小超过10MB限制"
                        )
                    await buffer.write(chunk)

            # 构建文件信息
            file_info = {
                "filePath": file_path.as_posix(),  # 文件完整路径
                "fileId": uuid_name,  # 唯一文件ID
                "fileName": file.filename,  # 原始文件名
                "contentType": file.content_type,  # 文件类型
                "size": total_size,  # 文件大小
            }
            uploaded_files.append(file_info)

            logger.success(f"   ✅ 文件上传成功: {file.filename} -> {file_path}")

        logger.success(
            f"🎉 [文件上传] 所有文件上传完成 | 用户ID: {user_id} | 成功: {len(uploaded_files)} 个"
        )

        return {
            "success": True,
            "message": "文件上传成功",
            "user_id": user_id,
            "files": uploaded_files,
            "total_files": len(uploaded_files),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [文件上传] 文件上传失败 | 用户ID: {user_id} | 错误: {e}")
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.post("/generate/streaming")
async def generate_testcase_streaming(request: StreamingGenerateRequest):
    """
    流式生成测试用例接口 - POST版本

    功能：启动需求分析和初步用例生成，返回流式输出
    流程：用户输入 → 需求分析智能体 → 测试用例生成智能体 → 流式SSE返回

    支持的流式输出类型：
    1. streaming_chunk - 智能体的流式输出块 (类似 ModelClientStreamingChunkEvent)
    2. text_message - 智能体的完整输出 (类似 TextMessage)
    3. task_result - 包含所有智能体输出的最终结果 (类似 TaskResult)

    Args:
        request: 流式生成请求对象

    Returns:
        EventSourceResponse: SSE流式响应，实时返回智能体处理结果
    """
    # 生成或使用提供的对话ID
    conversation_id = request.conversation_id or str(uuid.uuid4())

    logger.info(f"🚀 [API-流式生成] 收到流式测试用例生成请求")
    logger.info(f"   📋 对话ID: {conversation_id}")
    logger.info(f"   📝 文本内容长度: {len(request.text_content or '')}")
    logger.info(f"   📎 文件数量: {len(request.files) if request.files else 0}")
    logger.info(f"   🔢 轮次: {request.round_number}")
    logger.info(f"   🌊 流式模式: {request.enable_streaming}")
    logger.info(f"   🌐 请求方法: POST /api/testcase/generate/streaming")

    # 创建需求消息对象
    logger.info(f"📦 [API-流式生成] 创建需求消息对象 | 对话ID: {conversation_id}")
    requirement = RequirementMessage(
        text_content=request.text_content or "",
        files=request.files or [],
        file_paths=request.file_paths or [],  # 新增：支持文件路径
        conversation_id=conversation_id,
        round_number=request.round_number,
    )
    logger.debug(f"   📋 需求消息: {requirement}")
    logger.success(
        f"✅ [API-流式生成] 需求消息对象创建完成 | 对话ID: {conversation_id}"
    )

    async def generate():
        """
        流式SSE生成器函数

        支持AutoGen风格的流式输出：
        1. streaming_chunk - 模拟 ModelClientStreamingChunkEvent
        2. text_message - 模拟 TextMessage
        3. task_result - 模拟 TaskResult

        Returns:
            AsyncGenerator: SSE格式的数据流
        """
        try:
            logger.info(
                f"🌊 [流式SSE生成器] 启动流式生成器 | 对话ID: {conversation_id}"
            )

            # 启动流式生成
            logger.info(
                f"🚀 [流式SSE生成器] 启动流式测试用例生成 | 对话ID: {conversation_id}"
            )

            stream_count = 0
            async for stream_data in testcase_service.start_streaming_generation(
                requirement
            ):
                stream_count += 1
                stream_type = stream_data.get("type", "unknown")
                source = stream_data.get("source", "unknown")

                logger.info(f"📤 [流式SSE生成器] 发送流式数据 #{stream_count}")
                logger.info(f"   🏷️  类型: {stream_type}")
                logger.info(f"   🤖 来源: {source}")
                logger.debug(
                    f"   📄 内容长度: {len(str(stream_data.get('content', '')))}"
                )

                # 根据类型添加特殊标识
                if stream_type == "streaming_chunk":
                    # 流式输出块
                    content = stream_data.get("content", "")
                    logger.info(f"   📡 流式块: {source} | 内容: {content}")
                elif stream_type == "text_message":
                    # 智能体完整消息
                    content = stream_data.get("content", "")
                    logger.info(
                        f"   📝 完整消息: {source} | 内容长度: {len(content)} | 完整内容: {content}"
                    )
                elif stream_type == "task_result":
                    # 任务结果
                    logger.info(
                        f"   🏁 任务结果: {len(stream_data.get('messages', []))} 条消息"
                    )

                # 确保每个流式数据都包含conversation_id
                stream_data["conversation_id"] = conversation_id

                # 发送SSE数据 - EventSourceResponse会自动添加data:前缀
                sse_data = json.dumps(stream_data, ensure_ascii=False)
                yield f"{sse_data}"
                logger.debug(f"   📡 SSE数据已发送: {len(sse_data)} 字符")

                # 如果是任务结果，表示完成
                if stream_type == "task_result":
                    logger.success(
                        f"🎉 [流式SSE生成器] 任务完成 | 对话ID: {conversation_id}"
                    )
                    break

            logger.success(
                f"🎉 [流式SSE生成器] 流式生成完成 | 对话ID: {conversation_id}"
            )
            logger.info(f"   📊 总流式数据: {stream_count} 条")

        except Exception as e:
            logger.error(
                f"❌ [流式SSE生成器] 生成过程发生错误 | 对话ID: {conversation_id}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📄 错误详情: {str(e)}")
            logger.error(f"   📍 错误位置: 流式SSE生成器")

            # 发送错误消息
            error_message = {
                "type": "error",
                "source": "system",
                "content": f"❌ 流式生成失败: {str(e)}",
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
            }
            error_data = json.dumps(error_message, ensure_ascii=False)
            yield f"{error_data}"
            logger.debug(f"   📡 错误消息已发送: {error_data}")

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


@router.post("/feedback/streaming")
async def submit_feedback_streaming(request: FeedbackRequest):
    """
    流式处理用户反馈接口 - POST版本

    功能：根据用户反馈决定后续流程，返回流式输出
    - 当输入意见时：用户反馈 + 用例评审优化智能体，发布消息：用例优化
    - 当输入同意时：返回最终的结果，完成数据库落库，发布消息：用例结果

    支持的流式输出类型：
    1. streaming_chunk - 智能体的流式输出块
    2. text_message - 智能体的完整输出
    3. task_result - 包含所有智能体输出的最终结果

    Args:
        request: 用户反馈请求对象，包含反馈内容和相关信息

    Returns:
        EventSourceResponse: SSE流式响应，实时返回智能体处理结果
    """
    logger.info(f"💬 [API-流式反馈] 收到流式用户反馈请求")
    logger.info(f"   📋 对话ID: {request.conversation_id}")
    logger.info(f"   🔢 当前轮次: {request.round_number}")
    logger.info(f"   💭 反馈内容: {request.feedback}")
    logger.info(f"   📄 之前测试用例长度: {len(request.previous_testcases or '')}")
    logger.info(f"   🌐 请求方法: POST /api/testcase/feedback/streaming")

    # 检查轮次限制
    if request.round_number >= testcase_service.max_rounds:
        logger.warning(
            f"⚠️  [API-流式反馈] 达到最大轮次限制 | 对话ID: {request.conversation_id}"
        )

        async def error_generator():
            error_data = {
                "type": "error",
                "source": "system",
                "content": "已达到最大交互轮次",
                "conversation_id": request.conversation_id,
                "max_rounds_reached": True,
                "timestamp": datetime.now().isoformat(),
            }
            yield f"{json.dumps(error_data, ensure_ascii=False)}"

        return EventSourceResponse(
            error_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )

    # 创建反馈消息对象
    logger.info(
        f"📦 [API-流式反馈] 创建反馈消息对象 | 对话ID: {request.conversation_id}"
    )
    next_round = request.round_number + 1
    feedback = FeedbackMessage(
        feedback=request.feedback,
        conversation_id=request.conversation_id,
        round_number=next_round,
        previous_testcases=request.previous_testcases,
    )
    logger.debug(f"   📋 反馈消息: {feedback}")

    async def generate():
        """
        流式反馈处理生成器函数

        Returns:
            AsyncGenerator: SSE格式的数据流
        """
        try:
            logger.info(
                f"🌊 [流式反馈生成器] 启动流式反馈处理 | 对话ID: {request.conversation_id}"
            )

            # 分析反馈类型
            is_approval = (
                "同意" in request.feedback or "APPROVE" in request.feedback.upper()
            )
            logger.info(f"🔍 [流式反馈生成器] 反馈类型分析")
            logger.info(f"   📝 原始反馈: '{request.feedback}'")
            logger.info(f"   ✅ 是否同意: {is_approval}")

            # 启动流式反馈处理
            stream_count = 0
            async for stream_data in testcase_service.process_streaming_feedback(
                feedback
            ):
                stream_count += 1
                stream_type = stream_data.get("type", "unknown")
                source = stream_data.get("source", "unknown")

                logger.info(f"📤 [流式反馈生成器] 发送流式数据 #{stream_count}")
                logger.info(f"   🏷️  类型: {stream_type}")
                logger.info(f"   🤖 来源: {source}")
                logger.debug(
                    f"   📄 内容长度: {len(str(stream_data.get('content', '')))}"
                )

                # 根据类型添加特殊标识
                if stream_type == "streaming_chunk":
                    # 流式输出块
                    content = stream_data.get("content", "")
                    logger.info(f"   📡 流式块: {source} | 内容: {content}")
                elif stream_type == "text_message":
                    # 智能体完整消息
                    content = stream_data.get("content", "")
                    logger.info(
                        f"   📝 完整消息: {source} | 内容长度: {len(content)} | 完整内容: {content}"
                    )
                elif stream_type == "task_result":
                    # 任务结果
                    logger.info(
                        f"   🏁 任务结果: {len(stream_data.get('messages', []))} 条消息"
                    )

                # 确保每个流式数据都包含conversation_id
                stream_data["conversation_id"] = request.conversation_id

                # 发送SSE数据 - EventSourceResponse会自动添加data:前缀
                sse_data = json.dumps(stream_data, ensure_ascii=False)
                yield f"{sse_data}"
                logger.debug(f"   📡 SSE数据已发送: {len(sse_data)} 字符")

                # 如果是任务结果，表示完成
                if stream_type == "task_result":
                    logger.success(
                        f"🎉 [流式反馈生成器] 反馈处理完成 | 对话ID: {request.conversation_id}"
                    )
                    break

            logger.success(
                f"🎉 [流式反馈生成器] 流式反馈处理完成 | 对话ID: {request.conversation_id}"
            )
            logger.info(f"   📊 总流式数据: {stream_count} 条")

        except Exception as e:
            logger.error(
                f"❌ [流式反馈生成器] 处理过程发生错误 | 对话ID: {request.conversation_id}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📄 错误详情: {str(e)}")
            logger.error(f"   📍 错误位置: 流式反馈生成器")

            # 发送错误消息
            error_message = {
                "type": "error",
                "source": "system",
                "content": f"❌ 反馈处理失败: {str(e)}",
                "conversation_id": request.conversation_id,
                "timestamp": datetime.now().isoformat(),
            }
            error_data = json.dumps(error_message, ensure_ascii=False)
            yield f"{error_data}"
            logger.debug(f"   📡 错误消息已发送: {error_data}")

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


# 已删除 /conversation/{id} GET 接口 - 前端未使用


# 已删除 /conversation/{id} DELETE 接口 - 前端未使用


# 已删除 /stats 接口 - 前端未使用


# 旧的GET接口已移除，现在使用POST流式接口


@router.get("/history/{conversation_id}")
async def get_conversation_history(conversation_id: str):
    """
    获取对话历史接口

    功能：获取指定对话的完整历史记录和消息列表

    Args:
        conversation_id: 对话唯一标识符

    Returns:
        dict: 包含历史记录和消息列表的响应数据
    """
    logger.info(f"📚 [API-历史接口] 收到获取对话历史请求")
    logger.info(f"   📋 对话ID: {conversation_id}")
    logger.info(f"   🌐 请求方法: GET /api/testcase/history/{conversation_id}")

    try:
        # 步骤1: 获取历史记录
        logger.info(
            f"📖 [API-历史接口] 步骤1: 获取历史记录 | 对话ID: {conversation_id}"
        )
        history = await testcase_service.get_history(conversation_id)
        logger.info(f"   📊 历史记录数量: {len(history)}")
        logger.debug(f"   📋 历史记录: {history}")

        # 步骤2: 获取消息列表
        logger.info(
            f"📨 [API-历史接口] 步骤2: 获取消息列表 | 对话ID: {conversation_id}"
        )
        messages = testcase_service.get_messages(conversation_id)
        logger.info(f"   📊 消息数量: {len(messages)}")

        # 统计消息类型
        message_types = {}
        for msg in messages:
            msg_type = msg.get("message_type", "unknown")
            message_types[msg_type] = message_types.get(msg_type, 0) + 1
        logger.info(f"   📊 消息类型统计: {message_types}")

        # 步骤3: 构造响应数据
        logger.info(
            f"📋 [API-历史接口] 步骤3: 构造响应数据 | 对话ID: {conversation_id}"
        )
        response_data = {
            "conversation_id": conversation_id,
            "history": history,
            "messages": messages,
            "total_messages": len(messages),
            "total_history": len(history),
            "message_types": message_types,
        }
        logger.debug(f"   📦 响应数据: {response_data}")

        logger.success(
            f"✅ [API-历史接口] 对话历史获取成功 | 对话ID: {conversation_id}"
        )
        logger.info(f"   📊 历史记录: {len(history)} 条")
        logger.info(f"   📊 消息记录: {len(messages)} 条")

        return response_data

    except Exception as e:
        logger.error(f"❌ [API-历史接口] 获取对话历史失败 | 对话ID: {conversation_id}")
        logger.error(f"   🐛 错误类型: {type(e).__name__}")
        logger.error(f"   📄 错误详情: {str(e)}")
        logger.error(f"   📍 错误位置: 历史接口处理过程")

        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversation/{conversation_id}")
async def clear_conversation_history(conversation_id: str):
    """
    清除对话历史接口

    功能：清除指定对话的所有历史记录和消息

    Args:
        conversation_id: 对话唯一标识符

    Returns:
        dict: 清除结果
    """
    logger.info(f"🗑️ [API-清除历史] 收到清除对话历史请求")
    logger.info(f"   📋 对话ID: {conversation_id}")
    logger.info(f"   🌐 请求方法: DELETE /api/testcase/conversation/{conversation_id}")

    try:
        # 清除历史记录和消息
        await testcase_service.clear_conversation(conversation_id)

        logger.success(
            f"✅ [API-清除历史] 对话历史清除成功 | 对话ID: {conversation_id}"
        )

        return {
            "success": True,
            "message": "对话历史已清除",
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"❌ [API-清除历史] 清除对话历史失败 | 对话ID: {conversation_id}")
        logger.error(f"   🐛 错误类型: {type(e).__name__}")
        logger.error(f"   📄 错误详情: {str(e)}")
        logger.error(f"   📍 错误位置: 清除历史接口处理过程")

        raise HTTPException(status_code=500, detail=str(e))
