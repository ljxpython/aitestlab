#!/usr/bin/env python3

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PATHS = (
    (
        "Windows",
        re.compile(
            r"(?:^|[^A-Za-z0-9])[A-Z]:[\\/]+Users[\\/]+[A-Za-z0-9._-]+[\\/]+",
            re.IGNORECASE,
        ),
    ),
    ("macOS", re.compile(r"/Users/[A-Za-z0-9._-]+/")),
    ("Linux", re.compile(r"/home/[A-Za-z0-9._-]+/")),
)
LEGACY_HOSTS = ("platform-web-vue", "platform-api-v2")
HISTORICAL_PREFIXES = (
    ".omx/",
    "docs/CHANGELOG.md",
    "docs/archive/",
    "docs/releases/",
    "docs/platform-web-sub2api-migration/",
    "apps/platform-api/docs/archive/",
)
GENERATED_PREFIXES = ("graphify-out/", ".harness/graphify-out/", "i/")
ACTIVE_PLAN_PREFIX = ".harness/plans/"
CHANGE_STATUSES = {"Pending", "Complete"}
CHANGE_DISPOSITIONS = {"Pending acceptance", "Accepted", "Rejected", "Abandoned"}
REVIEW_STATUSES = {"Pending", "Approved", "Waived"}


def markdown_files() -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.md",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = (
        ROOT / name
        for name in result.stdout.splitlines()
        if name and not name.startswith(GENERATED_PREFIXES)
    )
    return [path for path in paths if path.is_file()]


def is_historical(path: Path, text: str) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    header = "\n".join(text.splitlines()[:12])
    return relative.startswith(HISTORICAL_PREFIXES) or any(
        marker in header
        for marker in (
            "Status: Archived",
            "状态：Archived",
            "状态： Archived",
        )
    )


def is_active_harness_plan(path: Path, text: str) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    return relative.startswith(ACTIVE_PLAN_PREFIX) and not is_historical(path, text)


def local_path_kind(line: str) -> str | None:
    for kind, pattern in LOCAL_PATHS:
        if pattern.search(line):
            return kind
    return None


def check_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(ROOT).as_posix()
    errors: list[str] = []

    if is_active_harness_plan(path, text):
        errors.append(
            f"{relative}: active .harness plan is forbidden; use openspec/changes"
        )

    if is_historical(path, text):
        return errors

    for line_number, line in enumerate(text.splitlines(), start=1):
        path_kind = local_path_kind(line)
        if path_kind:
            errors.append(
                f"{relative}:{line_number}: {path_kind} local absolute path"
            )
        for legacy_host in LEGACY_HOSTS:
            if legacy_host in line:
                errors.append(
                    f"{relative}:{line_number}: retired host name {legacy_host}"
                )
    return errors


