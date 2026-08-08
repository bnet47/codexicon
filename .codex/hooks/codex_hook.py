#!/usr/bin/env python3
"""Portable lifecycle policy for repository-local Codex sessions."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import shlex
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator


ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = Path(os.environ.get("CODEX_STATE_DIR", ROOT / ".codex-state"))
STATE_FILE_OVERRIDE = os.environ.get("CODEX_STATE_FILE")
STATE_FILE = Path(STATE_FILE_OVERRIDE) if STATE_FILE_OVERRIDE else STATE_DIR / "session-default.json"
RECEIPT_DIR = STATE_DIR / "receipts"
SUMMARY_DIR = STATE_DIR / "summaries"
RECEIPT_TTL_SECONDS = 3600
STATE_LOCK_TIMEOUT_SECONDS = 2.0
STATE_LOCK_RETRY_SECONDS = 0.025

SENSITIVE_PATH = re.compile(
    r"(?ix)(?:"
    r"\.env(?:\.[a-z0-9_-]+)*|"
    r"(?<![a-z0-9_.-])secrets[\\/]|"
    r"credentials\.json|"
    r"application_default_credentials\.json|"
    r"(?<![a-z0-9_.-])(?:\.npmrc|\.pypirc|\.netrc)(?![a-z0-9_.-])|"
    r"(?<![a-z0-9_.-])\.aws[\\/]credentials(?![a-z0-9_.-])|"
    r"(?<![a-z0-9_.-])\.ssh[\\/]id_(?:rsa|dsa|ecdsa|ed25519)(?![a-z0-9_.-])|"
    r"(?<![a-z0-9_.-])\.kube[\\/]config(?![a-z0-9_.-])|"
    r"(?<![a-z0-9_.-])\.docker[\\/]config\.json(?![a-z0-9_.-])|"
    r"(?<![a-z0-9_.-])\.config[\\/]gh[\\/]hosts\.yml(?![a-z0-9_.-])|"
    r"(?<![a-z0-9_.-])\.terraform\.d[\\/]credentials\.tfrc\.json(?![a-z0-9_.-])|"
    r"[^\s'\"<>|&;/\\]*\.(?:key|pem|p12|pfx|secret)"
    r")"
)
SAFE_PLACEHOLDER = re.compile(
    r"(?i)\.env\.example(?![a-z0-9_.\\/-])"
)
PATCH_PATH = re.compile(
    r"(?m)^\*\*\* (?:(?:Add|Update|Delete) File|Move to):\s*(.+?)\s*$"
)
RECEIPT_MARKER = re.compile(
    r"\[codex-verification\] check=(lint|test) receipt=([a-f0-9]{32})"
)
SECRET_ENV_NAME = r"[A-Z0-9_]*(?:API[_-]?KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|PRIVATE[_-]?KEY|ACCESS[_-]?KEY|SESSION|COOKIE)[A-Z0-9_]*"
ENV_ENUMERATION = re.compile(
    r"(?ix)(?:"
    r"(?:^|[;&|\n])\s*(?:env|printenv)\s*(?=$|[;&|\n]|(?:\d+\s*)?[<>])|"
    r"(?:^|[;&|\n])\s*(?:export\s+-p|declare\s+-x|compgen\s+-e)\s*(?=$|[;&|\n]|(?:\d+\s*)?[<>])|"
    r"(?:^|[;&|\n])\s*(?:cmd(?:\.exe)?\s+/[dqs]+\s+/c\s+)?set\s*(?=$|[;&|\n]|(?:\d+\s*)?[<>])|"
    r"(?:get-childitem|gci|dir|ls)\s+(?:-path\s+)?env:\*?|"
    r"get-item\s+(?:-path\s+)?env:\*|"
    r"getenvironmentvariables\s*\(|"
    r"(?:print|write-output|console\.log)\s*\(?\s*(?:os\.environ|process\.env)|"
    r"(?:dict|list|tuple|str|repr|json\.dumps|pprint|pprint\.pprint)\s*\(\s*os\.environ\b|"
    r"(?:object\.(?:entries|keys|values)|json\.stringify)\s*\(\s*process\.env\b|"
    r"os\.environ\.(?:items|keys|values)\s*\(|"
    r"\bfor\s+\w+\s+in\s+(?:os\.environ|process\.env)\b"
    r")"
)
SECRET_ENV_REFERENCE = re.compile(
    rf"(?ix)(?:"
    rf"\$env:(?:{SECRET_ENV_NAME})\b|"
    rf"\$(?:{SECRET_ENV_NAME})\b|"
    rf"\$\{{(?:{SECRET_ENV_NAME})\}}|"
    rf"%(?:{SECRET_ENV_NAME})%|"
    rf"(?:printenv|set|get-item|get-childitem|gci)\s+(?:env:)?(?:{SECRET_ENV_NAME})\b"
    rf")"
)
DOCUMENTATION_SUFFIXES = {".md", ".rst", ".txt", ".adoc"}
SEARCH_OPTIONS_WITH_VALUES = {
    "-A",
    "--after-context",
    "-B",
    "--before-context",
    "-C",
    "--context",
    "-f",
    "--file",
    "-g",
    "--glob",
    "-m",
    "--max-count",
    "-t",
    "--type",
    "-T",
    "--type-not",
}
SEARCH_PATTERN_OPTIONS = {"-e", "--regexp"}
SEARCH_BOOLEAN_OPTIONS = {
    "-F",
    "--fixed-strings",
    "-H",
    "--with-filename",
    "-h",
    "--no-filename",
    "-i",
    "--ignore-case",
    "-l",
    "--files-with-matches",
    "-n",
    "--line-number",
    "-N",
    "--no-line-number",
    "-o",
    "--only-matching",
    "-q",
    "--quiet",
    "-s",
    "--case-sensitive",
    "-S",
    "--smart-case",
    "-U",
    "--multiline",
    "-v",
    "--invert-match",
    "-w",
    "--word-regexp",
    "-x",
    "--line-regexp",
    "--heading",
    "--hidden",
    "--multiline-dotall",
    "--no-heading",
    "--no-ignore",
    "--no-messages",
    "--pcre2",
    "--stats",
}
CHECKPOINT_MARKER = re.compile(r"^<!--\s*codexicon-checkpoint:\s*(\{.*\})\s*-->$")
READ_ONLY_COMMANDS = {
    "cat",
    "find",
    "get-childitem",
    "get-command",
    "get-content",
    "get-date",
    "get-item",
    "get-location",
    "get-process",
    "get-variable",
    "gci",
    "head",
    "grep",
    "ls",
    "measure-object",
    "out-string",
    "pwd",
    "resolve-path",
    "select-object",
    "select-string",
    "sort-object",
    "sed",
    "stat",
    "tail",
    "tree",
    "test-path",
    "where",
    "where.exe",
    "wc",
    "which",
    "write-output",
}
READ_ONLY_GIT_COMMANDS = {"ls-files", "log", "rev-parse", "show", "status"}
UNSAFE_READ_ONLY_TOKENS = {
    "--ext-diff",
    "--exec",
    "--output",
    "--pre",
    "--pre-glob",
    "--textconv",
}


class StateLoadError(RuntimeError):
    """Raised when verification state is absent or cannot be trusted."""


def utc_now() -> tuple[float, str]:
    stamp = time.time()
    rendered = datetime.fromtimestamp(stamp, timezone.utc).isoformat(timespec="seconds")
    return stamp, rendered


def read_stdin() -> dict[str, Any]:
    if sys.stdin.isatty():
        return {}
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def configure_state_file(payload: dict[str, Any]) -> None:
    global STATE_FILE
    if STATE_FILE_OVERRIDE:
        STATE_FILE = Path(STATE_FILE_OVERRIDE)
        return
    session_id = str(payload.get("session_id") or "default")
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:20]
    STATE_FILE = STATE_DIR / f"session-{digest}.json"


def session_digest(session_id: Any) -> str:
    return hashlib.sha256(str(session_id).encode("utf-8")).hexdigest()[:20]


def counter(value: Any) -> int:
    try:
        return max(0, int(value))
    except (OverflowError, TypeError, ValueError):
        return 0


def epoch(value: Any) -> float:
    try:
        result = float(value)
    except (OverflowError, TypeError, ValueError):
        return 0.0
    return result if math.isfinite(result) and result >= 0 else 0.0


def write_session_summary(state: dict[str, Any]) -> None:
    """Write supported local telemetry without making hook success depend on it."""

    session_id = state.get("session_id")
    if not session_id:
        return
    summary = {
        "schema_version": 1,
        "session_id_hash": session_digest(session_id),
        "session_started_at": state.get("session_started_at"),
        "last_event_at": state.get("last_event_at"),
        "session_ended_at": state.get("session_ended_at"),
        "turn_count": counter(state.get("turn_count")),
        "compact_count": counter(state.get("compact_count")),
        "usage": {
            "availability": "not_exposed_by_hook_payloads",
            "input_tokens": None,
            "cached_input_tokens": None,
            "reasoning_output_tokens": None,
        },
    }
    try:
        save_json_atomic(
            SUMMARY_DIR / f"session-{summary['session_id_hash']}.json",
            summary,
        )
    except (OSError, TypeError, ValueError):
        pass


@contextmanager
def state_lock(*, blocking: bool = True) -> Iterator[bool]:
    """Serialize state updates with a deadline; telemetry may opt out immediately."""

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = STATE_FILE.with_suffix(STATE_FILE.suffix + ".lock")
    with lock_path.open("a+b") as handle:
        deadline = time.monotonic() + STATE_LOCK_TIMEOUT_SECONDS
        acquired = False
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            while not acquired:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                except OSError:
                    if not blocking:
                        yield False
                        return
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"timed out locking state file: {STATE_FILE.name}")
                    time.sleep(STATE_LOCK_RETRY_SECONDS)
        else:
            import fcntl

            while not acquired:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except BlockingIOError:
                    if not blocking:
                        yield False
                        return
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"timed out locking state file: {STATE_FILE.name}")
                    time.sleep(STATE_LOCK_RETRY_SECONDS)
        try:
            yield True
        finally:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def valid_state(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("schema_version") == 4
        and isinstance(value.get("has_writes"), bool)
        and isinstance(value.get("lint_passed"), bool)
        and isinstance(value.get("test_passed"), bool)
        and isinstance(value.get("test_required"), bool)
    )


def load_state_unlocked(strict: bool = False) -> dict[str, Any]:
    try:
        value = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        if strict:
            raise StateLoadError("verification state is missing") from exc
        return {}
    except (json.JSONDecodeError, OSError) as exc:
        if strict:
            raise StateLoadError("verification state is unreadable or malformed") from exc
        return {}
    if strict and not valid_state(value):
        raise StateLoadError("verification state has an unsupported or incomplete schema")
    return value if isinstance(value, dict) else {}


def save_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f"{path.stem}-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def pending_write_directory() -> Path:
    return STATE_FILE.parent / "pending-writes"


def trusted_pending_write_directory(*, create: bool) -> Path:
    directory = pending_write_directory()
    try:
        if directory.is_symlink():
            raise StateLoadError("pending write storage is not a trusted directory")
        if directory.exists():
            if not directory.is_dir():
                raise StateLoadError("pending write storage is not a trusted directory")
        elif create:
            directory.mkdir(parents=True, exist_ok=True)
            if directory.is_symlink() or not directory.is_dir():
                raise StateLoadError("pending write storage is not a trusted directory")
    except StateLoadError:
        raise
    except OSError as exc:
        raise StateLoadError("pending write state is unreadable") from exc
    return directory


def pending_write_key() -> str:
    material = str(STATE_FILE.resolve())
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def marker_tool_key(tool_use_id: Any) -> str | None:
    if not isinstance(tool_use_id, str) or not tool_use_id:
        return None
    return hashlib.sha256(tool_use_id.encode("utf-8")).hexdigest()[:20]


def pending_write_marker_path(tool_use_id: Any) -> Path | None:
    tool_key = marker_tool_key(tool_use_id)
    if tool_key is None:
        return None
    return pending_write_directory() / f"{pending_write_key()}-{tool_key}.json"


def write_pending_write_marker(
    payload: dict[str, Any],
    *,
    status: str,
    test_relevant: bool,
) -> Path:
    stamp, rendered = utc_now()
    directory = trusted_pending_write_directory(create=True)
    path = pending_write_marker_path(payload.get("tool_use_id"))
    if path is None:
        if status == "pending":
            raise StateLoadError("tool_use_id is missing from PreToolUse payload")
        path = directory / (
            f"{pending_write_key()}-unpaired-{secrets.token_hex(16)}.json"
        )

    created_epoch = stamp
    created_at = rendered
    existing_test_relevant = False
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and existing.get("schema_version") == 1:
                created_epoch = epoch(existing.get("created_epoch")) or stamp
                candidate_at = existing.get("created_at")
                if isinstance(candidate_at, str) and candidate_at:
                    created_at = candidate_at
                existing_test_relevant = existing.get("test_relevant") is not False
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            existing_test_relevant = True

    save_json_atomic(
        path,
        {
            "schema_version": 1,
            "status": status,
            "created_at": created_at,
            "created_epoch": created_epoch,
            "completed_at": rendered if status == "completed" else None,
            "completed_epoch": stamp if status == "completed" else None,
            "test_relevant": existing_test_relevant or test_relevant,
        },
    )
    return path


def pending_write_paths() -> list[Path]:
    directory = trusted_pending_write_directory(create=False)
    try:
        if not directory.exists():
            return []
        prefix = f"{pending_write_key()}-"
        return sorted(
            path
            for path in directory.iterdir()
            if path.name.startswith(prefix) and path.suffix == ".json"
        )
    except StateLoadError:
        raise
    except OSError as exc:
        raise StateLoadError("pending write state is unreadable") from exc


def load_pending_write_markers(paths: list[Path]) -> list[dict[str, Any]]:
    fallback_epoch, fallback_at = utc_now()
    markers: list[dict[str, Any]] = []
    for path in paths:
        try:
            marker = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(marker, dict) or marker.get("schema_version") != 1:
                marker = {}
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            marker = {}

        status = marker.get("status")
        if status not in {"pending", "completed"}:
            status = "completed"
        marker_epoch = epoch(marker.get("created_epoch")) or fallback_epoch
        marker_at = marker.get("created_at")
        if not isinstance(marker_at, str) or not marker_at:
            marker_at = fallback_at
        markers.append(
            {
                "path": path,
                "status": status,
                "created_epoch": marker_epoch,
                "created_at": marker_at,
                "test_relevant": marker.get("test_relevant") is not False,
            }
        )
    return markers


def reconcile_pending_writes_unlocked(
    state: dict[str, Any],
    markers: list[dict[str, Any]],
    *,
    force_tests: bool = False,
) -> None:
    state["active_write_intents"] = sum(
        marker.get("status") == "pending" for marker in markers
    )
    if not markers:
        return

    fallback_epoch, fallback_at = utc_now()
    latest_write_epoch = epoch(state.get("last_write_epoch"))
    latest_write_at = state.get("last_write_at")
    latest_test_write_epoch = epoch(state.get("last_test_relevant_write_epoch"))
    latest_test_write_at = state.get("last_test_relevant_write_at")
    test_required = bool(state.get("test_required")) or force_tests

    for marker in markers:
        marker_epoch = epoch(marker.get("created_epoch")) or fallback_epoch
        marker_at = marker.get("created_at") or fallback_at
        if marker_epoch >= latest_write_epoch:
            latest_write_epoch = marker_epoch
            latest_write_at = marker_at

        marker_requires_tests = force_tests or marker.get("test_relevant") is not False
        if marker_requires_tests:
            test_required = True
            if marker_epoch >= latest_test_write_epoch:
                latest_test_write_epoch = marker_epoch
                latest_test_write_at = marker_at

    state.update(
        schema_version=4,
        has_writes=True,
        lint_passed=False,
        test_passed=bool(state.get("test_passed")),
        test_required=test_required,
        last_write_at=latest_write_at or fallback_at,
        last_write_epoch=latest_write_epoch or fallback_epoch,
    )
    if test_required:
        state.update(
            test_passed=False,
            last_test_relevant_write_at=latest_test_write_at or fallback_at,
            last_test_relevant_write_epoch=latest_test_write_epoch or fallback_epoch,
        )


def remove_completed_write_markers(markers: list[dict[str, Any]]) -> None:
    for marker in markers:
        if marker.get("status") != "completed":
            continue
        path = marker["path"]
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise StateLoadError("completed pending-write marker could not be removed") from exc


def mutate_state(
    mutator: Callable[[dict[str, Any]], None],
    *,
    summarize: bool = False,
    blocking: bool = True,
) -> dict[str, Any] | None:
    with state_lock(blocking=blocking) as acquired:
        if not acquired:
            return None
        markers = load_pending_write_markers(pending_write_paths())
        state = load_state_unlocked()
        state_was_trusted = valid_state(state)
        if not state_was_trusted:
            state = {
                "schema_version": 4,
                "has_writes": False,
                "lint_passed": False,
                "test_passed": False,
                "test_required": False,
            }
        reconcile_pending_writes_unlocked(
            state,
            markers,
            force_tests=bool(markers) and not state_was_trusted,
        )
        mutator(state)
        reconcile_pending_writes_unlocked(
            state,
            markers,
            force_tests=bool(markers) and not state_was_trusted,
        )
        save_json_atomic(STATE_FILE, state)
        remove_completed_write_markers(markers)
        if summarize:
            write_session_summary(state)
        return dict(state)


def read_state(strict: bool = False) -> dict[str, Any]:
    with state_lock() as acquired:
        if not acquired:
            if strict:
                raise StateLoadError("verification state is busy")
            return {}
        markers = load_pending_write_markers(pending_write_paths())
        state_was_trusted = True
        try:
            state = load_state_unlocked(strict=strict)
        except StateLoadError:
            if not markers:
                raise
            state_was_trusted = False
            state = {
                "schema_version": 4,
                "has_writes": False,
                "lint_passed": False,
                "test_passed": False,
                "test_required": False,
            }
        previous_active = state.get("active_write_intents")
        reconcile_pending_writes_unlocked(
            state,
            markers,
            force_tests=bool(markers) and not state_was_trusted,
        )
        if markers or previous_active != state.get("active_write_intents"):
            save_json_atomic(STATE_FILE, state)
            remove_completed_write_markers(markers)
        return dict(state)


def reset_state(payload: dict[str, Any]) -> int:
    prune_receipts()
    stamp, rendered = utc_now()

    def reset(state: dict[str, Any]) -> None:
        consumed_receipts = state.get("consumed_receipts")
        if not isinstance(consumed_receipts, list):
            consumed_receipts = []
        consumed_receipts = [
            value for value in consumed_receipts if isinstance(value, str)
        ]
        state.clear()
        state.update(
            {
                "schema_version": 4,
                "session_id": payload.get("session_id"),
                "session_started_at": rendered,
                "session_started_epoch": stamp,
                "last_event_at": rendered,
                "turn_count": 0,
                "compact_count": 0,
                "seen_turn_ids": [],
                "consumed_receipts": consumed_receipts,
                "has_writes": False,
                "lint_passed": False,
                "test_passed": False,
                "test_required": False,
            }
        )

    state = mutate_state(reset, summarize=True, blocking=False)
    if state is None:
        print(
            "Session state is busy; initialization was not recorded. Retry the session start or clear.",
            file=sys.stderr,
        )
        return 2
    return 0


def repository_identity() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        common = Path(result.stdout.strip())
        if not common.is_absolute():
            common = ROOT / common
        material = str(common.resolve())
    else:
        material = str(ROOT.resolve())
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def latest_compatible_checkpoint() -> str | None:
    sessions = ROOT / "agent_docs" / "sessions"
    if not sessions.is_dir() or sessions.is_symlink():
        return None
    repo_id = repository_identity()
    candidates: list[tuple[datetime, str]] = []
    for path in sessions.glob("*.md"):
        if path.is_symlink():
            continue
        try:
            path.resolve().relative_to(ROOT.resolve())
        except (OSError, ValueError):
            continue
        try:
            with path.open("r", encoding="utf-8") as handle:
                first = handle.readline().strip()
            match = CHECKPOINT_MARKER.fullmatch(first)
            metadata = json.loads(match.group(1)) if match else None
        except (OSError, json.JSONDecodeError):
            continue
        if (
            not isinstance(metadata, dict)
            or metadata.get("schema_version") != 1
            or metadata.get("repository_id") != repo_id
            or not isinstance(metadata.get("checkpoint_id"), str)
            or not re.fullmatch(r"[a-f0-9]{16}", metadata["checkpoint_id"])
            or not isinstance(metadata.get("branch"), str)
            or not isinstance(metadata.get("head"), str)
            or not isinstance(metadata.get("related"), list)
        ):
            continue
        try:
            created = datetime.fromisoformat(str(metadata["created_at"]))
        except (KeyError, TypeError, ValueError):
            continue
        if created.tzinfo is None:
            continue
        related_valid = True
        normalized_related: set[str] = set()
        for raw in metadata["related"]:
            normalized = str(raw).replace("\\", "/")
            relative = PurePosixPath(normalized)
            if (
                not isinstance(raw, str)
                or not normalized
                or relative.is_absolute()
                or re.match(r"^[A-Za-z]:", normalized)
                or any(part in {"", ".", ".."} for part in relative.parts)
                or relative.as_posix() in normalized_related
            ):
                related_valid = False
                break
            normalized_related.add(relative.as_posix())
        if not related_valid:
            continue
        candidates.append((created, path.relative_to(ROOT).as_posix()))
    return max(candidates)[1] if candidates else None


def resume_state(payload: dict[str, Any]) -> int:
    stamp, rendered = utc_now()
    recovered = False
    with state_lock():
        try:
            state = load_state_unlocked(strict=True)
        except StateLoadError:
            recovered = True
            state = {
                "schema_version": 4,
                "session_id": payload.get("session_id"),
                "session_started_at": rendered,
                "session_started_epoch": stamp,
                "last_event_at": rendered,
                "turn_count": 0,
                "compact_count": 0,
                "seen_turn_ids": [],
                "consumed_receipts": [],
                "has_writes": True,
                "lint_passed": False,
                "test_passed": False,
                "test_required": True,
            }
            state.update(
                last_write_at=rendered,
                last_write_epoch=stamp,
                last_test_relevant_write_at=rendered,
                last_test_relevant_write_epoch=stamp,
            )
        state.update(
            session_id=payload.get("session_id") or state.get("session_id"),
            last_resume_at=rendered,
            last_resume_epoch=stamp,
            last_resume_source=payload.get("source"),
        )
        save_json_atomic(STATE_FILE, state)

    checkpoint = latest_compatible_checkpoint()
    messages: list[str] = []
    if recovered:
        messages.append(
            "Local verification state was unavailable; lint and tests are required again."
        )
    if checkpoint:
        messages.append(
            f"Compatible checkpoint: {checkpoint}. Run `python scripts/codexicon.py resume` "
            "and verify it against the current diff before continuing."
        )
    if messages:
        print(json.dumps({"systemMessage": " ".join(messages)}))
    return 0


def protected_text(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return str(tool_input)
    candidates = [
        tool_input.get("command", ""),
        tool_input.get("patch", ""),
        tool_input.get("file_path", ""),
        tool_input.get("path", ""),
    ]
    return "\n".join(str(value) for value in candidates if value)


def safely_scoped_search(command: str) -> bool:
    """Allow protected terms as search patterns when explicit targets are safe."""

    if re.search(r"(?:\r|\n|;|&&|\|\||(?<!\|)\|(?!\|)|>>?|<)", command):
        return False
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return False
    if not tokens or Path(tokens[0]).name.lower() not in {"rg", "rg.exe"}:
        return False

    pattern_seen = False
    targets: list[str] = []
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == "--":
            index += 1
            if not pattern_seen and index < len(tokens):
                pattern_seen = True
                index += 1
            targets.extend(tokens[index:])
            break
        if token in SEARCH_PATTERN_OPTIONS:
            if index + 1 >= len(tokens):
                return False
            pattern_seen = True
            index += 2
            continue
        if token.startswith("--regexp="):
            pattern_seen = True
            index += 1
            continue
        if token in SEARCH_BOOLEAN_OPTIONS:
            index += 1
            continue
        if token in SEARCH_OPTIONS_WITH_VALUES:
            if index + 1 >= len(tokens):
                return False
            if SENSITIVE_PATH.search(SAFE_PLACEHOLDER.sub("ENV_EXAMPLE", tokens[index + 1])):
                return False
            index += 2
            continue
        if token.startswith("-"):
            return False
        if not pattern_seen:
            pattern_seen = True
        else:
            targets.append(token)
        index += 1

    if not pattern_seen or not targets:
        return False
    unsafe_targets = {".", "./", ".\\", "..", "../", "..\\", "*", "**"}
    for target in targets:
        normalized = target.replace("\\", "/")
        if normalized in unsafe_targets or any(character in target for character in "*?["):
            return False
        scrubbed = SAFE_PLACEHOLDER.sub("ENV_EXAMPLE", target)
        if SENSITIVE_PATH.search(scrubbed):
            return False
    return True


def protect_secrets(payload: dict[str, Any]) -> int:
    text = protected_text(payload)
    if not text:
        return 0
    if wildcard_file_read(payload, text):
        print(
            "Blocked protected credential path: wildcard file reads can expand to credentials. "
            "Name a verified non-secret file explicitly.",
            file=sys.stderr,
        )
        return 2
    patch_paths = changed_paths(payload)
    if patch_paths:
        text = "\n".join(str(path) for path in patch_paths)
    scrubbed = SAFE_PLACEHOLDER.sub("ENV_EXAMPLE", text)
    resolved_sensitive = False
    for path in changed_paths(payload):
        try:
            resolved = path.expanduser().resolve(strict=False)
        except OSError:
            continue
        resolved_text = SAFE_PLACEHOLDER.sub("ENV_EXAMPLE", str(resolved))
        if SENSITIVE_PATH.search(resolved_text):
            resolved_sensitive = True
            break
    if not (
        SENSITIVE_PATH.search(scrubbed)
        or ENV_ENUMERATION.search(scrubbed)
        or SECRET_ENV_REFERENCE.search(scrubbed)
        or resolved_sensitive
    ):
        return 0
    if safely_scoped_search(text):
        return 0
    print(
        "Blocked protected credential path or environment secret. Use a named, non-secret value or the documented .env.example placeholder.",
        file=sys.stderr,
    )
    return 2


def wildcard_file_read(payload: dict[str, Any], text: str) -> bool:
    tool_name = str(payload.get("tool_name", "")).lower()
    if tool_name in {"read", "read_file", "read_text_file"}:
        return any(character in text for character in "*?[")
    read_commands = {
        "cat",
        "gc",
        "get-content",
        "head",
        "more",
        "select-string",
        "tail",
        "type",
    }
    segments = re.split(r"(?:\r?\n|;|&&|\|\||(?<!\|)\|(?!\|))", text)
    for segment in segments:
        try:
            tokens = shlex.split(segment, posix=True)
        except ValueError:
            continue
        if not tokens:
            continue
        if tokens[0] == "&":
            tokens = tokens[1:]
        if tokens and tokens[0].lower() == "command":
            tokens = tokens[1:]
        if not tokens:
            continue
        executable = Path(tokens[0]).name.lower()
        if executable in read_commands and any(
            any(character in token for character in "*?[") for token in tokens[1:]
        ):
            return True
    return False


def changed_paths(payload: dict[str, Any]) -> list[Path]:
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return []
    paths: list[str] = []
    for key in ("file_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            paths.append(value.strip().strip("'\""))
    command = tool_input.get("command") or tool_input.get("patch")
    if isinstance(command, str):
        paths.extend(match.strip().strip("'\"") for match in PATCH_PATH.findall(command))
    return [Path(value) for value in paths if value]


def documentation_only(paths: list[Path]) -> bool:
    if not paths:
        return False
    return all(path.suffix.lower() in DOCUMENTATION_SUFFIXES or path.name == "LICENSE" for path in paths)


def record_write(payload: dict[str, Any], force_tests: bool | None = None) -> int:
    stamp, rendered = utc_now()
    test_relevant = not documentation_only(changed_paths(payload)) if force_tests is None else force_tests

    try:
        write_pending_write_marker(
            payload,
            status="completed",
            test_relevant=test_relevant,
        )
    except (OSError, StateLoadError) as exc:
        print(f"Write verification could not be invalidated durably ({exc}).", file=sys.stderr)
        return 2

    def update(state: dict[str, Any]) -> None:
        state.update(
            session_id=payload.get("session_id") or state.get("session_id"),
            has_writes=True,
            last_write_at=rendered,
            last_write_epoch=stamp,
            lint_passed=False,
        )
        state.setdefault("test_required", False)
        if test_relevant:
            state.update(
                test_required=True,
                test_passed=False,
                last_test_relevant_write_at=rendered,
                last_test_relevant_write_epoch=stamp,
            )

    try:
        mutate_state(update)
    except (StateLoadError, TimeoutError) as exc:
        print(
            f"Verification state is busy; write invalidation remains pending ({exc}).",
            file=sys.stderr,
        )
        return 2
    return 0


def record_compact(payload: dict[str, Any]) -> int:
    stamp, rendered = utc_now()

    def update(state: dict[str, Any]) -> None:
        state.update(
            session_id=payload.get("session_id") or state.get("session_id"),
            last_event_at=rendered,
            last_compact_at=rendered,
            last_compact_epoch=stamp,
            compact_count=counter(state.get("compact_count")) + 1,
        )

    try:
        mutate_state(update, blocking=False)
    except (OSError, OverflowError, TypeError, ValueError):
        pass
    return 0


def record_turn(payload: dict[str, Any]) -> int:
    _, rendered = utc_now()
    turn_id = payload.get("turn_id")

    def update(state: dict[str, Any]) -> None:
        state.update(
            session_id=payload.get("session_id") or state.get("session_id"),
            last_event_at=rendered,
        )
        seen_turn_ids = state.get("seen_turn_ids")
        if not isinstance(seen_turn_ids, list):
            seen_turn_ids = []
        seen_turn_ids = [value for value in seen_turn_ids if isinstance(value, str)]
        if isinstance(turn_id, str) and turn_id and turn_id not in seen_turn_ids:
            seen_turn_ids.append(turn_id)
            state.update(seen_turn_ids=seen_turn_ids, turn_count=len(seen_turn_ids))

    try:
        mutate_state(update, blocking=False)
    except (OSError, OverflowError, TypeError, ValueError):
        pass
    return 0


def end_session(payload: dict[str, Any]) -> int:
    stamp, rendered = utc_now()

    def update(state: dict[str, Any]) -> None:
        state.update(
            session_id=payload.get("session_id") or state.get("session_id"),
            last_event_at=rendered,
            session_ended_at=rendered,
            session_ended_epoch=stamp,
        )

    try:
        mutate_state(update, summarize=True, blocking=False)
    except (OSError, OverflowError, TypeError, ValueError):
        pass
    return 0


def command_text(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command", "")
    return command if isinstance(command, str) else ""


def canonical_checks(command: str) -> list[str] | None:
    patterns = {
        "lint": [
            r"\s*(?:bash\s+)?(?:\./)?scripts/lint\.sh\s*",
            r"\s*(?:&\s*)?(?:\.\\|\./)?scripts[\\/]lint\.ps1\s*",
        ],
        "test": [
            r"\s*(?:bash\s+)?(?:\./)?scripts/test\.sh\s*",
            r"\s*(?:&\s*)?(?:\.\\|\./)?scripts[\\/]test\.ps1\s*",
        ],
        "security": [
            r"\s*(?:bash\s+)?(?:\./)?scripts/security\.sh\s*",
            r"\s*(?:&\s*)?(?:\.\\|\./)?scripts[\\/]security\.ps1\s*",
        ],
    }
    checks: list[str] = []
    for check, candidates in patterns.items():
        if any(re.fullmatch(pattern, command, flags=re.IGNORECASE) for pattern in candidates):
            checks.append(check)
    if checks:
        return checks
    try:
        tokens = shlex.split(command.strip(), posix=True)
    except ValueError:
        return None
    if tokens and tokens[0] == "&":
        tokens = tokens[1:]
    if not tokens:
        return None
    executable = Path(tokens[0]).name.lower()
    if executable in {"python", "python3", "python.exe"}:
        tokens = tokens[1:]
    if len(tokens) < 2:
        return None
    script = tokens[0].replace("\\", "/").removeprefix("./").lower()
    if script != "scripts/codexicon.py" or tokens[1].lower() != "verify":
        return None
    requested = [token.lower() for token in tokens[2:]]
    if any(token not in {"lint", "test", "security"} for token in requested):
        return None
    return [check for check in ("lint", "test") if not requested or check in requested]


def definitely_read_only(command: str) -> bool:
    if re.search(r">>|(?<![<>=])>|(?<![<>=])<", command):
        return False
    if re.search(r"(?:`|\$\(|[&{}()]|@\(|<\(|>\()", command):
        return False
    segments = re.split(r"(?:\r?\n|;|&&|\|\||(?<!\|)\|(?!\|))", command)
    return bool(segments) and all(definitely_read_only_segment(segment) for segment in segments)


def definitely_read_only_segment(command: str) -> bool:
    if not command.strip():
        return True
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError:
        return False
    if not tokens:
        return True
    lowered = [token.lower() for token in tokens]
    executable = Path(lowered[0]).name
    if any(
        token == unsafe or token.startswith(f"{unsafe}=")
        for token in lowered[1:]
        for unsafe in UNSAFE_READ_ONLY_TOKENS
    ):
        return False
    if executable in {"rg", "rg.exe"}:
        return True
    if executable == "git":
        if len(lowered) >= 2 and lowered[1] == "branch":
            return lowered[2:] in ([], ["--show-current"], ["--list"])
        return len(lowered) >= 2 and lowered[1] in READ_ONLY_GIT_COMMANDS | {
            "diff",
            "grep",
            "ls-tree",
        }
    if executable == "sed":
        return not any(
            token == "--in-place"
            or token.startswith("--in-place=")
            or token == "-i"
            or token.startswith("-i")
            for token in lowered[1:]
        )
    if executable == "find":
        return not any(
            token in {
                "-delete",
                "-exec",
                "-execdir",
                "-fdelete",
                "-fls",
                "-fprint",
                "-fprint0",
                "-fprintf",
                "-ok",
                "-okdir",
            }
            for token in lowered[1:]
        )
    if executable == "tree":
        return not any(
            token == "-o"
            or token.startswith("-o")
            or token == "--outfile"
            or token.startswith("--outfile=")
            for token in lowered[1:]
        )
    if executable in READ_ONLY_COMMANDS:
        return True
    if executable in {"python", "python3", "node"}:
        return lowered[1:] in (["--version"], ["-v"])
    if executable in {"npm", "pnpm", "yarn"}:
        return len(lowered) >= 2 and lowered[1] in {"info", "list", "ls", "view", "why"}
    return False


def prepare_write(payload: dict[str, Any]) -> int:
    tool_name = str(payload.get("tool_name", "")).lower()
    if tool_name == "bash":
        command = command_text(payload)
        if canonical_checks(command) is not None or definitely_read_only(command):
            return 0
        test_relevant = True
    elif tool_name in {"apply_patch", "edit", "write"}:
        test_relevant = not documentation_only(changed_paths(payload))
    else:
        return 0

    try:
        with state_lock() as acquired:
            if not acquired:
                raise StateLoadError("verification state is busy")
            write_pending_write_marker(
                payload,
                status="pending",
                test_relevant=test_relevant,
            )
    except (OSError, StateLoadError, TimeoutError) as exc:
        print(f"Write intent could not be recorded durably ({exc}).", file=sys.stderr)
        return 2
    return 0


def prepare_tool(payload: dict[str, Any]) -> int:
    protected = protect_secrets(payload)
    if protected:
        return protected
    return prepare_write(payload)


def prune_receipts(now: float | None = None) -> None:
    """Remove expired or malformed one-use receipts without exposing their content."""

    current = time.time() if now is None else now
    try:
        paths = [*RECEIPT_DIR.glob("*.json"), *RECEIPT_DIR.glob("*.claim")]
    except OSError:
        return
    for path in paths:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            created = epoch(value.get("created_epoch"))
            if created and current - created <= RECEIPT_TTL_SECONDS and created <= current + 60:
                continue
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def emit_receipt(check: str) -> int:
    if check not in {"lint", "test"}:
        print("Usage: codex_hook.py emit-success [lint|test]", file=sys.stderr)
        return 2
    stamp, rendered = utc_now()
    prune_receipts(stamp)
    receipt_id = secrets.token_hex(16)
    save_json_atomic(
        RECEIPT_DIR / f"{receipt_id}.json",
        {"schema_version": 1, "check": check, "created_at": rendered, "created_epoch": stamp},
    )
    print(f"[codex-verification] check={check} receipt={receipt_id}")
    return 0


def claim_receipt(
    check: str,
    response: Any,
    session_id: Any,
) -> tuple[str, Path, float] | None:
    """Atomically claim a receipt, leaving it recoverable until state is persisted."""

    text = response if isinstance(response, str) else json.dumps(response, sort_keys=True)
    now = time.time()
    prune_receipts(now)
    for marker_check, receipt_id in RECEIPT_MARKER.findall(text):
        if marker_check != check:
            continue
        source = RECEIPT_DIR / f"{receipt_id}.json"
        claim = RECEIPT_DIR / f"{receipt_id}-{session_digest(session_id)}.claim"
        try:
            if not claim.exists():
                try:
                    os.replace(source, claim)
                except FileNotFoundError:
                    if not claim.exists():
                        continue
            value = json.loads(claim.read_text(encoding="utf-8"))
            created = epoch(value.get("created_epoch"))
            if (
                value.get("check") != check
                or not created
                or now - created > RECEIPT_TTL_SECONDS
                or created > now + 60
            ):
                claim.unlink(missing_ok=True)
                continue
            return receipt_id, claim, created
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
            continue
    return None


def set_check_result(
    check: str,
    passed: bool,
    receipt_id: str | None = None,
    receipt_epoch: float = 0.0,
) -> bool:
    stamp, rendered = utc_now()
    accepted = passed

    def update(state: dict[str, Any]) -> None:
        nonlocal accepted
        if counter(state.get("active_write_intents")):
            accepted = False
            return
        consumed = state.get("consumed_receipts")
        if not isinstance(consumed, list):
            consumed = []
        consumed = [value for value in consumed if isinstance(value, str)]
        if receipt_id:
            if receipt_id in consumed:
                accepted = False
                return
            consumed.append(receipt_id)
            state["consumed_receipts"] = consumed
            session_started_epoch = epoch(state.get("session_started_epoch"))
            if not receipt_epoch or receipt_epoch < session_started_epoch:
                accepted = False
        state[f"{check}_passed"] = accepted
        if accepted:
            state[f"{check}_at"] = rendered
            state[f"{check}_epoch"] = receipt_epoch or stamp

    mutate_state(update)
    return accepted


def record_shell(payload: dict[str, Any]) -> int:
    command = command_text(payload)
    checks = canonical_checks(command)
    if checks is not None:
        for check in checks:
            if check not in {"lint", "test"}:
                continue
            claimed = claim_receipt(
                check,
                payload.get("tool_response", ""),
                payload.get("session_id") or STATE_FILE.name,
            )
            if claimed is None:
                set_check_result(check, False)
                continue
            receipt_id, claim_path, receipt_epoch = claimed
            set_check_result(check, True, receipt_id, receipt_epoch)
            try:
                claim_path.unlink()
            except FileNotFoundError:
                pass
        return 0
    if definitely_read_only(command):
        return 0
    return record_write(payload, force_tests=True)


def verify_stop(payload: dict[str, Any]) -> int:
    try:
        state = read_state(strict=True)
    except StateLoadError as exc:
        message = (
            f"Verification state cannot be trusted ({exc}). Run ./scripts/lint.sh and "
            "./scripts/test.sh from the repository root before stopping."
        )
        if payload.get("stop_hook_active"):
            print(json.dumps({"systemMessage": message}))
            return 0
        print(message, file=sys.stderr)
        return 2
    if not state.get("has_writes"):
        return 0

    write_epoch = epoch(state.get("last_write_epoch"))
    missing: list[str] = []
    lint_epoch = epoch(state.get("lint_epoch"))
    if not write_epoch or not state.get("lint_passed") or not lint_epoch or lint_epoch < write_epoch:
        missing.append("lint")
    if state.get("test_required"):
        test_write_epoch = epoch(state.get("last_test_relevant_write_epoch", write_epoch))
        test_epoch = epoch(state.get("test_epoch"))
        if (
            not test_write_epoch
            or not state.get("test_passed")
            or not test_epoch
            or test_epoch < test_write_epoch
        ):
            missing.append("tests")
    if not missing:
        return 0

    checks = "./scripts/lint.sh"
    if "tests" in missing:
        checks += " and ./scripts/test.sh"
    message = (
        "Repository files changed after the last verified checks. Run "
        f"{checks} from the repository root. Successful canonical scripts record their own "
        f"verification receipts. Missing or stale: {', '.join(missing)}."
    )

    if payload.get("stop_hook_active"):
        print(json.dumps({"systemMessage": message}))
        return 0
    print(message, file=sys.stderr)
    return 2


def record_stop(payload: dict[str, Any]) -> int:
    record_turn(payload)
    return verify_stop(payload)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "Usage: codex_hook.py [session-start|session-resume|prepare-tool|protect-secrets|record-write|record-shell|record-compact|record-turn|record-stop|end-session|verify-stop|emit-success]",
            file=sys.stderr,
        )
        return 2

    action = argv[1]
    if action == "emit-success":
        return emit_receipt(argv[2] if len(argv) > 2 else "")

    payload = read_stdin()
    configure_state_file(payload)
    handlers = {
        "session-start": reset_state,
        "session-resume": resume_state,
        "prepare-tool": prepare_tool,
        "protect-secrets": protect_secrets,
        "record-write": record_write,
        "record-shell": record_shell,
        "record-compact": record_compact,
        "record-turn": record_turn,
        "record-stop": record_stop,
        "end-session": end_session,
        "verify-stop": verify_stop,
    }
    handler = handlers.get(action)
    if handler is None:
        print(f"Unknown hook action: {action}", file=sys.stderr)
        return 2
    return handler(payload)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
