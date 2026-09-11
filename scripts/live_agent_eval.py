#!/usr/bin/env python3
"""Run a bounded direct-versus-Codexicon live Codex paired evaluation.

The evaluator intentionally keeps raw Codex output in memory only.  It records
event types, a short sanitized final-message excerpt, independent fixture-test
status, elapsed time, and explicit unmeasured telemetry fields.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
RUN_TIMEOUT_SECONDS = 90
TEST_TIMEOUT_SECONDS = 10
ORACLE_FILENAME = "test_calculator.py"
CALCULATOR_FILENAME = "calculator.py"
PROMPTS = {
    "direct": (
        "Fix the failing behavior in calculator.py so its unittest oracle passes. "
        "Inspect the files and run the oracle before and after the fix."
    ),
    "guided": (
        "Act as a Codexicon implementation agent. Inspect the task and existing files, "
        "run the unittest oracle to reproduce the deliberate failure, fix the behavior, "
        "verify by rerunning the oracle, and do not create or modify unrelated files."
    ),
}
UNMEASURED_FIELDS = ("model", "tokens", "cost", "tool_calls", "interventions")
_SECRET_PATTERNS = (
    (re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{8,}\b"), "<redacted-token>"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{8,}\b"), "<redacted-token>"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._-]{8,}"), "Bearer <redacted-token>"),
)


def build_codex_command(
    codex_executable: str | os.PathLike[str], fixture_dir: Path, prompt: str
) -> list[str]:
    """Build the one permitted local Codex invocation for a fixture."""

    return [
        os.fspath(codex_executable),
        "exec",
        "--ephemeral",
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "-C",
        str(fixture_dir),
        "--json",
        prompt,
    ]


def _oracle_source() -> str:
    return '''import unittest

import calculator


class CalculatorOracle(unittest.TestCase):
    def test_add_returns_the_sum(self):
        self.assertEqual(calculator.add(2, 3), 5)


if __name__ == "__main__":
    unittest.main()
'''


def create_fixture(fixture_dir: Path) -> None:
    """Create the deliberately failing calculator and canonical unittest oracle."""

    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / CALCULATOR_FILENAME).write_text(
        "def add(left, right):\n    return left - right\n",
        encoding="utf-8",
    )
    restore_oracle(fixture_dir)


def restore_oracle(fixture_dir: Path) -> None:
    """Restore the harness-owned oracle so the agent cannot redefine acceptance."""

    (fixture_dir / ORACLE_FILENAME).write_text(_oracle_source(), encoding="utf-8")


def _run_fixture_test(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: int,
    runner: Callable[..., Any],
) -> Any:
    return runner(
        list(command),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=timeout,
    )


def score_fixture(
    fixture_dir: Path,
    *,
    runner: Callable[..., Any] = subprocess.run,
    timeout: int = TEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Run the canonical oracle independently and return sanitized test status."""

    restore_oracle(fixture_dir)
    try:
        completed = _run_fixture_test(
            [sys.executable, "-B", "-m", "unittest", ORACLE_FILENAME],
            cwd=fixture_dir,
            timeout=timeout,
            runner=runner,
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "exit_status": "timeout"}
    except OSError as exc:
        return {"status": "error", "exit_status": type(exc).__name__}

    return {
        "status": "passed" if completed.returncode == 0 else "failed",
        "exit_status": completed.returncode,
    }


def _sanitize_text(value: str, fixture_dir: Path | None = None) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if fixture_dir is not None:
        value = value.replace(str(fixture_dir), "<temp>")
    for pattern, replacement in _SECRET_PATTERNS:
        value = pattern.sub(replacement, value)
    return value[:240]


def _event_message(event: Mapping[str, Any]) -> str | None:
    candidates: list[Any] = [event.get("message"), event.get("text")]
    item = event.get("item")
    if isinstance(item, Mapping):
        candidates.extend((item.get("text"), item.get("message")))
        content = item.get("content")
        if isinstance(content, list):
            candidates.extend(
                part.get("text")
                for part in content
                if isinstance(part, Mapping)
            )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    return None


