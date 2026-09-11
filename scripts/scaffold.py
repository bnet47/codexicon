#!/usr/bin/env python3
"""Create a clean Codexicon project starter from a trusted local template."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

try:
    from security_scan import is_protected_path
except ImportError:  # pragma: no cover - used when imported as scripts.scaffold
    from scripts.security_scan import is_protected_path


class ScaffoldError(ValueError):
    """Raised when a scaffold cannot be created without unsafe ambiguity."""


# This is deliberately an exact allowlist. New template files must be reviewed
# and added here before they can enter a generated starter.
STARTER_FILES = (
    ".codexicon.json",
    ".codex/config.toml",
    ".codex/hooks.json",
    ".codex/capabilities.toml",
    ".codex/hooks/codex_hook.py",
    ".codex/agents/github-researcher.toml",
    ".codex/agents/implementer.toml",
    ".codex/agents/researcher.toml",
    ".codex/agents/reviewer.toml",
    ".agents/skills/adopt-codexicon/SKILL.md",
    ".agents/skills/architecture-review/SKILL.md",
    ".agents/skills/autonomous-build/SKILL.md",
    ".agents/skills/brainstorm/SKILL.md",
    ".agents/skills/concise/SKILL.md",
    ".agents/skills/context-dump/SKILL.md",
    ".agents/skills/conventional-commit/SKILL.md",
    ".agents/skills/create-marketing/SKILL.md",
    ".agents/skills/create-marketing/agents/openai.yaml",
    ".agents/skills/create-marketing/references/campaigns-and-channels.md",
    ".agents/skills/create-marketing/references/copy-and-conversion.md",
    ".agents/skills/create-marketing/references/research-and-measurement.md",
    ".agents/skills/design-experience/SKILL.md",
    ".agents/skills/design-experience/agents/openai.yaml",
    ".agents/skills/design-experience/references/hardening.md",
    ".agents/skills/design-experience/references/interface-craft.md",
    ".agents/skills/discover/SKILL.md",
    ".agents/skills/engineering-loop/SKILL.md",
    ".agents/skills/engineering-loop/agents/openai.yaml",
    ".agents/skills/execute-plan/SKILL.md",
    ".agents/skills/find-skills/SKILL.md",
    ".agents/skills/find-skills/agents/openai.yaml",
    ".agents/skills/init/SKILL.md",
    ".agents/skills/investigate/SKILL.md",
    ".agents/skills/production-readiness/SKILL.md",
    ".agents/skills/production-readiness/agents/openai.yaml",
    ".agents/skills/quick/SKILL.md",
    ".agents/skills/retro/SKILL.md",
    ".agents/skills/review-creative/SKILL.md",
    ".agents/skills/review-creative/agents/openai.yaml",
    ".agents/skills/review-creative/references/review-rubric.md",
    ".agents/skills/review-creative/scripts/scan_interface.py",
    ".agents/skills/review/SKILL.md",
    ".agents/skills/ship/SKILL.md",
    ".agents/skills/spec/SKILL.md",
    ".agents/skills/write-plan/SKILL.md",
    ".gitattributes",
    ".gitignore",
    ".githooks/pre-commit",
    ".githooks/pre-push",
    "AGENTS.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "START_HERE.md",
    "SUPPORT.md",
    "TEMPLATE_VERSION",
    "agent_docs/operations.md",
    "agent_docs/security.md",
    "agent_docs/skills.lock.json",
    "docs/adr-template.md",
    "docs/agent-patterns.md",
    "docs/build-contracts.md",
    "docs/codex.md",
    "docs/repo-template-playbook.html",
    "docs/repo-template-playbook.shell.html",
    "docs/repo-template-playbook.source.html",
    "docs/scaffolding.md",
    "docs/upgrading.md",
    "docs/assets/codexicon-operating-model-mobile.svg",
    "docs/assets/codexicon-operating-model.svg",
    "docs/assets/codexicon-readme-hero-mobile.svg",
    "docs/assets/codexicon-readme-hero.svg",
    "scripts/codexicon.py",
    "scripts/install-git-hooks.ps1",
    "scripts/install-git-hooks.sh",
    "scripts/lint.ps1",
    "scripts/lint.sh",
    "scripts/scaffold.py",
    "scripts/security.ps1",
    "scripts/security.sh",
    "scripts/security_scan.py",
    "scripts/setup.sh",
    "scripts/skill_provenance.py",
    "scripts/test.ps1",
    "scripts/test.sh",
)

_SOURCE_MANIFEST_NAME = ".codexicon.json"
_MANIFEST_VERSION_PATH = "TEMPLATE_VERSION"
_MANIFEST_POLICIES = {"managed", "merge", "project"}


def _relative_path(raw: str) -> str:
    normalized = raw.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or (len(normalized) > 1 and normalized[1] == ":")
    ):
        raise ScaffoldError(f"unsafe scaffold path: {raw!r}")
    return path.as_posix()


def _safe_source_file(source_root: Path, relative: str) -> Path:
    relative = _relative_path(relative)
    if is_protected_path(relative):
        raise ScaffoldError(f"protected path is not eligible for scaffolding: {relative}")
    source = source_root.joinpath(*PurePosixPath(relative).parts)
    if source.is_symlink():
        raise ScaffoldError(f"symlink source is not eligible for scaffolding: {relative}")
    try:
        resolved = source.resolve(strict=True)
        resolved.relative_to(source_root)
    except (OSError, ValueError) as exc:
        raise ScaffoldError(f"source file is outside the template: {relative}") from exc
    if not source.is_file():
        raise ScaffoldError(f"allowlisted source file is missing: {relative}")
    return source


def _target_is_protected(target: Path) -> bool:
    normalized = target.as_posix()
    return is_protected_path(normalized) or any(
        part.lower() in {"secrets", ".aws", ".ssh", ".kube", ".docker"}
        for part in target.parts
    )


def _source_manifest(source_root: Path, copied_paths: set[str]) -> bytes:
    manifest_path = _safe_source_file(source_root, _SOURCE_MANIFEST_NAME)
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScaffoldError("source .codexicon.json is not readable JSON") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ScaffoldError("source .codexicon.json must use schema version 1")
    version_path = _safe_source_file(source_root, _MANIFEST_VERSION_PATH)
    version = version_path.read_text(encoding="utf-8").splitlines()[0].strip()
    entries = value.get("files")
    if not isinstance(entries, list):
        raise ScaffoldError("source .codexicon.json requires a files list")

    filtered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, dict):
            raise ScaffoldError("source .codexicon.json contains a non-object file entry")
        relative = _relative_path(str(item.get("path", "")))
        policy = item.get("policy")
        if policy not in _MANIFEST_POLICIES:
            raise ScaffoldError(f"source .codexicon.json has invalid policy for {relative}")
        if relative not in copied_paths or relative in seen:
            continue
        seen.add(relative)
        filtered.append(
            {
                "path": relative,
                "policy": policy,
                **({"executable": True} if item.get("executable") is True else {}),
            }
        )

    for relative, policy in (("scripts/scaffold.py", "managed"),):
        if relative not in seen:
            filtered.append({"path": relative, "policy": policy})
    filtered.sort(key=lambda item: item["path"])
    result = {"schema_version": 1, "version": version, "files": filtered}
    return (json.dumps(result, indent=2, sort_keys=False) + "\n").encode("utf-8")


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    shutil.copymode(source, target)


def scaffold(
    target: Path,
    *,
    source: Path,
    dry_run: bool = False,
    output: Any | None = None,
) -> list[str]:
    """Create ``target`` from the reviewed starter allowlist.

    The target must not already exist. All sources are validated before any
    target directory is created, and a temporary sibling directory prevents a
    failed copy from leaving a partial starter at the requested path.
    """

    source_root = source.resolve()
    target = target.absolute()
    if not source_root.is_dir():
        raise ScaffoldError(f"scaffold source directory does not exist: {source_root}")
    if _target_is_protected(target):
        raise ScaffoldError(f"scaffold target is a protected path: {target}")
    if target.exists() or target.is_symlink():
        raise ScaffoldError(f"scaffold target already exists: {target}")
    try:
        target.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise ScaffoldError("scaffold target must not be inside the source template")

    paths = tuple(dict.fromkeys(_relative_path(path) for path in STARTER_FILES))
    sources = {relative: _safe_source_file(source_root, relative) for relative in paths}
    copied_paths = set(paths)
    manifest = _source_manifest(source_root, copied_paths)
    listed = list(paths)

    if output is not None:
        print(f"[scaffold] {'Would copy' if dry_run else 'Copying'} {len(listed)} files", file=output)
        for relative in listed:
            print(relative, file=output)
    if dry_run:
        return listed

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".codexicon-scaffold-", dir=target.parent))
    try:
        for relative, source_path in sources.items():
            _copy_file(source_path, staging.joinpath(*PurePosixPath(relative).parts))
        _copy_file(source_root / _SOURCE_MANIFEST_NAME, staging / _SOURCE_MANIFEST_NAME)
        (staging / _SOURCE_MANIFEST_NAME).write_bytes(manifest)
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    if output is not None:
        print(f"[scaffold] Created clean starter at {target}", file=output)
    return listed


def format_allowlist() -> Iterable[str]:
    """Return the reviewed allowlist for documentation and tests."""

    return STARTER_FILES


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        scaffold(args.target, source=args.source, dry_run=args.dry_run, output=sys.stdout)
    except ScaffoldError as exc:
        print(f"[scaffold] {exc}", file=sys.stderr)
        raise SystemExit(2)
