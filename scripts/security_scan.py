#!/usr/bin/env python3
"""Deterministic, dependency-free credential scan for local and CI gates."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".codex-state",
    ".git",
    ".mypy_cache",
    ".next",
    ".nuxt",
    ".pytest_cache",
    ".ruff_cache",
    ".svelte-kit",
    ".venv",
    ".wrangler",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "out",
    "venv",
}
PROTECTED_NAME = re.compile(
    r"(?ix)(?:"
    r"^\.env(?:\.[a-z0-9_-]+)*$|"
    r"^(?:\.npmrc|\.pypirc|\.netrc)$|"
    r"^(?:credentials|application_default_credentials)\.json$|"
    r"\.(?:key|pem|p12|pfx|secret)$"
    r")"
)
PROTECTED_PATH = re.compile(
    r"(?ix)(?:"
    r"(?:^|/)secrets/|"
    r"(?:^|/)\.aws/credentials$|"
    r"(?:^|/)\.ssh/id_(?:rsa|dsa|ecdsa|ed25519)$|"
    r"(?:^|/)\.kube/config$|"
    r"(?:^|/)\.docker/config\.json$|"
    r"(?:^|/)\.config/gh/hosts\.yml$|"
    r"(?:^|/)\.terraform\.d/credentials\.tfrc\.json$"
    r")"
)
TOKEN_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b")),
    ("openai-api-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("stripe-live-secret", re.compile(r"\b(?:sk|rk)_live_[0-9A-Za-z]{16,}\b")),
)
SECRET_ASSIGNMENT = re.compile(
    r"(?ix)\b(?:api[_-]?key|client[_-]?secret|password|passwd|secret|access[_-]?token|auth[_-]?token)"
    r"\s*[:=]\s*['\"]([^'\"]{8,})['\"]"
)
SAFE_VALUE_MARKERS = (
    "${",
    "$env:",
    "<",
    "[",
    "changeme",
    "dummy",
    "example",
    "fake",
    "getenv",
    "placeholder",
    "process.env",
    "redacted",
    "replace",
    "sample",
    "test",
    "your_",
    "xxxx",
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    detector: str


def normalized_relative(path: Path, root: Path) -> str:
    return path.absolute().relative_to(root.absolute()).as_posix()


def is_protected_path(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized == ".env.example" or normalized.endswith("/.env.example"):
        return False
    return bool(PROTECTED_NAME.search(Path(normalized).name) or PROTECTED_PATH.search(normalized))


def git_paths(root: Path, *args: str) -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", *args, "-z"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return [part.decode("utf-8", errors="surrogateescape") for part in result.stdout.split(b"\0") if part]


def is_git_root(root: Path) -> bool:
    """Return true only when Git identifies ``root`` as the repository root."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
        )
    except OSError:
        return False
    if result.returncode != 0:
        return False
    try:
        return Path(result.stdout.strip()).resolve() == root.resolve()
    except OSError:
        return False


def safe_candidate(path: Path, relative: str, root: Path, findings: list[Finding]) -> Path | None:
    """Return a safe file to scan without following a link outside the repository."""

    if not path.is_symlink():
        return path if path.is_file() else None
    try:
        target = path.resolve(strict=True)
        target_relative = target.relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        findings.append(Finding(relative, 0, "external-or-broken-symlink"))
        return None
    if is_protected_path(target_relative):
        findings.append(Finding(relative, 0, "protected-symlink-target"))
        return None
    if EXCLUDED_DIRS.intersection(Path(target_relative).parts):
        findings.append(Finding(relative, 0, "excluded-symlink-target"))
        return None
    return target if target.is_file() else None


def repository_files(root: Path) -> tuple[list[Path], list[Finding]]:
    findings: list[Finding] = []
    tracked = git_paths(root, "ls-files", "--cached") if is_git_root(root) else None
    if tracked is not None:
        findings.extend(
            Finding(path, 0, "protected-tracked-path") for path in tracked if is_protected_path(path)
        )
        candidates = git_paths(root, "ls-files", "--cached", "--others", "--exclude-standard") or []
        files = []
        for relative in candidates:
            path = root / relative
            if is_protected_path(relative):
                continue
            candidate = safe_candidate(path, relative, root, findings)
            if candidate is not None:
                files.append(candidate)
        return sorted(set(files)), findings

    files = []
    for path in root.rglob("*"):
        relative = normalized_relative(path, root)
        if EXCLUDED_DIRS.intersection(Path(relative).parts) or is_protected_path(relative):
            continue
        candidate = safe_candidate(path, relative, root, findings)
        if candidate is not None:
            files.append(candidate)
    return sorted(set(files)), findings


def scan_lines(path: Path, root: Path) -> Iterable[Finding]:
    try:
        with path.open("rb") as raw:
            prefix = raw.read(8192)
            if b"\0" in prefix:
                return
            content = prefix + raw.read()
    except (OSError, PermissionError):
        return

    text = content.decode("utf-8", errors="replace")
    relative = normalized_relative(path, root)
    for line_number, line in enumerate(text.splitlines(), start=1):
        for detector, pattern in TOKEN_PATTERNS:
            if pattern.search(line):
                yield Finding(relative, line_number, detector)
        assignment = SECRET_ASSIGNMENT.search(line)
        if assignment:
            value = assignment.group(1).lower()
            if not any(marker in value for marker in SAFE_VALUE_MARKERS):
                yield Finding(relative, line_number, "literal-secret-assignment")


def scan_repository(root: Path) -> list[Finding]:
    files, findings = repository_files(root)
    for path in files:
        findings.extend(scan_lines(path, root))
    return sorted(set(findings), key=lambda item: (item.path, item.line, item.detector))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root to scan")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    findings = scan_repository(root)
    if findings:
        print("Security scan failed; potential credentials were found:", file=sys.stderr)
        for finding in findings:
            location = f":{finding.line}" if finding.line else ""
            safe_path = finding.path.encode("unicode_escape", errors="backslashreplace").decode("ascii")
            print(f"- {safe_path}{location} [{finding.detector}]", file=sys.stderr)
        print("Values are intentionally redacted. Rotate any real credential before removing it.", file=sys.stderr)
        return 1
    print("[security] Protected paths and high-confidence credential patterns passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
