from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from scripts import release as release_module
from scripts import scaffold as scaffold_module


ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix=f"codexicon-release-test-{uuid.uuid4().hex}-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        for relative in (*scaffold_module.STARTER_FILES, "README.md"):
            source = ROOT / relative
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        manifest = json.loads((ROOT / ".codexicon.json").read_text(encoding="utf-8"))
        for entry in manifest["files"]:
            relative = entry["path"]
            source = ROOT / relative
            if entry["policy"] != "project" and source.is_file() and not (self.root / relative).exists():
                target = self.root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)

    def test_release_identity_is_reproducible_and_excludes_internal_records(self) -> None:
        internal = self.root / "agent_docs" / "plans" / "internal-plan.md"
        internal.parent.mkdir(parents=True)
        internal.write_text("# Internal plan\n", encoding="utf-8")
        version = release_module.read_version(self.root)

        first = release_module.check_release(self.root, tag=f"v{version}")
        second = release_module.check_release(self.root, tag=f"v{version}")

        self.assertEqual(first, second)
        self.assertEqual(first["version"], version)
        self.assertEqual(first["expected_tag"], f"v{version}")
        self.assertGreater(len(first["starter"]["files"]), 1)
        starter_paths = {entry["path"] for entry in first["starter"]["files"]}
        self.assertNotIn("SPEC.md", starter_paths)
        self.assertNotIn("TASKS.md", starter_paths)
        self.assertNotIn("agent_docs/plans/internal-plan.md", starter_paths)

    def test_explicit_tag_must_match_canonical_version(self) -> None:
        version = release_module.read_version(self.root)
        with self.assertRaisesRegex(
            release_module.ReleaseCheckError, f"must exactly match v{version}"
        ):
            release_module.check_release(self.root, tag="v2.9.1")

    def test_readme_version_drift_fails_closed(self) -> None:
        readme = self.root / "README.md"
        version = release_module.read_version(self.root)
        readme.write_text(
            readme.read_text(encoding="utf-8").replace(f"v{version}", "v9.9.9").replace(
                version, "9.9.9"
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(release_module.ReleaseCheckError, "README.md version references"):
            release_module.check_release(self.root)

    def test_manifest_version_drift_fails_closed(self) -> None:
        manifest_path = self.root / ".codexicon.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["version"] = "2.9.1"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(release_module.ReleaseCheckError, "version must match"):
            release_module.check_release(self.root)

    def test_check_does_not_invoke_git_or_other_subprocesses(self) -> None:
        with mock.patch.object(subprocess, "run", side_effect=AssertionError("subprocess invoked")):
            release_module.check_release(self.root)


if __name__ == "__main__":
    unittest.main()
