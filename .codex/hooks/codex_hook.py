#!/usr/bin/env python3
"""Portable lifecycle policy for repository-local Codex sessions."""

from __future__ import annotations

import hashlib
import json
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
RECEIPT_TTL_SECONDS = 3600

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
    "ls",
    "measure-object",
    "out-string",
    "pwd",
    "resolve-path",
    "select-object",
    "select-string",
    "sort-object",
    "stat",
    "tail",
    "test-path",
    "where",
    "where.exe",
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


@contextmanager
def state_lock() -> Iterator[None]:
    """Serialize state updates across agents sharing a Codex session."""

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = STATE_FILE.with_suffix(STATE_FILE.suffix + ".lock")
    with lock_path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def valid_state(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and value.get("schema_version") == 2
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


def mutate_state(mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    with state_lock():
        state = load_state_unlocked()
        if state and not valid_state(state):
            state = {}
        state.setdefault("schema_version", 2)
        mutator(state)
        save_json_atomic(STATE_FILE, state)
        return dict(state)


def read_state(strict: bool = False) -> dict[str, Any]:
    with state_lock():
        return dict(load_state_unlocked(strict=strict))


def reset_state(payload: dict[str, Any]) -> int:
    prune_receipts()
    stamp, rendered = utc_now()

    def reset(state: dict[str, Any]) -> None:
        state.clear()
        state.update(
            {
                "schema_version": 2,
                "session_id": payload.get("session_id"),
                "session_started_at": rendered,
                "session_started_epoch": stamp,
                "has_writes": False,
                "lint_passed": False,
                "test_passed": False,
                "test_required": False,
            }
        )

    mutate_state(reset)
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
                "schema_version": 2,
                "session_id": payload.get("session_id"),
                "session_started_at": rendered,
                "session_started_epoch": stamp,
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

    mutate_state(update)
    return 0


def record_compact(payload: dict[str, Any]) -> int:
    stamp, rendered = utc_now()

    def update(state: dict[str, Any]) -> None:
        state.update(
            session_id=payload.get("session_id") or state.get("session_id"),
            last_compact_at=rendered,
            last_compact_epoch=stamp,
            compact_count=int(state.get("compact_count", 0)) + 1,
        )

    mutate_state(update)
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
    if executable in READ_ONLY_COMMANDS:
        return True
    if executable in {"rg", "rg.exe"}:
        return True
    if executable == "git":
        if len(lowered) >= 2 and lowered[1] == "branch":
            return lowered[2:] in ([], ["--show-current"], ["--list"])
        return len(lowered) >= 2 and lowered[1] in READ_ONLY_GIT_COMMANDS
    if executable in {"python", "python3", "node"}:
        return lowered[1:] in (["--version"], ["-v"])
    if executable in {"npm", "pnpm", "yarn"}:
        return len(lowered) >= 2 and lowered[1] in {"info", "list", "ls", "view", "why"}
    return False


def prune_receipts(now: float | None = None) -> None:
    """Remove expired or malformed one-use receipts without exposing their content."""

    current = time.time() if now is None else now
    try:
        paths = list(RECEIPT_DIR.glob("*.json"))
    except OSError:
        return
    for path in paths:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            created = float(value.get("created_epoch", 0))
            if current - created <= RECEIPT_TTL_SECONDS and created <= current + 60:
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


def consume_receipt(check: str, response: Any) -> bool:
    text = response if isinstance(response, str) else json.dumps(response, sort_keys=True)
    now = time.time()
    prune_receipts(now)
    for marker_check, receipt_id in RECEIPT_MARKER.findall(text):
        if marker_check != check:
            continue
        path = RECEIPT_DIR / f"{receipt_id}.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if value.get("check") != check or now - float(value.get("created_epoch", 0)) > RECEIPT_TTL_SECONDS:
                continue
            path.unlink()
            return True
        except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError, ValueError):
            continue
    return False


def set_check_result(check: str, passed: bool) -> None:
    stamp, rendered = utc_now()

    def update(state: dict[str, Any]) -> None:
        state[f"{check}_passed"] = passed
        if passed:
            state[f"{check}_at"] = rendered
            state[f"{check}_epoch"] = stamp

    mutate_state(update)


def record_shell(payload: dict[str, Any]) -> int:
    command = command_text(payload)
    checks = canonical_checks(command)
    if checks is not None:
        for check in checks:
            set_check_result(check, consume_receipt(check, payload.get("tool_response", "")))
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

    write_epoch = float(state.get("last_write_epoch", 0))
    missing: list[str] = []
    if not state.get("lint_passed") or float(state.get("lint_epoch", 0)) < write_epoch:
        missing.append("lint")
    if state.get("test_required"):
        test_write_epoch = float(state.get("last_test_relevant_write_epoch", write_epoch))
        if not state.get("test_passed") or float(state.get("test_epoch", 0)) < test_write_epoch:
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


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "Usage: codex_hook.py [session-start|session-resume|protect-secrets|record-write|record-shell|record-compact|verify-stop|emit-success]",
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
        "protect-secrets": protect_secrets,
        "record-write": record_write,
        "record-shell": record_shell,
        "record-compact": record_compact,
        "verify-stop": verify_stop,
    }
    handler = handlers.get(action)
    if handler is None:
        print(f"Unknown hook action: {action}", file=sys.stderr)
        return 2
    return handler(payload)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
