from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.messages import AIMessage
from runtime_service.runtime.runtime_request_resolver import resolve_trusted_runtime_context

MULTIMODAL_ATTACHMENTS_KEY = "multimodal_attachments"
REQUIREMENT_ANALYSIS_SKILL_PATH = "/skills/requirement-analysis/SKILL.md"
READ_FILE_TOOL_NAME = "read_file"
QUERY_PROJECT_KNOWLEDGE_TOOL_NAME = "query_project_knowledge"
_TEST_CASE_GENERATION_PATTERN = re.compile(
    r"(生成|设计|编写|输出|给出).{0,24}(测试用例|测试案例|用例)"
    r"|"
    r"(测试用例|测试案例|用例).{0,24}(生成|设计|编写|输出|给出)"
)


def _get_message_role(message: Any) -> str | None:
    value = getattr(message, "role", None)
    if isinstance(value, str):
        return value
    if isinstance(message, Mapping):
        value = message.get("role")
        return value if isinstance(value, str) else None
    return None


def _get_message_type(message: Any) -> str | None:
    value = getattr(message, "type", None)
    if isinstance(value, str):
        return value
    if isinstance(message, Mapping):
        value = message.get("type")
        return value if isinstance(value, str) else None
    return None


def _get_message_name(message: Any) -> str | None:
    value = getattr(message, "name", None)
    if isinstance(value, str):
        return value
    if isinstance(message, Mapping):
        value = message.get("name")
        return value if isinstance(value, str) else None
    return None


def _get_message_content(message: Any) -> Any:
    if hasattr(message, "content"):
        return getattr(message, "content")
    if isinstance(message, Mapping):
        return message.get("content")
    return None


def _extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return " ".join(content.split()).strip()
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            normalized = " ".join(item.split()).strip()
            if normalized:
                parts.append(normalized)
            continue
        if not isinstance(item, Mapping):
            continue
        text = item.get("text")
        if isinstance(text, str):
            normalized = " ".join(text.split()).strip()
            if normalized:
                parts.append(normalized)
    return " ".join(parts).strip()


def _content_has_attachment(content: Any) -> bool:
    if not isinstance(content, list):
        return False
    for item in content:
        if not isinstance(item, Mapping):
            continue
        if item.get("type") in {"file", "image"}:
            return True
    return False


def _state_has_attachment_context(state: Any) -> bool:
    if not isinstance(state, Mapping):
        return False
    attachments = state.get(MULTIMODAL_ATTACHMENTS_KEY)
    return isinstance(attachments, list) and len(attachments) > 0


def _get_latest_user_message(messages: Sequence[Any]) -> Any | None:
    for message in reversed(messages):
        message_type = _get_message_type(message)
        message_role = _get_message_role(message)
        if message_type in {"human", "user"} or message_role == "user":
            return message
    return None


def _get_latest_user_message_index(messages: Sequence[Any]) -> int | None:
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        message_type = _get_message_type(message)
        message_role = _get_message_role(message)
        if message_type in {"human", "user"} or message_role == "user":
            return index
    return None


def _collect_tool_names(messages: Sequence[Any]) -> list[str]:
    tool_names: list[str] = []
    for message in messages:
        tool_calls = getattr(message, "tool_calls", None)
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if isinstance(tool_call, Mapping):
                    name = tool_call.get("name")
                else:
                    name = getattr(tool_call, "name", None)
                if isinstance(name, str) and name.strip():
                    tool_names.append(name)

        message_type = _get_message_type(message)
        message_role = _get_message_role(message)
        if message_type == "tool" or message_role == "tool":
            name = _get_message_name(message)
            if isinstance(name, str) and name.strip():
                tool_names.append(name)
    return tool_names


def _resolve_project_id(request: ModelRequest) -> str | None:
    runtime = getattr(request, "runtime", None)
    try:
        return resolve_trusted_runtime_context(runtime).project_id
    except ValueError:
        return None


def _build_synthesized_tool_response(name: str, args: dict[str, Any]) -> ModelResponse:
    return ModelResponse(
        result=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": name,
                        "args": args,
                        "id": f"guard_{name}",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    )


