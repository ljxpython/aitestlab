from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from runtime_service.agents.skills_sql_assistant_agent.prompts import (
    SQL_ASSISTANT_SYSTEM_PROMPT,
)
from runtime_service.middlewares.multimodal import (
    MultimodalAgentState,
    MultimodalMiddleware,
)
from runtime_service.runtime.context import RuntimeContext
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain.messages import SystemMessage
from langchain_core.tools import tool


class Skill(TypedDict):
    name: str
    description: str
    content: str


SKILLS: list[Skill] = [
    {
        "name": "sales_analytics",
        "description": "Schema and business rules for sales analytics (customers, orders, revenue).",
        "content": (
            "# Sales Analytics Schema\n\n"
            "## Tables\n"
            "customers(customer_id, name, email, signup_date, status, customer_tier)\n"
            "orders(order_id, customer_id, order_date, status, total_amount, sales_region)\n"
            "order_items(item_id, order_id, product_id, quantity, unit_price, discount_percent)\n\n"
            "## Business Logic\n"
            "- Revenue only includes completed orders.\n"
            "- High-value orders are total_amount > 1000.\n"
            "- CLV is sum(total_amount) of completed orders by customer."
        ),
    },
    {
        "name": "inventory_management",
        "description": "Schema and business rules for inventory and warehouse stock tracking.",
        "content": (
            "# Inventory Management Schema\n\n"
            "## Tables\n"
            "products(product_id, product_name, sku, category, unit_cost, reorder_point, discontinued)\n"
            "warehouses(warehouse_id, warehouse_name, location, capacity)\n"
            "inventory(inventory_id, product_id, warehouse_id, quantity_on_hand, last_updated)\n"
            "stock_movements(movement_id, product_id, warehouse_id, movement_type, quantity, movement_date, reference_number)\n\n"
            "## Business Logic\n"
            "- Reorder when total stock <= reorder_point.\n"
            "- Exclude discontinued products by default.\n"
            "- Stock valuation is quantity_on_hand * unit_cost."
        ),
    },
]


@tool("load_skill", description="Load full content for a named SQL business skill.")
def load_skill(skill_name: str) -> str:
    for skill in SKILLS:
        if skill["name"] == skill_name:
            return f"Loaded skill: {skill_name}\n\n{skill['content']}"
    available = ", ".join(item["name"] for item in SKILLS)
    return f"Skill '{skill_name}' not found. Available skills: {available}"


class SkillMiddleware(AgentMiddleware):
    tools = [load_skill]

    def __init__(self) -> None:
        lines = [f"- {item['name']}: {item['description']}" for item in SKILLS]
        self._skills_prompt = "\n".join(lines)

    def _with_skill_system_message(self, request: ModelRequest) -> ModelRequest:
        addendum = (
            "\n\n## Available Skills\n"
            f"{self._skills_prompt}\n\n"
            "Use load_skill when you need schema and business rules for a skill."
        )
        existing_prompt = request.system_prompt or ""
        new_system_message = SystemMessage(content=f"{existing_prompt}{addendum}")
        return request.override(system_message=new_system_message)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        return handler(self._with_skill_system_message(request))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelResponse:
        return await handler(self._with_skill_system_message(request))


def build_skills_sql_assistant_agent(
    model: Any,
    base_tools: list[Any] | None = None,
    middleware: list[Any] | None = None,
) -> Any:
    tools = list(base_tools or [])
    return create_agent(
        model=model,
        tools=tools,
        system_prompt=SQL_ASSISTANT_SYSTEM_PROMPT,
        state_schema=MultimodalAgentState,
        middleware=[*(middleware or []), SkillMiddleware(), MultimodalMiddleware()],
        context_schema=RuntimeContext,
        name="skills_sql_assistant_demo",
    )
