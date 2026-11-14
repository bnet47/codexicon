#!/usr/bin/env python3
"""Run a bounded direct-versus-guided-versus-routed live Codex evaluation.

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
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

try:
    import autonomy_eval as autonomy
except ImportError:  # pragma: no cover - imported as scripts.live_agent_eval
    from scripts import autonomy_eval as autonomy


ROOT = Path(__file__).resolve().parents[1]
RUN_TIMEOUT_SECONDS = 90
TEST_TIMEOUT_SECONDS = 10
MAX_CAPTURE_BYTES_PER_STREAM = 1024 * 1024
CAPTURE_CHUNK_BYTES = 64 * 1024
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
    "routed": (
        "Act as a Codexicon routed implementation worker only when this task is eligible. "
        "Use the supplied minimum-sufficient task envelope, do not broaden files or authority, "
        "do not spawn another worker, fix calculator.py, run the unittest oracle before and "
        "after the fix, and leave integration and acceptance to the primary."
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


def score_fixture(
    fixture_dir: Path,
) -> dict[str, Any]:
    """Score a fixture without importing or executing agent-written Python."""

    result = autonomy.verify_fixture(fixture_dir, "calculator")
    passed = result["status"] == "passed"
    return {
        "status": result["status"],
        "exit_status": 0 if passed else 1,
        "method": result.get("method", "non-executing AST evaluation"),
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
    if fixture_dir.is_symlink() or not fixture_dir.is_dir():
        raise ValueError("evaluation fixture root is not a directory")
    snapshot: dict[str, str] = {}
    for path in fixture_dir.rglob("*"):
        relative = path.relative_to(fixture_dir).as_posix()
        if path.is_symlink():
            snapshot[relative] = "symlink"
            continue
        if not path.is_file():
            continue
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


class OutputLimitExceeded(RuntimeError):
    """Raised after evaluator output exceeds its bounded capture allowance."""


def _create_windows_kill_job(process: Any) -> Any:
    """Assign and then resume the suspended evaluator in a kill-on-close job."""

    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount",
        )]

    class ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", BasicLimitInformation),
            ("IoInfo", IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class ThreadEntry32(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ThreadID", wintypes.DWORD),
            ("th32OwnerProcessID", wintypes.DWORD),
            ("tpBasePri", wintypes.LONG),
            ("tpDeltaPri", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel32.SetInformationJobObject.restype = wintypes.BOOL
    kernel32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD,
    ]
    kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
    kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.TerminateJobObject.restype = wintypes.BOOL
    kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.Thread32First.restype = wintypes.BOOL
    kernel32.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry32)]
    kernel32.Thread32Next.restype = wintypes.BOOL
    kernel32.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(ThreadEntry32)]
    kernel32.OpenThread.restype = wintypes.HANDLE
    kernel32.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.ResumeThread.restype = wintypes.DWORD
    kernel32.ResumeThread.argtypes = [wintypes.HANDLE]

    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        error = ctypes.WinError(ctypes.get_last_error())
        if process.poll() is None:
            process.kill()
        process.wait()
        raise error
    limits = ExtendedLimitInformation()
    limits.BasicLimitInformation.LimitFlags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    try:
        if not kernel32.SetInformationJobObject(
            job, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel32.AssignProcessToJobObject(job, process._handle):
            raise ctypes.WinError(ctypes.get_last_error())
        snapshot = kernel32.CreateToolhelp32Snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
        invalid_handle = ctypes.c_void_p(-1).value
        if not snapshot or snapshot == invalid_handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry = ThreadEntry32()
            entry.dwSize = ctypes.sizeof(entry)
            primary_thread_id = None
            found = kernel32.Thread32First(snapshot, ctypes.byref(entry))
            while found:
                if entry.th32OwnerProcessID == process.pid:
                    if primary_thread_id is not None:
                        raise OSError("suspended evaluator has multiple startup threads")
                    primary_thread_id = entry.th32ThreadID
                found = kernel32.Thread32Next(snapshot, ctypes.byref(entry))
            if primary_thread_id is None:
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel32.CloseHandle(snapshot)
        thread = kernel32.OpenThread(0x0002, False, primary_thread_id)  # THREAD_SUSPEND_RESUME
        if not thread:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if kernel32.ResumeThread(thread) == 0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel32.CloseHandle(thread)
        return (kernel32, job)
    except BaseException:
        kernel32.TerminateJobObject(job, 1)
        kernel32.CloseHandle(job)
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=3,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
        process.wait()
        raise


def _close_windows_kill_job(job: Any) -> None:
    if job is not None:
        kernel32, handle = job
        if not kernel32.CloseHandle(handle):
            raise OSError("failed to close evaluator process Job Object")


def _terminate_process_tree(process: Any, job: Any) -> None:
    if os.name == "nt":
        _close_windows_kill_job(job)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            if process.poll() is None:
                process.kill()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _run_codex_process(command: Sequence[str], *, cwd: Path, timeout: int) -> Any:
    """Run Codex with bounded output and platform-specific process cleanup."""

    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    if os.name == "nt":
        creationflags |= getattr(subprocess, "CREATE_SUSPENDED", 0x00000004)
    process = subprocess.Popen(
        list(command),
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        creationflags=creationflags,
        start_new_session=os.name != "nt",
    )
    try:
        job = _create_windows_kill_job(process)
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait()
        raise
    output_exceeded = threading.Event()
    captured: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}

    def drain(name: str, stream: Any) -> None:
        while True:
            chunk = stream.read(CAPTURE_CHUNK_BYTES)
            if not chunk:
                return
            kept = captured[name]
            available = MAX_CAPTURE_BYTES_PER_STREAM - len(kept)
            if available > 0:
                kept.extend(chunk[:available])
            if len(chunk) > available:
                output_exceeded.set()

    readers = [
        threading.Thread(target=drain, args=(name, stream), daemon=True)
        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr))
    ]
    for reader in readers:
        reader.start()

    deadline = time.monotonic() + timeout
    timed_out = False
    try:
        while process.poll() is None:
            if output_exceeded.is_set():
                _terminate_process_tree(process, job)
                job = None
                raise OutputLimitExceeded("Codex output exceeded the capture limit")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                _terminate_process_tree(process, job)
                job = None
                raise subprocess.TimeoutExpired(command, timeout)
            time.sleep(min(0.02, remaining))
        if output_exceeded.is_set():
            _terminate_process_tree(process, job)
            job = None
            raise OutputLimitExceeded("Codex output exceeded the capture limit")
        # Remove background descendants even when the CLI itself exited normally.
        _terminate_process_tree(process, job)
        job = None
    finally:
        if job is not None:
            _close_windows_kill_job(job)
        for stream in (process.stdout, process.stderr):
            if stream is not None:
                stream.close()
        for reader in readers:
            reader.join(timeout=1)

    stdout = bytes(captured["stdout"]).decode("utf-8", errors="replace")
    stderr = bytes(captured["stderr"]).decode("utf-8", errors="replace")
    if timed_out:
        raise subprocess.TimeoutExpired(command, timeout)
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
            "invocation_started": True,
            "event_metadata": {
                "json_event_count": 0,
                "event_types": {},
                "non_json_line_count": 0,
                "stderr_present": False,
                "last_message_excerpt": None,
            },
        }
    except OutputLimitExceeded:
        return {
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "exit_status": "output_limit_exceeded",
            "interrupted": True,
            "invocation_started": True,
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
            "invocation_started": False,
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
        "invocation_started": True,
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
            "test_verification_method": score["method"],
            "elapsed_seconds": invocation["elapsed_seconds"],
            "exit_status": invocation["exit_status"],
            "interrupted": invocation["interrupted"],
            "invocation_started": invocation["invocation_started"],
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
        "attempted": sum(bool(arm.get("invocation_started")) for arm in arms),
        "unavailable": sum(not bool(arm.get("invocation_started")) for arm in arms),
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
            "routed_runs": runs,
        },
        "settings": {
            "fixture": "temporary calculator.py with canonical unittest oracle",
            "codex_commands": {
                "direct": _display_command("direct"),
                "guided": _display_command("guided"),
                "routed": _display_command("routed"),
            },
            "timeout_seconds": RUN_TIMEOUT_SECONDS,
            "permissions": "local fixture only; no external writes",
        },
        "trials": [],
        "unmeasured_fields": list(UNMEASURED_FIELDS),
        "limitations": [
            "One paired trial is not evidence of direct-versus-guided-or-routed superiority.",
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
    routed_arms: list[dict[str, Any]] = []
    for trial_number in range(1, runs + 1):
        direct = run_arm("direct", codex, runner=runner)
        guided = run_arm("guided", codex, runner=runner)
        routed = run_arm("routed", codex, runner=runner)
        direct_arms.append(direct)
        guided_arms.append(guided)
        routed_arms.append(routed)
        report["trials"].append(
            {
                "trial": trial_number,
                "direct": direct,
                "guided": guided,
                "routed": routed,
                "paired": True,
            }
        )

    report["aggregate"] = {
        "direct": _aggregate(direct_arms),
        "guided": _aggregate(guided_arms),
        "routed": _aggregate(routed_arms),
    }
    failed = any(
        arm["exit_status"] != 0 or arm["test_status"] != "passed"
        for arm in direct_arms + guided_arms + routed_arms
    )
    unavailable = any(not arm["invocation_started"] for arm in direct_arms + guided_arms + routed_arms)
    report["status"] = "unavailable" if unavailable else "failed" if failed else "passed"
    return report, 2 if unavailable else 1 if failed else 0


def _paired_arm(
    label: str,
    codex_executable: str,
    *,
    fixture_id: str,
    scenario_id: str | None,
    source_root: Path | None,
    timeout: int,
    runner: Callable[..., Any],
) -> dict[str, Any]:
    """Run one isolated arm with the same task, oracle, and timeout."""

    started = time.monotonic()
    temporary = tempfile.TemporaryDirectory(prefix=f"codexicon-paired-{fixture_id}-{label}-")
    name = Path(temporary.name)
    workspace = name / "workspace"
    record: dict[str, Any]
    try:
        staged = autonomy.prepare_arm(
            workspace,
            fixture_id=fixture_id,
            source_root=source_root,
        )
        before = autonomy._snapshot(workspace)
        trusted_workspace = workspace.resolve()
        task = (
            autonomy.recovery_scenario_task(fixture_id, scenario_id)
            if scenario_id
            else staged["task"]
        )
        invocation = invoke_codex(
            codex_executable,
            workspace,
            task,
            timeout=timeout,
            runner=runner,
        )
        after = autonomy._snapshot(workspace)
        changed_paths = autonomy._changed_paths(before, after)
        workspace_intact = (
            workspace.exists()
            and not workspace.is_symlink()
            and workspace.resolve() == trusted_workspace
        )
        scope_status = (
            "passed"
            if set(changed_paths) <= set(staged["allowed_paths"])
            and not autonomy._symlink_paths(workspace)
            and workspace_intact
            else "failed"
        )
        verification = (
            autonomy.verify_fixture(workspace, fixture_id, timeout=TEST_TIMEOUT_SECONDS)
            if workspace_intact and invocation["invocation_started"]
            else {"status": "unmeasured", "reason": "Codex process did not start"}
            if workspace_intact
            else {"status": "unmeasured", "reason": "fixture workspace root changed during the run"}
        )
        trial_status = (
            "unavailable"
            if not invocation["invocation_started"]
            else "timed_out"
            if invocation["exit_status"] == "timeout"
            else "completed"
            if invocation["exit_status"] == 0
            else "interrupted"
        )
        result = autonomy.assess_trial(
            trial_id=f"{fixture_id}-{label}",
            fixture_id=fixture_id,
            trial_status=trial_status,
            verification_status=verification["status"],
            scope_status=scope_status,
            cleanup_status="unmeasured",
            changed_paths=changed_paths,
            unauthorized_action_attempts=(),
            unauthorized_attempt_status="unmeasured",
            interruptions=int(bool(invocation["interrupted"])),
            metrics={"elapsed_seconds": invocation["elapsed_seconds"]},
            valid=trial_status == "completed" and invocation["exit_status"] == 0,
        )
        record = result.to_record()
        record.update(
            {
                "label": label,
                "exit_status": invocation["exit_status"],
                "invocation_started": invocation["invocation_started"],
                "event_metadata": invocation["event_metadata"],
                "verification": verification,
                "starter_staged": staged["starter_staged"],
                "starter_digest": staged["starter_digest"],
                "client_pickup_status": staged["client_pickup_status"],
                "method_observation_status": staged["method_observation_status"],
                "allowed_paths": staged["allowed_paths"],
                "required_capabilities": staged["required_capabilities"],
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        )
    except (OSError, ValueError) as exc:
        record = {
            "schema_version": 1,
            "trial_status": "unavailable",
            "verification_status": "unmeasured",
            "scope_status": "unmeasured",
            "cleanup_status": "unmeasured",
            "accepted": False,
            "label": label,
            "fixture_id": fixture_id,
                "recovery_scenario": scenario_id,
            "error": type(exc).__name__,
            "invocation_started": False,
            "starter_staged": False,
            "client_pickup_status": "unmeasured",
        }
    try:
        temporary.cleanup()
        cleanup_status = "passed" if not name.exists() else "failed"
    except OSError as exc:
        cleanup_status = "failed"
        record["cleanup_error"] = type(exc).__name__
    record["cleanup_status"] = cleanup_status
    if cleanup_status != "passed":
        record["trial_status"] = "invalid"
        record["accepted"] = False
    else:
        record["accepted"] = (
            bool(record.get("valid", True))
            and record.get("trial_status") == "completed"
            and record.get("verification_status") == "passed"
            and record.get("scope_status") == "passed"
        )
    record["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return record


def _client_version(executable: str) -> dict[str, Any]:
    """Read only the CLI's bounded version string; never capture other metadata."""

    try:
        result = subprocess.run(
            [executable, "--version"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"status": "unmeasured", "value": None}
    if result.returncode != 0:
        return {"status": "unmeasured", "value": None}
    version = (result.stdout or "").strip().splitlines()
    if not version:
        return {"status": "unmeasured", "value": None}
    return {"status": "measured", "value": _sanitize_text(version[0])[:120]}


def run_paired(
    *,
    fixture_id: str,
    scenario_id: str | None = None,
    runs: int = 1,
    baseline_source: Path,
    candidate_source: Path | None = None,
    timeout_seconds: int = RUN_TIMEOUT_SECONDS,
    codex_executable: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., Any] = subprocess.run,
    version_probe: Callable[[str], Mapping[str, Any]] = _client_version,
) -> tuple[dict[str, Any], int]:
    """Compare plain, actual starter, and optional candidate arms."""

    if fixture_id not in autonomy.FIXTURES:
        raise ValueError(f"unsupported fixture: {fixture_id}")
    scenario = None
    if scenario_id is not None:
        try:
            scenario = autonomy.RECOVERY_SCENARIOS[scenario_id]
        except KeyError as exc:
            raise ValueError(f"unsupported recovery scenario: {scenario_id}") from exc
        if scenario.fixture_id != fixture_id:
            raise ValueError(f"scenario {scenario_id} requires fixture {scenario.fixture_id}")
        if candidate_source is None:
            raise ValueError("recovery scenarios require --candidate-source for three-arm comparison")
    if runs < 1:
        raise ValueError("runs must be at least 1")
    if scenario_id is not None and runs > 2:
        raise ValueError("recovery scenarios are capped at two paired repeats")
    if timeout_seconds < 1 or timeout_seconds > 900:
        raise ValueError("timeout-seconds must be between 1 and 900")
    arms = ["plain", "starter"] + (["candidate"] if candidate_source else [])
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "paired",
        "fixture": fixture_id,
        "scenario": scenario_id,
        "fixture_catalog_version": 1,
        "status": "pending",
        "denominator": {
            "paired_trials": runs,
            **{f"{arm}_runs": runs for arm in arms},
        },
        "settings": {
            "task_text": (
                autonomy.recovery_scenario_task(fixture_id, scenario_id)
                if scenario_id
                else autonomy.FIXTURES[fixture_id].task
            ),
            "same_task_and_fixture": True,
            "same_model_settings": True,
            "same_tools_and_permissions": True,
            "same_timeout_seconds": timeout_seconds,
            "starter_source": str(baseline_source.resolve()),
            "candidate_source": str(candidate_source.resolve()) if candidate_source else None,
            "starter_identity": None,
            "candidate_identity": None,
            "client_version": {"status": "unmeasured", "value": None},
            "raw_transcripts_saved": False,
            "scenario_injection": "fixed task instruction" if scenario else None,
            "continuation_observation": "unmeasured",
        },
        "trials": [],
        "aggregate": {},
        "unmeasured_fields": [
            "client_pickup",
            "method_observation",
            "unauthorized_action_attempts",
            "tokens",
            "cost",
            "tool_calls",
        ],
        "limitations": [
            "Starter staging is observed; client pickup and delegation are unmeasured without a trustworthy client signal.",
            "A paired trial is a bounded pilot, not evidence of general superiority.",
            "The plain arm receives the same synthetic contract and task files but no Codexicon starter files.",
        ],
    }
    report["denominator"].update(
        {
            "planned_arm_trials": runs * len(arms),
            "attempted_arm_trials": 0,
        }
    )
    if scenario:
        report["scenario_definition"] = {
            "trigger": scenario.trigger,
            "required_observation": scenario.required_observation,
            "unavailable_reason": scenario.unavailable_reason,
        }
        if scenario_id == "tool-unavailable":
            report["limitations"].append(
                "Tool absence is represented in fixed task text; actual client tool availability is unmeasured."
            )
    try:
        report["settings"]["starter_identity"] = autonomy._starter_identity(
            baseline_source.resolve(strict=True)
        )
        if candidate_source:
            report["settings"]["candidate_identity"] = autonomy._starter_identity(
                candidate_source.resolve(strict=True)
            )
    except (OSError, ValueError) as exc:
        report["status"] = "invalid"
        report["error"] = f"starter source rejected ({type(exc).__name__})"
        return report, 2
    codex = codex_executable or which("codex")
    if not codex:
        report["status"] = "unavailable"
        report["error"] = "Codex CLI unavailable on PATH; no live invocations were run."
        return report, 2
    try:
        report["settings"]["client_version"] = dict(version_probe(codex))
    except Exception:  # Do not turn optional version telemetry into a failed trial.
        report["settings"]["client_version"] = {"status": "unmeasured", "value": None}

    if scenario and scenario.unavailable_reason:
        report["status"] = "unavailable"
        report["error"] = scenario.unavailable_reason
        report["aggregate"] = {
            label: {
                **autonomy.recovery_denominator(runs, []),
                "denominator": runs,
                "elapsed_seconds": 0,
            }
            for label in arms
        }
        return report, 2

    by_arm: dict[str, list[dict[str, Any]]] = {arm: [] for arm in arms}
    for run in range(runs):
        rotation = run % len(arms)
        order = arms[rotation:] + arms[:rotation]
        results: dict[str, Any] = {}
        for label in order:
            source = None if label == "plain" else (
                candidate_source if label == "candidate" else baseline_source
            )
            results[label] = _paired_arm(
                label,
                codex,
                fixture_id=fixture_id,
                scenario_id=scenario_id,
                source_root=source,
                timeout=timeout_seconds,
                runner=runner,
            )
            by_arm[label].append(results[label])
        report["trials"].append(
            {"trial": run + 1, "order": order, "arms": results, "paired": True}
        )
    report["aggregate"] = {
        label: {
            "accepted": sum(bool(item.get("accepted")) for item in values),
            "denominator": len(values),
            "attempted": sum(bool(item.get("invocation_started")) for item in values),
            "unavailable": sum(item.get("trial_status") == "unavailable" for item in values),
            "unmeasured": sum(
                item.get("verification_status") == "unmeasured"
                or item.get("scope_status") == "unmeasured"
                for item in values
            ),
            "interrupted": sum(item.get("trial_status") in {"interrupted", "timed_out"} for item in values),
            "scope_failures": sum(item.get("scope_status") == "failed" for item in values),
            "elapsed_seconds": round(
                sum(float(item.get("elapsed_seconds", 0)) for item in values), 3
            ),
        }
        for label, values in by_arm.items()
    }
    unavailable = any(
        item.get("trial_status") == "unavailable"
        for values in by_arm.values()
        for item in values
    )
    all_items = [item for values in by_arm.values() for item in values]
    report["denominator"]["attempted_arm_trials"] = sum(
        bool(item.get("invocation_started")) for item in all_items
    )
    failed = any(
        item.get("verification_status") == "failed"
        or item.get("scope_status") == "failed"
        or item.get("trial_status") in {"interrupted", "timed_out", "invalid"}
        or item.get("cleanup_status") == "failed"
        for item in all_items
    )
    unmeasured = any(
        item.get("verification_status") == "unmeasured"
        or item.get("scope_status") == "unmeasured"
        for item in all_items
    )
    report["status"] = (
        "unavailable" if unavailable else "failed" if failed else "unmeasured" if unmeasured else "passed"
    )
    return report, 2 if unavailable else 1 if failed else 3 if unmeasured else 0