def metadata_value(text: str, name: str) -> str | None:
    pattern = re.compile(
        rf"^\s*(?:[-*>]\s*)?{re.escape(name)}\s*:\s*`?([^`\n]+?)`?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else None


def delta_requirement_names(text: str) -> dict[str, set[str]]:
    result = {name: set() for name in ("ADDED", "MODIFIED", "REMOVED")}
    operation: str | None = None
    for line in text.splitlines():
        section = re.fullmatch(
            r"##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements\s*",
            line,
        )
        if section:
            operation = section.group(1)
            continue
        if line.startswith("## "):
            operation = None
            continue
        requirement = re.fullmatch(r"### Requirement:\s*(.+?)\s*", line)
        if requirement and operation in result:
            result[operation].add(requirement.group(1))
    return result


def main_requirement_names(text: str) -> set[str]:
    return set(re.findall(r"^### Requirement:\s*(.+?)\s*$", text, re.MULTILINE))


def check_accepted_spec_sync(change_dir: Path) -> list[str]:
    errors: list[str] = []
    for delta_path in sorted((change_dir / "specs").glob("*/spec.md")):
        capability = delta_path.parent.name
        main_path = ROOT / "openspec/specs" / capability / "spec.md"
        relative_delta = delta_path.relative_to(ROOT).as_posix()
        if not main_path.exists():
            errors.append(
                f"{relative_delta}: accepted archive was not synced to "
                f"openspec/specs/{capability}/spec.md"
            )
            continue

        delta = delta_requirement_names(delta_path.read_text(encoding="utf-8"))
        current = main_requirement_names(main_path.read_text(encoding="utf-8"))
        for name in sorted(delta["ADDED"] | delta["MODIFIED"]):
            if name not in current:
                errors.append(
                    f"{relative_delta}: synced spec is missing requirement {name!r}"
                )
        for name in sorted(delta["REMOVED"]):
            if name in current:
                errors.append(
                    f"{relative_delta}: removed requirement {name!r} remains in main spec"
                )
    return errors


def check_openspec_change(change_dir: Path, *, archived: bool) -> list[str]:
    tasks_path = change_dir / "tasks.md"
    verification_path = change_dir / "verification.md"
    relative = change_dir.relative_to(ROOT).as_posix()
    errors: list[str] = []

    if not tasks_path.exists() and not archived:
        return errors
    if not verification_path.exists():
        return [f"{relative}: persisted change is missing verification.md"]

    text = verification_path.read_text(encoding="utf-8")
    status = metadata_value(text, "Status")
    disposition = metadata_value(text, "Disposition")
    review = metadata_value(text, "Pre-apply review")
    fields = (
        ("Status", status, CHANGE_STATUSES),
        ("Disposition", disposition, CHANGE_DISPOSITIONS),
        ("Pre-apply review", review, REVIEW_STATUSES),
    )
    for name, value, allowed in fields:
        if value not in allowed:
            errors.append(
                f"{relative}/verification.md: {name} must be one of "
                f"{', '.join(sorted(allowed))}"
            )

    if not archived:
        return errors

    if disposition not in {"Accepted", "Rejected", "Abandoned"}:
        errors.append(
            f"{relative}/verification.md: archived change needs a final disposition"
        )
    if disposition == "Accepted":
        if status != "Complete":
            errors.append(
                f"{relative}/verification.md: accepted archive needs Complete evidence"
            )
        if review not in {"Approved", "Waived"}:
            errors.append(
                f"{relative}/verification.md: accepted archive needs Approved or Waived pre-apply review"
            )
        errors.extend(check_accepted_spec_sync(change_dir))
    return errors


def check_openspec_changes() -> list[str]:
    changes_dir = ROOT / "openspec/changes"
    if not changes_dir.exists():
        return []

    errors: list[str] = []
    for change_dir in sorted(path for path in changes_dir.iterdir() if path.is_dir()):
        if change_dir.name != "archive":
            errors.extend(check_openspec_change(change_dir, archived=False))
            continue
        for archived_dir in sorted(
            path for path in change_dir.iterdir() if path.is_dir()
        ):
            errors.extend(check_openspec_change(archived_dir, archived=True))
    return errors


def self_check() -> None:
    assert local_path_kind("/Users/alice/project/readme.md") == "macOS"
    assert local_path_kind("/home/alice/project/readme.md") == "Linux"
    assert local_path_kind(r"C:\Users\alice\project\readme.md") == "Windows"
    assert local_path_kind("C:/Users/alice/project/readme.md") == "Windows"
    assert local_path_kind("Path: C:/Users/alice/project/readme.md") == "Windows"
    assert local_path_kind("/Users/<name>/project") is None
    assert local_path_kind("/home/<name>/project") is None
    assert local_path_kind(r"C:\Users\<name>\project") is None
    assert is_historical(
        ROOT / ".harness/plans/example.md",
        "# Example\n\n> Status: Archived.",
    )
    assert is_active_harness_plan(
        ROOT / ".harness/plans/example.md",
        "# Example\n\n- Status: Active",
    )
    parsed = delta_requirement_names(
        "## ADDED Requirements\n\n### Requirement: New behavior\n"
        "## REMOVED Requirements\n\n### Requirement: Old behavior\n"
    )
    assert parsed["ADDED"] == {"New behavior"}
    assert parsed["REMOVED"] == {"Old behavior"}


def main() -> int:
    self_check()
    errors = [error for path in markdown_files() for error in check_file(path)]
    errors.extend(check_openspec_changes())
    if errors:
        print("\n".join(errors))
        return 1
    print("Documentation checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
