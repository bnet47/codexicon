#!/usr/bin/env python3
"""Validate structural invariants of the uninitialized Codex template."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 remains common in WSL distributions.
    tomllib = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".html", ".md", ".toml", ".json", ".py", ".ps1", ".sh", ".yml", ".yaml", ".txt"}
SKILL_INVOCATIONS = (
    "discover",
    "init",
    "brainstorm",
    "spec",
    "write-plan",
    "execute-plan",
    "quick",
    "review",
    "ship",
    "investigate",
    "architecture-review",
    "retro",
    "context-dump",
    "conventional-commit",
    "concise",
    "design-experience",
    "create-marketing",
    "review-creative",
    "production-readiness",
)

MAX_PROJECT_GUIDANCE_CHARS = 8192
MAX_SKILL_DESCRIPTION_CHARS = 200
MAX_REPO_SKILL_CATALOG_CHARS = 3500


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def text_files() -> list[Path]:
    ignored = {".git", "__pycache__", ".pytest_cache"}
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and not ignored.intersection(path.relative_to(ROOT).parts)
        and ".codex-state" not in path.relative_to(ROOT).parts
    )


def parse_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("missing opening YAML frontmatter delimiter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("missing closing YAML frontmatter delimiter") from exc

    result: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"')
    return result


def parse_template_toml(path: Path) -> dict:
    """Parse the small TOML subset used by this template on Python 3.10."""
    content = path.read_text(encoding="utf-8")
    if tomllib is not None:
        return tomllib.loads(content)

    result: dict = {}
    current = result
    lines = content.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        index += 1
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            if not section or "." in section:
                raise ValueError(f"unsupported section: {line}")
            current = result.setdefault(section, {})
            continue
        if "=" not in line:
            raise ValueError(f"invalid TOML line: {line}")
        key, raw_value = (part.strip() for part in line.split("=", 1))
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise ValueError(f"invalid TOML key: {key}")
        if raw_value.startswith('"""'):
            chunks = [raw_value[3:]]
            while not chunks[-1].endswith('"""'):
                if index >= len(lines):
                    raise ValueError(f"unterminated multiline string: {key}")
                chunks.append(lines[index])
                index += 1
            chunks[-1] = chunks[-1][:-3]
            current[key] = "\n".join(chunks)
            continue
        try:
            current[key] = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid TOML value for {key}: {raw_value}") from exc
    return result


