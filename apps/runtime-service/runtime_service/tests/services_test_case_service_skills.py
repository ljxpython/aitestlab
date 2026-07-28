# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""test_case_service Skills 真实加载验证脚本。

运行方式::

    cd apps/runtime-service
    .venv/bin/python runtime_service/tests/services_test_case_service_skills.py

验证内容:

1. _alist_skills 静态枚举：skills 元数据（名称/路径/描述）是否正确加载
2. SkillsMiddleware.abefore_agent 注入验证：skills 是否真实注入进 system prompt
3. static graph 集成验证：真实 graph 能否正常构建（不调用 LLM）

以上三项均无需 LLM 网络调用，可离线运行。
如需完整 astream 验证，在命令行加 --live 参数。
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.runnables import RunnableConfig

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# 加载 .env
_ENV_FILE = _PROJECT_ROOT / "runtime_service" / ".env"
if _ENV_FILE.exists():
    from dotenv import load_dotenv
    load_dotenv(_ENV_FILE, override=False)

os.environ.setdefault("APP_ENV", "test")

from runtime_service.conf.settings import require_model_spec  # noqa: E402
from deepagents.backends import FilesystemBackend  # noqa: E402
from deepagents.middleware.skills import SkillsMiddleware, _alist_skills  # noqa: E402
from langgraph.checkpoint.memory import MemorySaver  # noqa: E402
from langgraph.runtime import Runtime  # noqa: E402
from runtime_service.middlewares.multimodal import MultimodalMiddleware  # noqa: E402
from runtime_service.runtime.context import RuntimeContext  # noqa: E402
from runtime_service.runtime.runtime_request_resolver import (  # noqa: E402
    AgentDefaults,
    resolve_runtime_settings,
)
from runtime_service.services.test_case_service.prompts import SYSTEM_PROMPT  # noqa: E402
from runtime_service.services.test_case_service.schemas import get_service_root  # noqa: E402

SEP = "=" * 60
_BACKEND_ROOT = str(get_service_root())
_SKILLS_SOURCE = "/skills/"
_EXPECTED_SKILLS = {
    "requirement-analysis",
    "test-strategy",
    "test-case-design",
    "quality-review",
    "output-formatter",
    "test-data-generator",
}
_SCRIPT_DEFAULTS = AgentDefaults(
    model_id="deepseek_chat",
    system_prompt=SYSTEM_PROMPT,
    enable_tools=False,
)


