from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".codex" / "hooks" / "codex_hook.py"
HOOKS_JSON = ROOT / ".codex" / "hooks.json"
VALIDATOR = ROOT / "scripts" / "validate_template.py"
TEST_TEMP_ROOT = ROOT / ".codex-state" / "tests"
HOOK_SPEC = importlib.util.spec_from_file_location("codex_hook_test_module", HOOK)
assert HOOK_SPEC and HOOK_SPEC.loader
HOOK_MODULE = importlib.util.module_from_spec(HOOK_SPEC)
sys.modules[HOOK_SPEC.name] = HOOK_MODULE
HOOK_SPEC.loader.exec_module(HOOK_MODULE)


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
            "SessionStart": ["startup|clear", "resume|compact"],
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
                                initialized = subprocess.run(
                                    [sys.executable, str(HOOK), "session-start"],
                                    cwd=ROOT,
                                    input=json.dumps({"session_id": "bootstrap"}),
                                    text=True,
                                    capture_output=True,
                                    env=env,
                                    check=False,
                                )
                                self.assertEqual(
                                    initialized.returncode,
                                    0,
                                    initialized.stdout + initialized.stderr,
                                )

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

    def test_manager_verify_consumes_lint_and_test_receipts(self) -> None:
        self.run_hook("session-start", {"session_id": "s1"})
        self.run_hook(
            "record-write",
            {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
        )
        response = self.receipt("lint") + self.receipt("test")
        recorded = self.run_hook(
            "record-shell",
            {
                "session_id": "s1",
                "tool_input": {"command": "python scripts/codexicon.py verify"},
                "tool_response": response,
            },
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        allowed = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

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
            "env > dump.txt",
            "printenv 1>>dump.txt",
            "set 1>dump.txt",
            "export -p > dump.txt",
            "declare -x 1>dump.txt",
            "compgen -e > dump.txt",
            "Get-Content *",
            "Get-Content .*",
            "cat .??*",
            "head *",
            "Select-String token *",
            "& Get-Content *",
            "command cat .??*",
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
        execution_bearing_search = self.run_hook(
            "protect-secrets",
            {
                "tool_name": "Bash",
                "tool_input": {
                    "command": 'rg --pre="cat .env" password README.md',
                },
            },
        )
        unknown_option_search = self.run_hook(
            "protect-secrets",
            {
                "tool_name": "Bash",
                "tool_input": {"command": r"rg --unknown '\.env' README.md"},
            },
        )
        self.assertEqual(safe_search.returncode, 0, safe_search.stderr)
        self.assertEqual(protected_search.returncode, 2)
        self.assertEqual(broad_search.returncode, 2)
        self.assertEqual(execution_bearing_search.returncode, 2)
        self.assertEqual(unknown_option_search.returncode, 2)

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

    def test_execution_bearing_read_only_prefixes_invalidate_verification(self) -> None:
        commands = [
            "git status $(python generate.py)",
            "Get-Content README.md $(python generate.py)",
            "rg needle README.md `python generate.py`",
            "git status & python generate.py",
            "Get-Content README.md (python generate.py)",
            "rg --pre 'python generate.py' needle README.md",
            "cat <(python generate.py)",
            "git branch new-branch",
            "git branch -D old-branch",
            "git branch --edit-description",
            "git show --output=owned.txt HEAD",
            "git log --output owned.txt",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.run_hook("session-start", {"session_id": "s1"})
                self.run_hook(
                    "record-write",
                    {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
                )
                self.record_success("lint")
                self.record_success("test")
                recorded = self.run_hook(
                    "record-shell",
                    {"session_id": "s1", "tool_input": {"command": command}, "tool_response": ""},
                )
                self.assertEqual(recorded.returncode, 0, recorded.stderr)
                blocked = self.run_hook(
                    "verify-stop",
                    {"session_id": "s1", "stop_hook_active": False},
                )
                self.assertEqual(blocked.returncode, 2)

    def test_security_verification_does_not_invalidate_lint_and_test(self) -> None:
        self.run_hook("session-start", {"session_id": "s1"})
        self.run_hook(
            "record-write",
            {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
        )
        self.record_success("lint")
        self.record_success("test")
        for command in (
            "./scripts/security.sh",
            "python scripts/codexicon.py verify security",
        ):
            with self.subTest(command=command):
                recorded = self.run_hook(
                    "record-shell",
                    {
                        "session_id": "s1",
                        "tool_input": {"command": command},
                        "tool_response": "",
                    },
                )
                self.assertEqual(recorded.returncode, 0, recorded.stderr)
                allowed = self.run_hook(
                    "verify-stop",
                    {"session_id": "s1", "stop_hook_active": False},
                )
                self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_missing_malformed_and_wrong_schema_state_fail_closed(self) -> None:
        cases = [
            None,
            "{",
            json.dumps({"schema_version": 1, "has_writes": False}),
            json.dumps(
                {
                    "schema_version": 2,
                    "has_writes": "no",
                    "lint_passed": False,
                    "test_passed": False,
                    "test_required": False,
                }
            ),
        ]
        for content in cases:
            with self.subTest(content=content):
                self.state_file.unlink(missing_ok=True)
                if content is not None:
                    self.state_file.write_text(content, encoding="utf-8")
                result = self.run_hook(
                    "verify-stop",
                    {"session_id": "s1", "stop_hook_active": False},
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("cannot be trusted", result.stderr)

        active = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": True},
        )
        self.assertEqual(active.returncode, 0)
        self.assertIn("systemMessage", active.stdout)

    def test_resume_recovers_missing_state_conservatively(self) -> None:
        with (
            mock.patch.object(HOOK_MODULE, "STATE_FILE", self.state_file),
            mock.patch.object(HOOK_MODULE, "STATE_DIR", self.temp_dir),
            mock.patch.object(HOOK_MODULE, "latest_compatible_checkpoint", return_value=None),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            result = HOOK_MODULE.resume_state({"session_id": "resumed", "source": "resume"})

        self.assertEqual(result, 0)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertTrue(state["has_writes"])
        self.assertTrue(state["test_required"])
        self.assertFalse(state["lint_passed"])
        self.assertFalse(state["test_passed"])
        self.assertIn("required again", output.getvalue())

    def test_resume_ignores_malformed_newest_checkpoint(self) -> None:
        root = self.temp_dir / "project"
        sessions = root / "agent_docs" / "sessions"
        sessions.mkdir(parents=True)
        with mock.patch.object(HOOK_MODULE, "ROOT", root):
            repository_id = HOOK_MODULE.repository_identity()
            valid = {
                "schema_version": 1,
                "checkpoint_id": "a" * 16,
                "created_at": HOOK_MODULE.utc_now()[1],
                "repository_id": repository_id,
                "branch": "none",
                "head": "none",
                "related": [],
            }
            malformed = {**valid, "checkpoint_id": "b" * 16, "created_at": "zzzz"}
            duplicate = {
                **valid,
                "checkpoint_id": "c" * 16,
                "related": ["README.md", "README.md"],
            }
            drive = {
                **valid,
                "checkpoint_id": "d" * 16,
                "related": ["C:/outside"],
            }
            (sessions / "valid.md").write_text(
                f"<!-- codexicon-checkpoint: {json.dumps(valid)} -->\n",
                encoding="utf-8",
            )
            (sessions / "malformed.md").write_text(
                f"<!-- codexicon-checkpoint: {json.dumps(malformed)} -->\n",
                encoding="utf-8",
            )
            (sessions / "duplicate.md").write_text(
                f"<!-- codexicon-checkpoint: {json.dumps(duplicate)} -->\n",
                encoding="utf-8",
            )
            (sessions / "drive.md").write_text(
                f"<!-- codexicon-checkpoint: {json.dumps(drive)} -->\n",
                encoding="utf-8",
            )

            selected = HOOK_MODULE.latest_compatible_checkpoint()

        self.assertEqual(selected, "agent_docs/sessions/valid.md")

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