def _skill_file_digest(source_root: Path, relative: str) -> str:
    source = source_root.resolve(strict=True)
    skill = autonomy._trusted_workspace_file(source, relative)
    return hashlib.sha256(skill.read_bytes()).hexdigest()


def run_skill_comparison(
    *,
    baseline_source: Path,
    candidate_source: Path,
    runs: int = 1,
    timeout_seconds: int = RUN_TIMEOUT_SECONDS,
    codex_executable: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    runner: Callable[..., Any] = subprocess.run,
    version_probe: Callable[[str], Mapping[str, Any]] = _client_version,
) -> tuple[dict[str, Any], int]:
    """Compare a pinned first-party skill, candidate, and no-skill control."""

    if runs < 1 or runs > 2:
        raise ValueError("skill comparison runs must be between one and two")
    skill_path = ".agents/skills/autonomous-build/SKILL.md"
    try:
        baseline_identity = autonomy._starter_identity(baseline_source.resolve(strict=True))
        candidate_identity = autonomy._starter_identity(candidate_source.resolve(strict=True))
        baseline_skill_digest = _skill_file_digest(baseline_source, skill_path)
        candidate_skill_digest = _skill_file_digest(candidate_source, skill_path)
    except (OSError, ValueError) as exc:
        return {
            "schema_version": 1,
            "mode": "skill-comparison",
            "status": "invalid",
            "error": f"skill source rejected ({type(exc).__name__})",
            "trials": [],
        }, 2
    if baseline_skill_digest == candidate_skill_digest:
        raise ValueError("candidate skill must differ from the pinned current skill")

    client_version = {"status": "unmeasured", "value": None}
    codex = codex_executable or which("codex")
    if codex:
        try:
            client_version = dict(version_probe(codex))
        except Exception:  # Optional version telemetry cannot fail the evaluation.
            client_version = {"status": "unmeasured", "value": None}
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "skill-comparison",
        "skill": "autonomous-build",
        "status": "pending",
        "settings": {
            "baseline_source_identity": baseline_identity,
            "candidate_source_identity": candidate_identity,
            "current_skill_sha256": baseline_skill_digest,
            "candidate_skill_sha256": candidate_skill_digest,
            "client_version": client_version,
            "runs_per_case_arm": runs,
            "raw_transcripts_saved": False,
        },
        "cases": [],
        "denominator": {
            "cases": len(autonomy.SKILL_COMPARISON_CASES),
            "runs_per_case_arm": runs,
            "planned_arm_trials": len(autonomy.SKILL_COMPARISON_CASES) * runs * 3,
            "attempted_arm_trials": 0,
        },
        "observations_by_arm": {"current": [], "candidate": [], "no-skill": []},
        "unmeasured_fields": [
            "skill_invocation",
            "model",
            "tokens",
            "cost",
            "tool_calls",
            "interventions",
        ],
        "promotion": {
            "automatic": False,
            "authorized": False,
            "maintainer_decision_required": True,
        },
    }
    if not codex:
        report["status"] = "unavailable"
        report["error"] = "Codex CLI unavailable on PATH; no skill trials were run."
        report["summary"] = autonomy.skill_comparison_summary(
            autonomy.SKILL_COMPARISON_CASES, report["observations_by_arm"]
        )
        return report, 2

    status_codes: list[int] = []
    arm_names = {"plain": "no-skill", "starter": "current", "candidate": "candidate"}
    skill_digests = {
        "plain": None,
        "starter": baseline_skill_digest,
        "candidate": candidate_skill_digest,
    }
    for case in autonomy.SKILL_COMPARISON_CASES:
        paired, status = run_paired(
            fixture_id=str(case["fixture_id"]),
            runs=runs,
            baseline_source=baseline_source,
            candidate_source=candidate_source,
            timeout_seconds=timeout_seconds,
            codex_executable=codex,
            which=which,
            runner=runner,
            version_probe=lambda _: client_version,
        )
        status_codes.append(status)
        case_report = {
            "case_id": case["case_id"],
            "fixture_id": case["fixture_id"],
            "trigger_class": case["trigger_class"],
            "expected_trigger": case["expected_trigger"],
            "rationale": case["rationale"],
            "paired_report": paired,
        }
        for trial in paired.get("trials", []):
            for label, outcome in trial["arms"].items():
                arm = arm_names[label]
                observation = {
                    "case_id": case["case_id"],
                    "skill_presence": "absent" if label == "plain" else "present",
                    "skill_sha256": skill_digests[label],
                    "invocation_status": "unmeasured",
                    "invocation_started": bool(outcome.get("invocation_started")),
                    "outcome_status": (
                        "passed"
                        if outcome.get("accepted")
                        else "failed"
                        if outcome.get("trial_status") == "completed"
                        else "unmeasured"
                    ),
                    "elapsed_seconds": outcome.get("elapsed_seconds"),
                    "cost": None,
                }
                report["observations_by_arm"][arm].append(observation)
        report["cases"].append(case_report)
    report["denominator"]["attempted_arm_trials"] = sum(
        bool(item.get("invocation_started"))
        for records in report["observations_by_arm"].values()
        for item in records
    )
    report["summary"] = autonomy.skill_comparison_summary(
        autonomy.SKILL_COMPARISON_CASES, report["observations_by_arm"]
    )
    report["status"] = (
        "unavailable"
        if any(status == 2 for status in status_codes)
        else "failed"
        if any(status == 1 for status in status_codes)
        else "unmeasured"
        if any(status == 3 for status in status_codes)
        or any(
            observation.get("invocation_status") == "unmeasured"
            for observations in report["observations_by_arm"].values()
            for observation in observations
        )
        else "passed"
    )
    return report, 2 if report["status"] == "unavailable" else 1 if report["status"] == "failed" else 3 if report["status"] == "unmeasured" else 0