def context_budget() -> tuple[int, int]:
    guidance_chars = len((ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    catalog_chars = 0
    for path in sorted((ROOT / ".agents/skills").glob("*/SKILL.md")):
        metadata = parse_frontmatter(path)
        catalog_chars += len(metadata.get("name", ""))
        catalog_chars += len(metadata.get("description", ""))
        catalog_chars += len(rel(path))
    return guidance_chars, catalog_chars


def validate() -> list[str]:
    errors: list[str] = []

    guidance_chars = len((ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    if guidance_chars > MAX_PROJECT_GUIDANCE_CHARS:
        errors.append(
            f"AGENTS.md exceeds the {MAX_PROJECT_GUIDANCE_CHARS}-character always-loaded guidance budget"
        )

    required = [
        "AGENTS.md",
        "README.md",
        "START_HERE.md",
        "LICENSE",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        "SUPPORT.md",
        ".codex/config.toml",
        ".codex/hooks.json",
        ".codex/hooks/codex_hook.py",
        "scripts/lint.sh",
        "scripts/lint.ps1",
        "scripts/test.sh",
        "scripts/test.ps1",
        "scripts/security_scan.py",
        "scripts/security.sh",
        "scripts/security.ps1",
        "scripts/install-git-hooks.sh",
        "scripts/install-git-hooks.ps1",
        "scripts/render_playbook.py",
        ".githooks/pre-commit",
        ".githooks/pre-push",
        ".github/pull_request_template.md",
        ".github/CODEOWNERS",
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        "docs/codex.md",
        "docs/adr-template.md",
        "docs/maintainers.md",
        "docs/repo-template-playbook.html",
        "docs/repo-template-playbook.source.html",
        "docs/repo-template-playbook.shell.html",
        "agent_docs/decisions/ADR-001-codex-first-template.md",
        "agent_docs/security.md",
        "agent_docs/operations.md",
        ".agents/skills/production-readiness/SKILL.md",
        ".agents/skills/production-readiness/agents/openai.yaml",
        ".agents/skills/design-experience/references/interface-craft.md",
        ".agents/skills/design-experience/references/hardening.md",
        ".agents/skills/create-marketing/references/copy-and-conversion.md",
        ".agents/skills/create-marketing/references/campaigns-and-channels.md",
        ".agents/skills/create-marketing/references/research-and-measurement.md",
        ".agents/skills/review-creative/references/review-rubric.md",
        ".agents/skills/review-creative/scripts/scan_interface.py",
        "tests/test_ui_scanner.py",
    ]
    for item in required:
        if not (ROOT / item).is_file():
            errors.append(f"missing required file: {item}")

    obsolete = [
        "CLAUDE.md",
        "GEMINI.md",
        ".cursorrules",
        ".claude",
        ".antigravity",
        ".gemini",
        "agent_docs/sessions/2026-07-15-codex-template-retro.md",
    ]
    for item in obsolete:
        path = ROOT / item
        if path.is_file() or (path.is_dir() and any(candidate.is_file() for candidate in path.rglob("*"))):
            errors.append(f"obsolete compatibility surface remains: {item}")

    mojibake = (
        "\u00e2\u20ac",
        "\u00e2\u2020",
        "\u00e2\u201d",
        "\u00c3",
        "\u00c2",
        "\ufffd",
    )
    for path in text_files():
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"not valid UTF-8: {rel(path)}")
            continue
        markers = [marker for marker in mojibake if marker in content]
        if markers:
            errors.append(f"mojibake marker {markers[0]!r}: {rel(path)}")

    try:
        hooks = json.loads((ROOT / ".codex/hooks.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid .codex/hooks.json: {exc}")
        hooks = {}

    hook_text = json.dumps(hooks)
    if re.search(r"[A-Za-z]:\\\\", hook_text):
        errors.append(".codex/hooks.json contains a machine-specific Windows path")
    if ".claude" in hook_text.lower():
        errors.append(".codex/hooks.json references .claude state or scripts")
    if "git rev-parse" in hook_text.lower():
        errors.append(".codex/hooks.json depends on Git before template initialization")
    if "record-check" in hook_text.lower():
        errors.append(".codex/hooks.json uses unsafe command-text-only verification")
    if not all(name in hook_text for name in ("^Read$", "^read_file$", "^read_text_file$")):
        errors.append(".codex/hooks.json does not protect direct file-reading tools")
    for event, groups in hooks.get("hooks", {}).items():
        for group in groups:
            for handler in group.get("hooks", []):
                if handler.get("type") == "command" and not handler.get("commandWindows"):
                    errors.append(f"{event} command hook lacks commandWindows")

    for check in ("lint", "test"):
        for suffix in ("sh", "ps1"):
            path = ROOT / "scripts" / f"{check}.{suffix}"
            if path.is_file() and f"emit-success {check}" not in path.read_text(encoding="utf-8"):
                errors.append(f"{rel(path)} does not emit a success receipt after verification")

    for suffix in ("sh", "ps1"):
        path = ROOT / "scripts" / f"security.{suffix}"
        if path.is_file() and "security_scan.py" not in path.read_text(encoding="utf-8"):
            errors.append(f"{rel(path)} does not run the canonical credential scanner")

    git_hook_contract = {
        ".githooks/pre-commit": ("scripts/security.sh",),
        ".githooks/pre-push": ("scripts/lint.sh", "scripts/test.sh", "scripts/security.sh"),
    }
    for relative, commands in git_hook_contract.items():
        path = ROOT / relative
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for command in commands:
            if command not in content:
                errors.append(f"{relative} does not run {command}")

    workflow_path = ROOT / ".github" / "workflows" / "ci.yml"
    if workflow_path.is_file():
        workflow = workflow_path.read_text(encoding="utf-8")
        if re.search(r"uses:\s+[^\s@]+@(?:main|master|latest|v\d+)\s*$", workflow, re.MULTILINE):
            errors.append("CI action is not pinned to an immutable commit SHA")
        if "windows-latest" not in workflow or "scripts/test.ps1" not in workflow:
            errors.append("CI does not exercise the native Windows verification path")
        if '"3.10"' not in workflow or '"3.13"' not in workflow:
            errors.append("CI does not test both the minimum and current supported Python versions")
        if "persist-credentials: false" not in workflow:
            errors.append("CI checkout persists credentials")
        if "timeout-minutes:" not in workflow:
            errors.append("CI jobs do not define timeouts")
        if "scripts/security.sh" not in workflow:
            errors.append("CI does not run the canonical local security gate")

    for toml_path in [ROOT / ".codex/config.toml", *sorted((ROOT / ".codex/agents").glob("*.toml"))]:
        try:
            value = parse_template_toml(toml_path)
        except (OSError, ValueError) as exc:
            errors.append(f"invalid TOML {rel(toml_path)}: {exc}")
            continue
        if toml_path.parent.name == "agents":
            for field in ("name", "description", "developer_instructions"):
                if not value.get(field):
                    errors.append(f"{rel(toml_path)} missing required field: {field}")
            lowered = toml_path.read_text(encoding="utf-8").lower()
            for stale in ("haiku", "sonnet", "opus", "mcp__mem0"):
                if stale in lowered:
                    errors.append(f"{rel(toml_path)} contains stale agent assumption: {stale}")

    skill_names: dict[str, str] = {}
    skill_catalog_chars = 0
    skills = sorted((ROOT / ".agents/skills").glob("*/SKILL.md"))
    if not skills:
        errors.append("no repository skills found in .agents/skills")
    slash_pattern = re.compile(r"(?<![\w.])/(?:" + "|".join(map(re.escape, SKILL_INVOCATIONS)) + r")\b")
    for path in skills:
        try:
            metadata = parse_frontmatter(path)
        except ValueError as exc:
            errors.append(f"invalid skill metadata {rel(path)}: {exc}")
            continue
        name = metadata.get("name", "")
        description = metadata.get("description", "")
        if not name or not description:
            errors.append(f"{rel(path)} requires name and description")
        if len(description) > MAX_SKILL_DESCRIPTION_CHARS:
            errors.append(
                f"{rel(path)} description exceeds {MAX_SKILL_DESCRIPTION_CHARS} characters"
            )
        if name in skill_names:
            errors.append(f"duplicate skill name {name}: {skill_names[name]} and {rel(path)}")
        skill_names[name] = rel(path)
        skill_catalog_chars += len(name) + len(description) + len(rel(path))

        content = path.read_text(encoding="utf-8")
        match = slash_pattern.search(content)
        if match:
            errors.append(f"Claude-style invocation {match.group(0)!r} in {rel(path)}")

        if name not in {"ship", "conventional-commit"}:
            for side_effect in ("git commit", "git push", "gh pr create"):
                if side_effect in content.lower():
                    errors.append(f"unauthorized Git side effect {side_effect!r} in {rel(path)}")

    expected_skills = set(SKILL_INVOCATIONS)
    missing_skills = sorted(expected_skills - set(skill_names))
    if missing_skills:
        errors.append(f"missing expected skills: {', '.join(missing_skills)}")
    if skill_catalog_chars > MAX_REPO_SKILL_CATALOG_CHARS:
        errors.append(
            "repository skill catalog exceeds the "
            f"{MAX_REPO_SKILL_CATALOG_CHARS}-character initial-context budget"
        )

    for root_doc in ("AGENTS.md", "README.md", "START_HERE.md"):
        content = (ROOT / root_doc).read_text(encoding="utf-8").lower()
        for stale in ("antigravity", "gemini.md", "claude.md"):
            if stale in content:
                errors.append(f"{root_doc} retains obsolete harness reference: {stale}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for public_requirement in ("# Codexicon", "Use this template", "$production-readiness", "What Codexicon does not do"):
        if public_requirement not in readme:
            errors.append(f"README.md is missing public explanation: {public_requirement}")

    windows_root = r"[a-z]:" + r"[\\/]" + r"(?:users|ai_dev)[\\/]"
    mac_user_root = "/" + "users" + r"/[^/]+/"
    machine_path = re.compile(f"(?:{windows_root}|{mac_user_root})", flags=re.IGNORECASE)
    for path in text_files():
        content = path.read_text(encoding="utf-8")
        if machine_path.search(content):
            errors.append(f"machine-specific path or identity remains in {rel(path)}")

    for directory in ("briefs", "plans", "sessions"):
        task_records = sorted((ROOT / "agent_docs" / directory).glob("*.md"))
        if task_records:
            errors.append(
                f"template-development records remain in agent_docs/{directory}: "
                + ", ".join(path.name for path in task_records)
            )

    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    if "[YEAR]" in license_text or "[OWNER]" in license_text:
        errors.append("LICENSE retains template identity placeholders")

    security_policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    if "private vulnerability reporting" not in security_policy.lower():
        errors.append("SECURITY.md lacks a private reporting route")

    hook_policy = (ROOT / ".codex/hooks/codex_hook.py").read_text(encoding="utf-8")
    for required_policy in (".npmrc", ".aws", ".ssh", ".kube", ".docker", "ENV_ENUMERATION", "prune_receipts"):
        if required_policy not in hook_policy:
            errors.append(f"credential hook policy is missing {required_policy}")

    playbook_source = (ROOT / "docs/repo-template-playbook.source.html").read_text(encoding="utf-8")
    if not playbook_source.lstrip().startswith('<div id="codex-template-playbook">'):
        errors.append("playbook editable source is not an HTML fragment")
    if len(playbook_source.encode("utf-8")) >= 2 * 1024 * 1024:
        errors.append("playbook editable source exceeds the 2 MB visualization limit")
    for required_copy in ("$production-readiness", "READY WITH ACCEPTED RISK", "scripts/security.sh"):
        if required_copy not in playbook_source:
            errors.append(f"playbook source is missing production guidance: {required_copy}")
    render_check = subprocess.run(
        [sys.executable, str(ROOT / "scripts/render_playbook.py"), "--check"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if render_check.returncode != 0:
        errors.append(render_check.stderr.strip() or "playbook source and standalone output differ")

    markdown_link = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
    for path in sorted(ROOT.rglob("*.md")):
        if {".git", ".codex-state"}.intersection(path.relative_to(ROOT).parts):
            continue
        for raw_target in markdown_link.findall(path.read_text(encoding="utf-8")):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, flags=re.IGNORECASE):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                errors.append(f"broken local Markdown link in {rel(path)}: {raw_target}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("Template validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    guidance_chars, catalog_chars = context_budget()
    approximate_tokens = (guidance_chars + catalog_chars + 3) // 4
    print("Template structure, metadata, config, and policy checks passed.")
    print(
        "Repo context budget: "
        f"AGENTS.md {guidance_chars} chars; skill catalog {catalog_chars} chars; "
        f"about {approximate_tokens} tokens before platform/global instructions."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
