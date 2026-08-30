from __future__ import annotations

from runtime_service.agents.assistant_agent.prompts import (
    SYSTEM_PROMPT,
    resolve_assistant_system_prompt,
)
from runtime_service.agents.assistant_agent.tools import (
    build_langchain_concepts_demo_tools,
    draft_release_plan,
    lookup_internal_knowledge,
    send_demo_email,
)
from runtime_service.middlewares.multimodal import (
    MultimodalAgentState,
    MultimodalMiddleware,
)
from runtime_service.middlewares.runtime_request import RuntimeRequestMiddleware
from runtime_service.runtime.context import RuntimeContext
from runtime_service.runtime.modeling import resolve_model_by_id
from runtime_service.runtime.runtime_request_resolver import AgentDefaults
from runtime_service.tools.local import get_builtin_tools
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.tools import tool
from runtime_service.conf.settings import get_default_model_id


@tool(
    "submit_high_impact_action",
    description="Submit a high-impact action request for approval before execution.",
)
def submit_high_impact_action(action: str, details: str) -> str:
    return f"Approved execution request: action={action}; details={details}"


ASSISTANT_DEFAULTS = AgentDefaults(
    model_id=get_default_model_id(),
    system_prompt=resolve_assistant_system_prompt(
        SYSTEM_PROMPT,
        demo_enabled=True,
    ),
    temperature=0.2,
    enable_tools=True,
    public_tool_names=("word_count", "utc_now", "to_upper"),
)

BASELINE_MODEL = resolve_model_by_id(ASSISTANT_DEFAULTS.model_id)

ASSISTANT_REQUIRED_TOOLS = [
    lookup_internal_knowledge,
    draft_release_plan,
    send_demo_email,
    *build_langchain_concepts_demo_tools(BASELINE_MODEL),
    submit_high_impact_action,
]

ASSISTANT_PUBLIC_OPTIONAL_TOOLS = get_builtin_tools(
    list(ASSISTANT_DEFAULTS.public_tool_names)
)

graph = create_agent(
    model=BASELINE_MODEL,
    tools=[
        *ASSISTANT_REQUIRED_TOOLS,
        *ASSISTANT_PUBLIC_OPTIONAL_TOOLS,
    ],
    middleware=[
        RuntimeRequestMiddleware(
            defaults=ASSISTANT_DEFAULTS,
            required_tools=ASSISTANT_REQUIRED_TOOLS,
            public_tools=ASSISTANT_PUBLIC_OPTIONAL_TOOLS,
        ),
        HumanInTheLoopMiddleware(
            interrupt_on={
                "submit_high_impact_action": {
                    "allowed_decisions": ["approve", "edit", "reject"],
                    "description": "High-impact action requires human review.",
                }
            },
            description_prefix="Tool execution pending approval",
        ),
        MultimodalMiddleware(),
    ],
    system_prompt=ASSISTANT_DEFAULTS.system_prompt,
    state_schema=MultimodalAgentState,
    context_schema=RuntimeContext,
    name="assistant",
)
