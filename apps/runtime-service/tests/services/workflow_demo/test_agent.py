from __future__ import annotations

import asyncio

import pytest
from langgraph.pregel import Pregel
from langgraph.types import Command

from runtime_service.graphs.workflow_demo import get_agent


def _graph() -> Pregel:
    return asyncio.run(get_agent({}))


def _config(thread_id: str) -> dict[str, object]:
    return {"configurable": {"thread_id": thread_id}}


@pytest.mark.parametrize(
    ("route", "expected"),
    [("approve", "workflow approved: hello"), ("reject", "workflow rejected: hello")],
)
def test_workflow_demo_routes_to_one_conditional_branch(route: str, expected: str) -> None:
    result = _graph().invoke(
        {"message": "hello", "route": route},
        _config(f"workflow-branch-{route}"),
    )

    assert result["response"] == expected


def test_workflow_demo_static_topology_is_stable() -> None:
    first = _graph()
    second = _graph()
    first_graph = first.get_graph()
    second_graph = second.get_graph()

    assert first is second
    assert set(first_graph.nodes) == set(second_graph.nodes)
    assert {(edge.source, edge.target) for edge in first_graph.edges} == {
        (edge.source, edge.target) for edge in second_graph.edges
    }
    assert first.input_schema == second.input_schema
    assert first.output_schema == second.output_schema


def test_workflow_demo_interrupt_resume_does_not_repeat_completed_step() -> None:
    graph = _graph()
    config = {"configurable": {"thread_id": "workflow-resume-test"}}

    paused = graph.invoke(
        {
            "message": "hello",
            "route": "reject",
            "requires_confirmation": True,
        },
        config,
    )

    assert paused["__interrupt__"][0].value["kind"] == "workflow_confirmation"
    assert paused["prepared_count"] == 1

    interrupt_id = paused["__interrupt__"][0].id
    completed = graph.invoke(Command(resume={interrupt_id: "approve"}), config)

    assert completed["response"] == "workflow approved: hello"
    assert completed["prepared_count"] == 1
    assert completed["confirmation"] == "approve"


def test_workflow_demo_rejects_invalid_resume_without_completing_run() -> None:
    graph = _graph()
    config = {"configurable": {"thread_id": "workflow-invalid-resume-test"}}
    graph.invoke(
        {"message": "hello", "requires_confirmation": True},
        config,
    )

    invalid = graph.invoke(Command(resume={"missing-interrupt-id": "approve"}), config)
    assert invalid["__interrupt__"][0].value["error"] == "workflow.invalid_resume"

    interrupt_id = invalid["__interrupt__"][0].id
    completed = graph.invoke(Command(resume={interrupt_id: "reject"}), config)
    assert completed["response"] == "workflow rejected: hello"