def sanitize_events(stdout: str, stderr: str, fixture_dir: Path) -> dict[str, Any]:
    """Extract metadata only; never return arbitrary event payloads or stderr."""

    event_types: dict[str, int] = {}
    json_event_count = 0
    non_json_line_count = 0
    last_message: str | None = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            non_json_line_count += 1
            continue
        if not isinstance(event, Mapping):
            non_json_line_count += 1
            continue
        json_event_count += 1
        event_type = event.get("type")
        if isinstance(event_type, str):
            event_types[event_type] = event_types.get(event_type, 0) + 1
        message = _event_message(event)
        if message:
            last_message = _sanitize_text(message, fixture_dir)
    return {
        "json_event_count": json_event_count,
        "event_types": dict(sorted(event_types.items())),
        "non_json_line_count": non_json_line_count,
        "stderr_present": bool(stderr.strip()),
        "last_message_excerpt": last_message,
    }


def _fixture_snapshot(fixture_dir: Path) -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in fixture_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(fixture_dir).as_posix()
        if "__pycache__/" in f"{relative}/" or relative.endswith(".pyc"):
            continue
        snapshot[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def _changed_unrelated_files(before: Mapping[str, str], after: Mapping[str, str]) -> list[str]:
    changed = {
        name
        for name in set(before) | set(after)
        if before.get(name) != after.get(name)
    }
    return sorted(name for name in changed if name != CALCULATOR_FILENAME)


def _run_codex_process(command: Sequence[str], *, cwd: Path, timeout: int) -> Any:
    """Run Codex with a killable process group so Windows descendants cannot hang pipes."""

    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        process = subprocess.Popen(
            list(command),
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            creationflags=creationflags,
        )
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            if os.name == "nt":
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                        timeout=3,
                    )
                except subprocess.TimeoutExpired:
                    pass
            else:
                process.kill()
            raise subprocess.TimeoutExpired(command, timeout) from exc

        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read().decode("utf-8", errors="replace")
        stderr = stderr_file.read().decode("utf-8", errors="replace")
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def invoke_codex(
    codex_executable: str,
    fixture_dir: Path,
    prompt: str,
    *,
    timeout: int = RUN_TIMEOUT_SECONDS,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Invoke Codex once and retain only sanitized metadata."""

    command = build_codex_command(codex_executable, fixture_dir, prompt)
    started = time.monotonic()
    try:
        if runner is subprocess.run:
            completed = _run_codex_process(command, cwd=fixture_dir, timeout=timeout)
        else:
            completed = runner(
                command,
                cwd=fixture_dir,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=timeout,
            )
    except subprocess.TimeoutExpired:
        return {
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "exit_status": "timeout",
            "interrupted": True,
            "event_metadata": {
                "json_event_count": 0,
                "event_types": {},
                "non_json_line_count": 0,
                "stderr_present": False,
                "last_message_excerpt": None,
            },
        }
    except OSError as exc:
        return {
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "exit_status": type(exc).__name__,
            "interrupted": False,
            "event_metadata": {
                "json_event_count": 0,
                "event_types": {},
                "non_json_line_count": 0,
                "stderr_present": False,
                "last_message_excerpt": None,
            },
        }

    return {
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "exit_status": completed.returncode,
        "interrupted": False,
        "event_metadata": sanitize_events(
            getattr(completed, "stdout", "") or "",
            getattr(completed, "stderr", "") or "",
            fixture_dir,
        ),
    }


def run_arm(
    label: str,
    codex_executable: str,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"codexicon-live-{label}-") as name:
        fixture_dir = Path(name)
        create_fixture(fixture_dir)
        before = _fixture_snapshot(fixture_dir)
        invocation = invoke_codex(
            codex_executable,
            fixture_dir,
            PROMPTS[label],
            runner=runner,
        )
        after = _fixture_snapshot(fixture_dir)
        unrelated_files = _changed_unrelated_files(before, after)
        score = score_fixture(fixture_dir)
        return {
            "label": label,
            "acceptance": score["status"] == "passed",
            "test_status": score["status"],
            "test_exit_status": score["exit_status"],
            "elapsed_seconds": invocation["elapsed_seconds"],
            "exit_status": invocation["exit_status"],
            "interrupted": invocation["interrupted"],
            "regressions": unrelated_files,
            "regression_count": len(unrelated_files),
            "event_metadata": invocation["event_metadata"],
            "metrics": {field: "unmeasured" for field in UNMEASURED_FIELDS},
        }


def _aggregate(arms: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    accepted = sum(bool(arm["acceptance"]) for arm in arms)
    return {
        "accepted": accepted,
        "denominator": len(arms),
        "acceptance": f"{accepted}/{len(arms)}",
        "regressions": sum(int(arm["regression_count"]) for arm in arms),
        "interrupted": sum(bool(arm["interrupted"]) for arm in arms),
        "elapsed_seconds": round(sum(float(arm["elapsed_seconds"]) for arm in arms), 3),
    }


def _display_command(label: str) -> str:
    return (
        "codex exec --ephemeral --sandbox workspace-write --skip-git-repo-check "
        f"-C <temp> --json {label}-prompt"
    )


def _base_report(command: str, runs: int) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "denominator": {
            "paired_trials": runs,
            "direct_runs": runs,
            "guided_runs": runs,
        },
        "settings": {
            "fixture": "temporary calculator.py with canonical unittest oracle",
            "codex_commands": {
                "direct": _display_command("direct"),
                "guided": _display_command("guided"),
            },
            "timeout_seconds": RUN_TIMEOUT_SECONDS,
            "permissions": "local fixture only; no external writes",
        },
        "trials": [],
        "unmeasured_fields": list(UNMEASURED_FIELDS),
        "limitations": [
            "One paired trial is not evidence of direct-versus-guided superiority.",
            "The local CLI may not expose reliable model, token, cost, or tool-call telemetry.",
            "The fixture measures one calculator acceptance path, not general agent reliability.",
        ],
    }


def run_evaluation(
    *,
    runs: int = 1,
    command: str = "python scripts/live_agent_eval.py --smoke",
    codex_executable: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., Any] = subprocess.run,
) -> tuple[dict[str, Any], int]:
    if runs < 1:
        raise ValueError("runs must be at least 1")
    report = _base_report(command, runs)
    codex = codex_executable or which("codex")
    if not codex:
        report["status"] = "unavailable"
        report["error"] = "Codex CLI unavailable on PATH; no live invocations were run."
        report["limitations"].append("Live acceptance is unmeasured because the CLI was unavailable.")
        return report, 2

    direct_arms: list[dict[str, Any]] = []
    guided_arms: list[dict[str, Any]] = []
    for trial_number in range(1, runs + 1):
        direct = run_arm("direct", codex, runner=runner)
        guided = run_arm("guided", codex, runner=runner)
        direct_arms.append(direct)
        guided_arms.append(guided)
        report["trials"].append(
            {
                "trial": trial_number,
                "direct": direct,
                "guided": guided,
                "paired": True,
            }
        )

    report["aggregate"] = {
        "direct": _aggregate(direct_arms),
        "guided": _aggregate(guided_arms),
    }
    failed = any(
        arm["exit_status"] != 0 or arm["test_status"] != "passed"
        for arm in direct_arms + guided_arms
    )
    report["status"] = "failed" if failed else "passed"
    return report, 1 if failed else 0


def _print_report(report: Mapping[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(f"live paired evaluation: {report.get('status', 'unknown')}")
    print(f"paired trials: {report['denominator']['paired_trials']}")
    if "aggregate" in report:
        for label in ("direct", "guided"):
            aggregate = report["aggregate"][label]
            print(
                f"{label}: acceptance {aggregate['acceptance']}; "
                f"regressions {aggregate['regressions']}; "
                f"elapsed {aggregate['elapsed_seconds']}s"
            )
    if report.get("error"):
        print(f"error: {report['error']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--smoke", action="store_true", help="run exactly one paired trial")
    mode.add_argument("--runs", type=int, default=1, help="number of paired trials (default: 1)")
    parser.add_argument("--json", action="store_true", help="emit the sanitized report as JSON")
    parser.add_argument("--dry-run", action="store_true", help="print the planned command without invoking Codex")
    args = parser.parse_args(argv)
    runs = 1 if args.smoke else args.runs
    if runs < 1:
        parser.error("--runs must be at least 1")
    if args.dry_run:
        report = _base_report("python scripts/live_agent_eval.py --dry-run", runs)
        report["status"] = "dry-run"
        report["dry_run"] = True
        _print_report(report, args.json)
        return 0
    report, status = run_evaluation(
        runs=runs,
        command="python scripts/live_agent_eval.py --smoke" if args.smoke else f"python scripts/live_agent_eval.py --runs {runs}",
    )
    _print_report(report, args.json)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
