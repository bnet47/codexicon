#!/usr/bin/env python3
"""Verify the reproducible identity of a Codexicon template release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from scaffold import STARTER_FILES, ScaffoldError, scaffold
except ImportError:  # pragma: no cover - used when imported as scripts.release
    from scripts.scaffold import STARTER_FILES, ScaffoldError, scaffold


ROOT = Path(__file__).resolve().parents[1]
VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\Z")
README_VERSION_PATTERNS = (
    re.compile(r"template-v(?P<version>\d+\.\d+\.\d+)(?=-[0-9a-f]{6}\.svg)"),
    re.compile(r"Template version (?P<version>\d+\.\d+\.\d+)")
)
TAG_RE = re.compile(r"v\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\Z")
MANIFEST_POLICIES = {"managed", "merge", "project"}
INTERNAL_PARTS = {
    ".codex-state",
    "briefs",
    "checkpoints",
    "evals",
    "evaluation",
    "plans",
    "receipts",
    "sessions",
}
INTERNAL_ROOT_FILES = {"SPEC.md", "TASKS.md"}


class ReleaseCheckError(ValueError):
    """Raised when a release identity cannot be established safely."""


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def read_version(root: Path) -> str:
    """Read and validate the one canonical version from TEMPLATE_VERSION."""

    path = root / "TEMPLATE_VERSION"
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0].strip()
    except (FileNotFoundError, IndexError, OSError) as exc:
        raise ReleaseCheckError("TEMPLATE_VERSION is missing or empty") from exc
    if not VERSION_RE.fullmatch(first):
        raise ReleaseCheckError(f"TEMPLATE_VERSION has invalid version: {first!r}")
    return first


def _load_manifest(root: Path, version: str) -> dict[str, Any]:
    path = root / ".codexicon.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseCheckError(".codexicon.json is missing or invalid JSON") from exc
    if not isinstance(manifest, dict):
        raise ReleaseCheckError(".codexicon.json must contain an object")
    if manifest.get("schema_version") != 1:
        raise ReleaseCheckError(".codexicon.json must use schema_version 1")
    if manifest.get("version") != version:
        raise ReleaseCheckError(".codexicon.json version must match TEMPLATE_VERSION")
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ReleaseCheckError(".codexicon.json requires a non-empty files list")

    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ReleaseCheckError(".codexicon.json file entries must be objects")
        relative = entry.get("path")
        policy = entry.get("policy")
        if not isinstance(relative, str) or not relative:
            raise ReleaseCheckError(".codexicon.json contains an invalid file path")
        normalized = PurePosixPath(relative)
        if (
            normalized.is_absolute()
            or normalized.as_posix() != relative.replace("\\", "/")
            or any(part in {"", ".", ".."} for part in normalized.parts)
        ):
            raise ReleaseCheckError(f".codexicon.json contains unsafe path: {relative!r}")
        if relative in seen:
            raise ReleaseCheckError(f".codexicon.json contains duplicate path: {relative}")
        seen.add(relative)
        if policy not in MANIFEST_POLICIES:
            raise ReleaseCheckError(f".codexicon.json has invalid policy for {relative}")
        if "executable" in entry and not isinstance(entry["executable"], bool):
            raise ReleaseCheckError(f".codexicon.json has invalid executable flag for {relative}")
        if policy != "project" and not (root / relative).is_file():
            raise ReleaseCheckError(f".codexicon.json references missing source file: {relative}")
    return manifest


def _check_public_references(root: Path, version: str) -> None:
    template_version = (root / "TEMPLATE_VERSION").read_text(encoding="utf-8")
    if not re.search(rf"^## {re.escape(version)}(?:\s|$)", template_version, flags=re.MULTILINE):
        raise ReleaseCheckError(
            f"TEMPLATE_VERSION has no release-notes heading for canonical version {version}"
        )

    readme = (root / "README.md").read_text(encoding="utf-8")
    references = [
        match.group("version")
        for pattern in README_VERSION_PATTERNS
        for match in pattern.finditer(readme)
    ]
    if not references:
        raise ReleaseCheckError("README.md has no current template version reference")
    if set(references) != {version}:
        found = ", ".join(sorted(set(references)))
        raise ReleaseCheckError(f"README.md version references drift from {version}: {found}")


def _artifact_identity(starter: Path, version: str, manifest: dict[str, Any]) -> dict[str, Any]:
    paths: list[Path] = []
    for path in starter.rglob("*"):
        if path.is_symlink():
            raise ReleaseCheckError(
                f"starter artifact contains a symbolic link: {_relative(path, starter)}"
            )
        if path.is_file():
            paths.append(path)
    paths.sort(key=lambda path: _relative(path, starter))
    actual_paths = {_relative(path, starter) for path in paths}
    expected_paths = set(STARTER_FILES)
    if actual_paths != expected_paths:
        missing = sorted(expected_paths - actual_paths)
        extra = sorted(actual_paths - expected_paths)
        details = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"extra={extra}")
        raise ReleaseCheckError("starter artifact file set drift: " + ", ".join(details))

    forbidden = sorted(
        relative
        for relative in actual_paths
        if relative in INTERNAL_ROOT_FILES
        or any(part.lower() in INTERNAL_PARTS for part in PurePosixPath(relative).parts)
    )
    if forbidden:
        raise ReleaseCheckError(f"starter artifact contains internal development records: {forbidden}")

    manifest_bytes = (starter / ".codexicon.json").read_bytes()
    generated_manifest = json.loads(manifest_bytes.decode("utf-8"))
    if generated_manifest.get("version") != version:
        raise ReleaseCheckError("starter manifest version differs from TEMPLATE_VERSION")
    expected_manifest_entries: list[dict[str, Any]] = []
    copied_paths = set(STARTER_FILES)
    for entry in manifest["files"]:
        if entry["path"] not in copied_paths:
            continue
        expected_manifest_entries.append(
            {
                "path": entry["path"],
                "policy": entry["policy"],
                **({"executable": True} if entry.get("executable") is True else {}),
            }
        )
    if "scripts/scaffold.py" not in {entry["path"] for entry in expected_manifest_entries}:
        expected_manifest_entries.append({"path": "scripts/scaffold.py", "policy": "managed"})
    expected_manifest = {
        "schema_version": 1,
        "version": version,
        "files": sorted(expected_manifest_entries, key=lambda entry: entry["path"]),
    }
    if generated_manifest != expected_manifest:
        raise ReleaseCheckError("starter manifest is not the expected source manifest projection")

    files: list[dict[str, str]] = []
    artifact_hash = hashlib.sha256()
    for path in paths:
        relative = _relative(path, starter)
        content = path.read_bytes()
        digest = _sha256_bytes(content)
        files.append({"path": relative, "sha256": digest})
        encoded_path = relative.encode("utf-8")
        artifact_hash.update(len(encoded_path).to_bytes(8, "big"))
        artifact_hash.update(encoded_path)
        artifact_hash.update(len(content).to_bytes(8, "big"))
        artifact_hash.update(content)
    return {
        "version": version,
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "artifact_sha256": artifact_hash.hexdigest(),
        "files": files,
    }


def starter_identity(root: Path, version: str, manifest: dict[str, Any]) -> dict[str, Any]:
    """Generate one clean starter and return its deterministic content identity."""

    with tempfile.TemporaryDirectory(prefix="codexicon-release-") as temporary:
        starter = Path(temporary) / "starter"
        try:
            scaffold(starter, source=root)
        except (ScaffoldError, OSError, ValueError) as exc:
            raise ReleaseCheckError(f"clean starter generation failed: {exc}") from exc
        return _artifact_identity(starter, version, manifest)


def check_release(root: Path = ROOT, *, tag: str | None = None) -> dict[str, Any]:
    """Validate release identity and return reproducible starter evidence."""

    root = root.resolve()
    version = read_version(root)
    manifest = _load_manifest(root, version)
    _check_public_references(root, version)
    if tag is not None:
        if not TAG_RE.fullmatch(tag) or tag != f"v{version}":
            raise ReleaseCheckError(f"release tag must exactly match v{version}; got {tag!r}")

    first = starter_identity(root, version, manifest)
    second = starter_identity(root, version, manifest)
    if first != second:
        raise ReleaseCheckError("clean starter identity is not reproducible across two generations")
    return {
        "version": version,
        "tag": tag,
        "expected_tag": f"v{version}",
        "starter": first,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser("check", help="verify release identity without Git")
    check_parser.add_argument("--root", type=Path, default=ROOT)
    check_parser.add_argument(
        "--tag",
        help="explicit release tag to verify, which must be exactly vX.Y.Z for TEMPLATE_VERSION",
    )
    check_parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    try:
        result = check_release(args.root, tag=args.tag)
    except (OSError, ReleaseCheckError) as exc:
        print("Release check failed:", file=sys.stderr)
        print(f"- {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        starter = result["starter"]
        tag_status = result["tag"] or "not supplied (Git-free check)"
        print(
            f"Release check passed: version={result['version']} tag={tag_status} "
            f"files={len(starter['files'])} "
            f"manifest_sha256=sha256:{starter['manifest_sha256']} "
            f"artifact_sha256=sha256:{starter['artifact_sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
