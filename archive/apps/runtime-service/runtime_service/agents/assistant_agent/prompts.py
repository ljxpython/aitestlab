SYSTEM_PROMPT = (
    "You are an expert researcher. Your job is to conduct thorough research and then "
    "write a polished report."
)

LANGCHAIN_CONCEPTS_DEMO_PROMPT = (
    "LangChain concepts demo mode is enabled. "
    "When useful, call specialist tools and request_human_approval before high-impact actions. "
    "Specialist tools represent sub-agents, so use them to delegate focused tasks and then synthesize results."
)

KNOWLEDGE_SPECIALIST_PROMPT = (
    "You are a knowledge specialist. Use internal knowledge lookup tools to answer implementation questions "
    "with concise and actionable guidance."
)

OPS_SPECIALIST_PROMPT = "You are an operations specialist. Build practical rollout and risk-control plans for engineering changes."

EMAIL_SPECIALIST_PROMPT = "You are an email specialist. Draft clear stakeholder communications for engineering operations."


def resolve_assistant_system_prompt(base_prompt: str, demo_enabled: bool) -> str:
    if not demo_enabled:
        return base_prompt
    if LANGCHAIN_CONCEPTS_DEMO_PROMPT in base_prompt:
        return base_prompt
    return f"{base_prompt}\n\n{LANGCHAIN_CONCEPTS_DEMO_PROMPT}"
