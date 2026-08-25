#!/usr/bin/env python3
"""Inspect, adopt, diagnose, verify, checkpoint, and update Codexicon safely."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
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
            elif executable and os.name != "nt" and not os.access(
                checked_path(target_root, relative), os.X_OK
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
        or journal.get("phase") not in {"applying", "committed"}
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
    for item in actions:
        action = item["action"]
        if action not in {"create", "update", "remove"}:
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
            "target_mode": (target.stat().st_mode & 0o777) if target.is_file() else None,
            "before_sha256": before_sha256,
            "after_sha256": None,
        }
        if action != "remove":
            source = checked_path(source_root, relative)
            operation["after_sha256"] = sha256_file(source)
            operation["executable"] = bool(item.get("executable", False))
        operations.append(operation)
    lock_content = (json.dumps(next_lock, indent=2, sort_keys=True) + "\n").encode("utf-8")
    lock_target = checked_path(target_root, LOCK_NAME)
    lock_backup = None
    if lock_target.is_file():
        lock_backup = f"{backup_root_relative}/{operation_backup_name(len(operations), LOCK_NAME)}"
    operations.append(
        {
            "action": "write-lock",
            "path": LOCK_NAME,
            "backup": lock_backup,
            "target_mode": (lock_target.stat().st_mode & 0o777) if lock_target.is_file() else None,
            "before_sha256": sha256_file(lock_target) if lock_target.is_file() else None,
            "after_sha256": sha256_bytes(lock_content),
            "content": lock_content.decode("utf-8"),
        }
    )
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
    journal_path = transaction_path(target_root)
    atomic_write_json(journal_path, journal)
    try:
        for index, operation in enumerate(operations):
            target = checked_path(target_root, str(operation["path"]))
            if current_digest(target) != operation["before_sha256"]:
                raise CodexiconError(
                    f"target changed after planning; refusing to modify {operation['path']}"
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
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        result = None
    if result is not None and result.returncode == 0 and result.stdout.strip():
        common = Path(result.stdout.strip())
        if not common.is_absolute():
            common = root / common
        material = str(common.resolve())
    else:
        material = str(root.resolve())
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def git_value(root: Path, *args: str) -> str | None:
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


def dirty_paths(root: Path) -> list[str]:
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
        return None, None, "invalid checkpoint Git reference"
    related = metadata.get("related")
    if not isinstance(related, list):
        return None, None, "invalid checkpoint related paths"
    try:
        normalized_related = [normalize_relative(str(item)) for item in related]
    except CodexiconError:
        return None, None, "unsafe checkpoint related path"
    if len(normalized_related) != len(set(normalized_related)):
        return None, None, "duplicate checkpoint related path"
    metadata = {**metadata, "related": normalized_related}
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


def doctor(root: Path) -> int:
    root = root.resolve()
    diagnostics: list[tuple[str, str]] = []
    parse_config(root, diagnostics)
    parse_hooks(root, diagnostics)
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
        mode = git_index_mode(root, relative)
        if mode is None:
            diagnostics.append(
                (
                    "WARN",
                    f"executable path is not tracked yet; stage it, then run sync-git-modes: {relative}",
                )
            )
        elif mode != "100755":
            diagnostics.append(
                ("ERROR", f"executable path has Git index mode {mode}, expected 100755: {relative}")
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
        current_head = git_value(root, "rev-parse", "HEAD") or "none"
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
            if metadata["head"] != current_head:
                diagnostics.append(("WARN", f"checkpoint {path.name} references stale HEAD {metadata['head']}"))
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


def verify(root: Path, checks: Sequence[str]) -> int:
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
        try:
            result = subprocess.run(command, cwd=root, check=False)
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
    created = utc_now()
    branch = git_value(root, "branch", "--show-current") or "none"
    head = git_value(root, "rev-parse", "HEAD") or "none"
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "checkpoint_id": secrets.token_hex(8),
        "created_at": created,
        "repository_id": repository_identity(root),
        "branch": branch,
        "head": head,
        "related": related,
    }
    filename = f"{created[:10]}-{slug}.md"
    output = checked_path(root, f"agent_docs/sessions/{filename}")
    if output.exists():
        raise CodexiconError(f"checkpoint already exists: {output.relative_to(root).as_posix()}")
    changed = dirty_paths(root)
    marker = f"<!-- {CHECKPOINT_MARKER} {json.dumps(metadata, sort_keys=True)} -->"
    lines = [
        marker,
        f"# Checkpoint: {args.title}",
        "",
        f"**Created:** {created}  ",
        f"**Checkpoint ID:** `{metadata['checkpoint_id']}`  ",
        f"**Repository:** `{metadata['repository_id']}`  ",
        f"**Git branch / HEAD:** `{branch}` / `{head}`  ",
        f"**Related:** {', '.join(f'`{item}`' for item in related) if related else 'none'}",
        "",
        "## Current state",
        "",
        args.summary.strip(),
        "",
        "## Dirty paths",
        "",
        *([f"- `{path}`" for path in changed] or ["- None."]),
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
    current_head = git_value(root, "rev-parse", "HEAD") or "none"
    print(f"[codexicon] Resume checkpoint: {path.relative_to(root).as_posix()}")
    if metadata.get("head") != current_head:
        print(
            f"[codexicon] Warning: checkpoint HEAD {metadata.get('head')} differs from current HEAD {current_head}.",
            file=sys.stderr,
        )
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

    verify_parser = subparsers.add_parser("verify", help="run project-defined canonical checks")
    verify_parser.add_argument("checks", nargs="*", choices=CANONICAL_CHECKS)
    verify_parser.add_argument("--root", type=Path, default=ROOT)

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
    checkpoint_parser.add_argument("--verification", action="append", default=[])
    checkpoint_parser.add_argument("--blocker", action="append", default=[])
    checkpoint_parser.add_argument("--decision", action="append", default=[])

    resume_parser = subparsers.add_parser("resume", help="print the newest compatible checkpoint")
    resume_parser.add_argument("--root", type=Path, default=ROOT)
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
            return doctor(args.root)
        if args.command == "verify":
            return verify(args.root, args.checks)
        if args.command == "install-git-hooks":
            return install_git_hooks(args.root)
        if args.command == "sync-git-modes":
            return sync_git_modes(args.root)
        if args.command == "checkpoint":
            return create_checkpoint(args)
        if args.command == "resume":
            return resume(args.root)
        parser.error(f"unsupported command: {args.command}")
    except CodexiconError as exc:
        print(f"[codexicon] {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
