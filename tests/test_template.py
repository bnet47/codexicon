from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".codex" / "hooks" / "codex_hook.py"
HOOKS_JSON = ROOT / ".codex" / "hooks.json"
VALIDATOR = ROOT / "scripts" / "validate_template.py"
TEST_TEMP_ROOT = ROOT / ".codex-state" / "tests"


def make_test_directory() -> Path:
    path = TEST_TEMP_ROOT / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path


class TemplateValidationTests(unittest.TestCase):
    def test_repository_invariants(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_registered_hook_bootstraps_from_a_subdirectory_without_git(self) -> None:
        hooks = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        expected_matchers = {
            "SessionStart": ["startup|clear"],
            "PreToolUse": ["^Bash$|^apply_patch$|^Read$|^read_file$|^read_text_file$|Edit|Write"],
            "PostToolUse": ["^apply_patch$|Edit|Write", "^Bash$"],
            "PreCompact": [None],
            "Stop": [None],
        }
        self.assertEqual(set(hooks["hooks"]), set(expected_matchers))

        for event, groups in hooks["hooks"].items():
            self.assertEqual([group.get("matcher") for group in groups], expected_matchers[event])
            for group_index, group in enumerate(groups):
                for handler_index, handler in enumerate(group["hooks"]):
                    with self.subTest(event=event, group=group_index, handler=handler_index):
                        command = handler["commandWindows"] if os.name == "nt" else handler["command"]
                        temp_dir = make_test_directory()
                        try:
                            env = os.environ.copy()
                            env["CODEX_STATE_FILE"] = str(temp_dir / "state.json")
                            env["CODEX_STATE_DIR"] = str(temp_dir)
                            payload = {"session_id": "bootstrap"}
                            if event == "SessionStart":
                                payload["source"] = "startup"
                            elif event == "PreToolUse":
                                payload.update(tool_name="Bash", tool_input={"command": "git status"})
                            elif event == "PostToolUse":
                                if "apply_patch" in (group.get("matcher") or ""):
                                    payload.update(
                                        tool_name="apply_patch",
                                        tool_input={
                                            "command": "*** Begin Patch\n*** Update File: README.md\n*** End Patch"
                                        },
                                    )
                                else:
                                    payload.update(
                                        tool_name="Bash",
                                        tool_input={"command": "git status"},
                                        tool_response="",
                                    )
                            elif event == "PreCompact":
                                payload["trigger"] = "manual"
                            elif event == "Stop":
                                payload["stop_hook_active"] = False

                            result = subprocess.run(
                                command,
                                cwd=ROOT / "tests",
                                input=json.dumps(payload),
                                text=True,
                                capture_output=True,
                                env=env,
                                shell=True,
                                check=False,
                            )
                        finally:
                            shutil.rmtree(temp_dir, ignore_errors=True)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class CodexHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = make_test_directory()
        self.addCleanup(shutil.rmtree, self.temp_dir, True)
        self.state_file = self.temp_dir / "state.json"

    def run_hook(self, action: str, payload: dict | None = None, *extra: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["CODEX_STATE_FILE"] = str(self.state_file)
        env["CODEX_STATE_DIR"] = str(self.temp_dir)
        return subprocess.run(
            [sys.executable, str(HOOK), action, *extra],
            cwd=ROOT,
            input=json.dumps(payload or {}),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def receipt(self, check: str) -> str:
        result = self.run_hook("emit-success", None, check)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def record_success(self, check: str) -> None:
        suffix = "sh"
        command = f"./scripts/{check}.{suffix}"
        result = self.run_hook(
            "record-shell",
            {"session_id": "s1", "tool_input": {"command": command}, "tool_response": self.receipt(check)},
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_secret_policy_blocks_operator_bypasses_but_allows_example(self) -> None:
        blocked_commands = [
            "Get-Content .env.local",
            "cat<.env",
            "type<.env",
            "Get-Content .key",
            "Get-Content secrets/token.txt",
            "Get-Content credentials.json",
            "Get-Content $HOME/.npmrc",
            "Get-Content ~/.pypirc",
            "cat ~/.netrc",
            "cat ~/.aws/credentials",
            "cat ~/.ssh/id_ed25519",
            "cat ~/.kube/config",
            "cat ~/.docker/config.json",
            "Get-Content ~/.config/gh/hosts.yml",
            "Get-Content ~/.terraform.d/credentials.tfrc.json",
            "Get-ChildItem Env:",
            "printenv",
            "env",
            "Write-Output $env:OPENAI_API_KEY",
            "echo $AWS_SECRET_ACCESS_KEY",
            "printenv GITHUB_TOKEN",
            "export -p",
            "declare -x",
            "compgen -e",
            "python -c \"import os; print(dict(os.environ))\"",
            "node -e \"console.log(JSON.stringify(process.env))\"",
        ]
        for command in blocked_commands:
            with self.subTest(command=command):
                result = self.run_hook(
                    "protect-secrets",
                    {"tool_name": "Bash", "tool_input": {"command": command}},
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("Blocked protected credential path", result.stderr)

        allowed = self.run_hook(
            "protect-secrets",
            {"tool_name": "Bash", "tool_input": {"command": "Get-Content .env.example"}},
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

        for command in ("printenv PATH", "Write-Output $env:PATH", "set -e"):
            with self.subTest(allowed_command=command):
                safe_environment_read = self.run_hook(
                    "protect-secrets",
                    {"tool_name": "Bash", "tool_input": {"command": command}},
                )
                self.assertEqual(safe_environment_read.returncode, 0, safe_environment_read.stderr)

        protected_read_tool = self.run_hook(
            "protect-secrets",
            {"tool_name": "Read", "tool_input": {"file_path": ".ssh/id_rsa"}},
        )
        self.assertEqual(protected_read_tool.returncode, 2)

        safe_search = self.run_hook(
            "protect-secrets",
            {"tool_name": "Bash", "tool_input": {"command": r"rg -n '\.env' README.md"}},
        )
        protected_search = self.run_hook(
            "protect-secrets",
            {"tool_name": "Bash", "tool_input": {"command": r"rg -n '\.env' .env.local"}},
        )
        broad_search = self.run_hook(
            "protect-secrets",
            {"tool_name": "Bash", "tool_input": {"command": r"rg -n '\.env' ."}},
        )
        self.assertEqual(safe_search.returncode, 0, safe_search.stderr)
        self.assertEqual(protected_search.returncode, 2)
        self.assertEqual(broad_search.returncode, 2)

        documentation_patch = self.run_hook(
            "protect-secrets",
            {
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Update File: README.md\n@@\n+Never read .env.local.\n*** End Patch"
                },
            },
        )
        protected_patch = self.run_hook(
            "protect-secrets",
            {
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Update File: .env.local\n@@\n-old\n+new\n*** End Patch"
                },
            },
        )
        self.assertEqual(documentation_patch.returncode, 0, documentation_patch.stderr)
        self.assertEqual(protected_patch.returncode, 2)

    def test_expired_and_malformed_receipts_are_pruned(self) -> None:
        receipt_dir = self.temp_dir / "receipts"
        receipt_dir.mkdir(parents=True)
        expired = receipt_dir / "expired.json"
        malformed = receipt_dir / "malformed.json"
        expired.write_text(
            json.dumps({"check": "lint", "created_epoch": 1, "schema_version": 1}),
            encoding="utf-8",
        )
        malformed.write_text("not-json", encoding="utf-8")

        current = self.run_hook("emit-success", None, "lint")

        self.assertEqual(current.returncode, 0, current.stderr)
        self.assertFalse(expired.exists())
        self.assertFalse(malformed.exists())
        self.assertEqual(len(list(receipt_dir.glob("*.json"))), 1)

    def test_common_read_only_shell_commands_do_not_require_verification(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        read_only_commands = [
            "git branch --show-current",
            "git status; git branch --show-current",
            "Get-ChildItem | Select-Object Name",
        ]
        for command in read_only_commands:
            with self.subTest(command=command):
                result = self.run_hook(
                    "record-shell",
                    {"session_id": "s1", "tool_input": {"command": command}, "tool_response": ""},
                )
                self.assertEqual(result.returncode, 0, result.stderr)

        allowed = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_code_write_requires_fresh_lint_and_test_receipts(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        self.assertEqual(
            self.run_hook(
                "record-write",
                {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
            ).returncode,
            0,
        )

        blocked = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("Missing or stale: lint, tests", blocked.stderr)

        self.record_success("lint")
        self.record_success("test")
        allowed = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_documentation_only_write_requires_lint_but_not_tests(self) -> None:
        self.run_hook("session-start", {"session_id": "s1"})
        patch = "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch"
        self.run_hook(
            "record-write",
            {"session_id": "s1", "tool_input": {"command": patch}},
        )
        blocked = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("Missing or stale: lint.", blocked.stderr)
        self.assertNotIn("tests", blocked.stderr)

        self.record_success("lint")
        allowed = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_failed_or_masked_check_is_not_recorded_as_passing(self) -> None:
        self.run_hook("session-start", {"session_id": "s1"})
        self.run_hook(
            "record-write",
            {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
        )

        failed = self.run_hook(
            "record-shell",
            {
                "session_id": "s1",
                "tool_input": {"command": "./scripts/test.sh"},
                "tool_response": "Exit code: 0 but no authenticated receipt",
            },
        )
        self.assertEqual(failed.returncode, 0, failed.stderr)

        masked = self.run_hook(
            "record-shell",
            {
                "session_id": "s1",
                "tool_input": {"command": "./scripts/lint.sh || true"},
                "tool_response": self.receipt("lint"),
            },
        )
        self.assertEqual(masked.returncode, 0, masked.stderr)

        blocked = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("lint", blocked.stderr)
        self.assertIn("tests", blocked.stderr)

    def test_mutating_shell_command_invalidates_prior_verification(self) -> None:
        self.run_hook("session-start", {"session_id": "s1"})
        self.run_hook(
            "record-write",
            {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
        )
        self.record_success("lint")
        self.record_success("test")
        self.run_hook(
            "record-shell",
            {"session_id": "s1", "tool_input": {"command": "python generate.py"}, "tool_response": "done"},
        )

        blocked = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(blocked.returncode, 2)

    def test_active_stop_hook_does_not_loop_forever(self) -> None:
        self.run_hook("session-start", {"session_id": "s1"})
        self.run_hook(
            "record-write",
            {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
        )
        result = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": True})
        self.assertEqual(result.returncode, 0)
        self.assertIn("systemMessage", result.stdout)


if __name__ == "__main__":
    unittest.main()