def _resolve_script_runtime(model_id: str) -> tuple[Any, list[Any], dict[str, str]]:
    runtime_context = RuntimeContext(
        user_id="local-debug",
        tenant_id="local-debug",
        role="debug",
        permissions=[],
        project_id="local-debug",
    )
    settings = resolve_runtime_settings(
        runtime=Runtime(context=runtime_context),
        config={
            "configurable": {
                "platform_runtime": {"model_id": model_id},
            }
        },
        defaults=_SCRIPT_DEFAULTS,
        allow_internal_context=True,
    )
    resolved_model_id, spec = require_model_spec(model_id or _SCRIPT_DEFAULTS.model_id)
    return (
        settings,
        [],  # 当前 skills 验证脚本不依赖公共 optional tools
        {
            "runtime_model_id": resolved_model_id,
            "runtime_model": spec["model"],
            "runtime_provider": spec["model_provider"],
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# 验证 1：_alist_skills 静态枚举
# ─────────────────────────────────────────────────────────────────────────────

async def verify_static_enum() -> list[dict]:
    """通过 _alist_skills 直接枚举 backend 中的 skills，不调用 LLM。"""
    print(f"\n── 验证 1：_alist_skills 静态枚举 {'─' * 30}")
    print(f"  backend root_dir : {_BACKEND_ROOT}")
    print(f"  sources          : ['{_SKILLS_SOURCE}']  (graph.py 中配置)")

    backend = FilesystemBackend(root_dir=_BACKEND_ROOT, virtual_mode=True)
    skills = await _alist_skills(backend, _SKILLS_SOURCE)

    print(f"  发现 skills 数量 : {len(skills)}\n")

    found_names: set[str] = set()
    for s in skills:
        name = s["name"]
        path = s.get("path", "?")
        desc = str(s.get("description", ""))
        desc_short = desc[:60] + "..." if len(desc) > 60 else desc
        found_names.add(name)
        print(f"  ✔ [{name}]")
        print(f"      路径    : {path}")
        print(f"      用途    : {desc_short}")

    missing = _EXPECTED_SKILLS - found_names
    extra = found_names - _EXPECTED_SKILLS
    print()
    if missing:
        print(f"  ✘ 缺少预期 skills: {missing}")
    else:
        print(f"  ✔ 全部 {len(_EXPECTED_SKILLS)} 个预期 skills 均已加载")
    if extra:
        print(f"  ℹ 额外 skills（非预期）: {extra}")

    assert not missing, f"缺少 skills: {missing}"
    return skills


# ─────────────────────────────────────────────────────────────────────────────
# 验证 2：SkillsMiddleware.abefore_agent 注入验证
# ─────────────────────────────────────────────────────────────────────────────

async def verify_middleware_injection(skills_metadata: list[dict]) -> None:
    """调用 SkillsMiddleware.abefore_agent，验证 skills 被注入进 state。

    不调用 LLM，只验证 middleware 是否能正确读取 skills 并构建 system prompt 内容。
    """
    print(f"\n── 验证 2：SkillsMiddleware.abefore_agent 注入验证 {'─' * 15}")

    backend = FilesystemBackend(root_dir=_BACKEND_ROOT, virtual_mode=True)
    sm = SkillsMiddleware(backend=backend, sources=[_SKILLS_SOURCE])

    # 构造最小 state 和 runtime stub 来调用 abefore_agent
    # SkillsMiddleware 的 abefore_agent 需要 state 包含 messages 字段
    # 用 dataclass-like dict 模拟
    # 关键：用不含 skills_metadata key 的原始 dict
    # abefore_agent 检查 `"skills_metadata" in state`，dict 无该 key 则触发真实加载
    state: dict = {"messages": [{"role": "user", "content": "test"}]}

    # runtime stub（SkillsMiddleware 需要 runtime 来获取 backend）
    class _RuntimeStub:
        pass

    result = await sm.abefore_agent(state, runtime=_RuntimeStub(), config={"configurable": {}})  # type: ignore

    # abefore_agent 返回 state update dict，应包含 skills_metadata
    print(f"  abefore_agent 返回类型 : {type(result)}")
    if isinstance(result, dict):
        injected_skills = result.get("skills_metadata", [])
        print(f"  注入 skills 数量      : {len(injected_skills)}")
        for s in injected_skills:
            print(f"  ✔ 注入: [{s['name']}] → {s.get('path', '?')}")
        assert len(injected_skills) == len(_EXPECTED_SKILLS), (
            f"期望 {len(_EXPECTED_SKILLS)} 个 skills 被注入，实际 {len(injected_skills)}"
        )
        print(f"\n  ✔ SkillsMiddleware 成功将全部 {len(injected_skills)} 个 skills 注入 state")
    else:
        print(f"  返回值: {result}")


# ─────────────────────────────────────────────────────────────────────────────
# 验证 3：static graph 构建验证
# ─────────────────────────────────────────────────────────────────────────────

async def verify_static_graph() -> None:
    """验证 test_case_service 的静态 graph 能正常构建并暴露可调用对象。"""
    print(f"\n── 验证 3：static graph 构建验证 {'─' * 33}")

    from deepagents import create_deep_agent  # noqa: E402

    config: RunnableConfig = {
        "configurable": {
            "thread_id": str(uuid4()),
        }
    }
    settings, tools, _model_preview = _resolve_script_runtime("deepseek_chat")
    backend = FilesystemBackend(root_dir=_BACKEND_ROOT, virtual_mode=True)

    agent = create_deep_agent(
        name="test_case_agent",
        model=settings.model,
        tools=tools,
        middleware=[MultimodalMiddleware()],
        system_prompt=SYSTEM_PROMPT,
        backend=backend,
        skills=[_SKILLS_SOURCE],
        context_schema=RuntimeContext,
        checkpointer=MemorySaver(),
    )

    print(f"  ✔ agent 对象构建成功: {type(agent).__name__}")

    # 检查 agent 的 middleware 中是否包含 SkillsMiddleware
    middlewares = getattr(agent, "middleware", None) or getattr(agent, "middlewares", None)
    if middlewares is None:
        # 尝试从 compiled graph 内部找
        inner = getattr(agent, "_agent", None) or getattr(agent, "agent", None)
        middlewares = getattr(inner, "middleware", None) if inner else None

    if middlewares is not None:
        mw_names = [type(m).__name__ for m in middlewares]
        print(f"  middleware 列表: {mw_names}")
        has_skills_mw = any("Skill" in n for n in mw_names)
        if has_skills_mw:
            print("  ✔ SkillsMiddleware 已挂载到 agent")
        else:
            print("  ℹ SkillsMiddleware 可能在 create_deep_agent 内部自动构建（未直接暴露）")
    else:
        print("  ℹ middleware 属性未直接暴露（create_deep_agent 内部管理）")

    print("  ✔ static graph 集成验证通过")


# ─────────────────────────────────────────────────────────────────────────────
# 验证 4（可选）：真实 astream 询问
# ─────────────────────────────────────────────────────────────────────────────

async def verify_live_stream(model_id: str = "deepseek_chat") -> None:
    """向 agent 发送真实询问，流式打印回复。需要 LLM 网络连接。"""
    print(f"\n── 验证 4（--live）：真实 astream 询问 {'─' * 25}")
    print(f"  使用模型: {model_id}")

    from deepagents import create_deep_agent  # noqa: E402

    config: RunnableConfig = {
        "configurable": {
            "thread_id": str(uuid4()),
        }
    }
    settings, tools, model_preview = _resolve_script_runtime(model_id)
    print(f"  resolved model: {model_preview}")
    backend = FilesystemBackend(root_dir=_BACKEND_ROOT, virtual_mode=True)

    # 用 callback 拦截第一次 before_model，打印实际注入的 system prompt
    first_system_prompt_printed = False

    agent = create_deep_agent(
        name="test_case_agent",
        model=settings.model,
        tools=tools,
        middleware=[MultimodalMiddleware()],
        system_prompt=SYSTEM_PROMPT,
        backend=backend,
        skills=[_SKILLS_SOURCE],
        context_schema=RuntimeContext,
        checkpointer=MemorySaver(),
    )

    # ── 打印实际注入的 system prompt（不调用 LLM）──────────────────────────
    print("\n  ── 验证 system prompt 是否含 skills 内容 ──")
    from deepagents.middleware.skills import SkillsMiddleware as _SM
    _sm = _SM(backend=backend, sources=[_SKILLS_SOURCE])
    _state: dict = {"messages": []}
    _result = await _sm.abefore_agent(_state, runtime=None, config={"configurable": {}})  # type: ignore
    _skills_meta = _result["skills_metadata"] if _result else []
    _injected = _sm.system_prompt_template.format(
        skills_locations=_sm._format_skills_locations(),
        skills_list=_sm._format_skills_list(_skills_meta),
    )
    _full_prompt = f"{SYSTEM_PROMPT}\n\n{_injected}"
    has_skills_section = "## Skills System" in _injected
    has_skill_names = all(s in _injected for s in _EXPECTED_SKILLS)
    print(f"  system prompt 含 Skills System 段落: {'✔' if has_skills_section else '✘'}")
    print(f"  system prompt 含全部 skill 名称:    {'✔' if has_skill_names else '✘'}")
    print(f"  注入内容前200字符: {_injected[:200]}...")
    print()
    question = (
        "我有一个登录功能需要测试：用户输入用户名（4-20位字母数字）和密码（8-16位）登录系统。"
        "请帮我按照你的 skill 规范进行需求分析并制定测试策略。"
    )
    print(f"  [你] {question}")
    print("  [agent] ", end="", flush=True)

    collected: list[str] = []
    tool_calls: list[str] = []

    async def _stream() -> None:
        async for mode, event in agent.astream(
            {"messages": [{"role": "user", "content": question}]},
            config=config,
            stream_mode=["messages", "updates"],
        ):
            if mode == "messages":
                msg, _ = event
                text = getattr(msg, "content", "")
                if isinstance(text, str) and text:
                    print(text, end="", flush=True)
                    collected.append(text)
                # 捕获 tool_calls（AI 调用工具时）
                for tc in getattr(msg, "tool_calls", []) or []:
                    name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                    if name:
                        tool_calls.append(name)
                        print(f"\n  [tool_call: {name}]", flush=True)
            elif mode == "updates":
                if isinstance(event, dict):
                    for key in event:
                        if "skill" in key.lower():
                            print(f"\n  [skills_event: {key}]", flush=True)

    try:
        await asyncio.wait_for(_stream(), timeout=120.0)
    except asyncio.TimeoutError:
        print("\n  ⚠ 超时 120s")

    print()
    response = "".join(collected)
    print(f"\n  完整回复（{len(response)} 字符）:")
    print(f"  {response[:500]}" + ("..." if len(response) > 500 else ""))

    print(f"\n  ── 工具调用记录（共 {len(tool_calls)} 次）──")
    for tc in tool_calls:
        print(f"  · {tc}")
    skill_reads = [tc for tc in tool_calls if tc in ("read_file", "ls", "glob")]
    print(f"  skill 相关文件操作: {skill_reads if skill_reads else '（无）'}")

    print(f"\n  ── 回复中 skill 名称检测 ──")
    found = [name for name in _EXPECTED_SKILLS if name.lower() in response.lower()]
    missing = [name for name in _EXPECTED_SKILLS if name.lower() not in response.lower()]
    for name in found:
        print(f"  ✔ 回复提到: {name}")
    for name in missing:
        print(f"  △ 未提到: {name}")

    print()
    if found or skill_reads:
        print(f"  ✔ agent 感知到 skills（回复提到 {len(found)}/{len(_EXPECTED_SKILLS)} 个，文件操作 {len(skill_reads)} 次）")
    else:
        print(f"  ✘ agent 未感知到 skills（回复中无 skill 名称，无 skill 文件操作）")
        print(f"  → system prompt 注入验证请查看验证2结果")


# ─────────────────────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────────────────────

async def _run(live: bool, model_id: str) -> None:
    print(SEP)
    print("test_case_service Skills 真实加载验证")
    print(SEP)

    skills_metadata = await verify_static_enum()
    await verify_middleware_injection(skills_metadata)
    await verify_static_graph()

    if live:
        await verify_live_stream(model_id=model_id)

    print()
    print(SEP)
    if live:
        print("验证完成（含 --live astream 验证）")
    else:
        print("验证完成（离线模式，无 LLM 调用）")
        print("如需真实 astream 验证，运行时加 --live 参数")
    print(SEP)


def main() -> None:
    parser = argparse.ArgumentParser(description="验证 test_case_service skills 加载")
    parser.add_argument(
        "--live",
        action="store_true",
        help="追加验证4：真实 astream 询问（需要 LLM 网络连接）",
    )
    parser.add_argument(
        "--model",
        default="iflow_qwen3-max",
        help="live 模式使用的模型 ID（默认 iflow_qwen3-max）",
    )
    args = parser.parse_args()
    asyncio.run(_run(live=args.live, model_id=args.model))


if __name__ == "__main__":
    main()
