from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.agents.research_agent import tools as research_tools  # noqa: E402


def test_research_agent_skill_source_exists() -> None:
    skills = research_tools.list_research_agent_skills()
    assert len(skills) == 1

    skills_root = Path(skills[0])
    assert skills_root.exists()
    assert (skills_root / "web-research" / "SKILL.md").exists()


def test_research_subagent_definition_shape() -> None:
    subagents = research_tools.list_research_subagents()
    assert len(subagents) == 1

    subagent = subagents[0]
    assert subagent["name"] == "research-subagent"
    assert "web" in subagent["description"].lower()
    assert subagent.get("skills") == research_tools.list_research_agent_skills()


def test_research_private_tools_disabled_without_tavily_key() -> None:
    tools = asyncio.run(research_tools.aget_research_private_tools({}))
    assert tools == []


def test_research_private_tools_reads_env_key(monkeypatch) -> None:
    monkeypatch.setenv("RESEARCH_TAVILY_API_KEY", "fake-key")

    class DummyClient:
        def __init__(self, specs: dict[str, dict[str, str]]) -> None:
            self.specs = specs

        async def get_tools(self) -> list[str]:
            return ["tavily_tool"]

    monkeypatch.setattr(research_tools, "MultiServerMCPClient", DummyClient)

    tools = asyncio.run(research_tools.aget_research_private_tools({}))
    assert tools == ["tavily_tool"]
    monkeypatch.delenv("RESEARCH_TAVILY_API_KEY", raising=False)


def test_build_research_runtime_tools_exports_multimodal_reader() -> None:
    tools = research_tools.build_research_runtime_tools()
    names = [getattr(tool, "name", "") for tool in tools]
    assert names == ["read_multimodal_attachments"]


def test_read_multimodal_attachments_compacts_state_payload() -> None:
    class DummyRuntime:
        def __init__(self) -> None:
            self.state = {
                "multimodal_summary": "检测到附件摘要",
                "multimodal_attachments": [
                    {
                        "attachment_id": "att_1",
                        "kind": "pdf",
                        "name": "doc.pdf",
                        "status": "parsed",
                        "summary_for_model": "PDF 已解析：需求摘要",
                        "parsed_text": "A" * 1500,
                        "structured_data": {
                            "key_points": ["点1", "点2"],
                            "source_refs": [{"page": 1, "preview": "段落"}],
                        },
                    }
                ],
            }

    payload_raw = research_tools.read_multimodal_attachments.func(runtime=DummyRuntime())
    payload = json.loads(payload_raw)
    assert payload["multimodal_summary"] == "检测到附件摘要"
    assert payload["attachments"][0]["attachment_id"] == "att_1"
    assert payload["attachments"][0]["kind"] == "pdf"
    assert payload["attachments"][0]["key_points"] == ["点1", "点2"]
    assert payload["attachments"][0]["source_refs"][0]["page"] == 1
    assert payload["attachments"][0]["parsed_text_preview"].endswith("...[truncated]")


def test_langgraph_registers_research_demo() -> None:
    langgraph_file = _PROJECT_ROOT / "runtime_service" / "langgraph.json"
    data = json.loads(langgraph_file.read_text(encoding="utf-8"))
    assert "research_demo" in data["graphs"]