class TestCaseKnowledgeQueryGuardMiddleware(AgentMiddleware[Any, Any]):
    """对“无附件业务用例生成”施加硬性知识检索约束。"""

    @staticmethod
    def _requires_guard(request: ModelRequest) -> tuple[bool, str]:
        messages = list(request.messages or [])
        latest_user_message = _get_latest_user_message(messages)
        if latest_user_message is None:
            return False, ""

        content = _get_message_content(latest_user_message)
        if _content_has_attachment(content) or _state_has_attachment_context(request.state):
            return False, ""

        latest_user_text = _extract_text_from_content(content)
        if not latest_user_text:
            return False, ""
        if not _TEST_CASE_GENERATION_PATTERN.search(latest_user_text):
            return False, latest_user_text
        return True, latest_user_text

    @staticmethod
    def _current_turn_tool_names(messages: Sequence[Any]) -> list[str]:
        latest_user_index = _get_latest_user_message_index(messages)
        if latest_user_index is None:
            return []
        return _collect_tool_names(messages[latest_user_index + 1 :])

    @staticmethod
    def _filter_tools(request: ModelRequest, *, allowed_names: set[str]) -> ModelRequest:
        filtered_tools = [
            tool
            for tool in request.tools
            if isinstance(getattr(tool, "name", None), str)
            and getattr(tool, "name", "").strip() in allowed_names
        ]
        return request.override(tools=filtered_tools)

    @staticmethod
    def _has_tool_name(response: ModelResponse, tool_name: str) -> bool:
        result = getattr(response, "result", None)
        if not isinstance(result, list):
            return False
        for message in result:
            tool_calls = getattr(message, "tool_calls", None)
            if not isinstance(tool_calls, list):
                continue
            for tool_call in tool_calls:
                if isinstance(tool_call, Mapping):
                    name = tool_call.get("name")
                else:
                    name = getattr(tool_call, "name", None)
                if name == tool_name:
                    return True
        return False

    @staticmethod
    def _missing_tool_message(tool_name: str) -> ModelResponse:
        if tool_name == QUERY_PROJECT_KNOWLEDGE_TOOL_NAME:
            text = (
                "当前请求是无附件业务测试用例生成，但服务未挂载 `query_project_knowledge`，"
                "因此不能基于臆测继续生成。"
            )
        else:
            text = (
                "当前请求命中了无附件业务用例强制流程，但服务未挂载 `read_file`，"
                "无法先读取 requirement-analysis skill。"
            )
        return ModelResponse(result=[AIMessage(content=text)])

    @staticmethod
    def _append_guard_instruction(request: ModelRequest, text: str) -> ModelRequest:
        return request.override(
            system_message=append_to_system_message(request.system_message, text)
        )

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        guarded, latest_user_text = self._requires_guard(request)
        if not guarded:
            return handler(request)

        current_turn_tool_names = set(self._current_turn_tool_names(list(request.messages or [])))
        if QUERY_PROJECT_KNOWLEDGE_TOOL_NAME in current_turn_tool_names:
            return handler(request)

        if READ_FILE_TOOL_NAME not in current_turn_tool_names:
            updated_request = self._append_guard_instruction(
                self._filter_tools(request, allowed_names={READ_FILE_TOOL_NAME}),
                "当前请求命中了“无附件业务主题生成测试用例”强制流程。"
                "本轮先读取 `/skills/requirement-analysis/SKILL.md`，完成前禁止生成正式测试用例。",
            )
            read_file_available = any(
                getattr(tool, "name", None) == READ_FILE_TOOL_NAME
                for tool in updated_request.tools
            )
            response = handler(updated_request)
            if self._has_tool_name(response, READ_FILE_TOOL_NAME):
                return response
            if not read_file_available:
                return _build_synthesized_tool_response(
                    READ_FILE_TOOL_NAME,
                    {"file_path": REQUIREMENT_ANALYSIS_SKILL_PATH},
                )
            return _build_synthesized_tool_response(
                READ_FILE_TOOL_NAME,
                {"file_path": REQUIREMENT_ANALYSIS_SKILL_PATH},
            )

        updated_request = self._append_guard_instruction(
            self._filter_tools(request, allowed_names={QUERY_PROJECT_KNOWLEDGE_TOOL_NAME}),
            "当前请求命中了“无附件业务主题生成测试用例”强制流程。"
            "你已读取 requirement-analysis skill，下一步必须先调用 `query_project_knowledge`，"
            "基于命中的项目知识片段再继续生成需求摘要、策略和测试用例。",
        )
        if not any(
            getattr(tool, "name", None) == QUERY_PROJECT_KNOWLEDGE_TOOL_NAME
            for tool in updated_request.tools
        ):
            return self._missing_tool_message(QUERY_PROJECT_KNOWLEDGE_TOOL_NAME)

        response = handler(updated_request)
        if self._has_tool_name(response, QUERY_PROJECT_KNOWLEDGE_TOOL_NAME):
            return response

        project_id = _resolve_project_id(request)
        if not project_id:
            return ModelResponse(
                result=[
                    AIMessage(
                        content=(
                            "当前请求缺少 `project_id`，无法查询项目知识库。"
                            "在无附件场景下，我不能基于猜测生成业务测试用例。"
                        )
                    )
                ]
            )

        return _build_synthesized_tool_response(
            QUERY_PROJECT_KNOWLEDGE_TOOL_NAME,
            {
                "project_id": project_id,
                "query": latest_user_text,
            },
        )

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        guarded, latest_user_text = self._requires_guard(request)
        if not guarded:
            return await handler(request)

        current_turn_tool_names = set(self._current_turn_tool_names(list(request.messages or [])))
        if QUERY_PROJECT_KNOWLEDGE_TOOL_NAME in current_turn_tool_names:
            return await handler(request)

        if READ_FILE_TOOL_NAME not in current_turn_tool_names:
            updated_request = self._append_guard_instruction(
                self._filter_tools(request, allowed_names={READ_FILE_TOOL_NAME}),
                "当前请求命中了“无附件业务主题生成测试用例”强制流程。"
                "本轮先读取 `/skills/requirement-analysis/SKILL.md`，完成前禁止生成正式测试用例。",
            )
            read_file_available = any(
                getattr(tool, "name", None) == READ_FILE_TOOL_NAME
                for tool in updated_request.tools
            )
            response = await handler(updated_request)
            if self._has_tool_name(response, READ_FILE_TOOL_NAME):
                return response
            if not read_file_available:
                return _build_synthesized_tool_response(
                    READ_FILE_TOOL_NAME,
                    {"file_path": REQUIREMENT_ANALYSIS_SKILL_PATH},
                )
            return _build_synthesized_tool_response(
                READ_FILE_TOOL_NAME,
                {"file_path": REQUIREMENT_ANALYSIS_SKILL_PATH},
            )

        updated_request = self._append_guard_instruction(
            self._filter_tools(request, allowed_names={QUERY_PROJECT_KNOWLEDGE_TOOL_NAME}),
            "当前请求命中了“无附件业务主题生成测试用例”强制流程。"
            "你已读取 requirement-analysis skill，下一步必须先调用 `query_project_knowledge`，"
            "基于命中的项目知识片段再继续生成需求摘要、策略和测试用例。",
        )
        if not any(
            getattr(tool, "name", None) == QUERY_PROJECT_KNOWLEDGE_TOOL_NAME
            for tool in updated_request.tools
        ):
            return self._missing_tool_message(QUERY_PROJECT_KNOWLEDGE_TOOL_NAME)

        response = await handler(updated_request)
        if self._has_tool_name(response, QUERY_PROJECT_KNOWLEDGE_TOOL_NAME):
            return response

        project_id = _resolve_project_id(request)
        if not project_id:
            return ModelResponse(
                result=[
                    AIMessage(
                        content=(
                            "当前请求缺少 `project_id`，无法查询项目知识库。"
                            "在无附件场景下，我不能基于猜测生成业务测试用例。"
                        )
                    )
                ]
            )

        return _build_synthesized_tool_response(
            QUERY_PROJECT_KNOWLEDGE_TOOL_NAME,
            {
                "project_id": project_id,
                "query": latest_user_text,
            },
        )


__all__ = [
    "QUERY_PROJECT_KNOWLEDGE_TOOL_NAME",
    "READ_FILE_TOOL_NAME",
    "REQUIREMENT_ANALYSIS_SKILL_PATH",
    "TestCaseKnowledgeQueryGuardMiddleware",
]
