#!/usr/bin/env python3
"""Report deterministic interface patterns that warrant manual review."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


SOURCE_SUFFIXES = {
    ".astro",
    ".css",
    ".htm",
    ".html",
    ".js",
    ".jsx",
    ".less",
    ".mdx",
    ".sass",
    ".scss",
    ".svelte",
    ".ts",
    ".tsx",
    ".vue",
}
IGNORED_PARTS = {
    ".git",
    ".next",
    ".nuxt",
    ".output",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "vendor",
}


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    code: str
    message: str
    excerpt: str


LINE_RULES = (
    (
        "focus-outline-removed",
        re.compile(r"\boutline\s*:\s*(?:none|0(?:\s+[^;]+)?)\s*[;}]", re.IGNORECASE),
        "Focus outline is removed; verify an equally visible replacement for every input method.",
    ),
    (
        "transition-all",
        re.compile(r"\btransition(?:-property)?\s*:\s*all\b", re.IGNORECASE),
        "Transitioning all properties can animate layout unexpectedly; name only purposeful properties.",
    ),
    (
        "decorative-repeat-gradient",
        re.compile(r"repeating-(?:linear|radial|conic)-gradient\s*\(", re.IGNORECASE),
        "Repeating gradient may be decorative scaffolding; confirm it communicates the product or brand.",
    ),
    (
        "synthetic-sketch-filter",
        re.compile(r"<(?:feTurbulence|feDisplacementMap)\b", re.IGNORECASE),
        "Procedural sketch or grain filter may read as generated filler; confirm the art direction and cost.",
    ),
)


def iter_source_files(targets: Iterable[Path]) -> list[Path]:
    files: set[Path] = set()
    for target in targets:
        if target.is_file() and target.suffix.lower() in SOURCE_SUFFIXES:
            files.add(target.resolve())
            continue
        if not target.is_dir():
            continue
        for candidate in target.rglob("*"):
            if not candidate.is_file() or candidate.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            if IGNORED_PARTS.intersection(candidate.relative_to(target).parts):
                continue
            files.add(candidate.resolve())
    return sorted(files)


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def excerpt_for(text: str, line: int) -> str:
    lines = text.splitlines()
    if 1 <= line <= len(lines):
        return lines[line - 1].strip()[:180]
    return ""


def scan_text(path: Path, text: str) -> list[Finding]:
    findings: list[Finding] = []
    display_path = path.as_posix()

    for number, source_line in enumerate(text.splitlines(), start=1):
        for code, pattern, message in LINE_RULES:
            if pattern.search(source_line):
                findings.append(Finding(display_path, number, code, message, source_line.strip()[:180]))

        for match in re.finditer(r"\bz-index\s*:\s*(-?\d+)", source_line, re.IGNORECASE):
            if int(match.group(1)) >= 999:
                findings.append(
                    Finding(
                        display_path,
                        number,
                        "unbounded-z-index",
                        "Very high z-index suggests an unmanaged stacking system; verify a semantic layer scale.",
                        source_line.strip()[:180],
                    )
                )

    if re.search(r"(?:linear|radial|conic)-gradient\s*\(", text, re.IGNORECASE):
        for match in re.finditer(r"(?:-webkit-)?background-clip\s*:\s*text", text, re.IGNORECASE):
            number = line_number(text, match.start())
            findings.append(
                Finding(
                    display_path,
                    number,
                    "gradient-text",
                    "Gradient-clipped text is a common generated-design reflex; require a specific brand reason.",
                    excerpt_for(text, number),
                )
            )

    tag_pattern = re.compile(r"<(div|span)\b(?P<attrs>[^>]*\bonClick\s*=\s*[^>]*)>", re.IGNORECASE | re.DOTALL)
    for match in tag_pattern.finditer(text):
        attrs = match.group("attrs")
        if not re.search(r"\brole\s*=", attrs, re.IGNORECASE) or not re.search(
            r"\bonKey(?:Down|Up|Press)\s*=", attrs, re.IGNORECASE
        ):
            number = line_number(text, match.start())
            findings.append(
                Finding(
                    display_path,
                    number,
                    "nonsemantic-click-target",
                    "Clickable div or span may not support keyboard and assistive input; prefer a native control.",
                    excerpt_for(text, number),
                )
            )

    for match in re.finditer(r"<img\b(?P<attrs>[^>]*)>", text, re.IGNORECASE | re.DOTALL):
        if not re.search(r"\balt\s*=", match.group("attrs"), re.IGNORECASE):
            number = line_number(text, match.start())
            findings.append(
                Finding(
                    display_path,
                    number,
                    "image-alt-missing",
                    "Image has no explicit alt attribute; verify its accessible alternative or decorative intent.",
                    excerpt_for(text, number),
                )
            )

    return findings


def scan_paths(targets: Iterable[Path]) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    errors: list[str] = []
    for path in iter_source_files(targets):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"{path}: {exc}")
            continue
        findings.extend(scan_text(path, text))
    return findings, errors


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find deterministic interface patterns that need contextual review."
    )
    parser.add_argument("targets", nargs="+", type=Path, help="Source files or directories")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output")
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Return status 1 when findings exist; off by default because findings require review",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    missing = [str(target) for target in args.targets if not target.exists()]
    findings, errors = scan_paths(args.targets)
    errors.extend(f"target does not exist: {target}" for target in missing)

    if args.json:
        print(json.dumps({"findings": [asdict(item) for item in findings], "errors": errors}, indent=2))
    else:
        for item in findings:
            print(f"{item.path}:{item.line} [{item.code}] {item.message}")
        for error in errors:
            print(f"[scan-error] {error}", file=sys.stderr)
        print(f"Scanned with {len(findings)} review signal(s) and {len(errors)} error(s).")

    if errors:
        return 2
    if findings and args.fail_on_findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
