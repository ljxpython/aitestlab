import json
import os
import uuid
from pathlib import Path
from typing import Any

import aiofiles
from app.log.log import logger
from app.schemas import Success
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import (
    TextMessage,
    ToolCallSummaryMessage,
    UserInputRequestedEvent,
)
from autogen_core import CancellationToken, ClosureContext, MessageContext
from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from starlette.websockets import WebSocket, WebSocketDisconnect

from .requirement_agents import RequirementFilesMessage, ResponseMessage, start_runtime

router = APIRouter()


async def get_history(history_path: str) -> list[dict[str, Any]]:
    """Get chat history from file."""
    logger.info(f"获取需求分析历史: {history_path}")
    if not os.path.exists(history_path):
        return []
    async with aiofiles.open(history_path, "r") as file:
        return json.loads(await file.read())


@router.get("/requirements/history", summary="获取需求分析历史")
async def history(
    user_id: int = Query(..., description="用户ID"),
) -> list[dict[str, Any]]:
    try:
        return await get_history(str(user_id) + "_history.json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.websocket("/ws/analyze")
async def analyze_requirements(websocket: WebSocket):
    """
    处理 WebSocket 连接，分析需求文档并与前端进行交互。

    :param websocket: 用于与前端通信的 WebSocket 连接。
    """
    # 接受 WebSocket 连接
    await websocket.accept()

    # 将收到的消息发送给前端（浏览器）
    async def collect_result(
        _agent: ClosureContext, message: ResponseMessage, ctx: MessageContext
    ) -> None:
        """
        将代理返回的消息发送给前端。

        :param _agent: 闭包上下文，当前未使用。
        :param message: 响应消息对象。
        :param ctx: 消息上下文，当前未使用。
        """
        # 将响应消息转换为字典
        msg = message.model_dump()
        print("返回的消息：", msg)
        # 将收到的消息以 JSON 格式发送给前端（浏览器）
        await websocket.send_json(msg)

    async def _user_input(
        prompt: str, cancellation_token: CancellationToken | None
    ) -> str:
        """
        等待前端用户输入并返回输入内容。

        :param prompt: 提示信息，当前未使用。
        :param cancellation_token: 取消令牌，当前未使用。
        :return: 用户输入的文本内容。
        """
        # 等待用户输入（代码阻塞执行）,下面的代码的效果类似 input
        data = await websocket.receive_json()
        # 将接收到的数据验证为 TextMessage 对象
        message = TextMessage.model_validate(data)
        return message.content

    try:
        while True:
            # 从 WebSocket 接收前端发送的 JSON 数据
            data = await websocket.receive_json()

            # 创建需求文件消息
            requirement_files = RequirementFilesMessage(
                user_id=str(data.get("userId", "")),
                files=[file["path"] for file in data.get("files", [])],
                content=data.get("content", ""),
                task=data.get("task", "分析需求文档"),
            )

            try:
                # 启动需求分析运行时，传入需求文件消息、结果收集函数和用户输入函数
                await start_runtime(
                    requirement_files=requirement_files,
                    collect_result=collect_result,
                    user_input_func=_user_input,
                )
            except Exception as e:
                # 构建错误消息字典
                error_message = {
                    "type": "error",
                    "content": f"Error: {str(e)}",
                    "source": "system",
                }
                # 发送错误消息给客户端
                await websocket.send_json(error_message)
                # 错误后重新启用输入，提示用户重试
                await websocket.send_json(
                    {
                        "type": "UserInputRequestedEvent",
                        "content": "发生错误，请重试。",
                        "source": "system",
                    }
                )

    except WebSocketDisconnect:
        # 记录客户端断开连接的日志
        logger.info("客户端断开连接")
    except Exception as e:
        # 记录意外错误的日志
        logger.error(f"意外错误: {str(e)}")
        try:
            # 尝试将意外错误消息发送给客户端
            await websocket.send_json(
                {"type": "error", "content": f"意外错误: {str(e)}", "source": "system"}
            )
        except:
            # 若发送失败，忽略异常
            pass
    finally:
        # 关闭 WebSocket 连接
        await websocket.close()


@router.post("/upload", summary="上传文件")
async def upload_file(
    user_id: int = Query(..., description="用户ID"),
    file: UploadFile = File(..., description="上传的文件"),
):
    """处理文件上传并返回存储路径"""
    # 文件类型验证
    # ALLOWED_TYPES = [
    #     "application/pdf",
    #     "application/msword",
    #     "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    #     "text/plain"
    # ]
    # if file.content_type not in ALLOWED_TYPES:
    #     raise HTTPException(400, detail=f"不支持的文件类型: {file.content_type}")

    try:
        upload_dir = Path("uploads") / str(user_id)
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名
        file_ext = Path(file.filename).suffix
        uuid_name = f"{uuid.uuid4().hex}{file_ext}"
        file_path = upload_dir / uuid_name
        logger.info(f"文件上传路径: {file_path}")

        # 流式写入文件并控制大小
        max_size = 10 * 1024 * 1024  # 10MB
        total_size = 0
        async with aiofiles.open(file_path, "wb") as buffer:
            while chunk := await file.read(8192):
                total_size += len(chunk)
                if total_size > max_size:
                    await buffer.close()
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(413, detail="文件大小超过10MB限制")
                await buffer.write(chunk)
        # 将文件转换为html格式
        logger.info(f"文件上传成功")
        return Success(
            data={
                "filePath": file_path.as_posix(),
                "fileId": uuid_name,
                "fileName": file.filename,
            }
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(500, detail="文件上传失败") from e
