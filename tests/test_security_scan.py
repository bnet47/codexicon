from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCANNER_PATH = ROOT / "scripts" / "security_scan.py"
TEST_TEMP_ROOT = ROOT / ".codex-state" / "security-tests"
SPEC = importlib.util.spec_from_file_location("security_scan", SCANNER_PATH)
assert SPEC and SPEC.loader
SECURITY_SCAN = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SECURITY_SCAN
SPEC.loader.exec_module(SECURITY_SCAN)


class SecurityScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = TEST_TEMP_ROOT / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_protected_path_policy_does_not_require_opening_the_file(self) -> None:
        protected = [
            ".env",
            ".env.local",
            ".npmrc",
            ".aws/credentials",
            ".ssh/id_rsa",
            ".kube/config",
            ".docker/config.json",
            "secrets/token.txt",
            "credentials.json",
        ]
        for path in protected:
            with self.subTest(path=path):
                self.assertTrue(SECURITY_SCAN.is_protected_path(path))
        self.assertFalse(SECURITY_SCAN.is_protected_path(".env.example"))
        self.assertFalse(SECURITY_SCAN.is_protected_path("docs/security.md"))

    def test_scanner_detects_and_redacts_high_confidence_token(self) -> None:
        source = self.root / "app.py"
        fake_token = "gh" + "p_" + ("A" * 36)
        source.write_text(f'credential = "{fake_token}"\n', encoding="utf-8")

        result = subprocess.run(
            [sys.executable, str(SCANNER_PATH), "--root", str(self.root)],
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("app.py:1 [github-token]", result.stderr)
        self.assertNotIn(fake_token, result.stdout + result.stderr)

    def test_scanner_allows_documented_placeholders(self) -> None:
        source = self.root / "config.example.py"
        source.write_text(
            'api_key = "your_api_key_here"\npassword = "changeme-before-use"\n',
            encoding="utf-8",
        )

        findings = SECURITY_SCAN.scan_repository(self.root)

        self.assertEqual(findings, [])

    def test_tracked_protected_path_fails_without_opening_it(self) -> None:
        safe_source = self.root / "app.py"
        safe_source.write_text("print('safe')\n", encoding="utf-8")
        with (
            mock.patch.object(SECURITY_SCAN, "is_git_root", return_value=True),
            mock.patch.object(
                SECURITY_SCAN,
                "git_paths",
                side_effect=[[".env.local", "app.py"], [".env.local", "app.py"]],
            ),
        ):
            files, findings = SECURITY_SCAN.repository_files(self.root)

        self.assertEqual(files, [safe_source])
        self.assertEqual(
            findings,
            [SECURITY_SCAN.Finding(".env.local", 0, "protected-tracked-path")],
        )

    def test_external_symlink_is_rejected_without_opening_the_target(self) -> None:
        candidate = mock.Mock(spec=Path)
        candidate.is_symlink.return_value = True
        candidate.resolve.return_value = self.root.parent / "outside.txt"
        findings = []

        result = SECURITY_SCAN.safe_candidate(candidate, "linked.txt", self.root, findings)

        self.assertIsNone(result)
        self.assertEqual(
            findings,
            [SECURITY_SCAN.Finding("linked.txt", 0, "external-or-broken-symlink")],
        )


if __name__ == "__main__":
    unittest.main()
