#!/usr/bin/env python3
"""Inspect, adopt, diagnose, verify, checkpoint, and update Codexicon safely."""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Sequence

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 fallback uses conservative structural checks.
    tomllib = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = ".codexicon.json"
LOCK_NAME = ".codexicon.lock.json"
STATE_DIR_NAME = ".codexicon"
TRANSACTION_NAME = "transaction.json"
CHECKPOINT_MARKER = "codexicon-checkpoint:"
SCHEMA_VERSION = 1
POLICIES = {"managed", "merge", "project"}
CANONICAL_CHECKS = ("lint", "test", "security")
BUILD_MODE = "build"
SHIP_MODE = "ship"
VERIFICATION_MODES = (BUILD_MODE, SHIP_MODE)
SUPPORTED_HOOK_EVENTS = {
    "PermissionRequest",
    "PostCompact",
    "PostToolUse",
    "PreCompact",
    "PreToolUse",
    "SessionEnd",
    "SessionStart",
    "Stop",
    "SubagentStart",
    "SubagentStop",
    "UserPromptSubmit",
}


class CodexiconError(RuntimeError):
    """Expected safe refusal with a concise user-facing message."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, content: bytes, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f"{path.name}-", suffix=".tmp", dir=path.parent)
    try:
        if mode is None:
            try:
                mode = path.stat().st_mode & 0o777
            except FileNotFoundError:
                mode = 0o600
        os.chmod(temp_name, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, value: Any) -> None:
    content = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    atomic_write_bytes(path, content)


def normalize_relative(raw: str) -> str:
    normalized = raw.replace("\\", "/").strip()
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or re.match(r"^[A-Za-z]:", normalized)
    ):
        raise CodexiconError(f"unsafe manifest path: {raw!r}")
    return path.as_posix()


def checked_path(root: Path, relative: str, *, reject_symlinks: bool = True) -> Path:
    relative = normalize_relative(relative)
    root = root.resolve()
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    try:
        candidate.resolve(strict=False).relative_to(root)
    except (OSError, ValueError) as exc:
        raise CodexiconError(f"path escapes repository root: {relative}") from exc
    if reject_symlinks:
        current = root
        for part in PurePosixPath(relative).parts:
            current /= part
            if current.is_symlink():
                raise CodexiconError(f"refusing symbolic-link path: {relative}")
    return candidate


def read_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CodexiconError(f"{label} is missing: {path}") from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise CodexiconError(f"{label} is unreadable or malformed: {path}") from exc


def template_version(root: Path) -> str:
    path = root / "TEMPLATE_VERSION"
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0].strip()
    except (FileNotFoundError, IndexError, OSError) as exc:
        raise CodexiconError(f"TEMPLATE_VERSION is missing or empty in {root}") from exc
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", first):
        raise CodexiconError(f"invalid TEMPLATE_VERSION value: {first!r}")
    return first


def load_manifest(source_root: Path) -> dict[str, Any]:
    source_root = source_root.resolve()
    manifest_path = source_root / MANIFEST_NAME
    value = read_json(manifest_path, "Codexicon source manifest")
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise CodexiconError("unsupported Codexicon source manifest schema")
    raw_files = value.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise CodexiconError("Codexicon source manifest requires a non-empty files list")
    files: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw_files:
        if not isinstance(item, dict):
            raise CodexiconError("each source manifest file entry must be an object")
        path = normalize_relative(str(item.get("path", "")))
        policy = item.get("policy")
        if policy not in POLICIES:
            raise CodexiconError(f"unsupported ownership policy for {path}: {policy!r}")
        executable = item.get("executable", False)
        if not isinstance(executable, bool):
            raise CodexiconError(f"invalid executable flag for {path}")
        if path in seen:
            raise CodexiconError(f"duplicate source manifest path: {path}")
        seen.add(path)
        source = checked_path(source_root, path)
        if policy != "project" and not source.is_file():
            raise CodexiconError(f"source manifest file is missing: {path}")
        files.append({"path": path, "policy": policy, "executable": executable})
    declared_version = value.get("version")
    if declared_version is not None and (
        not isinstance(declared_version, str)
        or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", declared_version)
    ):
        raise CodexiconError("Codexicon source manifest has an invalid version")
    version_path = source_root / "TEMPLATE_VERSION"
    version = template_version(source_root) if version_path.is_file() else declared_version
    if version is None:
        raise CodexiconError("Codexicon source manifest needs version metadata")
    if declared_version is not None and declared_version != version:
        raise CodexiconError("Codexicon source manifest version differs from TEMPLATE_VERSION")
    return {
        "schema_version": SCHEMA_VERSION,
        "version": version,
        "files": files,
        "manifest_sha256": sha256_file(manifest_path),
    }


def load_lock(target_root: Path, *, required: bool) -> dict[str, Any] | None:
    path = target_root / LOCK_NAME
    if not path.exists() and not required:
        return None
    value = read_json(path, "Codexicon installation lock")
    if not isinstance(value, dict) or value.get("schema_version") != SCHEMA_VERSION:
        raise CodexiconError("unsupported Codexicon installation lock schema")
    files = value.get("files")
    unresolved = value.get("unresolved")
    version = value.get("codexicon_version")
    manifest_digest = value.get("source_manifest_sha256")
    updated_at = value.get("updated_at")
    if (
        not isinstance(files, dict)
        or not isinstance(unresolved, list)
        or not isinstance(version, str)
        or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", version)
        or not isinstance(manifest_digest, str)
        or not re.fullmatch(r"[a-f0-9]{64}", manifest_digest)
        or not isinstance(updated_at, str)
    ):
        raise CodexiconError("Codexicon installation lock has invalid files or unresolved data")
    try:
        parsed_updated = datetime.fromisoformat(updated_at)
    except ValueError as exc:
        raise CodexiconError("Codexicon installation lock has an invalid updated_at") from exc
    if parsed_updated.tzinfo is None:
        raise CodexiconError("Codexicon installation lock updated_at must include a timezone")
    normalized_files: dict[str, dict[str, str]] = {}
    for raw_path, item in files.items():
        path_key = normalize_relative(str(raw_path))
        if (
            not isinstance(item, dict)
            or item.get("policy") not in {"managed", "merge"}
            or not re.fullmatch(r"[a-f0-9]{64}", str(item.get("sha256", "")))
            or not isinstance(item.get("executable", False), bool)
        ):
            raise CodexiconError(f"invalid lock entry: {path_key}")
        normalized_files[path_key] = {
            "policy": str(item["policy"]),
            "sha256": str(item["sha256"]),
            "executable": bool(item.get("executable", False)),
        }
    normalized_unresolved = sorted({normalize_relative(str(path)) for path in unresolved})
    return {
        **value,
        "files": normalized_files,
        "unresolved": normalized_unresolved,
    }


def file_state(root: Path, relative: str) -> tuple[str, str | None]:
    path = checked_path(root, relative)
    if not path.exists():
        return "missing", None
    if not path.is_file():
        raise CodexiconError(f"expected a regular file: {relative}")
    return "file", sha256_file(path)


def has_execute_mode(path: Path) -> bool:
    return bool(path.stat().st_mode & 0o111)


def install_plan(
    source_root: Path,
    target_root: Path,
    manifest: dict[str, Any],
    old_lock: dict[str, Any] | None,
    *,
    update: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_root = source_root.resolve()
    target_root = target_root.resolve()
    if source_root == target_root:
        raise CodexiconError("source and target repositories must be different")
    try:
        target_root.relative_to(source_root)
    except ValueError:
        pass
    else:
        raise CodexiconError("target repository must not be nested inside the source")
    try:
        source_root.relative_to(target_root)
    except ValueError:
        pass
    else:
        raise CodexiconError("source repository must not be nested inside the target")
    old_files = (old_lock or {}).get("files", {})
    actions: list[dict[str, Any]] = []
    next_files: dict[str, dict[str, Any]] = {}
    unresolved: set[str] = set()
    manifest_paths = {item["path"] for item in manifest["files"]}

    for item in manifest["files"]:
        relative = item["path"]
        policy = item["policy"]
        executable = bool(item.get("executable", False))
        target_state, target_hash = file_state(target_root, relative)
        if policy == "project":
            if target_state == "missing":
                action = "required-missing"
            elif executable and os.name != "nt" and not has_execute_mode(
                checked_path(target_root, relative)
            ):
                action = "project-mode-conflict"
            else:
                action = "preserve"
            actions.append({"path": relative, "policy": policy, "action": action})
            if action != "preserve":
                unresolved.add(relative)
            continue

        source_path = checked_path(source_root, relative)
        source_hash = sha256_file(source_path)
        prior = old_files.get(relative)
        if target_state == "missing":
            if update and prior:
                action = "local-delete-conflict"
                unresolved.add(relative)
                next_files[relative] = dict(prior)
            else:
                action = "create"
                next_files[relative] = {
                    "policy": policy,
                    "sha256": source_hash,
                    "executable": executable,
                }
        elif target_hash == source_hash:
            if executable and os.name != "nt" and not has_execute_mode(
                checked_path(target_root, relative)
            ):
                action = "mode-correction"
            else:
                action = "identical"
            next_files[relative] = {
                "policy": policy,
                "sha256": source_hash,
                "executable": executable,
            }
        else:
            if update and prior and target_hash == prior.get("sha256"):
                action = "update"
                next_files[relative] = {
                    "policy": policy,
                    "sha256": source_hash,
                    "executable": executable,
                }
            else:
                action = "conflict"
                unresolved.add(relative)
                if prior:
                    next_files[relative] = dict(prior)
        actions.append(
            {
                "path": relative,
                "policy": policy,
                "action": action,
                "executable": executable,
                "expected_sha256": target_hash,
                "source_sha256": source_hash,
                "expected_mode": (
                    checked_path(target_root, relative).stat().st_mode & 0o777
                    if target_state == "file"
                    else None
                ),
            }
        )

    if update:
        for relative, prior in sorted(old_files.items()):
            if relative in manifest_paths:
                continue
            target_state, target_hash = file_state(target_root, relative)
            if target_state == "missing":
                actions.append({"path": relative, "policy": prior["policy"], "action": "already-removed"})
            elif target_hash == prior["sha256"]:
                actions.append(
                    {
                        "path": relative,
                        "policy": prior["policy"],
                        "action": "remove",
                        "expected_sha256": target_hash,
                    }
                )
            else:
                actions.append({"path": relative, "policy": prior["policy"], "action": "remove-conflict"})
                unresolved.add(relative)
                next_files[relative] = dict(prior)

    next_lock = {
        "schema_version": SCHEMA_VERSION,
        "codexicon_version": manifest["version"],
        "source_manifest_sha256": manifest["manifest_sha256"],
        "updated_at": utc_now(),
        "files": dict(sorted(next_files.items())),
        "unresolved": sorted(unresolved),
    }
    return actions, next_lock


def print_actions(actions: Iterable[dict[str, str]]) -> None:
    for item in actions:
        print(f"{item['action']:16} {item['policy']:8} {item['path']}")


def state_dir(target_root: Path) -> Path:
    return checked_path(target_root, STATE_DIR_NAME)


def transaction_path(target_root: Path) -> Path:
    return checked_path(target_root, f"{STATE_DIR_NAME}/{TRANSACTION_NAME}")


def remove_empty_parents(path: Path, stop: Path) -> None:
    current = path.parent
    stop = stop.resolve()
    while current != stop:
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def safe_remove_tree(path: Path, parent: Path) -> None:
    try:
        path.resolve().relative_to(parent.resolve())
    except (OSError, ValueError) as exc:
        raise CodexiconError(f"refusing cleanup outside transaction state: {path}") from exc
    if not path.exists():
        return
    shutil.rmtree(path)
    if path.exists():
        raise CodexiconError(f"transaction cleanup did not remove: {path}")


def validate_transaction_journal(
    target_root: Path, journal: dict[str, Any]
) -> tuple[list[dict[str, Any]], int, str]:
    transaction_id = journal.get("transaction_id")
    backup_root = journal.get("backup_root")
    operations = journal.get("operations")
    applied = journal.get("applied")
    if (
        journal.get("schema_version") != SCHEMA_VERSION
        or journal.get("format") != "codexicon-transaction-v1"
        or journal.get("phase") not in {"applying", "committed", "rolled-back"}
        or not isinstance(transaction_id, str)
        or not re.fullmatch(r"[a-f0-9]{16}", transaction_id)
        or backup_root != f"{STATE_DIR_NAME}/backups/{transaction_id}"
        or journal.get("repository_id") != repository_identity(target_root)
        or not isinstance(operations, list)
        or not operations
        or not isinstance(applied, int)
        or isinstance(applied, bool)
        or not 0 <= applied <= len(operations)
    ):
        raise CodexiconError("transaction journal is malformed; manual recovery is required")
    try:
        created = datetime.fromisoformat(str(journal["created_at"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise CodexiconError("transaction journal is malformed; manual recovery is required") from exc
    if created.tzinfo is None:
        raise CodexiconError("transaction journal is malformed; manual recovery is required")
    source_manifest_sha256 = journal.get("source_manifest_sha256")
    if source_manifest_sha256 is not None and (
        not isinstance(source_manifest_sha256, str)
        or not re.fullmatch(r"[a-f0-9]{64}", source_manifest_sha256)
    ):
        raise CodexiconError("transaction journal is malformed; manual recovery is required")

    seen: set[str] = set()
    for index, operation in enumerate(operations):
        if not isinstance(operation, dict):
            raise CodexiconError("transaction journal is malformed; manual recovery is required")
        action = operation.get("action")
        relative = normalize_relative(str(operation.get("path", "")))
        checked_path(target_root, relative)
        if relative in seen or action not in {"write", "delete", "write-lock"}:
            raise CodexiconError("transaction journal is malformed; manual recovery is required")
        seen.add(relative)
        before = operation.get("before_sha256")
        after = operation.get("after_sha256")
        if before is not None and not (
            isinstance(before, str) and re.fullmatch(r"[a-f0-9]{64}", before)
        ):
            raise CodexiconError("transaction journal is malformed; manual recovery is required")
        if after is not None and not (
            isinstance(after, str) and re.fullmatch(r"[a-f0-9]{64}", after)
        ):
            raise CodexiconError("transaction journal is malformed; manual recovery is required")
        source_sha256 = operation.get("source_sha256")
        if source_sha256 is not None and (
            not isinstance(source_sha256, str)
            or not re.fullmatch(r"[a-f0-9]{64}", source_sha256)
            or source_sha256 != after
        ):
            raise CodexiconError("transaction journal is malformed; manual recovery is required")
        operation_manifest_sha256 = operation.get("source_manifest_sha256")
        if operation_manifest_sha256 is not None and (
            not isinstance(operation_manifest_sha256, str)
            or not re.fullmatch(r"[a-f0-9]{64}", operation_manifest_sha256)
            or (
                source_manifest_sha256 is not None
                and operation_manifest_sha256 != source_manifest_sha256
            )
        ):
            raise CodexiconError("transaction journal is malformed; manual recovery is required")
        expected_backup = (
            f"{backup_root}/{operation_backup_name(index, relative)}"
            if before is not None
            else None
        )
        if operation.get("backup") != expected_backup:
            raise CodexiconError("transaction journal is malformed; manual recovery is required")
        mode = operation.get("target_mode")
        if mode is not None and (
            not isinstance(mode, int) or isinstance(mode, bool) or not 0 <= mode <= 0o777
        ):
            raise CodexiconError("transaction journal is malformed; manual recovery is required")
        if before is None and mode is not None:
            raise CodexiconError("transaction journal is malformed; manual recovery is required")
        if action == "delete":
            if before is None or after is not None or "content" in operation:
                raise CodexiconError("transaction journal is malformed; manual recovery is required")
        else:
            if after is None:
                raise CodexiconError("transaction journal is malformed; manual recovery is required")
            if action == "write-lock":
                content = operation.get("content")
                if (
                    relative != LOCK_NAME
                    or not isinstance(content, str)
                    or sha256_bytes(content.encode("utf-8")) != after
                ):
                    raise CodexiconError("transaction journal is malformed; manual recovery is required")
            elif relative == LOCK_NAME or "content" in operation:
                raise CodexiconError("transaction journal is malformed; manual recovery is required")
    return operations, applied, str(backup_root)


def current_digest(path: Path) -> str | None:
    if not path.exists():
        return None
    if not path.is_file():
        raise CodexiconError(f"expected a regular file: {path}")
    return sha256_file(path)


def validate_source_baseline(source_root: Path, journal: dict[str, Any]) -> None:
    """Refuse a planned transaction if its source bytes or manifest have drifted."""

    source_manifest_sha256 = journal.get("source_manifest_sha256")
    if source_manifest_sha256 is not None:
        manifest = checked_path(source_root, MANIFEST_NAME)
        if current_digest(manifest) != source_manifest_sha256:
            raise CodexiconError(
                "source manifest changed after planning; refusing to apply transaction"
            )
    for operation in journal["operations"]:
        if operation["action"] != "write" or operation.get("source_sha256") is None:
            continue
        source = checked_path(source_root, str(operation["path"]))
        if current_digest(source) != operation["source_sha256"]:
            raise CodexiconError(
                f"source changed after planning; refusing to apply {operation['path']}"
            )


def rollback_transaction(target_root: Path, journal: dict[str, Any]) -> None:
    operations, applied, _ = validate_transaction_journal(target_root, journal)
    for operation in reversed(operations[:applied]):
        relative = normalize_relative(str(operation.get("path", "")))
        target = checked_path(target_root, relative)
        backup_relative = operation.get("backup")
        if backup_relative:
            backup = checked_path(target_root, normalize_relative(str(backup_relative)))
            if not backup.is_file():
                raise CodexiconError(f"transaction backup is missing for {relative}")
            if sha256_file(backup) != operation["before_sha256"]:
                raise CodexiconError(f"transaction backup is corrupt for {relative}")
            digest = current_digest(target)
            if digest not in {None, operation["before_sha256"], operation["after_sha256"]}:
                raise CodexiconError(
                    f"refusing to overwrite a concurrent change while recovering {relative}"
                )
            target_mode = operation.get("target_mode")
            atomic_write_bytes(
                target,
                backup.read_bytes(),
                mode=int(target_mode) if isinstance(target_mode, int) else None,
            )
        else:
            digest = current_digest(target)
            if digest not in {None, operation["after_sha256"]}:
                raise CodexiconError(
                    f"refusing to delete a concurrent change while recovering {relative}"
                )
            try:
                target.unlink()
            except FileNotFoundError:
                pass
            remove_empty_parents(target, target_root)


def recover_transaction(target_root: Path) -> None:
    journal_path = transaction_path(target_root)
    if not journal_path.exists():
        return
    journal = read_json(journal_path, "Codexicon transaction journal")
    if not isinstance(journal, dict):
        raise CodexiconError("transaction journal is malformed; manual recovery is required")
    _, _, backup_root_raw = validate_transaction_journal(target_root, journal)
    if journal["phase"] == "applying":
        rollback_transaction(target_root, journal)
        journal["phase"] = "rolled-back"
        atomic_write_json(journal_path, journal)
    backup_root = checked_path(target_root, normalize_relative(backup_root_raw))
    safe_remove_tree(backup_root, state_dir(target_root))
    journal_path.unlink(missing_ok=True)
    print("[codexicon] Recovered an interrupted transaction.", file=sys.stderr)


def operation_backup_name(index: int, relative: str) -> str:
    digest = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16]
    return f"{index:04d}-{digest}.bak"


def build_operations(
    source_root: Path,
    target_root: Path,
    actions: list[dict[str, Any]],
    next_lock: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    operations: list[dict[str, Any]] = []
    transaction_id = secrets.token_hex(8)
    backup_root_relative = f"{STATE_DIR_NAME}/backups/{transaction_id}"
    source_manifest_sha256 = next_lock.get("source_manifest_sha256")
    for item in actions:
        action = item["action"]
        if action not in {"create", "update", "remove", "mode-correction"}:
            continue
        relative = item["path"]
        target = checked_path(target_root, relative)
        before_sha256 = item.get("expected_sha256")
        backup = None
        if before_sha256 is not None:
            backup = f"{backup_root_relative}/{operation_backup_name(len(operations), relative)}"
        operation: dict[str, Any] = {
            "action": "delete" if action == "remove" else "write",
            "path": relative,
            "backup": backup,
            "target_mode": (
                item.get("expected_mode")
                if action == "mode-correction"
                else (target.stat().st_mode & 0o777) if target.is_file() else None
            ),
            "before_sha256": before_sha256,
            "after_sha256": None,
        }
        if action != "remove":
            source_sha256 = item.get("source_sha256")
            if not isinstance(source_sha256, str) or not re.fullmatch(
                r"[a-f0-9]{64}", source_sha256
            ):
                raise CodexiconError(f"install plan lacks a source baseline: {relative}")
            operation["after_sha256"] = source_sha256
            operation["source_sha256"] = source_sha256
            operation["executable"] = bool(item.get("executable", False))
            if action == "mode-correction":
                operation["mode_correction"] = True
        if source_manifest_sha256 is not None:
            operation["source_manifest_sha256"] = source_manifest_sha256
        operations.append(operation)
    lock_content = (json.dumps(next_lock, indent=2, sort_keys=True) + "\n").encode("utf-8")
    lock_target = checked_path(target_root, LOCK_NAME)
    lock_backup = None
    if lock_target.is_file():
        lock_backup = f"{backup_root_relative}/{operation_backup_name(len(operations), LOCK_NAME)}"
    lock_operation: dict[str, Any] = {
        "action": "write-lock",
        "path": LOCK_NAME,
        "backup": lock_backup,
        "target_mode": (lock_target.stat().st_mode & 0o777) if lock_target.is_file() else None,
        "before_sha256": sha256_file(lock_target) if lock_target.is_file() else None,
        "after_sha256": sha256_bytes(lock_content),
        "content": lock_content.decode("utf-8"),
    }
    if source_manifest_sha256 is not None:
        lock_operation["source_manifest_sha256"] = source_manifest_sha256
    operations.append(lock_operation)
    return transaction_id, operations


def apply_operation(source_root: Path, target_root: Path, operation: dict[str, Any]) -> None:
    target = checked_path(target_root, str(operation["path"]))
    if operation["action"] == "delete":
        target.unlink()
        remove_empty_parents(target, target_root)
        return
    if operation["action"] == "write-lock":
        content = str(operation["content"]).encode("utf-8")
        mode = 0o644
    else:
        source = checked_path(source_root, str(operation["path"]))
        content = source.read_bytes()
        mode = source.stat().st_mode & 0o777
    if sha256_bytes(content) != operation["after_sha256"]:
        raise CodexiconError(f"source changed while applying: {operation['path']}")
    if operation["action"] == "write" and operation.get("executable"):
        mode = 0o755
    atomic_write_bytes(target, content, mode=mode)


def apply_transaction(
    source_root: Path,
    target_root: Path,
    actions: list[dict[str, Any]],
    next_lock: dict[str, Any],
) -> None:
    recover_transaction(target_root)
    transaction_id, operations = build_operations(source_root, target_root, actions, next_lock)
    backup_root_relative = f"{STATE_DIR_NAME}/backups/{transaction_id}"
    journal = {
        "schema_version": SCHEMA_VERSION,
        "format": "codexicon-transaction-v1",
        "transaction_id": transaction_id,
        "repository_id": repository_identity(target_root),
        "created_at": utc_now(),
        "phase": "applying",
        "backup_root": backup_root_relative,
        "applied": 0,
        "operations": operations,
    }
    if next_lock.get("source_manifest_sha256") is not None:
        journal["source_manifest_sha256"] = next_lock["source_manifest_sha256"]
    validate_source_baseline(source_root, journal)
    journal_path = transaction_path(target_root)
    atomic_write_json(journal_path, journal)
    try:
        for index, operation in enumerate(operations):
            target = checked_path(target_root, str(operation["path"]))
            if current_digest(target) != operation["before_sha256"]:
                raise CodexiconError(
                    f"target changed after planning; refusing to modify {operation['path']}"
                )
            if (
                operation.get("mode_correction")
                and (target.stat().st_mode & 0o777) != operation.get("target_mode")
            ):
                raise CodexiconError(
                    f"target mode changed after planning; refusing to modify {operation['path']}"
                )
            backup_relative = operation.get("backup")
            if backup_relative:
                backup = checked_path(target_root, str(backup_relative))
                atomic_write_bytes(backup, target.read_bytes(), mode=0o600)
                if sha256_file(backup) != operation["before_sha256"]:
                    raise CodexiconError(f"target changed while backing up {operation['path']}")
            journal["applied"] = index + 1
            atomic_write_json(journal_path, journal)
            if current_digest(target) != operation["before_sha256"]:
                journal["applied"] = index
                atomic_write_json(journal_path, journal)
                raise CodexiconError(
                    f"target changed before replacement; refusing to modify {operation['path']}"
                )
            apply_operation(source_root, target_root, operation)
    except BaseException:
        try:
            rollback_transaction(target_root, journal)
            journal["phase"] = "rolled-back"
            atomic_write_json(journal_path, journal)
            backup_root = checked_path(target_root, backup_root_relative)
            safe_remove_tree(backup_root, state_dir(target_root))
            journal_path.unlink(missing_ok=True)
        except BaseException:
            # Leave the valid journal and backups for deterministic next-run recovery.
            pass
        raise
    journal["phase"] = "committed"
    atomic_write_json(journal_path, journal)
    backup_root = checked_path(target_root, backup_root_relative)
    safe_remove_tree(backup_root, state_dir(target_root))
    journal_path.unlink(missing_ok=True)


def run_install(
    source_root: Path,
    target_root: Path,
    *,
    apply: bool,
    update: bool,
) -> int:
    source_root = source_root.resolve()
    target_root = target_root.resolve()
    if not target_root.is_dir():
        raise CodexiconError(f"target repository does not exist: {target_root}")
    if apply:
        recover_transaction(target_root)
    elif transaction_path(target_root).exists():
        raise CodexiconError(
            "an interrupted transaction requires recovery; re-run the intended adopt/update "
            "with --apply before requesting a new read-only plan"
        )
    manifest = load_manifest(source_root)
    old_lock = load_lock(target_root, required=update)
    if not update and old_lock is not None:
        raise CodexiconError(
            "target already has a Codexicon installation lock; use update with a trusted "
            "local source so deletions and retired paths remain conflicts"
        )
    actions, next_lock = install_plan(
        source_root,
        target_root,
        manifest,
        old_lock,
        update=update,
    )
    print_actions(actions)
    if not apply:
        print("[codexicon] Read-only plan. Re-run with --apply to perform listed create/update/remove actions.")
        return 2 if next_lock["unresolved"] else 0
    apply_transaction(source_root, target_root, actions, next_lock)
    if next_lock["unresolved"]:
        print(
            "[codexicon] Applied safe changes; unresolved project-owned or conflicting files remain: "
            + ", ".join(next_lock["unresolved"]),
            file=sys.stderr,
        )
        return 2
    print(f"[codexicon] {'Update' if update else 'Adoption'} completed.")
    return 0


def parse_hooks(root: Path, diagnostics: list[tuple[str, str]]) -> None:
    path = root / ".codex" / "hooks.json"
    if not path.is_file():
        diagnostics.append(("ERROR", "missing .codex/hooks.json"))
        return
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        diagnostics.append(("ERROR", f"malformed .codex/hooks.json: {exc}"))
        return
    hooks = value.get("hooks") if isinstance(value, dict) else None
    if not isinstance(hooks, dict):
        diagnostics.append(("ERROR", ".codex/hooks.json requires a hooks object"))
        return
    actions_by_event: dict[str, set[str]] = {}
    for event, groups in hooks.items():
        if event not in SUPPORTED_HOOK_EVENTS:
            diagnostics.append(("ERROR", f"unsupported hook event: {event}"))
        if not isinstance(groups, list):
            diagnostics.append(("ERROR", f"hook event {event} must contain a list"))
            continue
        for group in groups:
            handlers = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(handlers, list) or not handlers:
                diagnostics.append(("ERROR", f"hook event {event} has no command handlers"))
                continue
            for handler in handlers:
                if not isinstance(handler, dict) or handler.get("type") != "command":
                    diagnostics.append(("ERROR", f"hook event {event} has an unsupported handler"))
                elif not handler.get("command") or not handler.get("commandWindows"):
                    diagnostics.append(("ERROR", f"hook event {event} lacks cross-platform commands"))
                else:
                    command_text = f"{handler['command']} {handler['commandWindows']}"
                    action_capabilities = {
                        "session-start": "session-start",
                        "session-resume": "session-resume",
                        "prepare-tool": "protect-secrets",
                        "protect-secrets": "protect-secrets",
                        "record-write": "record-write",
                        "record-shell": "record-shell",
                        "record-compact": "record-compact",
                        "record-stop": "verify-stop",
                        "verify-stop": "verify-stop",
                    }
                    for action, capability in action_capabilities.items():
                        if action in command_text:
                            actions_by_event.setdefault(event, set()).add(capability)
    required_actions = {
        "SessionStart": {"session-start", "session-resume"},
        "PreToolUse": {"protect-secrets"},
        "PostToolUse": {"record-write", "record-shell"},
        "PreCompact": {"record-compact"},
        "Stop": {"verify-stop"},
    }
    for event, required in required_actions.items():
        missing = required - actions_by_event.get(event, set())
        for action in sorted(missing):
            diagnostics.append(("ERROR", f"hook event {event} lacks required {action} action"))


def strip_toml_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if quote == '"' and character == "\\":
            escaped = True
            continue
        if character in {"'", '"'}:
            quote = None if quote == character else character if quote is None else quote
            continue
        if character == "#" and quote is None:
            return line[:index].rstrip()
    return line.rstrip()


def parse_toml_scalar(raw_value: str, key: str) -> Any:
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    try:
        return ast.literal_eval(raw_value)
    except (SyntaxError, ValueError) as exc:
        raise ValueError(f"invalid TOML value for {key}: {raw_value}") from exc


def parse_toml_subset(content: str) -> dict[str, Any]:
    """Parse Codexicon's dependency-free TOML subset on Python 3.10."""

    result: dict[str, Any] = {}
    current = result
    seen_sections: set[str] = set()
    lines = content.splitlines()
    index = 0
    while index < len(lines):
        line = strip_toml_comment(lines[index]).strip()
        index += 1
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]") and not line.startswith("[["):
            section = line[1:-1].strip()
            parts = section.split(".")
            if (
                not section
                or section in seen_sections
                or any(
                    not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", part)
                    for part in parts
                )
            ):
                raise ValueError(f"unsupported TOML section: {line}")
            seen_sections.add(section)
            current = result
            for part in parts:
                value = current.setdefault(part, {})
                if not isinstance(value, dict):
                    raise ValueError(f"duplicate TOML key/section: {section}")
                current = value
            continue
        if "=" not in line:
            raise ValueError(f"invalid TOML line: {line}")
        key, raw_value = (part.strip() for part in line.split("=", 1))
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key) or key in current:
            raise ValueError(f"invalid or duplicate TOML key: {key}")
        delimiter = (
            '"""'
            if raw_value.startswith('"""')
            else "'''"
            if raw_value.startswith("'''")
            else None
        )
        if delimiter is not None:
            chunks = [raw_value[3:]]
            while not chunks[-1].endswith(delimiter):
                if index >= len(lines):
                    raise ValueError(f"unterminated multiline string: {key}")
                chunks.append(lines[index])
                index += 1
            chunks[-1] = chunks[-1][:-3]
            current[key] = "\n".join(chunks)
            continue
        current[key] = parse_toml_scalar(strip_toml_comment(raw_value).strip(), key)
    return result


def parse_config(root: Path, diagnostics: list[tuple[str, str]]) -> None:
    path = root / ".codex" / "config.toml"
    if not path.is_file():
        diagnostics.append(("ERROR", "missing .codex/config.toml"))
        return
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        diagnostics.append(("ERROR", f"unreadable .codex/config.toml: {exc}"))
        return
    parsed: dict[str, Any] | None = None
    if tomllib is not None:
        try:
            parsed = tomllib.loads(content)
        except tomllib.TOMLDecodeError as exc:
            diagnostics.append(("ERROR", f"malformed .codex/config.toml: {exc}"))
            return
    else:
        try:
            parsed = parse_toml_subset(content)
        except ValueError as exc:
            diagnostics.append(("ERROR", f"malformed .codex/config.toml: {exc}"))
            return
    agents = parsed.get("agents", {})
    if not isinstance(agents, dict):
        diagnostics.append(("ERROR", "agents configuration must be a table"))
        agents = {}
    if "max_depth" in agents:
        diagnostics.append(("ERROR", "undocumented agents.max_depth is configured"))
    if "max_threads" in agents:
        diagnostics.append(("WARN", "agents.max_threads is a legacy alias; use max_concurrent_threads_per_session"))
    assert parsed is not None
    markers = parsed.get("project_root_markers")
    features = parsed.get("features", {})
    if not isinstance(markers, list) or not all(isinstance(item, str) for item in markers):
        diagnostics.append(("ERROR", "project_root_markers must be a string list"))
    if not isinstance(features, dict) or features.get("hooks") is not True:
        diagnostics.append(("ERROR", "features.hooks must be true"))
    if not isinstance(features, dict) or features.get("multi_agent") is not True:
        diagnostics.append(("ERROR", "features.multi_agent must be true"))


def checkpoint_metadata(path: Path) -> dict[str, Any] | None:
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0]
    except (OSError, IndexError, UnicodeDecodeError):
        return None
    match = re.fullmatch(r"<!--\s*codexicon-checkpoint:\s*(\{.*\})\s*-->", first)
    if not match:
        return None
    try:
        value = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def repository_identity(root: Path) -> str:
    """Return a checkout-local identity without consulting Git metadata."""

    return hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:20]


