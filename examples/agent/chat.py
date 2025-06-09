import asyncio
import json

from app.core.llms import model_client
from app.core.websocket.base import ConnectionManager
from app.core.websocket.handlers import AIChatHandler
from app.log import logger
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import ModelClientStreamingChunkEvent, TextMessage
from autogen_core.models import SystemMessage, UserMessage
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
manager = ConnectionManager()

# 实现具体的AI客户端
# class OpenAIClient(BaseAIClient):
#     async def generate_response(self, user_input: str):
#         # 这里实现实际的AI调用逻辑
#         yield {"content": "模拟AI响应"}

# ai_handler = AIChatHandler(
#     ai_client=OpenAIClient(),
#     connection_manager=manager
# )


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 接收用户消息
            user_input = await websocket.receive_text()
            logger.info(f"Received message: {user_input}")

            # 发送确认回执
            await manager.send_message(
                {"type": "status", "content": "已收到消息，正在处理..."}, websocket
            )
            # 流式返回AI响应
            # response = model_client.create_stream([SystemMessage(content="你是一个AI助手，请根据用户的问题给出回答。"), UserMessage(content=user_input,source="user")])
            agent = AssistantAgent(
                "assistant", model_client=model_client, model_client_stream=True
            )

            async for chunk in agent.run_stream(task=user_input):
                if isinstance(chunk, TextMessage) and chunk.models_usage is not None:
                    # await websocket.send_text(json.dumps({
                    #     "type": "ai",
                    #     "content": chunk.content
                    # }))
                    pass
                elif isinstance(chunk, ModelClientStreamingChunkEvent):
                    await websocket.send_text(
                        json.dumps({"type": "ai", "content": chunk.content})
                    )
                    pass
                elif isinstance(chunk, TaskResult):
                    logger.info(f"TaskResult: {chunk}")
                    # await websocket.send_text(json.dumps({
                    #     "type": "ai",
                    #     "content": chunk.content
                    # }))

            # # 接收消息
            # data = await websocket.receive_text()
            # logger.info(f"Received message: {data}")
            # message_data = json.loads(data)

            # if message_data.get('type') == 'message':
            #     # 发送用户消息到前端
            #     await manager.send_message({
            #         'type': 'user',
            #         'content': message_data['content']
            #     }, websocket)

            #     # 模拟 AI 响应
            #     await asyncio.sleep(1)  # 模拟处理时间

            #     # 发送 AI 响应
            #     await manager.send_message({
            #         'type': 'ai',
            #         'content': f"收到你的消息: {message_data['content']}"
            #     }, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except json.JSONDecodeError:
        await manager.send_message(
            {"type": "error", "content": "消息格式错误"}, websocket
        )
    except Exception as e:
        await manager.send_message(
            {"type": "error", "content": f"处理消息时出错: {str(e)}"}, websocket
        )
    # await ai_handler.handle_connection(websocket)
