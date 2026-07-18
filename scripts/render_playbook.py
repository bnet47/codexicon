#!/usr/bin/env python3
"""Render the tracked playbook fragment into its standalone HTML document."""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "repo-template-playbook.source.html"
SHELL = ROOT / "docs" / "repo-template-playbook.shell.html"
OUTPUT = ROOT / "docs" / "repo-template-playbook.html"
MARKER = "{{CODEX_PLAYBOOK_FRAGMENT}}"


def render() -> str:
    fragment = SOURCE.read_text(encoding="utf-8")
    shell = SHELL.read_text(encoding="utf-8")
    if shell.count(MARKER) != 1:
        raise ValueError(f"playbook shell must contain exactly one {MARKER} marker")
    return shell.replace(MARKER, html.escape(fragment, quote=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the standalone file is stale")
    parser.add_argument("--output", type=Path, default=OUTPUT, help="standalone output path")
    args = parser.parse_args(argv)

    try:
        rendered = render()
    except (OSError, ValueError) as exc:
        print(f"Playbook render failed: {exc}", file=sys.stderr)
        return 1

    output = args.output.resolve()
    if args.check:
        try:
            current = output.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Playbook output is unavailable: {exc}", file=sys.stderr)
            return 1
        if current != rendered:
            print("Playbook output is stale; run: python scripts/render_playbook.py", file=sys.stderr)
            return 1
        print("[playbook] Editable source and standalone output match.")
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(rendered)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