def git_value(root: Path, *args: str) -> str | None:
    """Run an explicit Git integration query reserved for Ship-capable commands."""

    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def ship_dirty_paths(root: Path) -> list[str]:
    """Read Git dirty paths for explicit Ship auditing only."""

    value = git_value(root, "status", "--porcelain=v1", "-z")
    if value is None:
        return []
    paths: set[str] = set()
    entries = value.split("\0")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status = entry[:2]
        raw_paths = [entry[3:] if len(entry) >= 4 else entry]
        if ("R" in status or "C" in status) and index < len(entries):
            raw_paths.append(entries[index])
            index += 1
        for raw in raw_paths:
            try:
                paths.add(normalize_relative(raw))
            except CodexiconError:
                continue
    return sorted(paths)


def dirty_paths(root: Path, paths: Sequence[str] = ()) -> list[str]:
    """Normalize caller-supplied changed paths without inspecting checkout state."""

    del root  # The identity is intentionally path-list based, not repository based.
    return sorted({normalize_relative(path) for path in paths})


def protected_local_path(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    name = PurePosixPath(normalized).name.casefold()
    if name == ".env.example":
        return False
    return (
        name == ".env"
        or name.startswith(".env.")
        or name in {".npmrc", ".pypirc", ".netrc", "credentials.json"}
        or "/secrets/" in f"/{normalized.casefold()}/"
        or normalized.casefold().endswith(
            (
                "/.aws/credentials",
                "/.ssh/id_rsa",
                "/.ssh/id_dsa",
                "/.ssh/id_ecdsa",
                "/.ssh/id_ed25519",
                "/.kube/config",
                "/.docker/config.json",
            )
        )
        or name.endswith((".key", ".pem", ".p12", ".pfx", ".secret"))
    )


def local_path_identity(root: Path, relative: str) -> str:
    """Hash one safe local path, including deterministic directory contents."""

    if protected_local_path(relative):
        raise CodexiconError(f"local identity refuses protected path: {relative}")
    path = checked_path(root, relative)
    if not path.exists():
        return "missing"
    if path.is_file():
        return f"sha256:{sha256_file(path)}"
    if not path.is_dir():
        raise CodexiconError(f"local identity contains unsupported path: {relative}")
    entries: list[dict[str, str]] = []
    for child in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
        child_relative = child.relative_to(root).as_posix()
        if protected_local_path(child_relative):
            raise CodexiconError(f"local identity refuses protected path: {child_relative}")
        checked_path(root, child_relative)
        if child.is_dir():
            continue
        if not child.is_file():
            raise CodexiconError(f"local identity contains unsupported path: {child_relative}")
        entries.append({"path": child_relative, "sha256": sha256_file(child)})
    material = json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256_bytes(material)}"