def _print_report(report: Mapping[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print(f"live paired evaluation: {report.get('status', 'unknown')}")
    if "paired_trials" in report.get("denominator", {}):
        print(f"paired trials: {report['denominator']['paired_trials']}")
    elif "planned_arm_trials" in report.get("denominator", {}):
        print(f"planned arm trials: {report['denominator']['planned_arm_trials']}")
    if "aggregate" in report:
        labels = tuple(report["aggregate"])
        for label in labels:
            aggregate = report["aggregate"][label]
            acceptance = aggregate.get("acceptance")
            if acceptance is None:
                acceptance = f"{aggregate.get('accepted', 0)}/{aggregate['denominator']}"
            print(
                f"{label}: accepted {acceptance}; "
                f"scope failures {aggregate.get('scope_failures', aggregate.get('regressions', 0))}; "
                f"elapsed {aggregate['elapsed_seconds']}s"
            )
    if report.get("error"):
        print(f"error: {report['error']}")
    if report.get("summary", {}).get("arms"):
        for label, arm in report["summary"]["arms"].items():
            activation = arm["skill_activation"]
            outcome = arm["outcome_quality"]
            print(
                f"{label}: outcome {outcome['passed']}/{outcome['denominator']}; "
                f"skill invocation {activation['status']}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--smoke", action="store_true", help="run exactly one paired trial")
    mode.add_argument("--paired", action="store_true", help="compare plain, starter, and optional candidate arms")
    mode.add_argument(
        "--skill-comparison",
        action="store_true",
        help="compare current, candidate, and no-skill arms on fixed trigger cases",
    )
    parser.add_argument("--runs", type=int, help="number of paired trials (default: 1)")
    parser.add_argument("--fixture", help="declared synthetic fixture ID for --paired")
    parser.add_argument(
        "--scenario",
        choices=tuple(autonomy.RECOVERY_SCENARIOS),
        help="bounded recovery scenario for --paired",
    )
    parser.add_argument("--baseline-source", type=Path, help="reviewed local Codexicon starter source")
    parser.add_argument("--candidate-source", type=Path, help="optional reviewed local candidate source")
    parser.add_argument("--timeout-seconds", type=int, default=RUN_TIMEOUT_SECONDS, help="per-invocation hard timeout")
    parser.add_argument("--json", action="store_true", help="emit the sanitized report as JSON")
    parser.add_argument("--dry-run", action="store_true", help="print the planned command without invoking Codex")
    args = parser.parse_args(argv)
    runs = 1 if args.runs is None else args.runs
    if args.smoke and args.runs is not None:
        parser.error("--smoke always runs one trial and cannot be combined with --runs")
    if runs < 1:
        parser.error("--runs must be at least 1")
    if args.skill_comparison:
        if not args.baseline_source or not args.candidate_source:
            parser.error("--skill-comparison requires --baseline-source and --candidate-source")
        if args.fixture or args.scenario or args.dry_run:
            parser.error("--skill-comparison uses its fixed cases and cannot combine with --fixture, --scenario, or --dry-run")
        try:
            report, status = run_skill_comparison(
                baseline_source=args.baseline_source,
                candidate_source=args.candidate_source,
                runs=runs,
                timeout_seconds=args.timeout_seconds,
            )
        except ValueError as exc:
            parser.error(str(exc))
        _print_report(report, args.json)
        return status
    if args.paired:
        if not args.fixture or not args.baseline_source:
            parser.error("--paired requires --fixture and --baseline-source")
        if args.dry_run:
            parser.error("--dry-run is available only for the legacy prompt smoke")
        try:
            report, status = run_paired(
                fixture_id=args.fixture,
                scenario_id=args.scenario,
                runs=runs,
                baseline_source=args.baseline_source,
                candidate_source=args.candidate_source,
                timeout_seconds=args.timeout_seconds,
            )
        except ValueError as exc:
            parser.error(str(exc))
        _print_report(report, args.json)
        return status
    if any((args.fixture, args.scenario, args.baseline_source, args.candidate_source)):
        parser.error("fixture and source options require --paired or --skill-comparison")
    if args.dry_run:
        report = _base_report("python scripts/live_agent_eval.py --dry-run", 1 if args.smoke else runs)
        report["status"] = "dry-run"
        report["dry_run"] = True
        _print_report(report, args.json)
        return 0
    report, status = run_evaluation(
        runs=1 if args.smoke else runs,
        command="python scripts/live_agent_eval.py --smoke" if args.smoke else f"python scripts/live_agent_eval.py --runs {runs}",
    )
    _print_report(report, args.json)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
