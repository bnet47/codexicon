#!/usr/bin/env python3
"""Validate Codexicon's project-local external-skill provenance lock."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


LOCK_RELATIVE = "agent_docs/skills.lock.json"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
SOURCE = re.compile(
    r"^(?:[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_./-]+)?|"
    r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/tree/[^?#]+)?)$"
)
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def lock_path(root: Path) -> Path:
    return root / LOCK_RELATIVE


def validate_lock(root: Path) -> list[str]:
    """Return actionable validation errors without network access or mutation."""

    path = lock_path(root)
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"missing provenance lock: {LOCK_RELATIVE}"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"invalid provenance lock: {exc}"]

    errors: list[str] = []
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        return ["provenance lock requires schema_version 1"]
    policy = value.get("policy")
    if not isinstance(policy, dict):
        errors.append("provenance lock policy must be an object")
    else:
        expected_policy = {
            "install_scope": "project-local",
            "require_explicit_approval": True,
            "require_immutable_commit": True,
            "require_content_sha256": True,
            "allow_global_install": False,
        }
        for key, expected in expected_policy.items():
            if policy.get(key) != expected:
                errors.append(f"provenance lock policy.{key} must be {expected!r}")

    skills = value.get("skills")
    if not isinstance(skills, list):
        return errors + ["provenance lock skills must be a list"]

    names: set[str] = set()
    required = {
        "name",
        "source",
        "commit",
        "content_sha256",
        "license",
        "reviewed_at",
        "reviewer",
        "permissions",
        "notes",
    }
    for index, item in enumerate(skills):
        label = f"skills[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        missing = sorted(required - set(item))
        if missing:
            errors.append(f"{label} missing fields: {', '.join(missing)}")
            continue
        name = item["name"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", name):
            errors.append(f"{label}.name is not a valid skill name")
        elif name in names:
            errors.append(f"duplicate skill name: {name}")
        else:
            names.add(name)
        source = item["source"]
        if not isinstance(source, str) or not SOURCE.fullmatch(source):
            errors.append(f"{label}.source must be a GitHub owner/repo path or URL without query data")
        commit = item["commit"]
        if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
            errors.append(f"{label}.commit must be a 40-character immutable commit SHA")
        digest = item["content_sha256"]
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            errors.append(f"{label}.content_sha256 must be a lowercase SHA-256 digest")
        if not isinstance(item["license"], str) or not item["license"].strip():
            errors.append(f"{label}.license must be non-empty")
        if not isinstance(item["reviewed_at"], str) or not DATE.fullmatch(item["reviewed_at"]):
            errors.append(f"{label}.reviewed_at must use YYYY-MM-DD")
        if not isinstance(item["reviewer"], str) or not item["reviewer"].strip():
            errors.append(f"{label}.reviewer must be non-empty")
        permissions = item["permissions"]
        if not isinstance(permissions, list) or not permissions or not all(
            isinstance(permission, str) and permission.strip() for permission in permissions
        ):
            errors.append(f"{label}.permissions must be a non-empty string list")
        if not isinstance(item["notes"], str):
            errors.append(f"{label}.notes must be a string")
        serialized = json.dumps(item, ensure_ascii=False)
        if re.search(r"(?:gh[pousr]_|github_pat_|sk-[A-Za-z0-9]|BEGIN [A-Z ]+PRIVATE KEY)", serialized):
            errors.append(f"{label} contains a credential-like value")
    return errors


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "sha256"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--path", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "verify":
        errors = validate_lock(root)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        print(f"Skill provenance lock valid: {LOCK_RELATIVE}")
        return 0
    if args.path is None:
        parser.error("sha256 requires --path")
    path = args.path if args.path.is_absolute() else root / args.path
    print(sha256_file(path.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
