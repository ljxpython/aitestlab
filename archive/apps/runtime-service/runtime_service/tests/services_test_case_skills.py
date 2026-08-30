# pyright: reportMissingImports=false, reportMissingModuleSource=false
"""
test_case_service Skills 本地验证脚本

验证问题：
  1. test_case_agent 有哪些 skills？
  2. skills 来源于哪里（后端根目录）？
  3. 每个 SKILL.md 是否能被完整读取？

运行方式：
    cd apps/runtime-service
    .venv/bin/python runtime_service/tests/services_test_case_skills.py

    # 查看详细内容（显示每个 SKILL.md 完整内容）
    .venv/bin/python runtime_service/tests/services_test_case_skills.py --verbose
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 路径修复：确保在任意 cwd 下均可直接运行
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from deepagents.backends import FilesystemBackend  # noqa: E402
from runtime_service.services.test_case_service.schemas import (  # noqa: E402
    get_service_root,
    get_skills_root,
)

# ---------------------------------------------------------------------------
# ANSI 颜色辅助
# ---------------------------------------------------------------------------
_GREEN = "\033[32m"
_CYAN = "\033[36m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def _ok(msg: str) -> str:
    return f"{_GREEN}✔{_RESET}  {msg}"


def _fail(msg: str) -> str:
    return f"{_RED}✘{_RESET}  {msg}"


def _header(msg: str) -> str:
    return f"\n{_BOLD}{_CYAN}{'=' * 60}{_RESET}\n{_BOLD}{msg}{_RESET}\n{_BOLD}{_CYAN}{'=' * 60}{_RESET}"


def _section(msg: str) -> str:
    return f"\n{_BOLD}{_YELLOW}── {msg}{_RESET}"


# ---------------------------------------------------------------------------
# 核心验证逻辑
# ---------------------------------------------------------------------------

def _build_backend() -> FilesystemBackend:
    """构造与 graph.py 中完全相同的 FilesystemBackend。"""
    return FilesystemBackend(
        root_dir=str(get_service_root()),
        virtual_mode=True,
    )


def _verify_paths() -> None:
    """验证 1：服务根目录和 skills 目录路径正确性。"""
    print(_section("验证 1：目录路径"))

    service_root = get_service_root()
    skills_root = get_skills_root()

    print(f"  服务包根目录 : {service_root}")
    print(f"  Skills 目录  : {skills_root}")

    if service_root.exists():
        print(_ok(f"service_root 存在: {service_root}"))
    else:
        print(_fail(f"service_root 不存在: {service_root}"))
        sys.exit(1)

    if skills_root.exists():
        print(_ok(f"skills_root 存在: {skills_root}"))
    else:
        print(_fail(f"skills_root 不存在: {skills_root}"))
        sys.exit(1)

    # skills 目录必须在 service_root 内
    assert skills_root.is_relative_to(service_root), \
        f"skills_root ({skills_root}) 不在 service_root ({service_root}) 内"
    print(_ok("skills_root 在 service_root 内（路径关系正确）"))


def _verify_backend_glob(backend: FilesystemBackend) -> list[dict[str, Any]]:
    """验证 2：通过 FilesystemBackend.glob_info 枚举所有 SKILL.md。"""
    print(_section("验证 2：FilesystemBackend.glob_info('/skills/**') 枚举结果"))

    entries: list[dict[str, Any]] = backend.glob_info("/skills/**")
    skill_files = [e for e in entries if not e["is_dir"]]

    print(f"  Backend root_dir : {get_service_root()}")
    print(f"  glob 路径模式    : /skills/**")
    print(f"  发现文件数       : {len(skill_files)}")

    if not skill_files:
        print(_fail("未发现任何 skill 文件，请检查 skills 目录！"))
        sys.exit(1)

    for entry in sorted(skill_files, key=lambda e: e["path"]):
        size_kb = entry["size"] / 1024
        print(
            f"  {_GREEN}●{_RESET} {entry['path']:<45s}  "
            f"{size_kb:5.1f} KB  修改时间: {entry['modified_at']}"
        )

    return skill_files


def _verify_skill_content(
    backend: FilesystemBackend,
    skill_files: list[dict[str, Any]],
    verbose: bool = False,
) -> None:
    """验证 3：逐个读取每个 SKILL.md，检查内容完整性。"""
    print(_section("验证 3：逐个读取 SKILL.md 内容"))

    expected_skills = {
        "requirement-analysis",
        "test-strategy",
        "test-case-design",
        "quality-review",
        "output-formatter",
        "test-data-generator",
    }
    found_skills: set[str] = set()
    errors: list[str] = []

    for entry in sorted(skill_files, key=lambda e: e["path"]):
        path = entry["path"]  # e.g. /skills/requirement-analysis/SKILL.md
        skill_name = Path(path).parent.name  # e.g. requirement-analysis

        try:
            content: str = backend.read(path)
        except Exception as exc:
            errors.append(f"{path}: {exc}")
            print(_fail(f"读取失败 {path}: {exc}"))
            continue

        if not content.strip():
            errors.append(f"{path}: 内容为空")
            print(_fail(f"内容为空: {path}"))
            continue

        # 检查 frontmatter name 字段
        has_name = f"name: {skill_name}" in content
        # 检查关键 Markdown 结构
        has_activation = "## 激活场景" in content or "## Activation" in content
        has_output = "## 输出规范" in content or "## Output" in content

        status_parts = []
        if has_name:
            status_parts.append(f"{_GREEN}name✔{_RESET}")
        else:
            status_parts.append(f"{_RED}name✘{_RESET}")
            errors.append(f"{path}: frontmatter 缺少 name: {skill_name}")

        if has_activation:
            status_parts.append(f"{_GREEN}激活场景✔{_RESET}")
        else:
            status_parts.append(f"{_YELLOW}激活场景?{_RESET}")

        if has_output:
            status_parts.append(f"{_GREEN}输出规范✔{_RESET}")
        else:
            status_parts.append(f"{_YELLOW}输出规范?{_RESET}")

        lines = content.count("\n")
        status_str = "  ".join(status_parts)
        print(f"  {_GREEN}✔{_RESET} {skill_name:<30s}  {lines:3d} 行  [{status_str}]")

        if verbose:
            # 打印前 20 行预览
            preview = "\n".join(content.splitlines()[:20])
            print(f"{_CYAN}{'─' * 56}{_RESET}")
            print(preview)
            if content.count("\n") > 20:
                print(f"  ... (共 {lines} 行，使用 --verbose 仅显示前20行){_RESET}")
            print(f"{_CYAN}{'─' * 56}{_RESET}")

        found_skills.add(skill_name)

    # 检查是否有预期 skill 缺失
    missing = expected_skills - found_skills
    if missing:
        for m in sorted(missing):
            errors.append(f"缺少预期 skill: {m}")
            print(_fail(f"缺少预期 skill: {m}"))

    if errors:
        print(f"\n{_RED}发现 {len(errors)} 个问题：{_RESET}")
        for e in errors:
            print(f"  {_RED}•{_RESET} {e}")
        sys.exit(1)
    else:
        print(_ok(f"所有 {len(found_skills)} 个 skills 读取成功，内容完整"))


def _verify_skill_names_summary(skill_files: list[dict[str, Any]]) -> None:
    """验证 4：汇总 skill 名称列表（agent 实际会加载的 skills）。"""
    print(_section("验证 4：agent 加载的 skills 清单汇总"))

    print(f"  graph.py 中配置: skills = ['/skills/']")
    print(f"  backend root   : {get_service_root()}")
    print(f"  实际 skill 列表（共 {len(skill_files)} 个）：")

    for entry in sorted(skill_files, key=lambda e: e["path"]):
        skill_name = Path(entry["path"]).parent.name
        print(f"    {_GREEN}▸{_RESET} {skill_name}")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="验证 test_case_service skills 是否可被 FilesystemBackend 正确读取"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示每个 SKILL.md 的前20行内容预览",
    )
    args = parser.parse_args()

    print(_header("test_case_service Skills 验证报告"))

    # 构造 backend（与 graph.py 完全相同的参数）
    backend = _build_backend()

    # 逐步验证
    _verify_paths()
    skill_files = _verify_backend_glob(backend)
    _verify_skill_content(backend, skill_files, verbose=args.verbose)
    _verify_skill_names_summary(skill_files)

    print(_header("验证通过 ✔  所有 skills 均可被正确读取"))


if __name__ == "__main__":
    main()

