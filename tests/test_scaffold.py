from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

from scripts import scaffold as scaffold_module


ROOT = Path(__file__).resolve().parents[1]
class ScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix=f"codexicon-scaffold-{uuid.uuid4().hex}-"))
        self.addCleanup(shutil.rmtree, self.root, True)

    def create_starter(self) -> Path:
        target = self.root / "starter"
        scaffold_module.scaffold(target, source=ROOT)
        return target

    def test_clean_starter_contains_harness_and_excludes_development_state(self) -> None:
        target = self.create_starter()

        self.assertTrue((target / ".codex/hooks/codex_hook.py").is_file())
        self.assertTrue((target / ".agents/skills/discover/SKILL.md").is_file())
        self.assertTrue((target / "scripts/codexicon.py").is_file())
        self.assertTrue((target / "docs/scaffolding.md").is_file())
        self.assertFalse((target / "SPEC.md").exists())
        self.assertFalse((target / "TASKS.md").exists())

        excluded_parts = {
            ".codex-state",
            "briefs",
            "plans",
            "sessions",
            "receipts",
            "checkpoints",
            "evals",
            "evaluation",
        }
        generated = {
            path.relative_to(target).as_posix()
            for path in target.rglob("*")
            if path.is_file()
        }
        self.assertFalse(
            [path for path in generated if any(part in excluded_parts for part in Path(path).parts)]
        )
        self.assertNotIn("CODEXICON_EVOLUTION_EVALUATION_BRIEF-1.md", generated)

        manifest = json.loads((target / ".codexicon.json").read_text(encoding="utf-8"))
        manifest_paths = {item["path"] for item in manifest["files"]}
        self.assertIn("scripts/scaffold.py", manifest_paths)
        self.assertTrue(manifest_paths <= generated)
        self.assertFalse(any("eval" in path.lower() for path in manifest_paths))

    def test_documented_starter_smoke_command_passes_without_a_contract(self) -> None:
        target = self.create_starter()
        result = subprocess.run(
            [
                sys.executable,
                str(target / "scripts/codexicon.py"),
                "doctor",
                "--root",
                str(target),
            ],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("doctor: 0 error(s)", result.stdout)

    def test_dry_run_reports_allowlist_without_creating_target(self) -> None:
        target = self.root / "starter"
        output = io.StringIO()
        listed = scaffold_module.scaffold(target, source=ROOT, dry_run=True, output=output)

        self.assertFalse(target.exists())
        self.assertEqual(listed[0], ".codexicon.json")
        self.assertIn("scripts/scaffold.py", output.getvalue())
        self.assertNotIn("SPEC.md\n", output.getvalue())
        self.assertNotIn("TASKS.md\n", output.getvalue())

    def test_scaffold_refuses_existing_or_protected_targets(self) -> None:
        existing = self.root / "existing"
        existing.mkdir(parents=True)
        with self.assertRaisesRegex(scaffold_module.ScaffoldError, "already exists"):
            scaffold_module.scaffold(existing, source=ROOT)

        protected = self.root / "secrets" / "starter"
        with self.assertRaisesRegex(scaffold_module.ScaffoldError, "protected"):
            scaffold_module.scaffold(protected, source=ROOT)

    def test_allowlist_is_explicit_and_source_files_are_present(self) -> None:
        self.assertEqual(tuple(scaffold_module.format_allowlist()), scaffold_module.STARTER_FILES)
        for relative in scaffold_module.STARTER_FILES:
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file())


if __name__ == "__main__":
    unittest.main()