def local_path_evidence(root: Path, paths: Sequence[str]) -> dict[str, str]:
    normalized = sorted({normalize_relative(path) for path in paths})
    return {relative: local_path_identity(root, relative) for relative in normalized}


def local_path_evidence_identity(evidence: dict[str, str]) -> str:
    material = json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256_bytes(material)}"


def checkpoint_local_identities(root: Path, paths: Sequence[str]) -> dict[str, Any]:
    evidence = local_path_evidence(root, paths)
    return {
        "contract_identity": local_path_identity(root, "SPEC.md"),
        "task_identity": local_path_identity(root, "TASKS.md"),
        "path_identity": local_path_evidence_identity(evidence),
        "path_evidence": evidence,
    }


def checkpoint_identity_warnings(root: Path, metadata: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    identity_labels = (("contract_identity", "SPEC.md"), ("task_identity", "TASKS.md"))
    for key, label in identity_labels:
        expected = metadata.get(key)
        if isinstance(expected, str) and expected != local_path_identity(root, label):
            warnings.append(f"checkpoint {label} identity differs from the current local file")
    evidence = metadata.get("path_evidence")
    if isinstance(evidence, dict):
        current = local_path_evidence(root, [str(path) for path in evidence])
        for relative, expected in evidence.items():
            if current.get(relative) != expected:
                warnings.append(f"checkpoint path evidence differs for {relative}")
    return warnings


def validate_checkpoint(
    root: Path, path: Path
) -> tuple[datetime | None, dict[str, Any] | None, str | None]:
    metadata = checkpoint_metadata(path)
    if not metadata:
        return None, None, "missing or malformed checkpoint marker"
    if metadata.get("schema_version") != SCHEMA_VERSION:
        return None, None, "unsupported checkpoint schema"
    checkpoint_id = metadata.get("checkpoint_id")
    repository_id = metadata.get("repository_id")
    if not isinstance(checkpoint_id, str) or not re.fullmatch(r"[a-f0-9]{16}", checkpoint_id):
        return None, None, "invalid checkpoint ID"
    if not isinstance(repository_id, str) or not re.fullmatch(r"[a-f0-9]{20}", repository_id):
        return None, None, "invalid repository fingerprint"
    try:
        created = datetime.fromisoformat(str(metadata["created_at"]))
    except (KeyError, TypeError, ValueError):
        return None, None, "invalid checkpoint timestamp"
    if created.tzinfo is None:
        return None, None, "checkpoint timestamp lacks a timezone"
    if not isinstance(metadata.get("branch"), str) or not isinstance(metadata.get("head"), str):
        return None, None, "invalid checkpoint local reference"
    for key in ("contract_identity", "task_identity"):
        value = metadata.get(key)
        if value is not None and value != "missing" and (
            not isinstance(value, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", value)
        ):
            return None, None, f"invalid checkpoint {key}"
    path_identity = metadata.get("path_identity")
    if path_identity is not None and (
        not isinstance(path_identity, str)
        or not re.fullmatch(r"sha256:[a-f0-9]{64}", path_identity)
    ):
        return None, None, "invalid checkpoint path identity"
    evidence = metadata.get("path_evidence")
    if evidence is not None:
        if not isinstance(evidence, dict) or any(
            not isinstance(path, str)
            or not isinstance(identity, str)
            or (identity != "missing" and not re.fullmatch(r"sha256:[a-f0-9]{64}", identity))
            for path, identity in evidence.items()
        ):
            return None, None, "invalid checkpoint path evidence"
        try:
            evidence = {normalize_relative(path): identity for path, identity in evidence.items()}
        except CodexiconError:
            return None, None, "unsafe checkpoint path evidence"
        if any(protected_local_path(path) for path in evidence):
            return None, None, "checkpoint path evidence includes a protected path"
        if path_identity is not None and path_identity != local_path_evidence_identity(evidence):
            return None, None, "checkpoint path identity does not match its evidence"
    related = metadata.get("related")
    if not isinstance(related, list):
        return None, None, "invalid checkpoint related paths"
    try:
        normalized_related = [normalize_relative(str(item)) for item in related]
    except CodexiconError:
        return None, None, "unsafe checkpoint related path"
    if len(normalized_related) != len(set(normalized_related)):
        return None, None, "duplicate checkpoint related path"
    changed = metadata.get("changed", [])
    if not isinstance(changed, list):
        return None, None, "invalid checkpoint changed paths"
    try:
        normalized_changed = [normalize_relative(str(item)) for item in changed]
    except CodexiconError:
        return None, None, "unsafe checkpoint changed path"
    if len(normalized_changed) != len(set(normalized_changed)):
        return None, None, "duplicate checkpoint changed path"
    metadata = {**metadata, "related": normalized_related}
    metadata["changed"] = normalized_changed
    if evidence is not None:
        metadata["path_evidence"] = evidence
    return created, metadata, None


def compatible_checkpoints(root: Path) -> list[tuple[datetime, Path, dict[str, Any]]]:
    sessions = checked_path(root, "agent_docs/sessions")
    if not sessions.is_dir():
        return []
    repo_id = repository_identity(root)
    candidates: list[tuple[datetime, Path, dict[str, Any]]] = []
    for path in sessions.glob("*.md"):
        try:
            path = checked_path(root, path.relative_to(root).as_posix())
        except (CodexiconError, ValueError):
            continue
        created, metadata, error = validate_checkpoint(root, path)
        if error or created is None or metadata is None or metadata["repository_id"] != repo_id:
            continue
        candidates.append((created, path, metadata))
    return sorted(candidates, key=lambda item: (item[0], item[1].name), reverse=True)


SPEC_SECTIONS = {
    "Requirements": re.compile(r"^\s*-\s+\*\*(R-\d+):\*\*\s*(.*?)\s*$"),
    "Interfaces": re.compile(r"^\s*-\s+\*\*(I-\d+):\*\*\s*(.*?)\s*$"),
    "Acceptance": re.compile(r"^\s*-\s+\*\*(A-\d+):\*\*\s*(.*?)\s*$"),
    "Anti-goals": re.compile(r"^\s*-\s+\*\*(AG-\d+):\*\*\s*(.*?)\s*$"),
}
REQUIRED_SPEC_SECTIONS = ("Outcome", *SPEC_SECTIONS)
SPEC_STATUS_RE = re.compile(r"^\s*\*\*Status:\*\*\s*(.*?)\s*$")
SPEC_REVISION_RE = re.compile(r"^\s*\*\*Revision:\*\*\s*(.*?)\s*$")
CONTRACT_REFERENCE_RE = re.compile(r"\b(?:R|I|A|AG)-\d+\b")
AMENDMENT_DATE_RE = re.compile(r"^\s*-\s+\*\*(\d{4}-\d{2}-\d{2}):\*\*\s+\S")
PLACEHOLDER_RE = re.compile(
    r"^(?:\[.*\]|[-_.]{2,}|none\.?|tbd\.?|todo\.?|n/?a\.?|"
    r"placeholder|to be defined|fill in|replace me)$",
    re.IGNORECASE,
)
TASK_HEADERS = ("id", "state", "requirement", "interface", "scope", "verification")
TASK_EXTENDED_HEADERS = (
    *TASK_HEADERS,
    "Dependencies",
    "Blocker",
    "Evidence",
)
TASK_STATES = {"TODO", "ACTIVE", "DONE", "BLOCKED"}
QUEUE_READY = "READY"
QUEUE_RESUME_ACTIVE = "RESUME_ACTIVE"
QUEUE_BLOCKED = "BLOCKED"
QUEUE_COMPLETE = "COMPLETE"
QUEUE_INVALID = "INVALID"
QUEUE_EXIT_CODES = {
    QUEUE_READY: 0,
    QUEUE_RESUME_ACTIVE: 0,
    QUEUE_BLOCKED: 3,
    QUEUE_COMPLETE: 0,
    QUEUE_INVALID: 2,
}


@dataclass(frozen=True)
class QueueSelection:
    outcome: str
    task: dict[str, Any] | None = None
    reason: str = ""
    blockers: dict[str, list[str]] | None = None


@dataclass(frozen=True)
class ContractDetails:
    """Validated contract data, including the identity used for drift checks."""

    text: str
    revision: str
    digest: str
    requirements: set[str]
    interfaces: set[str]
    acceptance: set[str]
    anti_goals: set[str]

    @property
    def identity(self) -> str:
        return f"sha256:{self.digest}"


EVIDENCE_SCHEMA_VERSION = 1
EVIDENCE_PASS = "passed"
REVIEW_DISPOSITIONS = {"accepted", "fixed", "rejected", "not_applicable"}


def _digest_identity(raw: Any, label: str) -> str:
    if not isinstance(raw, str):
        raise CodexiconError(f"task evidence requires a {label}")
    value = raw.strip().removeprefix("sha256:")
    if not re.fullmatch(r"[a-f0-9]{64}", value):
        raise CodexiconError(f"task evidence has an invalid {label}")
    return f"sha256:{value}"


def _scope_paths(scope: str) -> list[str]:
    code_spans = re.findall(r"`([^`]+)`", scope)
    candidates = code_spans or [part.strip() for part in scope.split(",")]
    paths: list[str] = []
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        try:
            normalized = normalize_relative(candidate)
        except CodexiconError:
            if code_spans:
                raise
            # A prose scope has no safely enumerable path; its literal still
            # participates in the digest below, so it cannot be confused with
            # a different scope description.
            continue
        if normalized not in paths:
            paths.append(normalized)
    return paths


def relevant_source_digest(root: Path, row: dict[str, Any]) -> str:
    """Return a deterministic digest of the files named by a task scope.

    This is an identity check, not a security boundary. Verification commands
    are recorded as data and are never executed by the task manager.
    """

    root = root.resolve()
    entries: list[dict[str, str]] = []
    paths = _scope_paths(str(row["scope"]))
    if not paths:
        entries.append({"scope": str(row["scope"]).strip()})
    for relative in paths:
        path = checked_path(root, relative)
        if not path.exists():
            entries.append({"path": relative, "sha256": "missing"})
            continue
        if path.is_file():
            entries.append({"path": relative, "sha256": sha256_file(path)})
            continue
        if path.is_dir():
            found = False
            for child in sorted(path.rglob("*"), key=lambda item: item.as_posix()):
                child_relative = child.relative_to(root).as_posix()
                checked_path(root, child_relative)
                if child.is_dir():
                    continue
                if not child.is_file():
                    raise CodexiconError(f"task scope contains unsupported path: {child_relative}")
                found = True
                entries.append({"path": child_relative, "sha256": sha256_file(child)})
            if not found:
                entries.append({"path": relative, "sha256": "empty-directory"})
            continue
        raise CodexiconError(f"task scope contains unsupported path: {relative}")
    material = json.dumps(
        {"task_id": row["id"], "scope": str(row["scope"]), "entries": entries},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{sha256_bytes(material)}"


def _command_identity(command: Any) -> tuple[str, bool]:
    if isinstance(command, list):
        if not command or any(not isinstance(part, str) or not part.strip() for part in command):
            raise CodexiconError("task evidence commands must be non-empty string argument lists")
        return " ".join(part.strip() for part in command), True
    if isinstance(command, str) and command.strip():
        return " ".join(command.split()), False
    raise CodexiconError("task evidence requires a check command")


def _declared_command_identity(value: str) -> str:
    spans = re.findall(r"`([^`]+)`", value)
    command = spans[0] if spans else value
    return " ".join(command.split())


def _command_tokens(value: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(value, posix=True))
    except ValueError:
        return tuple(value.split())


def _evidence_value(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        value = raw
    elif isinstance(raw, str) and raw.strip():
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CodexiconError("task evidence must be a JSON object") from exc
    else:
        raise CodexiconError("task evidence is required and must be a JSON object")
    if not isinstance(value, dict):
        raise CodexiconError("task evidence must be a JSON object")
    return value


def validate_task_evidence(
    root: Path,
    row: dict[str, Any],
    raw: Any,
    *,
    contract: ContractDetails | None = None,
) -> dict[str, Any]:
    """Validate and normalize one task-local completion receipt."""

    value = _evidence_value(raw)
    version = value.get("schema_version", value.get("version", EVIDENCE_SCHEMA_VERSION))
    if version != EVIDENCE_SCHEMA_VERSION:
        raise CodexiconError("task evidence has an unsupported schema version")
    if value.get("task_id") != row["id"]:
        raise CodexiconError(f"task evidence belongs to the wrong task: {row['id']}")

    acceptance = value.get("acceptance_ids", value.get("acceptance"))
    if not isinstance(acceptance, list) or not acceptance or any(
        not isinstance(item, str) or not re.fullmatch(r"A-\d+", item) for item in acceptance
    ):
        raise CodexiconError(f"task evidence for {row['id']} requires acceptance_ids")
    contract = contract or read_contract_details(root.resolve())
    unknown_acceptance = sorted(set(acceptance) - contract.acceptance)
    if unknown_acceptance:
        raise CodexiconError(
            f"task evidence for {row['id']} references unknown acceptance ID(s): "
            f"{', '.join(unknown_acceptance)}"
        )

    result = value.get("result")
    if result != EVIDENCE_PASS:
        raise CodexiconError(f"task evidence for {row['id']} is not successful")

    timestamp = value.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise CodexiconError(f"task evidence for {row['id']} requires a timestamp")
    try:
        parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CodexiconError(f"task evidence for {row['id']} has an invalid timestamp") from exc
    if parsed_timestamp.tzinfo is None:
        raise CodexiconError(f"task evidence for {row['id']} timestamp requires a timezone")
    if parsed_timestamp > datetime.now(timezone.utc):
        raise CodexiconError(f"task evidence for {row['id']} has a future timestamp")

    source_digest = _digest_identity(
        value.get("source_digest", value.get("relevant_source_digest")),
        "source digest",
    )
    current_source_digest = relevant_source_digest(root, row)
    if source_digest != current_source_digest:
        raise CodexiconError(f"task evidence for {row['id']} is stale: source digest changed")
    contract_digest = _digest_identity(value.get("contract_digest"), "contract digest")
    if contract_digest != contract.identity:
        raise CodexiconError(f"task evidence for {row['id']} is stale: contract digest changed")

    checks = value.get("checks")
    if checks is None and isinstance(value.get("check"), dict):
        checks = [value["check"]]
    if checks is None and "command" in value:
        checks = [
            {
                "identity": value.get("check_identity", value.get("check_id")),
                "command": value.get("command"),
                "result": value.get("check_result", result),
                "reviewed": value.get("reviewed"),
            }
        ]
    if not isinstance(checks, list) or not checks:
        raise CodexiconError(f"task evidence for {row['id']} requires checks")
    normalized_checks: list[dict[str, Any]] = []
    declared_command = _declared_command_identity(str(row["verification"]))
    declared_tokens = _command_tokens(declared_command)
    for check in checks:
        if not isinstance(check, dict):
            raise CodexiconError(f"task evidence for {row['id']} contains a malformed check")
        identity = check.get("identity", check.get("id"))
        if not isinstance(identity, str) or not identity.strip():
            raise CodexiconError(f"task evidence for {row['id']} checks require an identity")
        command, structured = _command_identity(check.get("command"))
        if not structured and check.get("reviewed") is not True:
            raise CodexiconError(
                f"task evidence check {identity} must use an argument list or reviewed command text"
            )
        check_result = check.get("result", result)
        if check_result != EVIDENCE_PASS:
            raise CodexiconError(f"task evidence check {identity} is not successful")
        if identity not in CANONICAL_CHECKS and _command_tokens(command) != declared_tokens:
            raise CodexiconError(
                f"task evidence check {identity} does not match the task verification command"
            )
        normalized_checks.append(
            {
                "identity": identity.strip(),
                "command": check["command"] if structured else command,
                "result": EVIDENCE_PASS,
            }
        )

    review_findings = value.get("review_findings", value.get("review", []))
    if not isinstance(review_findings, list):
        raise CodexiconError("task evidence review_findings must be a list")
    normalized_reviews: list[dict[str, str]] = []
    for finding in review_findings:
        if not isinstance(finding, dict):
            raise CodexiconError("task evidence review findings must be objects")
        finding_id = finding.get("id", finding.get("finding"))
        disposition = finding.get("disposition")
        if not isinstance(finding_id, str) or not finding_id.strip() or disposition not in REVIEW_DISPOSITIONS:
            raise CodexiconError(
                "task evidence review findings require an id and a recognized disposition"
            )
        normalized_reviews.append({"id": finding_id.strip(), "disposition": disposition})

    normalized: dict[str, Any] = {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "task_id": row["id"],
        "acceptance_ids": list(dict.fromkeys(acceptance)),
        "checks": normalized_checks,
        "result": EVIDENCE_PASS,
        "timestamp": timestamp,
        "source_digest": source_digest,
        "contract_digest": contract_digest,
    }
    if normalized_reviews:
        normalized["review_findings"] = normalized_reviews
    return normalized


def _completion_evidence_issues(
    root: Path, rows: Sequence[dict[str, Any]], contract: ContractDetails
) -> tuple[list[str], set[str], set[str]]:
    issues: list[str] = []
    covered: set[str] = set()
    final_checks: set[str] = set()
    for row in rows:
        if row["state"] != "DONE":
            continue
        try:
            evidence = validate_task_evidence(root, row, row["evidence"], contract=contract)
            declared_tokens = _command_tokens(_declared_command_identity(str(row["verification"])))
            if not any(
                check["identity"] not in CANONICAL_CHECKS
                and _command_tokens(_command_identity(check["command"])[0]) == declared_tokens
                for check in evidence["checks"]
            ):
                raise CodexiconError(
                    f"task evidence for {row['id']} requires a successful check matching its declared verification"
                )
        except CodexiconError as exc:
            issues.append(str(exc))
            continue
        covered.update(evidence["acceptance_ids"])
        final_checks.update(
            check["identity"] for check in evidence["checks"] if check["identity"] in CANONICAL_CHECKS
        )
    issues.extend(
        f"missing acceptance evidence: {identifier}"
        for identifier in sorted(contract.acceptance - covered)
    )
    issues.extend(
        f"missing final configured check evidence: {name}"
        for name in CANONICAL_CHECKS
        if name not in final_checks
    )
    return issues, covered, final_checks


def _task_evidence_for_done(
    root: Path, row: dict[str, Any], raw: Any, contract: ContractDetails
) -> str:
    """Validate a DONE receipt and return its stable JSON representation."""

    normalized = validate_task_evidence(root, row, raw, contract=contract)
    declared_tokens = _command_tokens(_declared_command_identity(str(row["verification"])))
    if not any(
        check["identity"] not in CANONICAL_CHECKS
        and _command_tokens(_command_identity(check["command"])[0]) == declared_tokens
        for check in normalized["checks"]
    ):
        raise CodexiconError(
            f"task evidence for {row['id']} requires a successful check matching its declared verification"
        )
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def _fence_marker(line: str) -> str | None:
    match = re.match(r"^\s*(`{3,}|~{3,})", line)
    return match.group(1)[0] if match else None


def _outside_fence_lines(
    lines: Sequence[str], *, label: str = "TASKS.md"
) -> list[tuple[int, str]]:
    outside: list[tuple[int, str]] = []
    fence: str | None = None
    fence_line = 0
    for line_number, line in enumerate(lines, start=1):
        marker = _fence_marker(line)
        if marker:
            if fence is None:
                fence = marker
                fence_line = line_number
            elif marker == fence:
                fence = None
            continue
        if fence is None:
            outside.append((line_number, line))
    if fence is not None:
        raise CodexiconError(f"{label} line {fence_line}: unterminated fenced example")
    return outside


def _line_error(line_number: int, message: str, *, label: str = "TASKS.md") -> CodexiconError:
    return CodexiconError(f"{label} line {line_number}: {message}")


def _table_cells(
    line_number: int, line: str, *, kind: str, expected_columns: int
) -> list[str]:
    stripped = line.strip()
    if r"\|" in stripped:
        raise _line_error(line_number, f"unsupported escaped pipe in {kind}")
    if not stripped.startswith("|") or not stripped.endswith("|"):
        raise _line_error(
            line_number,
            f"malformed {kind}; expected a leading and trailing pipe",
        )
    cells = [cell.strip() for cell in stripped[1:-1].split("|")]
    if len(cells) != expected_columns:
        detail = "extra columns or an unescaped pipe" if len(cells) > expected_columns else "missing columns"
        raise _line_error(
            line_number,
            f"malformed {kind}; expected {expected_columns} columns, found {len(cells)} ({detail})",
        )
    return cells


def _looks_like_task_row(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:].lstrip()
    return stripped.startswith("T-")


def _declared_column_count(line: str) -> int:
    stripped = line.strip()
    if stripped.startswith("|") and stripped.endswith("|"):
        return len(stripped[1:-1].split("|"))
    return len(TASK_HEADERS)


def _parse_task_row(
    line_number: int,
    line: str,
    requirements: set[str],
    interfaces: set[str],
    *,
    extended: bool = False,
) -> dict[str, Any]:
    columns = len(TASK_EXTENDED_HEADERS) if extended else len(TASK_HEADERS)
    cells = _table_cells(line_number, line, kind="task row", expected_columns=columns)
    task_id, state, requirement, interface, scope, verification = cells[:6]
    if not re.fullmatch(r"T-\d+", task_id):
        raise _line_error(line_number, f"invalid task ID: {task_id or '<empty>'}")
    if state not in TASK_STATES:
        raise _line_error(line_number, f"unsupported task state for {task_id}: {state or '<empty>'}")

    requirement_refs = re.findall(r"\bR-\d+\b", requirement)
    if len(requirement_refs) > 1:
        raise _line_error(
            line_number,
            f"{task_id} has multiple requirement references; six-column migration rows support one",
        )
    if not re.fullmatch(r"R-\d+", requirement):
        raise _line_error(
            line_number,
            f"{task_id} requires exactly one requirement reference (R-*)",
        )
    if requirement not in requirements:
        raise _line_error(
            line_number,
            f"{task_id} references missing requirement: {requirement}",
        )

    interface_refs = re.findall(r"\bI-\d+\b", interface)
    if len(interface_refs) > 1:
        raise _line_error(
            line_number,
            f"{task_id} has multiple interface references; six-column migration rows support one",
        )
    if interface != "None" and not re.fullmatch(r"I-\d+", interface):
        raise _line_error(
            line_number,
            f"{task_id} requires one interface reference (I-*) or None",
        )
    if interface != "None" and interface not in interfaces:
        raise _line_error(
            line_number,
            f"{task_id} references missing interface: {interface}",
        )
    if not scope or scope == "-" or not verification or verification == "-":
        raise _line_error(line_number, f"{task_id} requires scope and verification")
    dependencies: list[str] = []
    blocker = ""
    evidence = ""
    if extended:
        dependencies = _parse_task_dependencies(line_number, task_id, cells[6])
        blocker = "" if cells[7] in {"", "-", "None"} else cells[7]
        evidence = "" if cells[8] in {"", "-", "None"} else cells[8]
        if state == "BLOCKED" and not blocker:
            raise _line_error(line_number, f"{task_id} BLOCKED rows require a blocker reason")
    return {
        "id": task_id,
        "state": state,
        "requirement": requirement,
        "interface": interface,
        "scope": scope,
        "verification": verification,
        "dependencies": dependencies,
        "blocker": blocker,
        "evidence": evidence,
        "_line_number": line_number,
        "_extended": extended,
    }


def _parse_task_dependencies(line_number: int, task_id: str, raw: str) -> list[str]:
    if raw.strip() in {"", "-", "None"}:
        return []
    dependencies = [value.strip() for value in raw.split(",")]
    if any(not re.fullmatch(r"T-\d+", dependency) for dependency in dependencies):
        raise _line_error(
            line_number,
            f"{task_id} dependencies must be comma-separated T-* IDs or None",
        )
    if len(set(dependencies)) != len(dependencies):
        raise _line_error(line_number, f"{task_id} has duplicate dependency references")
    return dependencies


def _is_placeholder_definition(definition: str) -> bool:
    return not definition.strip() or bool(PLACEHOLDER_RE.fullmatch(definition.strip()))


def _contract_sections(
    outside: Sequence[tuple[int, str]],
) -> tuple[dict[str, tuple[int, list[tuple[int, str]]]], list[tuple[int, str]]]:
    sections: dict[str, tuple[int, list[tuple[int, str]]]] = {}
    current_name: str | None = None
    current_body: list[tuple[int, str]] = []
    headings: list[tuple[int, str]] = []

    def finish() -> None:
        if current_name is not None:
            sections[current_name] = (sections[current_name][0], current_body.copy())

    for line_number, line in outside:
        match = re.match(r"^\s*##\s+([^#].*?)\s*#*\s*$", line)
        if match:
            finish()
            heading = match.group(1).strip()
            headings.append((line_number, heading))
            current_name = heading
            if heading in sections:
                raise _line_error(line_number, f"duplicate SPEC.md section: {heading}")
            sections[heading] = (line_number, [])
            current_body = sections[heading][1]
            continue
        if current_name is not None:
            current_body.append((line_number, line))
    finish()
    return sections, headings


def _validate_amendments(
    section: tuple[int, list[tuple[int, str]]] | None,
) -> str:
    if section is None:
        return "0"
    _, body = section
    entries = [(line_number, line.strip()) for line_number, line in body if line.strip()]
    if not entries:
        raise CodexiconError("SPEC.md Amendments section must not be empty")
    if any(line.casefold() in {"- none.", "- none"} for _, line in entries):
        if len(entries) != 1:
            raise CodexiconError("SPEC.md Amendments: None cannot be combined with amendments")
        return "0"
    dates: list[tuple[int, str]] = []
    for line_number, line in entries:
        match = AMENDMENT_DATE_RE.match(line)
        if not match:
            raise _line_error(
                line_number,
                "amendments must be dated `- **YYYY-MM-DD:** description` entries",
                label="SPEC.md",
            )
        dates.append((line_number, match.group(1)))
    date_values = [date for _, date in dates]
    if date_values != sorted(date_values):
        raise CodexiconError("SPEC.md Amendments are append-only and must be chronological")
    return date_values[-1]


def read_contract_details(root: Path) -> ContractDetails:
    path = checked_path(root, "SPEC.md")
    if not path.is_file():
        raise CodexiconError("SPEC.md is missing; run $discover before building")
    try:
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise CodexiconError(f"SPEC.md is unreadable: {exc}") from exc
    outside = _outside_fence_lines(lines, label="SPEC.md")
    sections, _ = _contract_sections(outside)
    missing_sections = [section for section in REQUIRED_SPEC_SECTIONS if section not in sections]
    if missing_sections:
        raise CodexiconError(
            f"SPEC.md is missing required section(s): {', '.join(missing_sections)}"
        )

    statuses = [
        (line_number, match.group(1).strip())
        for line_number, line in outside
        if (match := SPEC_STATUS_RE.match(line))
    ]
    if len(statuses) != 1 or statuses[0][1] != "ACTIVE":
        rendered = ", ".join(value or "<empty>" for _, value in statuses) or "none"
        raise CodexiconError(
            "SPEC.md must declare exactly one unambiguous **Status:** ACTIVE "
            f"(found: {rendered})"
        )

    revisions = [
        (line_number, match.group(1).strip())
        for line_number, line in outside
        if (match := SPEC_REVISION_RE.match(line))
    ]
    if len(revisions) > 1:
        raise CodexiconError("SPEC.md must declare at most one **Revision:**")
    amendment_revision = _validate_amendments(sections.get("Amendments"))
    revision = revisions[0][1] if revisions else amendment_revision
    if _is_placeholder_definition(revision) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", revision):
        raise CodexiconError("SPEC.md has an invalid or placeholder revision")

    outcome_line, outcome_body = sections["Outcome"]
    outcome = " ".join(line.strip() for _, line in outcome_body if line.strip())
    if _is_placeholder_definition(outcome):
        raise _line_error(
            outcome_line,
            "Outcome must contain a non-placeholder definition",
            label="SPEC.md",
        )

    found: dict[str, set[str]] = {section: set() for section in SPEC_SECTIONS}
    definitions: dict[str, tuple[str, str, int]] = {}
    for section, pattern in SPEC_SECTIONS.items():
        _, body = sections[section]
        for line_number, line in body:
            match = pattern.match(line)
            if not match:
                if CONTRACT_REFERENCE_RE.search(line) and line.lstrip().startswith("-"):
                    raise _line_error(line_number, f"malformed {section} entry", label="SPEC.md")
                continue
            identifier, definition = match.groups()
            if identifier in definitions:
                prior_section, _, prior_line = definitions[identifier]
                raise _line_error(
                    line_number,
                    f"duplicate SPEC.md ID: {identifier} (first declared in {prior_section} on line {prior_line})",
                    label="SPEC.md",
                )
            if _is_placeholder_definition(definition):
                raise _line_error(
                    line_number,
                    f"{identifier} has a missing or placeholder definition",
                    label="SPEC.md",
                )
            found[section].add(identifier)
            definitions[identifier] = (section, definition, line_number)

    missing_entries = [section for section, values in found.items() if not values]
    if missing_entries:
        raise CodexiconError(f"SPEC.md has no entries in: {', '.join(missing_entries)}")

    known_ids = set(definitions)
    for identifier, (section, definition, line_number) in definitions.items():
        references = set(CONTRACT_REFERENCE_RE.findall(definition)) - {identifier}
        unknown = sorted(references - known_ids)
        if unknown:
            raise _line_error(
                line_number,
                f"{identifier} references unknown contract ID(s): {', '.join(unknown)}",
                label="SPEC.md",
            )

    # Hash the actual Markdown contract, normalized only for line endings and
    # excluding fenced examples so examples cannot silently change the contract.
    canonical = "\n".join(line for _, line in outside)
    digest = sha256_bytes(canonical.encode("utf-8"))
    return ContractDetails(
        text=text,
        revision=revision,
        digest=digest,
        requirements=found["Requirements"],
        interfaces=found["Interfaces"],
        acceptance=found["Acceptance"],
        anti_goals=found["Anti-goals"],
    )


def read_contract(root: Path) -> tuple[str, set[str], set[str], set[str], set[str]]:
    """Return the legacy contract tuple; use read_contract_details for identity."""

    contract = read_contract_details(root)
    return (
        contract.text,
        contract.requirements,
        contract.interfaces,
        contract.acceptance,
        contract.anti_goals,
    )


def contract_identity(root: Path) -> dict[str, str]:
    contract = read_contract_details(root.resolve())
    return {"revision": contract.revision, "digest": contract.digest, "identity": contract.identity}


def contract_check(root: Path) -> int:
    contract = read_contract_details(root.resolve())
    print(
        "[codexicon] SPEC.md valid: "
        f"{len(contract.requirements)} requirement(s), {len(contract.interfaces)} interface(s), "
        f"{len(contract.acceptance)} acceptance condition(s), {len(contract.anti_goals)} anti-goal(s); "
        f"revision={contract.revision}, digest={contract.identity}."
    )
    return 0


def _validate_task_contract_binding(
    outside: Sequence[tuple[int, str]], contract: ContractDetails
) -> None:
    declarations: dict[str, list[tuple[int, str]]] = {"revision": [], "digest": []}
    for line_number, line in outside:
        revision_match = re.match(r"^\s*\*\*Contract revision:\*\*\s*(.*?)\s*$", line)
        digest_match = re.match(r"^\s*\*\*Contract digest:\*\*\s*(.*?)\s*$", line)
        if revision_match:
            declarations["revision"].append((line_number, revision_match.group(1).strip()))
        if digest_match:
            declarations["digest"].append((line_number, digest_match.group(1).strip()))
    if not any(declarations.values()):
        return
    if any(len(values) != 1 for values in declarations.values()):
        raise CodexiconError("TASKS.md contract binding requires exactly one revision and digest")
    expected_revision = declarations["revision"][0][1]
    expected_digest = declarations["digest"][0][1].removeprefix("sha256:")
    if not re.fullmatch(r"[a-f0-9]{64}", expected_digest):
        raise CodexiconError("TASKS.md contract binding has an invalid digest")
    if expected_revision != contract.revision or expected_digest != contract.digest:
        raise CodexiconError(
            "TASKS.md contract drift: declared revision/digest does not match SPEC.md; "
            "reconcile the task baseline after an authorized append-only amendment"
        )


def task_rows(root: Path) -> tuple[Path, list[dict[str, Any]], set[str], set[str]]:
    root = root.resolve()
    contract = read_contract_details(root)
    requirements, interfaces = contract.requirements, contract.interfaces
    path = checked_path(root, "TASKS.md")
    if not path.is_file():
        raise CodexiconError("TASKS.md is missing; create a task register for multi-task work")
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise CodexiconError(f"TASKS.md is unreadable: {exc}") from exc

    outside = _outside_fence_lines(lines)
    _validate_task_contract_binding(outside, contract)
    header_indexes: list[int] = []
    extended = False
    for line_number, line in outside:
        if not re.match(r"^\s*\|?\s*ID\b", line, re.IGNORECASE):
            continue
        column_count = _declared_column_count(line)
        cells = _table_cells(
            line_number,
            line,
            kind="task table header",
            expected_columns=column_count if column_count in {6, 9} else 6,
        )
        normalized_header = tuple(cell.casefold() for cell in cells)
        if normalized_header == TASK_HEADERS:
            header_indexes.append(line_number - 1)
            extended = False
        elif normalized_header == tuple(value.casefold() for value in TASK_EXTENDED_HEADERS):
            header_indexes.append(line_number - 1)
            extended = True
        elif cells and cells[0].casefold() == "id" and len(cells) > 1 and cells[1].casefold() == "state":
            raise _line_error(
                line_number,
                "malformed task table header; expected the six-column migration format or "
                "the nine-column format with Dependencies, Blocker, Evidence",
            )
    if not header_indexes:
        for line_number, line in outside:
            if _looks_like_task_row(line):
                _parse_task_row(line_number, line, requirements, interfaces)
        raise CodexiconError("TASKS.md has no declared six-column task table")
    if len(header_indexes) > 1:
        raise _line_error(header_indexes[1] + 1, "duplicate task table declaration")

    header_index = header_indexes[0]
    separator_index = header_index + 1
    if separator_index >= len(lines):
        raise _line_error(header_index + 1, "task table is missing its separator row")
    separator_cells = _table_cells(
        separator_index + 1,
        lines[separator_index],
        kind="task table separator",
        expected_columns=9 if extended else 6,
    )
    if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator_cells):
        raise _line_error(
            separator_index + 1,
            f"malformed task table separator; each of the {'9' if extended else '6'} columns needs a markdown separator",
        )

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_lines: dict[str, int] = {}
    parsed_line_indexes: set[int] = {header_index, separator_index}
    table_line_index = separator_index + 1
    while table_line_index < len(lines):
        line = lines[table_line_index]
        if not line.strip() or _fence_marker(line):
            break
        if not line.strip().startswith("|") and not _looks_like_task_row(line):
            break
        line_number = table_line_index + 1
        row = _parse_task_row(
            line_number, line, requirements, interfaces, extended=extended
        )
        task_id = row["id"]
        if task_id in seen:
            raise _line_error(
                line_number,
                f"duplicate task ID: {task_id} (first declared on line {seen_lines[task_id]})",
            )
        seen.add(task_id)
        seen_lines[task_id] = line_number
        rows.append(row)
        parsed_line_indexes.add(table_line_index)
        table_line_index += 1

    for line_number, line in outside:
        line_index = line_number - 1
        if line_index in parsed_line_indexes or not _looks_like_task_row(line):
            continue
        row = _parse_task_row(
            line_number, line, requirements, interfaces, extended=extended
        )
        task_id = row["id"]
        if task_id in seen:
            raise _line_error(
                line_number,
                f"duplicate task ID: {task_id} (first declared on line {seen_lines[task_id]})",
            )
        raise _line_error(line_number, "task-like row is outside the declared task table")

    if not rows:
        raise CodexiconError("TASKS.md contains no task rows")
    _validate_task_graph(rows)
    return path, rows, requirements, interfaces


def _validate_task_graph(rows: Sequence[dict[str, Any]]) -> None:
    by_id = {row["id"]: row for row in rows}
    for row in rows:
        unknown = [dependency for dependency in row["dependencies"] if dependency not in by_id]
        if unknown:
            raise _line_error(
                row["_line_number"],
                f"{row['id']} references unknown dependency: {', '.join(unknown)}",
            )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str, trail: list[str]) -> None:
        if task_id in visiting:
            cycle = " -> ".join([*trail, task_id])
            raise CodexiconError(f"task dependency cycle detected: {cycle}")
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in by_id[task_id]["dependencies"]:
            visit(dependency, [*trail, task_id])
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in by_id:
        visit(task_id, [])


def _dependency_blockers(
    task: dict[str, Any], by_id: dict[str, dict[str, Any]], memo: dict[str, list[str]]
) -> list[str]:
    if task["id"] in memo:
        return memo[task["id"]]
    blockers: list[str] = []
    for dependency_id in task["dependencies"]:
        dependency = by_id[dependency_id]
        if dependency["state"] == "DONE":
            continue
        if dependency["state"] == "BLOCKED":
            detail = dependency["blocker"] or "blocked"
            blockers.append(f"{dependency_id}: {detail}")
        elif dependency["state"] == "TODO":
            blockers.extend(_dependency_blockers(dependency, by_id, memo) or [f"{dependency_id}: not complete"])
        else:
            blockers.append(f"{dependency_id}: ACTIVE")
    memo[task["id"]] = list(dict.fromkeys(blockers))
    return memo[task["id"]]


def select_runnable_task(rows: Sequence[dict[str, Any]]) -> QueueSelection:
    """Select the resumable or first runnable task from an already validated register."""

    active = [row for row in rows if row["state"] == "ACTIVE"]
    if len(active) > 1:
        return QueueSelection(
            QUEUE_INVALID,
            reason="multiple ACTIVE tasks violate the single implementation owner rule",
        )
    if active:
        return QueueSelection(QUEUE_RESUME_ACTIVE, active[0])

    by_id = {row["id"]: row for row in rows}
    memo: dict[str, list[str]] = {}
    dependency_blockers = {
        row["id"]: _dependency_blockers(row, by_id, memo)
        for row in rows
        if row["state"] == "TODO"
    }
    for row in rows:
        if row["state"] == "TODO" and not dependency_blockers[row["id"]]:
            return QueueSelection(QUEUE_READY, row, blockers=dependency_blockers)

    if all(row["state"] == "DONE" for row in rows):
        return QueueSelection(QUEUE_COMPLETE, blockers=dependency_blockers)
    blocked = {
        row["id"]: ([row["blocker"]] if row["state"] == "BLOCKED" and row["blocker"] else dependency_blockers.get(row["id"], []))
        for row in rows
        if row["state"] in {"TODO", "BLOCKED"}
    }
    return QueueSelection(
        QUEUE_BLOCKED,
        reason="no runnable task; all remaining work is blocked",
        blockers=blocked,
    )


@contextlib.contextmanager
def _task_register_lock(path: Path):
    """Serialize manager writers without depending on Git or a service."""

    lock_path = path.with_name(f".{path.name}.codexicon-lock")
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise CodexiconError("TASKS.md update conflict: another writer owns the register lock") from exc
    try:
        os.write(fd, f"pid={os.getpid()}\n".encode("ascii"))
        yield
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _public_task(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_")}


def _queue_payload(selection: QueueSelection) -> dict[str, Any]:
    return {
        "outcome": selection.outcome,
        "task": _public_task(selection.task) if selection.task else None,
        "reason": selection.reason,
        "blockers": selection.blockers or {},
    }


def tasks_next(root: Path, *, json_output: bool = False) -> int:
    root = root.resolve()
    _, rows, _, _ = task_rows(root)
    contract = read_contract_details(root)
    selection = select_runnable_task(rows)
    if selection.outcome == QUEUE_INVALID:
        raise CodexiconError(selection.reason)
    completion_issues: list[str] = []
    if selection.outcome == QUEUE_COMPLETE:
        completion_issues, _, _ = _completion_evidence_issues(root, rows, contract)
        if completion_issues:
            selection = QueueSelection(
                QUEUE_BLOCKED,
                reason="completion evidence is incomplete or stale",
                blockers={"completion": completion_issues},
            )
    if json_output:
        print(json.dumps(_queue_payload(selection), sort_keys=True))
    elif selection.task:
        row = selection.task
        print(
            f"[{selection.outcome}] {row['id']} | {row['requirement']} | {row['interface']} | "
            f"{row['scope']} | {row['verification']}"
        )
    elif selection.outcome == QUEUE_BLOCKED:
        print(f"[{selection.outcome}] {selection.reason}")
    else:
        print(f"[{selection.outcome}] TASKS.md has no remaining work.")
    return QUEUE_EXIT_CODES[selection.outcome]


def _replace_task_row(
    line: str,
    row: dict[str, Any],
    *,
    state: str,
    reason: str | None,
    evidence: str | None,
) -> str:
    newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    content = line.rstrip("\r\n")
    cells = _table_cells(
        row["_line_number"],
        content,
        kind="task row",
        expected_columns=9 if row["_extended"] else 6,
    )
    cells[1] = state
    if row["_extended"]:
        cells[7] = reason if state == "BLOCKED" and reason else "None"
        if evidence is not None:
            cells[8] = evidence if evidence else "None"
    leading = re.match(r"^\s*", content).group(0)
    return leading + "| " + " | ".join(cells) + " |" + newline


def _write_task_register_if_unchanged(path: Path, original: bytes, output: bytes) -> None:
    try:
        current = path.read_bytes()
    except OSError as exc:
        raise CodexiconError(f"TASKS.md became unreadable during update: {exc}") from exc
    if sha256_bytes(current) != sha256_bytes(original):
        raise CodexiconError("TASKS.md update conflict: register changed concurrently; no edits applied")
    atomic_write_bytes(path, output, mode=0o644)


def _tasks_transition(
    root: Path,
    task_id: str,
    state: str,
    *,
    reason: str | None = None,
    evidence: str | None = None,
    allow_reopen: bool = False,
    expected_state: str | None = None,
) -> int:
    root = root.resolve()
    if not re.fullmatch(r"T-\d+", task_id):
        raise CodexiconError("task ID must look like T-001")
    if state not in TASK_STATES:
        raise CodexiconError("unsupported task state")
    register_path = checked_path(root, "TASKS.md")
    with _task_register_lock(register_path):
        path, rows, _, _ = task_rows(root)
        contract = read_contract_details(root)
        by_id = {row["id"]: row for row in rows}
        if task_id not in by_id:
            raise CodexiconError(f"unknown task ID: {task_id}")
        row = by_id[task_id]
        current = row["state"]
        if expected_state is not None and current != expected_state:
            raise CodexiconError(
                f"{expected_state.lower()} task required for controlled reopen: {task_id}"
            )
        if current == state and state == "ACTIVE":
            print(f"[codexicon] {task_id} is already ACTIVE; resume it")
            return 0
        legal = {
            "TODO": {"ACTIVE", "BLOCKED"},
            "ACTIVE": {"DONE", "BLOCKED"},
            "BLOCKED": {"TODO"} if allow_reopen else set(),
            "DONE": {"TODO"} if allow_reopen else set(),
        }
        if state not in legal[current]:
            raise CodexiconError(f"illegal task transition: {current} -> {state} for {task_id}")
        if state == "ACTIVE":
            active = [item["id"] for item in rows if item["state"] == "ACTIVE" and item["id"] != task_id]
            if active:
                raise CodexiconError(
                    f"task start conflict: {active[0]} is ACTIVE and owns the implementation slot"
                )
            blockers = _dependency_blockers(row, by_id, {})
            if blockers:
                raise CodexiconError(f"{task_id} is blocked by dependencies: {'; '.join(blockers)}")
        if state == "BLOCKED" and not reason:
            raise CodexiconError("tasks-blocked requires a persistent --reason")
        if state == "BLOCKED" and not row["_extended"]:
            raise CodexiconError("blocker reasons require the nine-column register; run tasks-migrate first")
        if allow_reopen and current == "DONE" and not reason:
            raise CodexiconError("reopening a DONE task requires a --reason")
        normalized_evidence = None
        if state == "DONE":
            if not row["_extended"]:
                raise CodexiconError("completion evidence requires the nine-column register; run tasks-migrate first")
            normalized_evidence = _task_evidence_for_done(root, row, evidence, contract)

        try:
            original = path.read_bytes()
            lines = original.decode("utf-8").splitlines(keepends=True)
        except (OSError, UnicodeDecodeError) as exc:
            raise CodexiconError(f"TASKS.md is unreadable: {exc}") from exc
        output: list[str] = []
        replaced = False
        for index, line in enumerate(lines, start=1):
            if index == row["_line_number"]:
                output.append(
                    _replace_task_row(
                        line,
                        row,
                        state=state,
                        reason=reason,
                        evidence=normalized_evidence if normalized_evidence is not None else evidence,
                    )
                )
                replaced = True
            else:
                output.append(line)
        if not replaced:
            raise CodexiconError(f"unable to update task row: {task_id}")
        _write_task_register_if_unchanged(
            path, original, "".join(output).encode("utf-8")
        )
    print(f"[codexicon] {task_id} -> {state}")
    return 0


def tasks_set_state(
    root: Path,
    task_id: str,
    state: str,
    *,
    reason: str | None = None,
    evidence: str | None = None,
) -> int:
    return _tasks_transition(root, task_id, state, reason=reason, evidence=evidence)


def tasks_reopen(root: Path, task_id: str, *, reason: str, expected: str) -> int:
    return _tasks_transition(
        root,
        task_id,
        "TODO",
        reason=reason,
        allow_reopen=True,
        expected_state=expected,
    )


def migrate_task_register(root: Path) -> int:
    """Upgrade a legacy six-column register without changing task meaning."""

    root = root.resolve()
    path = checked_path(root, "TASKS.md")
    with _task_register_lock(path):
        path, rows, _, _ = task_rows(root)
        if all(row["_extended"] for row in rows):
            print("[codexicon] TASKS.md already uses the nine-column register format")
            return 0
        try:
            original = path.read_bytes()
            lines = original.decode("utf-8").splitlines(keepends=True)
        except (OSError, UnicodeDecodeError) as exc:
            raise CodexiconError(f"TASKS.md is unreadable: {exc}") from exc
        header_index = None
        outside = dict(_outside_fence_lines(lines))
        for line_number, content in outside.items():
            if not re.match(r"^\s*\|?\s*ID\b", content, re.IGNORECASE):
                continue
            column_count = _declared_column_count(content)
            if column_count != 6:
                continue
            cells = _table_cells(
                line_number, content, kind="task table header", expected_columns=6
            )
            if tuple(cell.casefold() for cell in cells) == TASK_HEADERS:
                header_index = line_number - 1
                break
        if header_index is None:
            raise CodexiconError("unable to locate the legacy six-column task table")
        newline = "\r\n" if any(line.endswith("\r\n") for line in lines) else "\n"
        output = list(lines)
        output[header_index] = "| " + " | ".join(TASK_EXTENDED_HEADERS) + " |" + newline
        output[header_index + 1] = "| " + " | ".join("---" for _ in TASK_EXTENDED_HEADERS) + " |" + newline
        for row in rows:
            old = lines[row["_line_number"] - 1]
            cells = _table_cells(row["_line_number"], old.rstrip("\r\n"), kind="task row", expected_columns=6)
            extended = cells + ["None", "None", "None"]
            output[row["_line_number"] - 1] = "| " + " | ".join(extended) + " |" + ("\r\n" if old.endswith("\r\n") else "\n" if old.endswith("\n") else "")
        identity = contract_identity(root)
        metadata = (
            f"**Register format:** 2{newline}"
            f"**Contract revision:** {identity['revision']}{newline}"
            f"**Contract digest:** {identity['identity']}{newline}{newline}"
        )
        if "**Register format:**" not in "".join(output):
            output.insert(0, metadata)
        _write_task_register_if_unchanged(path, original, "".join(output).encode("utf-8"))
    print("[codexicon] TASKS.md migrated to the nine-column register format")
    return 0


def doctor(root: Path, *, mode: str = BUILD_MODE) -> int:
    if mode not in VERIFICATION_MODES:
        raise CodexiconError(f"unsupported verification mode: {mode}")
    root = root.resolve()
    diagnostics: list[tuple[str, str]] = []
    parse_config(root, diagnostics)
    parse_hooks(root, diagnostics)
    if (root / "SPEC.md").exists():
        try:
            read_contract(root)
        except CodexiconError as exc:
            diagnostics.append(("ERROR", f"invalid SPEC.md: {exc}"))
    if (root / "TASKS.md").exists():
        try:
            task_rows(root)
        except CodexiconError as exc:
            diagnostics.append(("ERROR", f"invalid TASKS.md: {exc}"))
    for name in CANONICAL_CHECKS:
        for suffix in ("sh", "ps1"):
            relative = f"scripts/{name}.{suffix}"
            try:
                command_path = checked_path(root, relative)
            except CodexiconError as exc:
                diagnostics.append(("ERROR", str(exc)))
                continue
            if not command_path.is_file():
                diagnostics.append(("ERROR", f"missing canonical command: {relative}"))
    for name in ("implementer", "reviewer", "researcher", "github-researcher"):
        path = root / ".codex" / "agents" / f"{name}.toml"
        if not path.is_file():
            diagnostics.append(("WARN", f"missing project agent profile: {path.relative_to(root).as_posix()}"))
            continue
        try:
            content = path.read_text(encoding="utf-8")
            value = tomllib.loads(content) if tomllib is not None else parse_toml_subset(content)
        except (OSError, tomllib.TOMLDecodeError if tomllib is not None else ValueError) as exc:
            diagnostics.append(("ERROR", f"malformed project agent {name}: {exc}"))
            continue
        for field in ("name", "description", "developer_instructions"):
            if not value.get(field):
                diagnostics.append(("ERROR", f"project agent {name} lacks {field}"))
    lock_path = root / LOCK_NAME
    if lock_path.exists():
        try:
            lock = load_lock(root, required=True)
        except CodexiconError as exc:
            diagnostics.append(("ERROR", str(exc)))
        else:
            assert lock is not None
            for relative, item in lock["files"].items():
                try:
                    state, digest = file_state(root, relative)
                except CodexiconError as exc:
                    diagnostics.append(("ERROR", str(exc)))
                    continue
                if state == "missing":
                    diagnostics.append(("ERROR", f"installed harness file is missing: {relative}"))
                elif digest != item["sha256"]:
                    diagnostics.append(("INFO", f"locally modified harness file: {relative}"))
            for relative in lock["unresolved"]:
                diagnostics.append(("WARN", f"unresolved adoption/update path: {relative}"))
    elif (root / MANIFEST_NAME).exists():
        try:
            load_manifest(root)
        except CodexiconError as exc:
            diagnostics.append(("ERROR", str(exc)))
        else:
            diagnostics.append(("INFO", "source template mode; no installation lock is expected"))
    else:
        diagnostics.append(("WARN", "no Codexicon source manifest or installation lock found"))

    try:
        executable_paths = expected_executable_paths(root)
    except CodexiconError:
        executable_paths = []
    for relative in executable_paths:
        executable_path = checked_path(root, relative)
        if executable_path.is_file() and os.name != "nt" and not os.access(
            executable_path, os.X_OK
        ):
            diagnostics.append(("ERROR", f"executable path lacks filesystem execute mode: {relative}"))
        if mode == SHIP_MODE:
            index_mode = git_index_mode(root, relative)
            if index_mode is None:
                diagnostics.append(
                    (
                        "WARN",
                        f"executable path is not tracked yet; stage it, then run sync-git-modes: {relative}",
                    )
                )
            elif index_mode != "100755":
                diagnostics.append(
                    ("ERROR", f"executable path has Git index mode {index_mode}, expected 100755: {relative}")
                )

    try:
        pending_journal = transaction_path(root)
    except CodexiconError as exc:
        diagnostics.append(("ERROR", str(exc)))
    else:
        if pending_journal.exists():
            try:
                journal = read_json(pending_journal, "Codexicon transaction journal")
                if not isinstance(journal, dict):
                    raise CodexiconError(
                        "transaction journal is malformed; manual recovery is required"
                    )
                validate_transaction_journal(root, journal)
            except CodexiconError as exc:
                diagnostics.append(("ERROR", str(exc)))
            else:
                diagnostics.append(
                    (
                        "ERROR",
                        "an interrupted transaction is pending; run the intended adopt/update "
                        "with --apply to authorize rollback",
                    )
                )

    try:
        sessions = checked_path(root, "agent_docs/sessions")
    except CodexiconError as exc:
        diagnostics.append(("ERROR", str(exc)))
        sessions = None
    if sessions is not None and sessions.is_dir():
        repo_id = repository_identity(root)
        for path in sorted(sessions.glob("*.md")):
            try:
                path = checked_path(root, path.relative_to(root).as_posix())
            except (CodexiconError, ValueError):
                diagnostics.append(("ERROR", "checkpoint candidate uses an unsafe symbolic-link path"))
                continue
            try:
                first_line = path.read_text(encoding="utf-8").splitlines()[0]
            except (OSError, IndexError, UnicodeDecodeError) as exc:
                diagnostics.append(("ERROR", f"unreadable session record {path.name}: {exc}"))
                continue
            if CHECKPOINT_MARKER not in first_line:
                continue
            _, metadata, error = validate_checkpoint(root, path)
            if error or metadata is None:
                diagnostics.append(("ERROR", f"checkpoint {path.name}: {error}"))
                continue
            if metadata["repository_id"] != repo_id:
                diagnostics.append(("WARN", f"checkpoint {path.name} belongs to another repository"))
                continue
            diagnostics.extend(
                ("WARN", f"checkpoint {path.name}: {warning}")
                for warning in checkpoint_identity_warnings(root, metadata)
            )
            for related in metadata["related"]:
                try:
                    related_path = checked_path(root, str(related))
                except CodexiconError:
                    diagnostics.append(("ERROR", f"checkpoint {path.name} has an unsafe related path"))
                    continue
                if not related_path.exists():
                    diagnostics.append(("WARN", f"checkpoint {path.name} references missing {related}"))

    severity_order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    for level, message in sorted(diagnostics, key=lambda item: (severity_order[item[0]], item[1])):
        print(f"{level:5} {message}")
    errors = sum(level == "ERROR" for level, _ in diagnostics)
    warnings = sum(level == "WARN" for level, _ in diagnostics)
    print(f"[codexicon] doctor: {errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


def verify(root: Path, checks: Sequence[str], *, mode: str = BUILD_MODE) -> int:
    if mode not in VERIFICATION_MODES:
        raise CodexiconError(f"unsupported verification mode: {mode}")
    root = root.resolve()
    requested = list(checks) or list(CANONICAL_CHECKS)
    ordered = [name for name in CANONICAL_CHECKS if name in requested]
    if len(ordered) != len(set(requested)):
        raise CodexiconError("verification checks must be lint, test, and/or security")
    for name in ordered:
        if os.name == "nt":
            shell = shutil.which("pwsh") or shutil.which("powershell")
            if not shell:
                raise CodexiconError("PowerShell is required for native Windows verification")
            script = checked_path(root, f"scripts/{name}.ps1")
            command = [shell, "-NoProfile", "-File", str(script)]
        else:
            script = checked_path(root, f"scripts/{name}.sh")
            command = [str(script)]
        if not script.is_file():
            raise CodexiconError(f"canonical verification command is missing: {script}")
        print(
            f"[codexicon] Running {name}: {script.relative_to(root).as_posix()}",
            flush=True,
        )
        environment = None
        if name == "security" and mode == SHIP_MODE:
            environment = os.environ.copy()
            environment["CODEXICON_SECURITY_MODE"] = SHIP_MODE
        try:
            result = subprocess.run(command, cwd=root, check=False, env=environment)
        except OSError as exc:
            print(f"[codexicon] unable to run {name}: {exc}", file=sys.stderr)
            return 126
        if result.returncode != 0:
            print(f"[codexicon] {name} failed with exit code {result.returncode}.", file=sys.stderr)
            return result.returncode
    print("[codexicon] Requested verification passed.")
    return 0


def install_git_hooks(root: Path) -> int:
    root = root.resolve()
    top = git_value(root, "rev-parse", "--show-toplevel")
    if not top or Path(top).resolve() != root:
        raise CodexiconError("run install-git-hooks from the Git repository root")
    for relative in (".githooks/pre-commit", ".githooks/pre-push"):
        path = checked_path(root, relative)
        if not path.is_file():
            raise CodexiconError(f"tracked Git hook is missing: {relative}")
    existing = git_value(root, "config", "--local", "--get", "core.hooksPath")
    if existing and existing.replace("\\", "/").rstrip("/") != ".githooks":
        raise CodexiconError(
            "refusing to replace existing core.hooksPath "
            f"{existing!r}; integrate it deliberately or restore it with "
            f"`git config --local core.hooksPath {existing}`"
        )
    if os.name != "nt":
        for relative in (".githooks/pre-commit", ".githooks/pre-push"):
            path = checked_path(root, relative)
            path.chmod(path.stat().st_mode | 0o111)
    result = subprocess.run(
        ["git", "config", "--local", "core.hooksPath", ".githooks"],
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        raise CodexiconError("Git failed to configure core.hooksPath")
    print("[codexicon] Installed repository pre-commit and pre-push gates.")
    return 0


def expected_executable_paths(root: Path) -> list[str]:
    paths: set[str] = set()
    lock_path = checked_path(root, LOCK_NAME)
    if lock_path.exists():
        lock = load_lock(root, required=True)
        assert lock is not None
        paths.update(
            relative for relative, item in lock["files"].items() if item.get("executable")
        )
    manifest_path = checked_path(root, MANIFEST_NAME)
    if manifest_path.exists():
        manifest = load_manifest(root)
        paths.update(item["path"] for item in manifest["files"] if item.get("executable"))
    return sorted(paths)


def git_index_mode(root: Path, relative: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--stage", "--", relative],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    mode = result.stdout.split(maxsplit=1)[0]
    return mode if re.fullmatch(r"\d{6}", mode) else None


def sync_git_modes(root: Path) -> int:
    root = root.resolve()
    paths = expected_executable_paths(root)
    untracked = [relative for relative in paths if git_index_mode(root, relative) is None]
    if untracked:
        rendered = ", ".join(untracked)
        raise CodexiconError(
            "cannot set executable index modes until these files are staged or tracked: "
            f"{rendered}"
        )
    if not paths:
        print("[codexicon] No manifest-managed executable paths.")
        return 0
    try:
        result = subprocess.run(
            ["git", "update-index", "--chmod=+x", "--", *paths],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise CodexiconError("Git is required to synchronize executable index modes") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or "Git rejected the index mode update"
        raise CodexiconError(detail)
    print(f"[codexicon] Set executable Git index mode on {len(paths)} path(s).")
    return 0


def create_checkpoint(args: argparse.Namespace) -> int:
    root = args.root.resolve()
    slug = args.slug.strip().lower()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise CodexiconError("checkpoint slug must contain lowercase words separated by hyphens")
    related = [normalize_relative(path) for path in args.related]
    for relative in related:
        if not checked_path(root, relative).exists():
            raise CodexiconError(f"related checkpoint path does not exist: {relative}")
    changed = [normalize_relative(path) for path in getattr(args, "changed", [])]
    for relative in changed:
        if not checked_path(root, relative).exists():
            raise CodexiconError(f"changed checkpoint path does not exist: {relative}")
    evidence_paths = sorted(set(related + changed))
    created = utc_now()
    local_identities = checkpoint_local_identities(root, evidence_paths)
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "checkpoint_id": secrets.token_hex(8),
        "created_at": created,
        "repository_id": repository_identity(root),
        "branch": "local-build",
        "head": "none",
        "related": related,
        **local_identities,
        "changed": changed,
    }
    filename = f"{created[:10]}-{slug}.md"
    output = checked_path(root, f"agent_docs/sessions/{filename}")
    if output.exists():
        raise CodexiconError(f"checkpoint already exists: {output.relative_to(root).as_posix()}")
    marker = f"<!-- {CHECKPOINT_MARKER} {json.dumps(metadata, sort_keys=True)} -->"
    lines = [
        marker,
        f"# Checkpoint: {args.title}",
        "",
        f"**Created:** {created}  ",
        f"**Checkpoint ID:** `{metadata['checkpoint_id']}`  ",
        f"**Repository:** `{metadata['repository_id']}`  ",
        "**Build identity:** local filesystem (Git-free)  ",
        f"**Contract / task:** `{metadata['contract_identity']}` / `{metadata['task_identity']}`  ",
        f"**Related:** {', '.join(f'`{item}`' for item in related) if related else 'none'}",
        "",
        "## Current state",
        "",
        args.summary.strip(),
        "",
        "## Changed paths",
        "",
        *([f"- `{path}`" for path in changed] or ["- None supplied; related-path evidence is recorded in the checkpoint header."]),
        "",
        "## Verification",
        "",
        *([f"- {item}" for item in args.verification] or ["- No verification recorded."]),
        "",
        "## Next actions",
        "",
        *[f"{index}. {item}" for index, item in enumerate(args.next, start=1)],
        "",
        "## Blockers and decisions",
        "",
        *([f"- {item}" for item in args.blocker] or ["- None."]),
        *([f"- Decision: {item}" for item in args.decision] or []),
        "",
        "## Resume note",
        "",
        args.resume_note.strip(),
        "",
    ]
    atomic_write_bytes(output, "\n".join(lines).encode("utf-8"), mode=0o644)
    print(output.relative_to(root).as_posix())
    return 0


def resume(root: Path) -> int:
    root = root.resolve()
    candidates = compatible_checkpoints(root)
    if not candidates:
        raise CodexiconError("no compatible Codexicon checkpoint was found")
    _, path, metadata = candidates[0]
    print(f"[codexicon] Resume checkpoint: {path.relative_to(root).as_posix()}")
    for warning in checkpoint_identity_warnings(root, metadata):
        print(f"[codexicon] Warning: {warning}.", file=sys.stderr)
    print(path.read_text(encoding="utf-8"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="read-only adoption compatibility plan")
    inspect_parser.add_argument("target", type=Path)
    inspect_parser.add_argument("--source", type=Path, default=ROOT)

    adopt_parser = subparsers.add_parser("adopt", help="adopt Codexicon into an existing repository")
    adopt_parser.add_argument("target", type=Path)
    adopt_parser.add_argument("--source", type=Path, default=ROOT)
    adopt_parser.add_argument("--apply", action="store_true")

    update_parser = subparsers.add_parser("update", help="apply a future Codexicon source safely")
    update_parser.add_argument("--root", type=Path, default=ROOT)
    update_parser.add_argument("--source", type=Path, required=True)
    update_parser.add_argument("--apply", action="store_true")

    doctor_parser = subparsers.add_parser("doctor", help="diagnose installed or source harness state")
    doctor_parser.add_argument("--root", type=Path, default=ROOT)
    doctor_parser.add_argument("--mode", choices=VERIFICATION_MODES, default=BUILD_MODE)

    verify_parser = subparsers.add_parser("verify", help="run project-defined canonical checks")
    verify_parser.add_argument("checks", nargs="*", choices=CANONICAL_CHECKS)
    verify_parser.add_argument("--root", type=Path, default=ROOT)
    verify_parser.add_argument("--mode", choices=VERIFICATION_MODES, default=BUILD_MODE)

    hooks_parser = subparsers.add_parser("install-git-hooks", help="install tracked Git hooks safely")
    hooks_parser.add_argument("--root", type=Path, default=ROOT)

    modes_parser = subparsers.add_parser(
        "sync-git-modes", help="set manifest-declared executable modes in the Git index"
    )
    modes_parser.add_argument("--root", type=Path, default=ROOT)

    checkpoint_parser = subparsers.add_parser("checkpoint", help="atomically create a durable checkpoint")
    checkpoint_parser.add_argument("--root", type=Path, default=ROOT)
    checkpoint_parser.add_argument("--slug", required=True)
    checkpoint_parser.add_argument("--title", required=True)
    checkpoint_parser.add_argument("--summary", required=True)
    checkpoint_parser.add_argument("--resume-note", required=True)
    checkpoint_parser.add_argument("--next", action="append", required=True)
    checkpoint_parser.add_argument("--related", action="append", default=[])
    checkpoint_parser.add_argument("--changed", action="append", default=[])
    checkpoint_parser.add_argument("--verification", action="append", default=[])
    checkpoint_parser.add_argument("--blocker", action="append", default=[])
    checkpoint_parser.add_argument("--decision", action="append", default=[])

    resume_parser = subparsers.add_parser("resume", help="print the newest compatible checkpoint")
    resume_parser.add_argument("--root", type=Path, default=ROOT)

    contract_parser = subparsers.add_parser("spec-check", help="validate the active root SPEC.md contract")
    contract_parser.add_argument("--root", type=Path, default=ROOT)

    next_parser = subparsers.add_parser(
        "tasks-next", help="select the resumable or next runnable task from TASKS.md"
    )
    next_parser.add_argument("--root", type=Path, default=ROOT)
    next_parser.add_argument("--json", action="store_true", dest="json_output")

    for state in ("start", "done", "blocked"):
        task_parser = subparsers.add_parser(
            f"tasks-{state}", help=f"mark a TASKS.md row {state}"
        )
        task_parser.add_argument("task_id")
        task_parser.add_argument("--root", type=Path, default=ROOT)
        task_parser.add_argument("--reason")
        task_parser.add_argument("--evidence")
    for command, expected in (("tasks-unblock", "BLOCKED"), ("tasks-reopen", "DONE")):
        task_parser = subparsers.add_parser(
            command, help=f"controlled reopen of a {expected.lower()} TASKS.md row"
        )
        task_parser.add_argument("task_id")
        task_parser.add_argument("--reason", required=True)
        task_parser.add_argument("--root", type=Path, default=ROOT)

    migrate_parser = subparsers.add_parser(
        "tasks-migrate", help="upgrade a six-column register to the additive nine-column format"
    )
    migrate_parser.add_argument("--root", type=Path, default=ROOT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            return run_install(args.source, args.target, apply=False, update=False)
        if args.command == "adopt":
            return run_install(args.source, args.target, apply=args.apply, update=False)
        if args.command == "update":
            return run_install(args.source, args.root, apply=args.apply, update=True)
        if args.command == "doctor":
            return doctor(args.root, mode=args.mode)
        if args.command == "verify":
            return verify(args.root, args.checks, mode=args.mode)
        if args.command == "install-git-hooks":
            return install_git_hooks(args.root)
        if args.command == "sync-git-modes":
            return sync_git_modes(args.root)
        if args.command == "checkpoint":
            return create_checkpoint(args)
        if args.command == "resume":
            return resume(args.root)
        if args.command == "spec-check":
            return contract_check(args.root)
        if args.command == "tasks-next":
            return tasks_next(args.root, json_output=args.json_output)
        if args.command == "tasks-start":
            return tasks_set_state(args.root, args.task_id, "ACTIVE")
        if args.command == "tasks-done":
            return tasks_set_state(args.root, args.task_id, "DONE", evidence=args.evidence)
        if args.command == "tasks-blocked":
            return tasks_set_state(args.root, args.task_id, "BLOCKED", reason=args.reason)
        if args.command == "tasks-unblock":
            return tasks_reopen(args.root, args.task_id, reason=args.reason, expected="BLOCKED")
        if args.command == "tasks-reopen":
            return tasks_reopen(args.root, args.task_id, reason=args.reason, expected="DONE")
        if args.command == "tasks-migrate":
            return migrate_task_register(args.root)
        parser.error(f"unsupported command: {args.command}")
    except CodexiconError as exc:
        if getattr(args, "command", None) == "tasks-next" and getattr(args, "json_output", False):
            print(json.dumps({"outcome": QUEUE_INVALID, "task": None, "reason": str(exc), "blockers": {}}, sort_keys=True))
        print(f"[codexicon] {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
