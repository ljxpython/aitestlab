from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal, cast

from runtime_service.agents.customer_support_agent.prompts import (
    ISSUE_CLASSIFIER_PROMPT,
    RESOLUTION_SPECIALIST_PROMPT,
    WARRANTY_COLLECTOR_PROMPT,
)
from runtime_service.middlewares.multimodal import (
    MultimodalAgentState,
    MultimodalMiddleware,
)
from runtime_service.runtime.context import RuntimeContext
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.messages import SystemMessage, ToolMessage
from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langgraph.types import Command
from typing_extensions import NotRequired

SupportStep = Literal["warranty_collector", "issue_classifier", "resolution_specialist"]
WarrantyStatus = Literal["in_warranty", "out_of_warranty"]
IssueType = Literal["hardware", "software"]


class SupportState(MultimodalAgentState):
    current_step: NotRequired[SupportStep]
    warranty_status: NotRequired[WarrantyStatus]
    issue_type: NotRequired[IssueType]


@tool(
    "record_warranty_status",
    description="Record warranty status and move to issue classification.",
)
def record_warranty_status(
    status: WarrantyStatus, runtime: ToolRuntime[None, SupportState]
) -> Command:
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Warranty status recorded as: {status}",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "warranty_status": status,
            "current_step": "issue_classifier",
        }
    )


@tool("record_issue_type", description="Record issue type and move to resolution step.")
def record_issue_type(
    issue_type: IssueType, runtime: ToolRuntime[None, SupportState]
) -> Command:
    return Command(
        update={
            "messages": [
                ToolMessage(
                    content=f"Issue type recorded as: {issue_type}",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
            "issue_type": issue_type,
            "current_step": "resolution_specialist",
        }
    )


@tool(
    "escalate_to_human", description="Escalate the case to human support with a reason."
)
def escalate_to_human(reason: str) -> str:
    return f"Escalating to human support. Reason: {reason}"


@tool("provide_solution", description="Provide a concrete solution to the customer.")
def provide_solution(solution: str) -> str:
    return f"Solution provided: {solution}"


STEP_CONFIG: dict[SupportStep, dict[str, Any]] = {
    "warranty_collector": {
        "prompt": WARRANTY_COLLECTOR_PROMPT,
        "tools": [record_warranty_status],
        "requires": [],
    },
    "issue_classifier": {
        "prompt": ISSUE_CLASSIFIER_PROMPT,
        "tools": [record_issue_type],
        "requires": ["warranty_status"],
    },
    "resolution_specialist": {
        "prompt": RESOLUTION_SPECIALIST_PROMPT,
        "tools": [provide_solution, escalate_to_human],
        "requires": ["warranty_status", "issue_type"],
    },
}


class StepMiddleware(AgentMiddleware):
    tools = [
        record_warranty_status,
        record_issue_type,
        provide_solution,
        escalate_to_human,
    ]

    @staticmethod
    def _apply_step_config(request: ModelRequest) -> ModelRequest:
        current_step = request.state.get("current_step", "warranty_collector")
        step = str(current_step)
        if step not in STEP_CONFIG:
            raise ValueError(f"Unknown support step: {step}")

        config = cast(dict[str, Any], STEP_CONFIG[cast(SupportStep, step)])
        for key in config["requires"]:
            if request.state.get(key) is None:
                raise ValueError(f"{key} must be set before reaching {step}")

        step_prompt = str(config["prompt"]).format(**request.state)
        existing_prompt = request.system_prompt or ""
        system_prompt = (
            f"{existing_prompt}\n\n{step_prompt}".strip()
            if existing_prompt
            else step_prompt
        )
        return request.override(
            system_message=SystemMessage(content=system_prompt),
            tools=[*(request.tools or []), *list(config["tools"])],
        )

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        return handler(self._apply_step_config(request))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        return await handler(self._apply_step_config(request))


def build_customer_support_agent(
    model: Any,
    base_tools: list[Any] | None = None,
    middleware: list[Any] | None = None,
) -> Any:
    tools = list(base_tools or [])
    return create_agent(
        model=model,
        tools=tools,
        state_schema=SupportState,
        middleware=[*(middleware or []), StepMiddleware(), MultimodalMiddleware()],
        context_schema=RuntimeContext,
        name="customer_support_handoff_demo",
    )
