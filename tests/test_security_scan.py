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
        token_name = "auth_" + "token"
        environment_reference = "process.env." + "AUTH_TOKEN"
        source.write_text(
            'api_key = "your_api_key_here"\n'
            'password = "changeme-before-use"\n'
            f"{token_name} = {environment_reference}\n",
            encoding="utf-8",
        )

        findings = SECURITY_SCAN.scan_repository(self.root)

        self.assertEqual(findings, [])

    def test_safe_first_assignment_does_not_hide_later_secret(self) -> None:
        source = self.root / "config.py"
        key_name = "API_" + "KEY"
        password_name = "PASS" + "WORD"
        source.write_text(
            f"{key_name}=placeholder; {password_name}=ActualSecret123\n",
            encoding="utf-8",
        )

        findings = SECURITY_SCAN.scan_repository(self.root)

        self.assertIn(
            SECURITY_SCAN.Finding("config.py", 1, "literal-secret-assignment"),
            findings,
        )

    def test_placeholder_words_do_not_suppress_real_assignments(self) -> None:
        source = self.root / "config.py"
        api_name = "api_" + "key"
        password_name = "pass" + "word"
        token_name = "auth_" + "token"
        first_value = "latest-" + "production-secret"
        second_value = "contest-" + "winner-credential"
        third_value = "realproduction" + "credential"
        source.write_text(
            f'{api_name} = "{first_value}"\n'
            f'{password_name} = "{second_value}"\n'
            f"{token_name}={third_value}\n",
            encoding="utf-8",
        )

        findings = SECURITY_SCAN.scan_repository(self.root)

        self.assertEqual(
            [(finding.line, finding.detector) for finding in findings],
            [
                (1, "literal-secret-assignment"),
                (2, "literal-secret-assignment"),
                (3, "literal-secret-assignment"),
            ],
        )

    def test_quoted_json_yaml_and_dictionary_keys_detect_literal_secrets(self) -> None:
        source = self.root / "config.txt"
        json_key = '"' + "password" + '": "'
        json_value = "json" + "-" + "secret" + "-" + "value"
        yaml_key = "'" + "api-key" + "': '"
        yaml_value = "yaml" + "-" + "secret" + "-" + "value"
        dictionary_key = '{"' + "auth_token" + '": "'
        dictionary_value = "dictionary" + "-" + "secret" + "-" + "value"
        source.write_text(
            f"{json_key}{json_value}\"\n"
            f"{yaml_key}{yaml_value}'\n"
            f"{dictionary_key}{dictionary_value}\"}}\n",
            encoding="utf-8",
        )

        findings = SECURITY_SCAN.scan_repository(self.root)

        self.assertEqual(
            [(finding.line, finding.detector) for finding in findings],
            [
                (1, "literal-secret-assignment"),
                (2, "literal-secret-assignment"),
                (3, "literal-secret-assignment"),
            ],
        )

    def test_quoted_key_placeholders_and_environment_references_pass(self) -> None:
        source = self.root / "config.json"
        password_key = '"' + "password" + '": "'
        password_value = "${" + "PASSWORD" + "}"
        api_key = '"' + "api_key" + '": '
        api_value = "process" + ".env." + "API_KEY"
        auth_key = "'" + "auth-token" + "': "
        auth_value = "os" + ".environ['AUTH_TOKEN']"
        source.write_text(
            f"{password_key}{password_value}\"\n"
            f"{api_key}{api_value}\n"
            f"{auth_key}{auth_value}\n",
            encoding="utf-8",
        )

        self.assertEqual(SECURITY_SCAN.scan_repository(self.root), [])

    def test_unreadable_candidate_fails_closed_without_value_output(self) -> None:
        source = self.root / "restricted.txt"
        source.write_text("safe\n", encoding="utf-8")

        with mock.patch.object(Path, "open", side_effect=PermissionError("denied")):
            findings = list(SECURITY_SCAN.scan_lines(source, self.root))

        self.assertEqual(
            findings,
            [SECURITY_SCAN.Finding("restricted.txt", 0, "unreadable-file")],
        )

    def test_failed_ship_git_enumeration_is_reported_without_build_fallback(self) -> None:
        source = self.root / "app.py"
        source.write_text("print('safe')\n", encoding="utf-8")
        with (
            mock.patch.object(SECURITY_SCAN, "is_git_root", return_value=True),
            mock.patch.object(
                SECURITY_SCAN,
                "git_paths",
                side_effect=[["app.py"], None],
            ),
        ):
            files, findings = SECURITY_SCAN.repository_files(
                self.root, mode=SECURITY_SCAN.SHIP_MODE
            )

        self.assertEqual(files, [])
        self.assertIn(
            SECURITY_SCAN.Finding(".", 0, "git-enumeration-failed"),
            findings,
        )

    def test_failed_first_ship_git_enumeration_is_reported(self) -> None:
        with (
            mock.patch.object(SECURITY_SCAN, "is_git_root", return_value=True),
            mock.patch.object(SECURITY_SCAN, "git_paths", return_value=None),
        ):
            files, findings = SECURITY_SCAN.repository_files(
                self.root, mode=SECURITY_SCAN.SHIP_MODE
            )

        self.assertEqual(files, [])
        self.assertEqual(
            findings,
            [SECURITY_SCAN.Finding(".", 0, "git-enumeration-failed")],
        )

    def test_build_scan_does_not_call_git_when_git_is_unavailable(self) -> None:
        source = self.root / "app.py"
        source.write_text("print('safe')\n", encoding="utf-8")
        with mock.patch.object(
            SECURITY_SCAN.subprocess, "run", side_effect=AssertionError("Git is forbidden")
        ):
            files, findings = SECURITY_SCAN.repository_files(self.root)
        self.assertEqual(files, [source])
        self.assertEqual(findings, [])

    def test_build_scan_prunes_generated_and_protected_files_before_reads(self) -> None:
        source = self.root / "app.py"
        protected = self.root / ".env.local"
        generated = self.root / "build" / "generated.py"
        source.write_text("print('safe')\n", encoding="utf-8")
        protected.write_text("protected-but-not-a-secret\n", encoding="utf-8")
        generated.parent.mkdir()
        generated.write_text("credential = 'should-not-be-read'\n", encoding="utf-8")
        original_open = Path.open

        def guarded_open(path: Path, *args, **kwargs):
            if path == protected or path == generated:
                raise AssertionError(f"unsafe read: {path}")
            return original_open(path, *args, **kwargs)

        with mock.patch.object(Path, "open", new=guarded_open):
            findings = SECURITY_SCAN.scan_repository(self.root)

        self.assertEqual(findings, [])

    def test_ship_scan_fails_closed_without_a_git_repository(self) -> None:
        with mock.patch.object(SECURITY_SCAN, "is_git_root", return_value=False):
            files, findings = SECURITY_SCAN.repository_files(
                self.root, mode=SECURITY_SCAN.SHIP_MODE
            )
        self.assertEqual(files, [])
        self.assertEqual(
            findings,
            [SECURITY_SCAN.Finding(".", 0, "git-repository-required")],
        )

    def test_ship_scan_reports_protected_paths_in_history_without_opening_them(self) -> None:
        safe_source = self.root / "app.py"
        safe_source.write_text("print('safe')\n", encoding="utf-8")
        with (
            mock.patch.object(SECURITY_SCAN, "is_git_root", return_value=True),
            mock.patch.object(
                SECURITY_SCAN,
                "git_paths",
                side_effect=[["app.py"], ["app.py"], [".env.local"]],
            ),
        ):
            files, findings = SECURITY_SCAN.repository_files(
                self.root, mode=SECURITY_SCAN.SHIP_MODE
            )
        self.assertEqual(files, [safe_source])
        self.assertIn(
            SECURITY_SCAN.Finding(".env.local", 0, "protected-history-path"),
            findings,
        )

    def test_tracked_protected_path_fails_without_opening_it(self) -> None:
        safe_source = self.root / "app.py"
        safe_source.write_text("print('safe')\n", encoding="utf-8")
        with (
            mock.patch.object(SECURITY_SCAN, "is_git_root", return_value=True),
            mock.patch.object(
                SECURITY_SCAN,
                "git_paths",
                side_effect=[[".env.local", "app.py"], [".env.local", "app.py"], []],
            ),
        ):
            files, findings = SECURITY_SCAN.repository_files(
                self.root, mode=SECURITY_SCAN.SHIP_MODE
            )

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
