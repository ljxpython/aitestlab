from __future__ import annotations

from typing import Any

from runtime_service.agents.personal_assistant_agent.prompts import (
    CALENDAR_AGENT_PROMPT,
    EMAIL_AGENT_PROMPT,
    SUPERVISOR_PROMPT,
)
from runtime_service.middlewares.runtime_request import RuntimeRequestMiddleware
from runtime_service.middlewares.multimodal import (
    MultimodalAgentState,
    MultimodalMiddleware,
)
from runtime_service.runtime.context import RuntimeContext
from runtime_service.runtime.runtime_request_resolver import (
    AgentDefaults,
    resolve_trusted_runtime_context,
)
from runtime_service.conf.settings import get_default_model_id
from langchain.agents import create_agent
from langchain.tools import ToolRuntime
from langchain_core.tools import tool


@tool(
    "create_calendar_event",
    description="Create a calendar event with ISO datetime inputs.",
)
def create_calendar_event(
    title: str,
    start_time: str,
    end_time: str,
    attendees: list[str],
    location: str = "",
) -> str:
    suffix = f" at {location}" if location else ""
    return (
        f"Event created: {title} from {start_time} to {end_time} "
        f"with {len(attendees)} attendees{suffix}"
    )


@tool(
    "send_email",
    description="Send an email with composed subject, body, recipients, and optional cc.",
)
def send_email(
    to: list[str],
    subject: str,
    body: str,
    cc: list[str] | None = None,
) -> str:
    del body
    cc_list = cc or []
    cc_text = f" (cc: {', '.join(cc_list)})" if cc_list else ""
    return f"Email sent to {', '.join(to)} - Subject: {subject}{cc_text}"


@tool(
    "get_available_time_slots",
    description="Check attendee availability and return candidate time slots.",
)
def get_available_time_slots(
    attendees: list[str], date: str, duration_minutes: int
) -> list[str]:
    del attendees
    del date
    del duration_minutes
    return ["09:00", "14:00", "16:00"]


def _message_to_text(message: Any) -> str:
    text = getattr(message, "text", None)
    if isinstance(text, str) and text.strip():
        return text

    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                maybe = item.get("text")
                if isinstance(maybe, str) and maybe:
                    parts.append(maybe)
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    return str(message)


def _build_specialist_runtime_context(runtime: Any) -> RuntimeContext:
    return resolve_trusted_runtime_context(runtime)


def build_personal_assistant_supervisor_tools(model: Any) -> list[Any]:
    calendar_tools = [create_calendar_event, get_available_time_slots]
    email_tools = [send_email]

    calendar_agent = create_agent(
        model=model,
        tools=calendar_tools,
        system_prompt=CALENDAR_AGENT_PROMPT,
        middleware=[
            RuntimeRequestMiddleware(
                defaults=AgentDefaults(
                    model_id=get_default_model_id(),
                    system_prompt=CALENDAR_AGENT_PROMPT,
                    enable_tools=False,
                ),
                required_tools=calendar_tools,
                public_tools=[],
                allow_internal_context=True,
            )
        ],
        context_schema=RuntimeContext,
        name="calendar_assistant",
    )

    email_agent = create_agent(
        model=model,
        tools=email_tools,
        system_prompt=EMAIL_AGENT_PROMPT,
        middleware=[
            RuntimeRequestMiddleware(
                defaults=AgentDefaults(
                    model_id=get_default_model_id(),
                    system_prompt=EMAIL_AGENT_PROMPT,
                    enable_tools=False,
                ),
                required_tools=email_tools,
                public_tools=[],
                allow_internal_context=True,
            )
        ],
        context_schema=RuntimeContext,
        name="email_assistant",
    )

    @tool(
        "schedule_event",
        description="Use the calendar specialist to handle scheduling requests.",
    )
    def schedule_event(
        request: str,
        runtime: ToolRuntime[RuntimeContext | None, Any],
    ) -> str:
        result = calendar_agent.invoke(
            {"messages": [{"role": "user", "content": request}]},
            context=_build_specialist_runtime_context(runtime),
            config=runtime.config,
        )
        return _message_to_text(result["messages"][-1])

    @tool(
        "manage_email",
        description="Use the email specialist to draft and send message requests.",
    )
    def manage_email(
        request: str,
        runtime: ToolRuntime[RuntimeContext | None, Any],
    ) -> str:
        result = email_agent.invoke(
            {"messages": [{"role": "user", "content": request}]},
            context=_build_specialist_runtime_context(runtime),
            config=runtime.config,
        )
        return _message_to_text(result["messages"][-1])

    return [schedule_event, manage_email]


def build_personal_assistant_agent(
    model: Any,
    base_tools: list[Any] | None = None,
    middleware: list[Any] | None = None,
) -> Any:
    tools = list(base_tools or [])
    tools.extend(build_personal_assistant_supervisor_tools(model))

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SUPERVISOR_PROMPT,
        state_schema=MultimodalAgentState,
        middleware=[*(middleware or []), MultimodalMiddleware()],
        context_schema=RuntimeContext,
        name="personal_assistant_supervisor",
    )
