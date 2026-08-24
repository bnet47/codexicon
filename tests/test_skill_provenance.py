from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "skill_provenance.py"
SPEC = importlib.util.spec_from_file_location("skill_provenance_under_test", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class SkillProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = ROOT / ".codex-state" / "skill-provenance-tests" / uuid.uuid4().hex
        (self.root / "agent_docs").mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, True)

    def write_lock(self, value: dict) -> None:
        (self.root / "agent_docs" / "skills.lock.json").write_text(
            json.dumps(value), encoding="utf-8"
        )

    def base_lock(self) -> dict:
        return {
            "schema_version": 1,
            "policy": {
                "install_scope": "project-local",
                "require_explicit_approval": True,
                "require_immutable_commit": True,
                "require_content_sha256": True,
                "allow_global_install": False,
            },
            "skills": [],
        }

    def valid_entry(self, name: str = "example-skill") -> dict:
        skill_path = self.root / ".agents" / "skills" / name
        skill_path.mkdir(parents=True, exist_ok=True)
        (skill_path / "SKILL.md").write_text("# Example skill\n", encoding="utf-8")
        return {
            "name": name,
            "path": f".agents/skills/{name}",
            "source": "example-owner/example-repo/tree/main/skills/example-skill",
            "commit": "a" * 40,
            "content_sha256": MODULE.sha256_path(skill_path),
            "license": "MIT",
            "reviewed_at": "2026-08-24",
            "reviewer": "maintainer",
            "permissions": ["read repository files"],
            "notes": "Reviewed before installation.",
        }

    def test_empty_lock_is_valid(self) -> None:
        value = self.base_lock()
        self.write_lock(value)
        self.assertEqual(MODULE.validate_lock(self.root), [])

    def test_valid_entry_is_accepted(self) -> None:
        value = self.base_lock()
        value["skills"].append(self.valid_entry())
        self.write_lock(value)
        self.assertEqual(MODULE.validate_lock(self.root), [])

    def test_duplicate_and_unpinned_entries_are_rejected(self) -> None:
        value = self.base_lock()
        first = self.valid_entry()
        second = self.valid_entry()
        second["commit"] = "main"
        value["skills"] = [first, second]
        self.write_lock(value)
        errors = MODULE.validate_lock(self.root)
        self.assertTrue(any("duplicate skill name" in error for error in errors))
        self.assertTrue(any("immutable commit SHA" in error for error in errors))

    def test_sensitive_values_are_rejected(self) -> None:
        value = self.base_lock()
        entry = self.valid_entry()
        marker = (66, 69, 71, 73, 78, 32, 82, 83, 65, 32, 80, 82, 73, 86, 65, 84, 69, 32, 75, 69, 89)
        entry["notes"] = "".join(chr(code) for code in marker)
        value["skills"] = [entry]
        self.write_lock(value)
        self.assertTrue(any("credential-like" in error for error in MODULE.validate_lock(self.root)))

    def test_missing_lock_is_rejected(self) -> None:
        self.assertEqual(
            MODULE.validate_lock(self.root),
            ["missing provenance lock: agent_docs/skills.lock.json"],
        )

    def test_digest_mismatch_is_rejected(self) -> None:
        value = self.base_lock()
        entry = self.valid_entry()
        entry["content_sha256"] = "b" * 64
        value["skills"] = [entry]
        self.write_lock(value)
        self.assertTrue(
            any("does not match local skill content" in error for error in MODULE.validate_lock(self.root))
        )

    def test_path_traversal_is_rejected(self) -> None:
        value = self.base_lock()
        entry = self.valid_entry()
        entry["path"] = "../outside"
        value["skills"] = [entry]
        self.write_lock(value)
        self.assertTrue(any("cannot traverse parents" in error for error in MODULE.validate_lock(self.root)))


if __name__ == "__main__":
    unittest.main()
