from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import time
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
CODEX_HOOK = HOOK_MODULE
VALIDATOR_SPEC = importlib.util.spec_from_file_location("template_validator_under_test", VALIDATOR)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
TEMPLATE_VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(TEMPLATE_VALIDATOR)


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

    def test_durable_guidance_policy_detects_brittle_external_assumptions(self) -> None:
        samples = {
            "Use gpt-5.4 for every review.": "named or versioned model choice",
            "Keep the report at most five lines.": "fixed workflow threshold",
            "This costs $2 per million input tokens.": "token-unit pricing",
            "Charge $2 / 1M tokens.": "token-unit pricing",
            "Offer it at half price.": "fixed pricing discount",
            "Compact at 50% of the context.": "fixed context threshold",
            "Compact when 100k tokens remain.": "fixed context threshold",
            "Handle roughly one to three files.": "fixed workflow count",
            "Use three agents.": "fixed workflow count",
        }
        for content, expected in samples.items():
            with self.subTest(content=content):
                self.assertIn(
                    expected,
                    TEMPLATE_VALIDATOR.durable_guidance_findings(content),
                )

        self.assertEqual(
            TEMPLATE_VALIDATOR.durable_guidance_findings(
                "Choose current capabilities for the task and keep the report compact."
            ),
            [],
        )

    def test_toml_fallback_preserves_nested_mcp_sections(self) -> None:
        config = self.temp_config(
            '[mcp_servers.docs]\nenabled = false\n'
            'default_tools_approval_mode = "prompt"\n'
        )
        original_tomllib = TEMPLATE_VALIDATOR.tomllib
        TEMPLATE_VALIDATOR.tomllib = None
        try:
            parsed = TEMPLATE_VALIDATOR.parse_template_toml(config)
        finally:
            TEMPLATE_VALIDATOR.tomllib = original_tomllib
        self.assertIn("docs", parsed["mcp_servers"])
        self.assertTrue(TEMPLATE_VALIDATOR.has_active_mcp_servers(parsed))

    def temp_config(self, content: str) -> Path:
        directory = make_test_directory()
        self.addCleanup(shutil.rmtree, directory, True)
        path = directory / "config.toml"
        path.write_text(content, encoding="utf-8")
        return path

    def test_every_registered_hook_bootstraps_from_a_subdirectory_without_git(self) -> None:
        hooks = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        expected_matchers = {
            "SessionStart": ["startup|clear", "resume|compact"],
            "PreToolUse": ["^Bash$|^apply_patch$|^Read$|^read_file$|^read_text_file$|Edit|Write"],
            "PostToolUse": ["^apply_patch$|Edit|Write", "^Bash$"],
            "PreCompact": [None],
            "Stop": [None],
            "SessionEnd": [None],
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
                                payload.update(
                                    tool_name="Bash",
                                    tool_use_id=f"bootstrap-pre-{group_index}-{handler_index}",
                                    tool_input={"command": "git status"},
                                )
                            elif event == "PostToolUse":
                                payload["tool_use_id"] = (
                                    f"bootstrap-post-{group_index}-{handler_index}"
                                )
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
                                payload.update(
                                    turn_id="turn-bootstrap",
                                    stop_hook_active=False,
                                )
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
                            elif event == "SessionEnd":
                                payload["reason"] = "other"
                                self.assertLessEqual(handler["timeout"], 3)

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

    def session_summary(self, session_id: str = "s1") -> dict:
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:20]
        path = self.temp_dir / "summaries" / f"session-{digest}.json"
        return json.loads(path.read_text(encoding="utf-8"))

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

    def test_session_summary_records_supported_lifecycle_fields(self) -> None:
        started = self.run_hook("session-start", {"session_id": "s1", "source": "startup"})
        self.assertEqual(started.returncode, 0, started.stderr)

        first_turn = {"session_id": "s1", "turn_id": "turn-1"}
        self.assertEqual(self.run_hook("record-stop", {**first_turn, "stop_hook_active": False}).returncode, 0)
        self.assertEqual(self.run_hook("record-stop", {**first_turn, "stop_hook_active": False}).returncode, 0)
        self.assertEqual(
            self.run_hook(
                "record-stop",
                {"session_id": "s1", "turn_id": "turn-2", "stop_hook_active": False},
            ).returncode,
            0,
        )
        self.assertEqual(
            self.run_hook("record-stop", {**first_turn, "stop_hook_active": False}).returncode,
            0,
        )
        self.assertEqual(
            self.run_hook("record-compact", {"session_id": "s1", "trigger": "manual"}).returncode,
            0,
        )
        self.assertEqual(self.session_summary()["turn_count"], 0)
        self.assertEqual(
            self.run_hook("end-session", {"session_id": "s1", "reason": "other"}).returncode,
            0,
        )

        summary = self.session_summary()
        self.assertEqual(summary["turn_count"], 2)
        self.assertEqual(summary["compact_count"], 1)
        self.assertIsNotNone(summary["session_started_at"])
        self.assertIsNotNone(summary["session_ended_at"])
        self.assertEqual(summary["usage"]["availability"], "not_exposed_by_hook_payloads")
        self.assertIsNone(summary["usage"]["input_tokens"])
        self.assertIsNone(summary["usage"]["cached_input_tokens"])
        self.assertIsNone(summary["usage"]["reasoning_output_tokens"])

    def test_session_telemetry_ignores_missing_optional_fields(self) -> None:
        self.assertEqual(self.run_hook("record-turn", {}).returncode, 0)
        self.assertEqual(self.run_hook("record-compact", {}).returncode, 0)
        self.assertEqual(self.run_hook("end-session", {}).returncode, 0)

    def test_telemetry_skips_busy_state_lock_without_blocking(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        original_state_file = CODEX_HOOK.STATE_FILE
        CODEX_HOOK.STATE_FILE = self.state_file
        try:
            with CODEX_HOOK.state_lock() as acquired:
                self.assertTrue(acquired)
                started = time.monotonic()
                result = self.run_hook("record-turn", {"session_id": "s1", "turn_id": "busy"})
                elapsed = time.monotonic() - started
        finally:
            CODEX_HOOK.STATE_FILE = original_state_file

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 1.0)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state["turn_count"], 0)

    def test_session_start_fails_fast_when_state_lock_is_busy(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        original = json.loads(self.state_file.read_text(encoding="utf-8"))
        original_state_file = CODEX_HOOK.STATE_FILE
        CODEX_HOOK.STATE_FILE = self.state_file
        try:
            with CODEX_HOOK.state_lock() as acquired:
                self.assertTrue(acquired)
                started = time.monotonic()
                result = self.run_hook("session-start", {"session_id": "s1", "source": "clear"})
                elapsed = time.monotonic() - started
        finally:
            CODEX_HOOK.STATE_FILE = original_state_file

        self.assertEqual(result.returncode, 2)
        self.assertIn("initialization was not recorded", result.stderr)
        self.assertLess(elapsed, 1.0)
        current = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(current["session_started_at"], original["session_started_at"])

    def test_write_invalidation_survives_busy_state_lock(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        self.assertEqual(
            self.run_hook(
                "record-write",
                {"session_id": "s1", "tool_input": {"file_path": "src/before.py"}},
            ).returncode,
            0,
        )
        self.record_success("lint")
        self.record_success("test")
        self.assertEqual(
            self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False}).returncode,
            0,
        )

        busy_write = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "busy-write",
            "tool_input": {"file_path": "src/after.py"},
        }
        prepared = self.run_hook("prepare-tool", busy_write)
        self.assertEqual(prepared.returncode, 0, prepared.stderr)

        original_state_file = CODEX_HOOK.STATE_FILE
        CODEX_HOOK.STATE_FILE = self.state_file
        try:
            with CODEX_HOOK.state_lock() as acquired:
                self.assertTrue(acquired)
                result = self.run_hook("record-write", busy_write)
        finally:
            CODEX_HOOK.STATE_FILE = original_state_file

        self.assertEqual(result.returncode, 2)
        self.assertIn("write invalidation remains pending", result.stderr)
        stale = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertTrue(stale["lint_passed"])
        self.assertTrue(stale["test_passed"])
        self.assertTrue(list((self.temp_dir / "pending-writes").glob("*.json")))

        blocked = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("Missing or stale: lint, tests", blocked.stderr)
        reconciled = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertFalse(reconciled["lint_passed"])
        self.assertFalse(reconciled["test_passed"])
        self.assertFalse(list((self.temp_dir / "pending-writes").glob("*.json")))

        self.record_success("lint")
        self.record_success("test")
        allowed = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_pending_write_intent_blocks_checks_and_stop_until_completion(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        payload = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "active-write",
            "tool_input": {"file_path": "src/example.py"},
        }
        prepared = self.run_hook("prepare-tool", payload)
        self.assertEqual(prepared.returncode, 0, prepared.stderr)

        self.record_success("lint")
        self.record_success("test")
        blocked = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(blocked.returncode, 2)
        self.assertTrue(list((self.temp_dir / "pending-writes").glob("*.json")))

        completed = self.run_hook("record-write", payload)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.record_success("lint")
        self.record_success("test")
        allowed = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_pretool_intent_waits_for_state_snapshot_lock(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        payload = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "serialized-intent",
            "tool_input": {"file_path": "src/example.py"},
        }
        results: list[subprocess.CompletedProcess[str]] = []

        original_state_file = CODEX_HOOK.STATE_FILE
        CODEX_HOOK.STATE_FILE = self.state_file
        try:
            with CODEX_HOOK.state_lock() as acquired:
                self.assertTrue(acquired)
                worker = threading.Thread(
                    target=lambda: results.append(self.run_hook("prepare-tool", payload))
                )
                worker.start()
                time.sleep(0.2)
                self.assertTrue(worker.is_alive())
                self.assertFalse(list((self.temp_dir / "pending-writes").glob("*.json")))
            worker.join(timeout=5)
        finally:
            CODEX_HOOK.STATE_FILE = original_state_file

        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0].returncode, 0, results[0].stderr)
        self.assertTrue(list((self.temp_dir / "pending-writes").glob("*.json")))

    def test_unusable_pending_write_storage_fails_closed(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        pending_directory = self.temp_dir / "pending-writes"
        pending_directory.write_text("not a directory", encoding="utf-8")
        payload = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "blocked-storage",
            "tool_input": {"file_path": "src/example.py"},
        }

        prepared = self.run_hook("prepare-tool", payload)
        self.assertEqual(prepared.returncode, 2)
        stopped = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(stopped.returncode, 2)
        self.assertIn("pending write storage is not a trusted directory", stopped.stderr)

    def test_pending_write_storage_symlink_is_rejected(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        external = self.temp_dir / "external"
        external.mkdir()
        try:
            (self.temp_dir / "pending-writes").symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest("symbolic links are unavailable")
        payload = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "symlink-storage",
            "tool_input": {"file_path": "src/example.py"},
        }

        prepared = self.run_hook("prepare-tool", payload)
        self.assertEqual(prepared.returncode, 2)
        self.assertFalse(list(external.iterdir()))
        stopped = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(stopped.returncode, 2)
        self.assertIn("pending write storage is not a trusted directory", stopped.stderr)

    def test_session_reset_preserves_pending_write_intent(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        payload = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "reset-write",
            "tool_input": {"file_path": "src/example.py"},
        }
        self.assertEqual(self.run_hook("prepare-tool", payload).returncode, 0)

        reset = self.run_hook("session-start", {"session_id": "s1", "source": "clear"})
        self.assertEqual(reset.returncode, 0, reset.stderr)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertTrue(state["has_writes"])
        self.assertEqual(state["active_write_intents"], 1)
        self.assertTrue(list((self.temp_dir / "pending-writes").glob("*.json")))
        blocked = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(blocked.returncode, 2)

    def test_documentation_marker_on_malformed_state_requires_tests(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        self.state_file.write_text("{", encoding="utf-8")
        payload = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "malformed-doc-write",
            "tool_input": {"file_path": "README.md"},
        }
        self.assertEqual(self.run_hook("prepare-tool", payload).returncode, 0)
        recorded = self.run_hook("record-write", payload)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertTrue(state["test_required"])

        self.record_success("lint")
        blocked = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("Missing or stale: tests", blocked.stderr)

    def test_summary_write_is_serialized_with_authoritative_state(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        original_paths = (
            CODEX_HOOK.STATE_FILE,
            CODEX_HOOK.STATE_DIR,
            CODEX_HOOK.RECEIPT_DIR,
            CODEX_HOOK.SUMMARY_DIR,
        )
        CODEX_HOOK.STATE_FILE = self.state_file
        CODEX_HOOK.STATE_DIR = self.temp_dir
        CODEX_HOOK.RECEIPT_DIR = self.temp_dir / "receipts"
        CODEX_HOOK.SUMMARY_DIR = self.temp_dir / "summaries"
        original_summary = CODEX_HOOK.write_session_summary
        concurrent_results: list[subprocess.CompletedProcess[str]] = []

        def inspect_lock(state: dict) -> None:
            concurrent_results.append(
                self.run_hook("record-turn", {"session_id": "s1", "turn_id": "late"})
            )
            original_summary(state)

        try:
            with mock.patch.object(CODEX_HOOK, "write_session_summary", side_effect=inspect_lock):
                self.assertEqual(CODEX_HOOK.end_session({"session_id": "s1"}), 0)
        finally:
            (
                CODEX_HOOK.STATE_FILE,
                CODEX_HOOK.STATE_DIR,
                CODEX_HOOK.RECEIPT_DIR,
                CODEX_HOOK.SUMMARY_DIR,
            ) = original_paths

        self.assertEqual(concurrent_results[0].returncode, 0, concurrent_results[0].stderr)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state["turn_count"], 0)
        self.assertEqual(self.session_summary()["turn_count"], 0)

    def test_malformed_numeric_telemetry_degrades_safely(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        state["compact_count"] = float("inf")
        self.state_file.write_text(json.dumps(state), encoding="utf-8")

        compact = self.run_hook("record-compact", {"session_id": "s1"})
        ended = self.run_hook("end-session", {"session_id": "s1"})

        self.assertEqual(compact.returncode, 0, compact.stderr)
        self.assertEqual(ended.returncode, 0, ended.stderr)
        self.assertEqual(self.session_summary()["compact_count"], 1)

    def test_malformed_verification_epochs_fail_closed(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        state.update(
            has_writes=True,
            last_write_epoch="not-a-number",
            lint_passed=True,
            lint_epoch=float("nan"),
        )
        self.state_file.write_text(json.dumps(state), encoding="utf-8")

        result = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Missing or stale: lint", result.stderr)

    def test_common_read_only_shell_commands_do_not_require_verification(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        read_only_commands = [
            "git diff",
            "git diff --stat",
            "git diff --name-only",
            "git grep needle",
            "git branch --show-current",
            "git ls-tree HEAD",
            "git show HEAD",
            "git status; git branch --show-current",
            "find . -maxdepth 1",
            "tree",
            "grep needle README.md",
            'sed -n "1,5p" README.md',
            "wc -l README.md",
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

    def test_common_inspection_does_not_invalidate_fresh_verification(self) -> None:
        commands = [
            "git diff",
            "git diff --stat",
            "git diff --name-only",
            "git grep needle",
            "git ls-tree HEAD",
            "find . -maxdepth 1",
            "tree",
            "grep needle README.md",
            'sed -n "1,5p" README.md',
            "wc -l README.md",
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
                allowed = self.run_hook(
                    "verify-stop",
                    {"session_id": "s1", "stop_hook_active": False},
                )
                self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_read_only_commands_with_write_options_still_invalidate_verification(self) -> None:
        commands = [
            "git diff --output=owned.txt",
            "find . -delete",
            "find . -exec python generate.py {} ;",
            "sed -i s/old/new/ README.md",
            "tree -o owned.txt",
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

    def test_receipt_remains_recoverable_until_state_is_persisted(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        receipt = self.receipt("lint")
        receipt_id = receipt.rsplit("receipt=", 1)[1].strip()
        payload = {
            "session_id": "s1",
            "tool_input": {"command": "./scripts/lint.sh"},
            "tool_response": receipt,
        }
        original_paths = (
            CODEX_HOOK.STATE_FILE,
            CODEX_HOOK.STATE_DIR,
            CODEX_HOOK.RECEIPT_DIR,
            CODEX_HOOK.SUMMARY_DIR,
        )
        CODEX_HOOK.STATE_FILE = self.state_file
        CODEX_HOOK.STATE_DIR = self.temp_dir
        CODEX_HOOK.RECEIPT_DIR = self.temp_dir / "receipts"
        CODEX_HOOK.SUMMARY_DIR = self.temp_dir / "summaries"
        original_save = CODEX_HOOK.save_json_atomic

        def fail_state_write(path: Path, value: dict) -> None:
            if path == self.state_file:
                raise OSError("simulated state persistence failure")
            original_save(path, value)

        try:
            with mock.patch.object(CODEX_HOOK, "save_json_atomic", side_effect=fail_state_write):
                with self.assertRaises(OSError):
                    CODEX_HOOK.record_shell(payload)
            claims = list((self.temp_dir / "receipts").glob(f"{receipt_id}-*.claim"))
            self.assertEqual(len(claims), 1)

            self.assertEqual(CODEX_HOOK.record_shell(payload), 0)
            self.assertFalse(claims[0].exists())
            successful_state = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.assertTrue(successful_state["lint_passed"])
            self.assertIn(receipt_id, successful_state["consumed_receipts"])
            self.assertEqual(CODEX_HOOK.reset_state({"session_id": "s1"}), 0)
            reset_state = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.assertFalse(reset_state["lint_passed"])
            self.assertIn(receipt_id, reset_state["consumed_receipts"])
        finally:
            (
                CODEX_HOOK.STATE_FILE,
                CODEX_HOOK.STATE_DIR,
                CODEX_HOOK.RECEIPT_DIR,
                CODEX_HOOK.SUMMARY_DIR,
            ) = original_paths

    def test_receipt_created_before_session_reset_cannot_verify_new_writes(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        stale_receipt = self.receipt("lint")
        self.assertEqual(
            self.run_hook("session-start", {"session_id": "s1", "source": "clear"}).returncode,
            0,
        )
        self.assertEqual(
            self.run_hook(
                "record-write",
                {"session_id": "s1", "tool_input": {"file_path": "README.md"}},
            ).returncode,
            0,
        )

        replay = self.run_hook(
            "record-shell",
            {
                "session_id": "s1",
                "tool_input": {"command": "./scripts/lint.sh"},
                "tool_response": stale_receipt,
            },
        )
        blocked = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})

        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("Missing or stale: lint", blocked.stderr)

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
