from __future__ import annotations

from typing import Any

from runtime_service.agents.assistant_agent.prompts import (
    EMAIL_SPECIALIST_PROMPT,
    KNOWLEDGE_SPECIALIST_PROMPT,
    OPS_SPECIALIST_PROMPT,
)
from langchain.agents import create_agent
from langchain_core.tools import tool
from langgraph.config import get_config
from langgraph.types import interrupt

def _has_runnable_context() -> bool:
    try:
        config = get_config()
    except RuntimeError:
        return False
    configurable = config.get("configurable") if isinstance(config, dict) else None
    return isinstance(configurable, dict) and "__pregel_scratchpad" in configurable


def _build_interrupt_payload(
    action_name: str,
    args: dict[str, Any],
    allowed_decisions: list[str],
    description: str,
) -> dict[str, Any]:
    normalized_args = dict(args)
    return {
        "action_requests": [
            {
                "name": action_name,
                "args": normalized_args,
                "arguments": normalized_args,
                "description": description,
            }
        ],
        "review_configs": [
            {
                "action_name": action_name,
                "allowed_decisions": allowed_decisions,
            }
        ],
    }


def _extract_decision(resume_value: Any) -> dict[str, Any]:
    if isinstance(resume_value, dict):
        decisions = resume_value.get("decisions")
        if isinstance(decisions, list) and decisions and isinstance(decisions[0], dict):
            return dict(decisions[0])
        if isinstance(resume_value.get("type"), str):
            return dict(resume_value)
    return {"type": "approve"}


def _resolve_decision(
    *,
    action_name: str,
    args: dict[str, Any],
    allowed_decisions: list[str],
    description: str,
) -> tuple[dict[str, Any] | None, str | None]:
    if not _has_runnable_context():
        return dict(args), None

    resume_value = interrupt(
        _build_interrupt_payload(
            action_name=action_name,
            args=args,
            allowed_decisions=allowed_decisions,
            description=description,
        )
    )
    decision = _extract_decision(resume_value)
    decision_type = str(decision.get("type", "")).strip().lower()

    if decision_type == "approve":
        return dict(args), None

    if decision_type == "reject":
        reject_message = decision.get("message")
        message = (
            reject_message.strip()
            if isinstance(reject_message, str) and reject_message.strip()
            else "Rejected by reviewer."
        )
        return None, message

    if decision_type == "edit":
        edited_action = decision.get("edited_action")
        if not isinstance(edited_action, dict):
            return None, "Edited decision missing edited_action."
        edited_name = edited_action.get("name")
        edited_args = edited_action.get("args")
        if isinstance(edited_name, str) and edited_name != action_name:
            return None, f"Edited action name mismatch: {edited_name}."
        if not isinstance(edited_args, dict):
            return None, "Edited decision args must be an object."
        return dict(edited_args), None

    return None, f"Unsupported decision type: {decision_type or 'unknown'}."


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


def _extract_agent_reply(result: dict[str, Any]) -> str:
    messages = result.get("messages", [])
    if not messages:
        return "Specialist agent returned no message."
    return _message_to_text(messages[-1])


@tool(
    "lookup_internal_knowledge",
    description="Search internal implementation notes for a given topic.",
)
def lookup_internal_knowledge(topic: str) -> str:
    return (
        f"Knowledge note for '{topic}': use model-bound tools for deterministic actions, "
        "and keep user-facing summaries concise."
    )


@tool(
    "draft_release_plan",
    description="Draft a rollout plan and risk controls for a feature release.",
)
def draft_release_plan(feature: str, risk_level: str = "medium") -> str:
    return (
        f"Release plan for '{feature}' (risk={risk_level}): "
        "1) canary rollout, 2) monitor error budget, 3) prepare rollback switch."
    )


@tool(
    "send_demo_email",
    description="Draft and send a stakeholder email for a rollout update.",
)
def send_demo_email(to: list[str], subject: str, body: str) -> str:
    reviewed_args, rejection_message = _resolve_decision(
        action_name="send_demo_email",
        args={"to": to, "subject": subject, "body": body},
        allowed_decisions=["approve", "reject"],
        description="Approve or reject this email sending action.",
    )
    if reviewed_args is None:
        return f"Email cancelled: {rejection_message}"

    reviewed_to = reviewed_args.get("to", to)
    if isinstance(reviewed_to, list):
        recipients_list = [str(item) for item in reviewed_to]
    elif isinstance(reviewed_to, str):
        recipients_list = [reviewed_to]
    else:
        recipients_list = [str(item) for item in to]
    reviewed_subject = str(reviewed_args.get("subject", subject))
    reviewed_body = str(reviewed_args.get("body", body))

    recipients = ", ".join(recipients_list)
    return f"Email sent to {recipients}. Subject: {reviewed_subject}. Body: {reviewed_body}"


def build_langchain_concepts_demo_tools(model: Any) -> list[Any]:
    knowledge_specialist = create_agent(
        model=model,
        tools=[lookup_internal_knowledge],
        system_prompt=KNOWLEDGE_SPECIALIST_PROMPT,
        name="assistant_knowledge_specialist",
    )
    ops_specialist = create_agent(
        model=model,
        tools=[draft_release_plan],
        system_prompt=OPS_SPECIALIST_PROMPT,
        name="assistant_ops_specialist",
    )
    email_specialist = create_agent(
        model=model,
        tools=[send_demo_email],
        system_prompt=EMAIL_SPECIALIST_PROMPT,
        name="assistant_email_specialist",
    )

    @tool(
        "ask_knowledge_specialist",
        description="Delegate implementation Q&A to the knowledge specialist sub-agent.",
    )
    def ask_knowledge_specialist(request: str) -> str:
        result = knowledge_specialist.invoke(
            {"messages": [{"role": "user", "content": request}]}
        )
        return _extract_agent_reply(result)

    @tool(
        "ask_ops_specialist",
        description="Delegate rollout and reliability planning to the operations specialist sub-agent.",
    )
    def ask_ops_specialist(request: str) -> str:
        result = ops_specialist.invoke(
            {"messages": [{"role": "user", "content": request}]}
        )
        return _extract_agent_reply(result)

    @tool(
        "ask_email_specialist",
        description="Delegate stakeholder communication drafting to the email specialist sub-agent.",
    )
    def ask_email_specialist(request: str) -> str:
        result = email_specialist.invoke(
            {"messages": [{"role": "user", "content": request}]}
        )
        return _extract_agent_reply(result)

    @tool(
        "request_human_approval",
        description=(
            "Create a human-review checkpoint before high-impact actions. "
            "This tool interrupts execution and requires approve/edit/reject decisions."
        ),
    )
    def request_human_approval(action: str, details: str) -> str:
        reviewed_args, rejection_message = _resolve_decision(
            action_name="request_human_approval",
            args={"action": action, "details": details},
            allowed_decisions=["approve", "edit", "reject"],
            description="Approve, edit, or reject this high-impact action.",
        )
        if reviewed_args is None:
            return f"Approval rejected: {rejection_message}"

        approved_action = str(reviewed_args.get("action", action))
        approved_details = str(reviewed_args.get("details", details))
        return (
            "Approval checkpoint reached. "
            f"Action='{approved_action}', details='{approved_details}'. If you see this message, review approved execution."
        )

    return [
        ask_knowledge_specialist,
        ask_ops_specialist,
        ask_email_specialist,
        request_human_approval,
    ]
