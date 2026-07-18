from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / ".agents" / "skills" / "review-creative" / "scripts" / "scan_interface.py"


def load_scanner():
    spec = importlib.util.spec_from_file_location("scan_interface", SCANNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load interface scanner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class InterfaceScannerTests(unittest.TestCase):
    def test_reports_review_signals_without_failing_by_default(self) -> None:
        scanner = load_scanner()
        source = """
.title {
  background: linear-gradient(90deg, red, blue);
  background-clip: text;
  transition: all 200ms ease;
}
"""
        findings = scanner.scan_text(Path("example.css"), source)
        self.assertEqual({item.code for item in findings}, {"gradient-text", "transition-all"})

    def test_cli_can_be_opted_into_failure(self) -> None:
        directory = ROOT / ".codex-state" / "tests" / f"scanner-{uuid.uuid4().hex}"
        directory.mkdir(parents=True, exist_ok=False)
        try:
            source = directory / "example.css"
            source.write_text("button:focus { outline: none; }", encoding="utf-8")

            advisory = subprocess.run(
                [sys.executable, str(SCANNER), str(source)],
                text=True,
                capture_output=True,
                check=False,
            )
            strict = subprocess.run(
                [sys.executable, str(SCANNER), str(source), "--fail-on-findings"],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(advisory.returncode, 0, advisory.stdout + advisory.stderr)
            self.assertEqual(strict.returncode, 1, strict.stdout + strict.stderr)
            self.assertIn("focus-outline-removed", advisory.stdout)
        finally:
            shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
