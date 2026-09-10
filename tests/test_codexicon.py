from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MANAGER_PATH = ROOT / "scripts" / "codexicon.py"
HOOK_PATH = ROOT / ".codex" / "hooks" / "codex_hook.py"
TEST_TEMP_ROOT = ROOT / ".codex-state" / "codexicon-tests"
SPEC = importlib.util.spec_from_file_location("codexicon_manager", MANAGER_PATH)
assert SPEC and SPEC.loader
CODEXICON = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CODEXICON
SPEC.loader.exec_module(CODEXICON)
HOOK_SPEC = importlib.util.spec_from_file_location("codex_hook", HOOK_PATH)
assert HOOK_SPEC and HOOK_SPEC.loader
CODEX_HOOK = importlib.util.module_from_spec(HOOK_SPEC)
sys.modules[HOOK_SPEC.name] = CODEX_HOOK
HOOK_SPEC.loader.exec_module(CODEX_HOOK)


def remove_test_directory(path: Path) -> None:
    """Remove Git-heavy fixtures reliably on Windows instead of hiding leaked state."""

    def make_writable(function, blocked_path, _error) -> None:
        os.chmod(blocked_path, stat.S_IWRITE)
        function(blocked_path)

    for attempt in range(6):
        try:
            shutil.rmtree(path, onerror=make_writable)
            return
        except FileNotFoundError:
            return
        except OSError:
            if attempt == 5:
                raise
            time.sleep(0.05 * (attempt + 1))


def run_fixture_git(*arguments: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Use Git only to construct an isolated temporary Ship-test fixture."""

    return subprocess.run(["git", *arguments], cwd=cwd, check=True)


class CodexiconManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TEST_TEMP_ROOT / uuid.uuid4().hex
        self.temp_dir.mkdir(parents=True)
        self.addCleanup(remove_test_directory, self.temp_dir)

    def test_hook_classifies_safe_manager_commands_across_shells(self) -> None:
        evidence = json.dumps({"task_id": "T-005"})
        cases = {
            "python ./scripts/codexicon.py spec-check": "inspection",
            r"& python .\scripts\codexicon.py tasks-next --json": "inspection",
            r"python .\scripts\codexicon.py spec-check --root .": "inspection",
            "python scripts/codexicon.py tasks-next --root . --json": "inspection",
            "python scripts/codexicon.py update --root target --source source": "inspection",
            "python scripts/codexicon.py tasks-done T-005 --evidence '" + evidence + "'": "bookkeeping",
            r"python .\scripts\codexicon.py tasks-blocked T-005 --reason waiting": "bookkeeping",
            "python scripts/codexicon.py tasks-next --unknown": None,
            "python scripts/codexicon.py tasks-done T-005 --evidence not-json": None,
            "python scripts/codexicon.py update --root target --source source --unknown": None,
            "python scripts/codexicon.py update --root target --source source && echo unsafe": None,
            "python scripts/codexicon.py adopt project --apply": "mutation",
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(CODEX_HOOK.codexicon_manager_classification(command), expected)

    def test_hook_preserves_evidence_for_bookkeeping_but_invalidates_mutations(self) -> None:
        evidence = json.dumps({"task_id": "T-005"})
        safe_payload = {
            "tool_name": "bash",
            "tool_input": {
                "command": "python scripts/codexicon.py tasks-done T-005 --evidence '" + evidence + "'"
            },
        }
        with mock.patch.object(CODEX_HOOK, "record_write") as record_write:
            self.assertEqual(CODEX_HOOK.prepare_tool(safe_payload), 0)
            self.assertEqual(CODEX_HOOK.record_shell(safe_payload), 0)
            record_write.assert_not_called()

        for command in (
            "python scripts/codexicon.py adopt project --apply",
            "printf changed > source.py",
        ):
            with self.subTest(command=command), mock.patch.object(
                CODEX_HOOK, "record_write", return_value=0
            ) as record_write:
                payload = {"tool_name": "bash", "tool_input": {"command": command}}
                self.assertEqual(CODEX_HOOK.record_shell(payload), 0)
                record_write.assert_called_once_with(payload, force_tests=True)

    def test_resume_context_is_bounded_authoritative_and_checkpoint_supplemental(self) -> None:
        root = self.temp_dir / "resume-context"
        root.mkdir()
        spec_text = (
            "# Specification\n\n**Revision:** test-1\n\n## Outcome\nValid.\n\n"
            "## Requirements\n- **R-001:** Requirement.\n\n## Interfaces\n"
            "- **I-001:** Interface.\n\n## Acceptance\n- **A-001:** Accept.\n\n"
            "## Anti-goals\n- **AG-001:** No transcript.\n"
        )
        (root / "SPEC.md").write_text(
            spec_text,
            encoding="utf-8",
        )
        digest = "sha256:" + hashlib.sha256(
            "\n".join(spec_text.splitlines()).encode("utf-8")
        ).hexdigest()
        (root / "TASKS.md").write_text(
            f"**Contract revision:** test-1\n**Contract digest:** {digest}\n\n"
            "| id | state | requirement | interface | scope | verification | Dependencies | Blocker | Evidence |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| T-001 | ACTIVE | R-001 | I-001 | safe.py | test | None | None | None |\n"
            "| T-002 | DONE | R-001 | I-001 | safe.py | test | None | None | not-json |\n"
            "| T-003 | DONE | R-001 | I-001 | safe.py | test | None | None | {\"contract_digest\":\"sha256:"
            + "0" * 64
            + "\"} |\n",
            encoding="utf-8",
        )
        context = CODEX_HOOK.build_resume_context(
            root, "agent_docs/sessions/checkpoint.md"
        )
        self.assertLessEqual(len(context), CODEX_HOOK.RESUME_CONTEXT_MAX_CHARS)
        self.assertIn("Authoritative reread required: SPEC.md and TASKS.md", context)
        self.assertIn("revision=test-1", context)
        self.assertIn("active=T-001 (ACTIVE)", context)
        self.assertIn("Next runnable action: resume T-001", context)
        self.assertIn("Checkpoint: agent_docs/sessions/checkpoint.md (supplemental", context)
        self.assertIn("no healthy evidence", context)
        self.assertIn("stale=1", context)
        self.assertIn("malformed=1", context)
        self.assertNotIn("safe.py", context)

    def test_resume_context_reports_stale_contract_malformed_state_and_blockers(self) -> None:
        root = self.temp_dir / "resume-errors"
        root.mkdir()
        (root / "SPEC.md").write_text(
            "# Specification\n\n**Revision:** current\n\n## Outcome\nValid.\n\n"
            "## Requirements\n- **R-001:** Requirement.\n\n## Interfaces\n"
            "- **I-001:** Interface.\n\n## Acceptance\n- **A-001:** Accept.\n\n"
            "## Anti-goals\n- **AG-001:** No transcript.\n",
            encoding="utf-8",
        )
        (root / "TASKS.md").write_text(
            "**Contract revision:** old\n**Contract digest:** sha256:" + "0" * 64 + "\n\n"
            "| id | state | requirement | interface | scope | verification | Dependencies | Blocker | Evidence |\n"
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
            "| T-001 | BLOCKED | R-001 | I-001 | safe.py | test | None | waiting | None |\n",
            encoding="utf-8",
        )
        context = CODEX_HOOK.build_resume_context(root)
        self.assertIn("stale contract baseline", context)

        (root / "TASKS.md").write_text(
            "| id | state | requirement | interface | scope | verification |\n"
            "| --- | --- | --- | --- | --- | --- |\n"
            "| T-001 | NOT_A_STATE | R-001 | I-001 | safe.py | test |\n",
            encoding="utf-8",
        )
        malformed = CODEX_HOOK.build_resume_context(root, None)
        self.assertIn("malformed task state", malformed)

    def test_session_start_resume_emits_additional_context_schema(self) -> None:
        root = self.temp_dir / "session-start"
        root.mkdir()
        state_root = root / ".state"
        payload = {"session_id": "session-start-test", "source": "compact"}
        output = io.StringIO()
        with (
            mock.patch.object(CODEX_HOOK, "ROOT", root),
            mock.patch.object(CODEX_HOOK, "STATE_ROOT", state_root),
            mock.patch.object(CODEX_HOOK, "STATE_DIR", state_root),
            contextlib.redirect_stdout(output),
        ):
            CODEX_HOOK.configure_state_file(payload)
            self.assertEqual(CODEX_HOOK.resume_state(payload), 0)
        rendered = json.loads(output.getvalue())
        self.assertEqual(rendered["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("additionalContext", rendered["hookSpecificOutput"])
        self.assertIn("SPEC.md and TASKS.md", rendered["hookSpecificOutput"]["additionalContext"])

    def make_source(
        self,
        name: str,
        files: dict[str, tuple[str, str]],
        version: str = "1.0.0",
    ) -> Path:
        root = self.temp_dir / name
        root.mkdir()
        (root / "TEMPLATE_VERSION").write_text(f"{version}\n", encoding="utf-8")
        manifest_files = []
        for relative, (policy, content) in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            manifest_files.append({"path": relative, "policy": policy})
        (root / ".codexicon.json").write_text(
            json.dumps({"schema_version": 1, "files": manifest_files}),
            encoding="utf-8",
        )
        return root

    def test_test_fixture_cleanup_handles_read_only_files(self) -> None:
        fixture = self.temp_dir / "cleanup-fixture"
        fixture.mkdir()
        read_only = fixture / "object"
        read_only.write_text("fixture\n", encoding="utf-8")
        os.chmod(read_only, stat.S_IREAD)

        remove_test_directory(fixture)

        self.assertFalse(fixture.exists())

    def write_contract(self, root: Path, *, include_anti_goal: bool = True) -> None:
        anti_goal = "- **AG-001:** No unrelated features.\n" if include_anti_goal else ""
        (root / "SPEC.md").write_text(
            "# Specification\n\n"
            "**Status:** ACTIVE\n\n"
            "## Outcome\n\n"
            "The service provides a useful result.\n\n"
            "## Requirements\n\n"
            "- **R-001:** The service returns a healthy response.\n\n"
            "## Interfaces\n\n"
            "- **I-001:** The health endpoint returns JSON.\n\n"
            "## Acceptance\n\n"
            "- **A-001:** The health check passes.\n\n"
            "## Anti-goals\n\n"
            + anti_goal
            + "\n## Assumptions\n\n- Local execution is sufficient.\n\n"
            "## Amendments\n\n- None.\n",
            encoding="utf-8",
        )

    def write_spec(self, root: Path, content: str) -> None:
        (root / "SPEC.md").write_text(content, encoding="utf-8")

    def valid_contract_text(self) -> str:
        return (
            "# Specification\n\n"
            "**Status:** ACTIVE\n\n"
            "## Outcome\n\n"
            "A useful local result is produced.\n\n"
            "## Requirements\n\n"
            "- **R-001:** The service returns a useful result.\n\n"
            "## Interfaces\n\n"
            "- **I-001:** The service exposes the result.\n\n"
            "## Acceptance\n\n"
            "- **A-001:** The result is verified.\n\n"
            "## Anti-goals\n\n"
            "- **AG-001:** No unrelated behavior is included.\n\n"
            "## Amendments\n\n"
            "- None.\n"
        )

    def test_spec_check_requires_active_contract_and_anti_goals(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.assertEqual(self.run_quietly(CODEXICON.contract_check, root), 0)

        self.write_contract(root, include_anti_goal=False)
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "Anti-goals"):
            CODEXICON.contract_check(root)

    def test_spec_check_rejects_fenced_duplicate_conflicting_missing_placeholder_and_boundary(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        cases = {
            "fenced-only": (
                "# Specification\n\n**Status:** ACTIVE\n\n"
                "```markdown\n"
                + self.valid_contract_text()
                + "```\n"
            ),
            "duplicate-id": self.valid_contract_text().replace(
                "## Interfaces\n\n", "- **R-001:** Duplicated identifier.\n\n## Interfaces\n\n"
            ),
            "conflicting-status": self.valid_contract_text().replace(
                "**Status:** ACTIVE", "**Status:** ACTIVE\n**Status:** DRAFT"
            ),
            "missing-outcome": self.valid_contract_text().replace(
                "## Outcome\n\nA useful local result is produced.\n\n", ""
            ),
            "placeholder": self.valid_contract_text().replace(
                "A useful local result is produced.", "[Observable result.]"
            ),
            "section-boundary": self.valid_contract_text().replace(
                "## Requirements\n\n- **R-001:** The service returns a useful result.\n\n",
                "## Requirements\n\n## Notes\n\n- **R-001:** The service returns a useful result.\n\n",
            ),
        }
        expected = {
            "fenced-only": "missing required section",
            "duplicate-id": "duplicate SPEC.md ID",
            "conflicting-status": "exactly one unambiguous",
            "missing-outcome": "missing required section",
            "placeholder": "placeholder definition",
            "section-boundary": "no entries in: Requirements",
        }
        for name, content in cases.items():
            with self.subTest(case=name):
                self.write_spec(root, content)
                with self.assertRaisesRegex(CODEXICON.CodexiconError, expected[name]):
                    CODEXICON.contract_check(root)

    def test_contract_identity_is_stable_and_task_binding_detects_drift(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        first = CODEXICON.read_contract_details(root)
        second = CODEXICON.read_contract_details(root)
        self.assertEqual(first.identity, second.identity)
        self.assertEqual(first.revision, "0")
        self.assertEqual(CODEXICON.contract_identity(root)["digest"], first.digest)

        (root / "TASKS.md").write_text(
            f"**Contract revision:** {first.revision}\n"
            f"**Contract digest:** {first.identity}\n\n"
            "| ID | State | Requirement | Interface | Scope | Verification |\n"
            "|---|---|---|---|---|---|\n"
            "| T-001 | TODO | R-001 | I-001 | src | test |\n",
            encoding="utf-8",
        )
        self.assertEqual(CODEXICON.tasks_next(root), 0)
        self.write_spec(root, self.valid_contract_text().replace(
            "A useful local result is produced.", "A changed local result is produced."
        ))
        changed = CODEXICON.read_contract_details(root)
        self.assertNotEqual(changed.digest, first.digest)
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "contract drift"):
            CODEXICON.tasks_next(root)

    def test_spec_check_rejects_unknown_structural_reference(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_spec(
            root,
            self.valid_contract_text().replace(
                "The result is verified.", "The result verifies R-999."
            ),
        )
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "unknown contract ID.*R-999"):
            CODEXICON.contract_check(root)

    def test_task_register_traces_requirements_and_supports_state_transitions(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        tasks = root / "TASKS.md"
        tasks.write_text(
            "# Task Register\n\n"
            "| ID | State | Requirement | Interface | Scope | Verification |\n"
            "|---|---|---|---|---|---|\n"
            "| T-001 | TODO | R-001 | I-001 | `src/health.py` | `pytest tests/test_health.py` |\n",
            encoding="utf-8",
        )

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(CODEXICON.tasks_next(root), 0)
        self.assertIn("T-001 | R-001 | I-001", output.getvalue())
        self.assertEqual(CODEXICON.tasks_set_state(root, "T-001", "ACTIVE"), 0)
        self.assertIn("| T-001 | ACTIVE |", tasks.read_text(encoding="utf-8"))
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "completion evidence"):
            CODEXICON.tasks_set_state(root, "T-001", "DONE")
        self.assertIn("| T-001 | ACTIVE |", tasks.read_text(encoding="utf-8"))

    def test_task_register_rejects_orphan_requirement(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        (root / "TASKS.md").write_text(
            "| ID | State | Requirement | Interface | Scope | Verification |\n"
            "|---|---|---|---|---|---|\n"
            "| T-001 | TODO | R-999 | I-001 | src | test |\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "missing requirement"):
            CODEXICON.tasks_next(root)

    def write_tasks(self, root: Path, body: str, *, line_ending: str = "\n") -> None:
        content = body.replace("\n", line_ending)
        (root / "TASKS.md").write_bytes(content.encode("utf-8"))

    def test_task_register_accepts_whitespace_crlf_and_ignores_fenced_examples(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.write_tasks(
            root,
            "# Task Register\n\n"
            "```markdown\n"
            "| ID | State | Requirement | Interface | Scope | Verification |\n"
            "|---|---|---|---|---|---|\n"
            "| T-999 | TODO | R-001 | I-001 | hidden | hidden |\n"
            "```\n\n"
            "  | ID | State | Requirement | Interface | Scope | Verification |  \n"
            "  | --- | --- | --- | --- | --- | --- |  \n"
            "  | T-001 | TODO | R-001 | I-001 | src | test |  \n",
            line_ending="\r\n",
        )

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(CODEXICON.tasks_next(root), 0)
        self.assertIn("T-001 | R-001 | I-001", output.getvalue())
        self.assertEqual(CODEXICON.tasks_set_state(root, "T-001", "ACTIVE"), 0)
        self.assertIn(b"\r\n  | T-001 | ACTIVE |", (root / "TASKS.md").read_bytes())

    def test_task_register_rejects_malformed_unfinished_work_after_done_row(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.write_tasks(
            root,
            "| ID | State | Requirement | Interface | Scope | Verification |\n"
            "|---|---|---|---|---|---|\n"
            "| T-001 | DONE | R-001 | I-001 | src | test |\n"
            "| T-002 | TODO | R-001 | I-001 | src | test\n",
        )

        with self.assertRaisesRegex(CODEXICON.CodexiconError, r"line 4: malformed task row"):
            CODEXICON.tasks_next(root)

    def test_task_register_rejects_invalid_columns_and_pipe_syntax_with_line_numbers(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        cases = (
            (
                "| T-001 | TODO | R-001 | I-001 | src | test | extra |\n",
                r"line 3: malformed task row; expected 6 columns, found 7",
            ),
            (
                "| T-001 | TODO | R-001 | I-001 | src | test\n",
                r"line 3: malformed task row; expected a leading and trailing pipe",
            ),
            (
                r"| T-001 | TODO | R-001 | I-001 | src \| detail | test |\n",
                r"line 3: unsupported escaped pipe",
            ),
        )
        for row, expected in cases:
            with self.subTest(expected=expected):
                self.write_tasks(
                    root,
                    "| ID | State | Requirement | Interface | Scope | Verification |\n"
                    "|---|---|---|---|---|---|\n"
                    + row,
                )
                with self.assertRaisesRegex(CODEXICON.CodexiconError, expected):
                    CODEXICON.tasks_next(root)

    def test_task_register_rejects_multiple_references_and_duplicate_ids(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.write_tasks(
            root,
            "| ID | State | Requirement | Interface | Scope | Verification |\n"
            "|---|---|---|---|---|---|\n"
            "| T-001 | TODO | R-001, R-001 | I-001 | src | test |\n",
        )
        with self.assertRaisesRegex(CODEXICON.CodexiconError, r"line 3: T-001 has multiple requirement"):
            CODEXICON.tasks_next(root)

        self.write_tasks(
            root,
            "| ID | State | Requirement | Interface | Scope | Verification |\n"
            "|---|---|---|---|---|---|\n"
            "| T-001 | TODO | R-001 | I-001, I-001 | src | test |\n",
        )
        with self.assertRaisesRegex(CODEXICON.CodexiconError, r"line 3: T-001 has multiple interface"):
            CODEXICON.tasks_next(root)

        self.write_tasks(
            root,
            "| ID | State | Requirement | Interface | Scope | Verification |\n"
            "|---|---|---|---|---|---|\n"
            "| T-001 | TODO | R-001 | I-001 | src | test |\n"
            "| T-001 | ACTIVE | R-001 | I-001 | src | test |\n",
        )
        with self.assertRaisesRegex(CODEXICON.CodexiconError, r"line 4: duplicate task ID: T-001"):
            CODEXICON.tasks_next(root)

    def test_task_register_rejects_task_like_rows_outside_declared_table(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.write_tasks(
            root,
            "| ID | State | Requirement | Interface | Scope | Verification |\n"
            "|---|---|---|---|---|---|\n"
            "| T-001 | TODO | R-001 | I-001 | src | test |\n\n"
            "| T-002 | TODO | R-001 | I-001 | src | test |\n",
        )
        with self.assertRaisesRegex(
            CODEXICON.CodexiconError,
            r"line 5: task-like row is outside the declared task table",
        ):
            CODEXICON.tasks_next(root)

    def write_extended_tasks(self, root: Path, rows: str) -> None:
        self.write_tasks(
            root,
            "# Task Register\n\n"
            "**Register format:** 2\n\n"
            "| ID | State | Requirement | Interface | Scope | Verification | Dependencies | Blocker | Evidence |\n"
            "|---|---|---|---|---|---|---|---|---|\n"
            + rows,
        )

    def task_evidence(
        self,
        root: Path,
        task_id: str = "T-001",
        *,
        acceptance_ids: list[str] | None = None,
        checks: list[dict[str, object]] | None = None,
        **overrides: object,
    ) -> str:
        row = next(row for row in CODEXICON.task_rows(root)[1] if row["id"] == task_id)
        contract = CODEXICON.read_contract_details(root)
        value: dict[str, object] = {
            "schema_version": 1,
            "task_id": task_id,
            "acceptance_ids": acceptance_ids or ["A-001"],
            "checks": checks
            or [
                {
                    "identity": "task-verification",
                    "command": ["python", "-m", "unittest", "tests.test_codexicon"],
                    "result": "passed",
                }
            ],
            "result": "passed",
            "timestamp": CODEXICON.utc_now(),
            "source_digest": CODEXICON.relevant_source_digest(root, row),
            "contract_digest": contract.identity,
        }
        value.update(overrides)
        return json.dumps(value)

    def test_queue_resumes_active_before_todo_and_reports_complete_distinctly(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.write_extended_tasks(
            root,
            "| T-001 | ACTIVE | R-001 | I-001 | src | test | None | None | None |\n"
            "| T-002 | TODO | R-001 | I-001 | src | test | None | None | None |\n",
        )
        selection = CODEXICON.select_runnable_task(CODEXICON.task_rows(root)[1])
        self.assertEqual(selection.outcome, "RESUME_ACTIVE")
        self.assertEqual(selection.task["id"], "T-001")

        self.write_extended_tasks(
            root,
            "| T-001 | BLOCKED | R-001 | I-001 | src | test | None | waiting | None |\n",
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(CODEXICON.tasks_next(root), 3)
        self.assertIn("[BLOCKED]", output.getvalue())

        self.write_extended_tasks(
            root,
            "| T-001 | DONE | R-001 | I-001 | src | test | None | None | None |\n",
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(CODEXICON.tasks_next(root), 3)
        self.assertIn("[BLOCKED]", output.getvalue())

    def test_queue_blocks_dependencies_but_keeps_independent_work_runnable(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.write_extended_tasks(
            root,
            "| T-001 | TODO | R-001 | I-001 | consumer | test | T-002 | None | None |\n"
            "| T-002 | BLOCKED | R-001 | I-001 | dependency | test | None | external wait | None |\n"
            "| T-003 | TODO | R-001 | I-001 | independent | test | None | None | None |\n",
        )
        selection = CODEXICON.select_runnable_task(CODEXICON.task_rows(root)[1])
        self.assertEqual(selection.outcome, "READY")
        self.assertEqual(selection.task["id"], "T-003")

        self.write_extended_tasks(
            root,
            "| T-001 | TODO | R-001 | I-001 | consumer | test | T-002 | None | None |\n"
            "| T-002 | BLOCKED | R-001 | I-001 | dependency | test | None | external wait | None |\n",
        )
        self.assertEqual(CODEXICON.tasks_next(root), 3)

    def test_queue_rejects_unknown_and_cyclic_dependencies(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.write_extended_tasks(
            root,
            "| T-001 | TODO | R-001 | I-001 | src | test | T-999 | None | None |\n",
        )
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "unknown dependency"):
            CODEXICON.tasks_next(root)
        self.write_extended_tasks(
            root,
            "| T-001 | TODO | R-001 | I-001 | src | test | T-002 | None | None |\n"
            "| T-002 | TODO | R-001 | I-001 | src | test | T-001 | None | None |\n",
        )
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "dependency cycle"):
            CODEXICON.tasks_next(root)

    def test_task_transitions_are_legal_and_single_owner(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.write_extended_tasks(
            root,
            "| T-001 | TODO | R-001 | I-001 | src | `python -m unittest tests.test_codexicon` | None | None | None |\n"
            "| T-002 | TODO | R-001 | I-001 | src | test | None | None | None |\n",
        )
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "illegal task transition"):
            CODEXICON.tasks_set_state(root, "T-001", "DONE")
        CODEXICON.tasks_set_state(root, "T-001", "ACTIVE")
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "implementation slot"):
            CODEXICON.tasks_set_state(root, "T-002", "ACTIVE")
        evidence = self.task_evidence(root)
        CODEXICON.tasks_set_state(root, "T-001", "DONE", evidence=evidence)
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "illegal task transition"):
            CODEXICON.tasks_set_state(root, "T-001", "ACTIVE")
        CODEXICON.tasks_reopen(root, "T-001", reason="regression found", expected="DONE")
        self.assertEqual(CODEXICON.task_rows(root)[1][0]["state"], "TODO")

    def test_done_requires_current_task_receipt_and_does_not_execute_command_text(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.write_extended_tasks(
            root,
            "| T-001 | ACTIVE | R-001 | I-001 | docs/build-contracts.md | `python -m unittest tests.test_codexicon` | None | None | None |\n",
        )
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "evidence"):
            CODEXICON.tasks_set_state(root, "T-001", "DONE")
        self.assertEqual(CODEXICON.task_rows(root)[1][0]["state"], "ACTIVE")

        evidence = json.loads(self.task_evidence(root))
        evidence["checks"][0]["command"] = "python -m unittest tests.test_codexicon"
        evidence["checks"][0]["reviewed"] = True
        with mock.patch.object(CODEXICON.subprocess, "run") as run:
            CODEXICON.tasks_set_state(root, "T-001", "DONE", evidence=json.dumps(evidence))
        run.assert_not_called()
        stored = CODEXICON.task_rows(root)[1][0]["evidence"]
        self.assertEqual(json.loads(stored)["result"], "passed")

    def test_done_rejects_wrong_and_stale_receipts(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.write_extended_tasks(
            root,
            "| T-001 | ACTIVE | R-001 | I-001 | src | `python -m unittest tests.test_codexicon` | None | None | None |\n",
        )
        wrong_value = json.loads(self.task_evidence(root))
        wrong_value["task_id"] = "T-999"
        wrong = json.dumps(wrong_value)
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "wrong task"):
            CODEXICON.tasks_set_state(root, "T-001", "DONE", evidence=wrong)
        stale = json.loads(self.task_evidence(root))
        stale["source_digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "source digest"):
            CODEXICON.tasks_set_state(root, "T-001", "DONE", evidence=json.dumps(stale))

    def test_complete_requires_acceptance_coverage_and_final_checks(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.write_extended_tasks(
            root,
            "| T-001 | ACTIVE | R-001 | I-001 | src | `python -m unittest tests.test_codexicon` | None | None | None |\n",
        )
        evidence = json.loads(
            self.task_evidence(
                root,
                acceptance_ids=["A-001"],
                checks=[
                    {"identity": "task-verification", "command": ["python", "-m", "unittest", "tests.test_codexicon"], "result": "passed"},
                    {"identity": "lint", "command": ["scripts/lint.sh"], "result": "passed"},
                    {"identity": "test", "command": ["scripts/test.sh"], "result": "passed"},
                    {"identity": "security", "command": ["scripts/security.sh"], "result": "passed"},
                ],
            )
        )
        CODEXICON.tasks_set_state(root, "T-001", "DONE", evidence=json.dumps(evidence))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(CODEXICON.tasks_next(root), 0)
        self.assertIn("[COMPLETE]", output.getvalue())

    def test_task_update_conflict_preserves_concurrent_edit(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.write_extended_tasks(
            root,
            "| T-001 | TODO | R-001 | I-001 | src | test | None | None | None |\n",
        )
        tasks = root / "TASKS.md"
        original = tasks.read_bytes()
        concurrent = original.replace(b"| T-001 | TODO |", b"| T-001 | BLOCKED |")
        tasks.write_bytes(concurrent)
        with self.assertRaisesRegex(CODEXICON.CodexiconError, "changed concurrently"):
            CODEXICON._write_task_register_if_unchanged(tasks, original, b"lost edit")
        self.assertEqual(tasks.read_bytes(), concurrent)

    def test_legacy_register_migrates_to_metadata_format_and_persists_blocker(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        self.write_contract(root)
        self.write_tasks(
            root,
            "# Task Register\n\n"
            "| ID | State | Requirement | Interface | Scope | Verification |\n"
            "|---|---|---|---|---|---|\n"
            "| T-001 | TODO | R-001 | I-001 | src | test |\n",
        )
        self.assertEqual(CODEXICON.migrate_task_register(root), 0)
        text = (root / "TASKS.md").read_text(encoding="utf-8")
        self.assertIn("Dependencies", text)
        self.assertIn("**Contract digest:** sha256:", text)
        CODEXICON.tasks_set_state(root, "T-001", "BLOCKED", reason="needs input")
        self.assertEqual(CODEXICON.task_rows(root)[1][0]["blocker"], "needs input")

    def test_test_fixture_cleanup_retries_and_reports_exhaustion(self) -> None:
        fixture = self.temp_dir / "retry-fixture"
        with (
            mock.patch.object(shutil, "rmtree", side_effect=[OSError("busy"), None]) as remove,
            mock.patch.object(time, "sleep") as sleep,
        ):
            remove_test_directory(fixture)
        self.assertEqual(remove.call_count, 2)
        sleep.assert_called_once()

        with (
            mock.patch.object(shutil, "rmtree", side_effect=OSError("still busy")) as remove,
            mock.patch.object(time, "sleep"),
            self.assertRaisesRegex(OSError, "still busy"),
        ):
            remove_test_directory(fixture)
        self.assertEqual(remove.call_count, 6)

    def run_quietly(self, function, *args, **kwargs):
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            return function(*args, **kwargs)

    def test_inspect_is_read_only_and_reports_required_project_files(self) -> None:
        source = self.make_source(
            "source",
            {
                "managed.txt": ("managed", "managed\n"),
                "AGENTS.md": ("project", "source guidance\n"),
            },
        )
        target = self.temp_dir / "target"
        target.mkdir()

        result = self.run_quietly(
            CODEXICON.run_install,
            source,
            target,
            apply=False,
            update=False,
        )

        self.assertEqual(result, 2)
        self.assertEqual(list(target.iterdir()), [])

    def test_adoption_creates_absent_files_and_preserves_conflicts(self) -> None:
        source = self.make_source(
            "source",
            {
                "managed.txt": ("managed", "managed\n"),
                "merge.txt": ("merge", "source merge\n"),
                "AGENTS.md": ("project", "source guidance\n"),
            },
        )
        target = self.temp_dir / "target"
        target.mkdir()
        (target / "merge.txt").write_text("project merge\n", encoding="utf-8")
        (target / "AGENTS.md").write_text("project guidance\n", encoding="utf-8")

        result = self.run_quietly(
            CODEXICON.run_install,
            source,
            target,
            apply=True,
            update=False,
        )

        self.assertEqual(result, 2)
        self.assertEqual((target / "managed.txt").read_text(encoding="utf-8"), "managed\n")
        self.assertEqual((target / "merge.txt").read_text(encoding="utf-8"), "project merge\n")
        self.assertEqual((target / "AGENTS.md").read_text(encoding="utf-8"), "project guidance\n")
        lock = json.loads((target / ".codexicon.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["unresolved"], ["merge.txt"])
        self.assertNotIn("merge.txt", lock["files"])

    @unittest.skipIf(os.name == "nt", "filesystem execute modes are not portable on Windows")
    def test_adoption_journals_mode_correction_for_identical_executable_file(self) -> None:
        source = self.make_source("mode-source", {"tool.sh": ("managed", "#!/bin/sh\n")})
        source.joinpath("tool.sh").chmod(0o755)
        manifest_path = source / ".codexicon.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][0]["executable"] = True
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        target = self.temp_dir / "mode-target"
        target.mkdir()
        target_file = target / "tool.sh"
        target_file.write_bytes((source / "tool.sh").read_bytes())
        target_file.chmod(0o644)

        actions, _ = CODEXICON.install_plan(
            source, target, CODEXICON.load_manifest(source), None, update=False
        )
        self.assertEqual(
            next(item for item in actions if item["path"] == "tool.sh")["action"],
            "mode-correction",
        )
        self.assertEqual(
            self.run_quietly(CODEXICON.run_install, source, target, apply=True, update=False),
            0,
        )
        self.assertTrue(target_file.stat().st_mode & 0o111)

    @unittest.skipIf(os.name == "nt", "filesystem execute modes are not portable on Windows")
    def test_mode_correction_rollback_restores_original_mode(self) -> None:
        source = self.make_source("rollback-mode-source", {"tool.sh": ("managed", "#!/bin/sh\n")})
        source.joinpath("tool.sh").chmod(0o755)
        manifest_path = source / ".codexicon.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][0]["executable"] = True
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        target = self.temp_dir / "rollback-mode-target"
        target.mkdir()
        target_file = target / "tool.sh"
        target_file.write_bytes((source / "tool.sh").read_bytes())
        target_file.chmod(0o644)
        actions, next_lock = CODEXICON.install_plan(
            source, target, CODEXICON.load_manifest(source), None, update=False
        )
        original_apply = CODEXICON.apply_operation

        def interrupt_after_correction(source_root, target_root, operation):
            result = original_apply(source_root, target_root, operation)
            if operation["path"] == "tool.sh":
                raise KeyboardInterrupt()
            return result

        with mock.patch.object(CODEXICON, "apply_operation", side_effect=interrupt_after_correction):
            with self.assertRaises(KeyboardInterrupt):
                CODEXICON.apply_transaction(source, target, actions, next_lock)
        self.assertEqual(target_file.stat().st_mode & 0o777, 0o644)

    @unittest.skipIf(os.name == "nt", "filesystem execute modes are not portable on Windows")
    def test_project_owned_mode_is_preserved(self) -> None:
        source = self.make_source("project-mode-source", {"AGENTS.md": ("project", "guidance\n")})
        manifest_path = source / ".codexicon.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][0]["executable"] = True
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        target = self.temp_dir / "project-mode-target"
        target.mkdir()
        target_file = target / "AGENTS.md"
        target_file.write_bytes((source / "AGENTS.md").read_bytes())
        target_file.chmod(0o644)

        result = self.run_quietly(CODEXICON.run_install, source, target, apply=True, update=False)
        self.assertEqual(result, 2)
        self.assertEqual(target_file.stat().st_mode & 0o777, 0o644)

    def test_update_changes_only_unchanged_files_and_removes_retired_files(self) -> None:
        source1 = self.make_source(
            "source1",
            {
                "a.txt": ("managed", "a1\n"),
                "b.txt": ("managed", "b1\n"),
            },
            "1.0.0",
        )
        target = self.temp_dir / "target"
        target.mkdir()
        self.assertEqual(
            self.run_quietly(
                CODEXICON.run_install,
                source1,
                target,
                apply=True,
                update=False,
            ),
            0,
        )
        source2 = self.make_source(
            "source2",
            {"a.txt": ("managed", "a2\n")},
            "1.1.0",
        )

        updated = self.run_quietly(
            CODEXICON.run_install,
            source2,
            target,
            apply=True,
            update=True,
        )

        self.assertEqual(updated, 0)
        self.assertEqual((target / "a.txt").read_text(encoding="utf-8"), "a2\n")
        self.assertFalse((target / "b.txt").exists())
        target.joinpath("a.txt").write_text("project edit\n", encoding="utf-8")
        source3 = self.make_source(
            "source3",
            {"a.txt": ("managed", "a3\n")},
            "1.2.0",
        )
        conflicted = self.run_quietly(
            CODEXICON.run_install,
            source3,
            target,
            apply=True,
            update=True,
        )
        self.assertEqual(conflicted, 2)
        self.assertEqual((target / "a.txt").read_text(encoding="utf-8"), "project edit\n")

    def test_update_preserves_local_deletion_as_a_conflict(self) -> None:
        source1 = self.make_source("source1", {"a.txt": ("managed", "a1\n")})
        target = self.temp_dir / "target"
        target.mkdir()
        self.assertEqual(
            self.run_quietly(
                CODEXICON.run_install, source1, target, apply=True, update=False
            ),
            0,
        )
        (target / "a.txt").unlink()
        source2 = self.make_source(
            "source2", {"a.txt": ("managed", "a2\n")}, version="1.1.0"
        )

        result = self.run_quietly(
            CODEXICON.run_install, source2, target, apply=True, update=True
        )

        self.assertEqual(result, 2)
        self.assertFalse((target / "a.txt").exists())
        lock = json.loads((target / ".codexicon.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["unresolved"], ["a.txt"])

    def test_repeated_adopt_refuses_to_restore_a_local_deletion(self) -> None:
        source = self.make_source("source", {"a.txt": ("managed", "a1\n")})
        target = self.temp_dir / "target"
        target.mkdir()
        self.run_quietly(
            CODEXICON.run_install, source, target, apply=True, update=False
        )
        (target / "a.txt").unlink()

        with self.assertRaises(CODEXICON.CodexiconError):
            CODEXICON.run_install(source, target, apply=True, update=False)

        self.assertFalse((target / "a.txt").exists())

    def test_apply_refuses_target_changed_after_planning(self) -> None:
        source1 = self.make_source("source1", {"a.txt": ("managed", "a1\n")})
        target = self.temp_dir / "target"
        target.mkdir()
        self.run_quietly(
            CODEXICON.run_install, source1, target, apply=True, update=False
        )
        source2 = self.make_source(
            "source2", {"a.txt": ("managed", "a2\n")}, version="1.1.0"
        )
        manifest = CODEXICON.load_manifest(source2)
        old_lock = CODEXICON.load_lock(target, required=True)
        actions, next_lock = CODEXICON.install_plan(
            source2, target, manifest, old_lock, update=True
        )
        (target / "a.txt").write_text("concurrent edit\n", encoding="utf-8")

        with self.assertRaises(CODEXICON.CodexiconError):
            CODEXICON.apply_transaction(source2, target, actions, next_lock)

        self.assertEqual((target / "a.txt").read_text(encoding="utf-8"), "concurrent edit\n")
        self.assertFalse(CODEXICON.transaction_path(target).exists())

    def test_apply_refuses_source_file_drift_before_writing_target(self) -> None:
        source1 = self.make_source("source1", {"a.txt": ("managed", "a1\n")})
        target = self.temp_dir / "target"
        target.mkdir()
        self.run_quietly(CODEXICON.run_install, source1, target, apply=True, update=False)
        source2 = self.make_source(
            "source2", {"a.txt": ("managed", "a2\n")}, version="1.1.0"
        )
        manifest = CODEXICON.load_manifest(source2)
        old_lock = CODEXICON.load_lock(target, required=True)
        actions, next_lock = CODEXICON.install_plan(
            source2, target, manifest, old_lock, update=True
        )
        (source2 / "a.txt").write_text("drifted\n", encoding="utf-8")

        with self.assertRaisesRegex(CODEXICON.CodexiconError, "source changed after planning"):
            CODEXICON.apply_transaction(source2, target, actions, next_lock)

        self.assertEqual((target / "a.txt").read_text(encoding="utf-8"), "a1\n")
        self.assertEqual(CODEXICON.load_lock(target, required=True), old_lock)
        self.assertFalse(CODEXICON.transaction_path(target).exists())

    def test_apply_refuses_source_manifest_drift_before_writing_target(self) -> None:
        source = self.make_source("source", {"a.txt": ("managed", "a\n")})
        target = self.temp_dir / "target"
        target.mkdir()
        manifest = CODEXICON.load_manifest(source)
        actions, next_lock = CODEXICON.install_plan(source, target, manifest, None, update=False)
        (source / ".codexicon.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "version": "1.0.0",
                    "files": [{"path": "a.txt", "policy": "managed"}],
                }
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(CODEXICON.CodexiconError, "source manifest changed after planning"):
            CODEXICON.apply_transaction(source, target, actions, next_lock)

        self.assertFalse((target / "a.txt").exists())
        self.assertFalse((target / ".codexicon.lock.json").exists())
        self.assertFalse(CODEXICON.transaction_path(target).exists())

    def test_interrupted_transaction_rolls_back_and_recovers(self) -> None:
        source = self.make_source(
            "source",
            {
                "a.txt": ("managed", "a\n"),
                "b.txt": ("managed", "b\n"),
            },
        )
        target = self.temp_dir / "target"
        target.mkdir()
        manifest = CODEXICON.load_manifest(source)
        actions, next_lock = CODEXICON.install_plan(
            source,
            target,
            manifest,
            None,
            update=False,
        )
        original = CODEXICON.apply_operation
        calls = 0

        def interrupt(source_root, target_root, operation):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise KeyboardInterrupt()
            return original(source_root, target_root, operation)

        with mock.patch.object(CODEXICON, "apply_operation", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                CODEXICON.apply_transaction(source, target, actions, next_lock)

        self.assertFalse((target / "a.txt").exists())
        self.assertFalse((target / "b.txt").exists())
        self.assertFalse(CODEXICON.transaction_path(target).exists())
        self.assertEqual(
            self.run_quietly(
                CODEXICON.run_install,
                source,
                target,
                apply=True,
                update=False,
            ),
            0,
        )

    def test_next_run_recovers_a_persisted_partial_transaction(self) -> None:
        target = self.temp_dir / "target"
        target.mkdir()
        source = self.make_source(
            "recovery-source",
            {"created.txt": ("managed", "partial\n")},
        )
        manifest = CODEXICON.load_manifest(source)
        actions, next_lock = CODEXICON.install_plan(
            source, target, manifest, None, update=False
        )
        transaction_id, operations = CODEXICON.build_operations(
            source, target, actions, next_lock
        )
        operations = [
            {
                key: value
                for key, value in operation.items()
                if key not in {"source_sha256", "source_manifest_sha256"}
            }
            for operation in operations
        ]
        created = target / "created.txt"
        created.write_text("partial\n", encoding="utf-8")
        journal = {
            "schema_version": 1,
            "format": "codexicon-transaction-v1",
            "transaction_id": transaction_id,
            "repository_id": CODEXICON.repository_identity(target),
            "created_at": CODEXICON.utc_now(),
            "phase": "applying",
            "backup_root": f".codexicon/backups/{transaction_id}",
            "applied": 1,
            "operations": operations,
        }
        CODEXICON.atomic_write_json(CODEXICON.transaction_path(target), journal)

        with self.assertRaises(CODEXICON.CodexiconError):
            CODEXICON.run_install(
                source,
                target,
                apply=False,
                update=False,
            )
        self.assertTrue(created.exists())
        self.assertTrue(CODEXICON.transaction_path(target).exists())

        self.run_quietly(CODEXICON.recover_transaction, target)

        self.assertFalse(created.exists())
        self.assertFalse(CODEXICON.transaction_path(target).exists())

    def test_malformed_transaction_cannot_delete_an_existing_file(self) -> None:
        target = self.temp_dir / "target"
        target.mkdir()
        victim = target / "victim.txt"
        victim.write_text("project data\n", encoding="utf-8")
        journal = {
            "schema_version": 1,
            "created_at": CODEXICON.utc_now(),
            "backup_root": ".codexicon/backups/forged",
            "applied": 1,
            "operations": [
                {
                    "action": "write",
                    "path": "victim.txt",
                    "backup": None,
                    "target_mode": None,
                }
            ],
        }
        CODEXICON.atomic_write_json(CODEXICON.transaction_path(target), journal)

        with self.assertRaises(CODEXICON.CodexiconError):
            CODEXICON.recover_transaction(target)

        self.assertEqual(victim.read_text(encoding="utf-8"), "project data\n")
        self.assertTrue(CODEXICON.transaction_path(target).exists())

    def test_committed_transaction_recovery_finishes_cleanup_without_rollback(self) -> None:
        target = self.temp_dir / "target"
        target.mkdir()
        source = self.make_source(
            "committed-source",
            {"created.txt": ("managed", "complete\n")},
        )
        manifest = CODEXICON.load_manifest(source)
        actions, next_lock = CODEXICON.install_plan(
            source, target, manifest, None, update=False
        )
        transaction_id, operations = CODEXICON.build_operations(
            source, target, actions, next_lock
        )
        for operation in operations:
            CODEXICON.apply_operation(source, target, operation)
        journal = {
            "schema_version": 1,
            "format": "codexicon-transaction-v1",
            "transaction_id": transaction_id,
            "repository_id": CODEXICON.repository_identity(target),
            "created_at": CODEXICON.utc_now(),
            "phase": "committed",
            "backup_root": f".codexicon/backups/{transaction_id}",
            "applied": len(operations),
            "operations": operations,
        }
        CODEXICON.atomic_write_json(CODEXICON.transaction_path(target), journal)

        self.run_quietly(CODEXICON.recover_transaction, target)

        self.assertEqual((target / "created.txt").read_text(encoding="utf-8"), "complete\n")
        self.assertTrue((target / ".codexicon.lock.json").is_file())
        self.assertFalse(CODEXICON.transaction_path(target).exists())

    def test_cleanup_failure_keeps_committed_journal_for_next_run(self) -> None:
        source1 = self.make_source("source1", {"created.txt": ("managed", "before\n")})
        target = self.temp_dir / "target"
        target.mkdir()
        self.run_quietly(
            CODEXICON.run_install, source1, target, apply=True, update=False
        )
        source2 = self.make_source(
            "source2", {"created.txt": ("managed", "complete\n")}, version="1.1.0"
        )
        original_rmtree = CODEXICON.shutil.rmtree

        with (
            mock.patch.object(CODEXICON.shutil, "rmtree", side_effect=OSError("busy")),
            self.assertRaises(OSError),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            CODEXICON.run_install(source2, target, apply=True, update=True)

        journal_path = CODEXICON.transaction_path(target)
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        self.assertEqual(journal["phase"], "committed")
        self.assertEqual((target / "created.txt").read_text(encoding="utf-8"), "complete\n")
        with mock.patch.object(CODEXICON.shutil, "rmtree", side_effect=original_rmtree):
            self.run_quietly(CODEXICON.recover_transaction, target)
        self.assertFalse(journal_path.exists())
        self.assertEqual((target / "created.txt").read_text(encoding="utf-8"), "complete\n")

    def test_cleanup_after_backup_deletion_is_retryable(self) -> None:
        source1 = self.make_source("source1", {"a.txt": ("managed", "before\n")})
        target = self.temp_dir / "target"
        target.mkdir()
        self.run_quietly(CODEXICON.run_install, source1, target, apply=True, update=False)
        source2 = self.make_source(
            "source2", {"a.txt": ("managed", "after\n")}, version="1.1.0"
        )
        original_cleanup = CODEXICON.safe_remove_tree
        interrupted = False

        def cleanup_then_interrupt(path, parent):
            nonlocal interrupted
            original_cleanup(path, parent)
            if not interrupted:
                interrupted = True
                raise OSError("journal removal interrupted")

        with mock.patch.object(CODEXICON, "safe_remove_tree", side_effect=cleanup_then_interrupt):
            with self.assertRaisesRegex(OSError, "journal removal interrupted"):
                CODEXICON.run_install(source2, target, apply=True, update=True)

        journal_path = CODEXICON.transaction_path(target)
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        self.assertEqual(journal["phase"], "committed")
        self.assertFalse((target / journal["backup_root"]).exists())

        self.run_quietly(CODEXICON.recover_transaction, target)
        self.assertFalse(journal_path.exists())
        self.assertEqual((target / "a.txt").read_text(encoding="utf-8"), "after\n")

    def test_partial_rollback_retries_after_filesystem_failure(self) -> None:
        source1 = self.make_source(
            "source1", {"a.txt": ("managed", "a1\n"), "b.txt": ("managed", "b1\n")}
        )
        target = self.temp_dir / "target"
        target.mkdir()
        self.run_quietly(CODEXICON.run_install, source1, target, apply=True, update=False)
        source2 = self.make_source(
            "source2", {"a.txt": ("managed", "a2\n"), "b.txt": ("managed", "b2\n")}, version="1.1.0"
        )
        original_apply = CODEXICON.apply_operation
        original_atomic_write = CODEXICON.atomic_write_bytes
        calls = 0
        fail_rollback = False

        def interrupt_after_apply(source_root, target_root, operation):
            nonlocal calls, fail_rollback
            calls += 1
            result = original_apply(source_root, target_root, operation)
            if calls == 2:
                fail_rollback = True
                raise KeyboardInterrupt()
            return result

        def fail_restore(path, content, *, mode=None):
            if fail_rollback and path == target / "a.txt":
                raise OSError("restore interrupted")
            return original_atomic_write(path, content, mode=mode)

        with (
            mock.patch.object(CODEXICON, "apply_operation", side_effect=interrupt_after_apply),
            mock.patch.object(CODEXICON, "atomic_write_bytes", side_effect=fail_restore),
            self.assertRaises(KeyboardInterrupt),
        ):
            CODEXICON.apply_transaction(
                source2,
                target,
                *CODEXICON.install_plan(
                    source2,
                    target,
                    CODEXICON.load_manifest(source2),
                    CODEXICON.load_lock(target, required=True),
                    update=True,
                ),
            )

        journal_path = CODEXICON.transaction_path(target)
        self.assertEqual(json.loads(journal_path.read_text(encoding="utf-8"))["phase"], "applying")
        self.assertEqual((target / "a.txt").read_text(encoding="utf-8"), "a2\n")
        self.assertEqual((target / "b.txt").read_text(encoding="utf-8"), "b1\n")

        self.run_quietly(CODEXICON.recover_transaction, target)
        self.assertFalse(journal_path.exists())
        self.assertEqual((target / "a.txt").read_text(encoding="utf-8"), "a1\n")
        self.assertEqual((target / "b.txt").read_text(encoding="utf-8"), "b1\n")

    def test_failed_terminal_rollback_persistence_leaves_recoverable_journal(self) -> None:
        source = self.make_source(
            "source", {"a.txt": ("managed", "a\n"), "b.txt": ("managed", "b\n")}
        )
        target = self.temp_dir / "target"
        target.mkdir()
        original_apply = CODEXICON.apply_operation
        original_write_json = CODEXICON.atomic_write_json
        calls = 0

        def interrupt_on_second(source_root, target_root, operation):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise KeyboardInterrupt()
            return original_apply(source_root, target_root, operation)

        def fail_terminal_persistence(path, value):
            if isinstance(value, dict) and value.get("phase") == "rolled-back":
                raise OSError("terminal state unavailable")
            return original_write_json(path, value)

        with (
            mock.patch.object(CODEXICON, "apply_operation", side_effect=interrupt_on_second),
            mock.patch.object(CODEXICON, "atomic_write_json", side_effect=fail_terminal_persistence),
            self.assertRaises(KeyboardInterrupt),
        ):
            CODEXICON.apply_transaction(
                source,
                target,
                *CODEXICON.install_plan(
                    source, target, CODEXICON.load_manifest(source), None, update=False
                ),
            )

        journal_path = CODEXICON.transaction_path(target)
        self.assertEqual(json.loads(journal_path.read_text(encoding="utf-8"))["phase"], "applying")
        self.assertTrue(journal_path.exists())

        self.run_quietly(CODEXICON.recover_transaction, target)
        self.assertFalse(journal_path.exists())
        self.assertFalse((target / "a.txt").exists())
        self.assertFalse((target / "b.txt").exists())

    def test_rollback_preserves_a_concurrent_target_edit(self) -> None:
        source1 = self.make_source("source1", {"a.txt": ("managed", "before\n")})
        target = self.temp_dir / "target"
        target.mkdir()
        self.run_quietly(CODEXICON.run_install, source1, target, apply=True, update=False)
        source2 = self.make_source(
            "source2", {"a.txt": ("managed", "after\n")}, version="1.1.0"
        )
        original_apply = CODEXICON.apply_operation

        def edit_after_apply(source_root, target_root, operation):
            result = original_apply(source_root, target_root, operation)
            if operation["path"] == "a.txt":
                (target / "a.txt").write_text("concurrent edit\n", encoding="utf-8")
                raise KeyboardInterrupt()
            return result

        with mock.patch.object(CODEXICON, "apply_operation", side_effect=edit_after_apply):
            with self.assertRaises(KeyboardInterrupt):
                CODEXICON.apply_transaction(
                    source2,
                    target,
                    *CODEXICON.install_plan(
                        source2,
                        target,
                        CODEXICON.load_manifest(source2),
                        CODEXICON.load_lock(target, required=True),
                        update=True,
                    ),
                )

        self.assertEqual((target / "a.txt").read_text(encoding="utf-8"), "concurrent edit\n")
        self.assertTrue(CODEXICON.transaction_path(target).exists())

    def test_manifest_traversal_and_symlinks_are_rejected(self) -> None:
        source = self.temp_dir / "source"
        source.mkdir()
        (source / "TEMPLATE_VERSION").write_text("1.0.0\n", encoding="utf-8")
        (source / ".codexicon.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "files": [{"path": "../outside.txt", "policy": "managed"}],
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(CODEXICON.CodexiconError):
            CODEXICON.load_manifest(source)

        linked_source = self.make_source(
            "linked-source",
            {"safe.txt": ("managed", "safe\n")},
        )
        outside = self.temp_dir / "outside.txt"
        outside.write_text("outside\n", encoding="utf-8")
        link = linked_source / "safe.txt"
        link.unlink()
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("symbolic links are unavailable")
        with self.assertRaises(CODEXICON.CodexiconError):
            CODEXICON.load_manifest(linked_source)

    def test_state_and_checkpoint_symlinks_are_rejected(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        outside = self.temp_dir / "outside"
        outside.mkdir()
        try:
            (root / ".codexicon").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symbolic links are unavailable")
        with self.assertRaises(CODEXICON.CodexiconError):
            CODEXICON.transaction_path(root)
        (root / ".codexicon").unlink()
        (root / "agent_docs").mkdir()
        (root / "agent_docs" / "sessions").symlink_to(outside, target_is_directory=True)
        args = argparse.Namespace(
            root=root,
            slug="escape",
            title="Escape",
            summary="Must stay local.",
            resume_note="None.",
            next=["Stop."],
            related=[],
            verification=[],
            blocker=[],
            decision=[],
        )
        with self.assertRaises(CODEXICON.CodexiconError):
            CODEXICON.create_checkpoint(args)
        self.assertEqual(list(outside.iterdir()), [])

    def test_checkpoint_leaf_symlink_is_not_selected(self) -> None:
        root = self.temp_dir / "project"
        sessions = root / "agent_docs" / "sessions"
        sessions.mkdir(parents=True)
        outside = self.temp_dir / "external-checkpoint.md"
        metadata = {
            "schema_version": 1,
            "checkpoint_id": "d" * 16,
            "created_at": CODEXICON.utc_now(),
            "repository_id": CODEXICON.repository_identity(root),
            "branch": "none",
            "head": "none",
            "related": [],
        }
        outside.write_text(
            f"<!-- codexicon-checkpoint: {json.dumps(metadata)} -->\nsecret body\n",
            encoding="utf-8",
        )
        try:
            (sessions / "linked.md").symlink_to(outside)
        except OSError:
            self.skipTest("symbolic links are unavailable")

        self.assertEqual(CODEXICON.compatible_checkpoints(root), [])

    def test_malformed_lock_is_rejected(self) -> None:
        target = self.temp_dir / "target"
        target.mkdir()
        (target / ".codexicon.lock.json").write_text("{", encoding="utf-8")
        with self.assertRaises(CODEXICON.CodexiconError):
            CODEXICON.load_lock(target, required=True)

    def test_doctor_reports_malformed_configuration_and_hooks(self) -> None:
        root = self.temp_dir / "project"
        (root / ".codex").mkdir(parents=True)
        (root / ".codex" / "config.toml").write_text("[agents\n", encoding="utf-8")
        (root / ".codex" / "hooks.json").write_text("{", encoding="utf-8")
        (root / "scripts").mkdir()
        for name in CODEXICON.CANONICAL_CHECKS:
            for suffix in ("sh", "ps1"):
                (root / "scripts" / f"{name}.{suffix}").write_text("stub\n", encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = CODEXICON.doctor(root)

        self.assertEqual(result, 1)
        self.assertIn("malformed .codex/config.toml", output.getvalue())
        self.assertIn("malformed .codex/hooks.json", output.getvalue())

    def test_doctor_rejects_disabled_features_and_missing_hook_actions(self) -> None:
        root = self.temp_dir / "project"
        (root / ".codex").mkdir(parents=True)
        (root / ".codex" / "config.toml").write_text(
            'project_root_markers = [".git"]\n'
            "[features]\n"
            "hooks = false\n"
            "multi_agent = false\n"
            "[agents]\n"
            "max_concurrent_threads_per_session = 2\n",
            encoding="utf-8",
        )
        (root / ".codex" / "hooks.json").write_text(
            json.dumps({"hooks": {}}),
            encoding="utf-8",
        )
        diagnostics = []

        CODEXICON.parse_config(root, diagnostics)
        CODEXICON.parse_hooks(root, diagnostics)

        messages = "\n".join(message for _, message in diagnostics)
        self.assertIn("features.hooks must be true", messages)
        self.assertIn("features.multi_agent must be true", messages)
        self.assertIn("lacks required verify-stop action", messages)

    def test_doctor_accepts_runtime_managed_subagent_concurrency(self) -> None:
        root = self.temp_dir / "project"
        (root / ".codex").mkdir(parents=True)
        (root / ".codex" / "config.toml").write_text(
            'project_root_markers = [".git"]\n'
            "[features]\n"
            "hooks = true\n"
            "multi_agent = true\n",
            encoding="utf-8",
        )
        diagnostics = []

        CODEXICON.parse_config(root, diagnostics)

        self.assertFalse(
            any("concurrency" in message for _, message in diagnostics),
            diagnostics,
        )

    def test_source_repository_passes_doctor(self) -> None:
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            result = CODEXICON.doctor(ROOT)

        self.assertEqual(result, 0, output.getvalue())
        unexpected_warnings = [
            line
            for line in output.getvalue().splitlines()
            if line.startswith("WARN")
            and "executable path is not tracked yet; stage it, then run sync-git-modes" not in line
        ]
        self.assertEqual(unexpected_warnings, [], output.getvalue())

    def test_ship_doctor_reports_missing_git_mode_metadata(self) -> None:
        output = io.StringIO()

        with (
            mock.patch.object(CODEXICON, "git_index_mode", return_value=None),
            contextlib.redirect_stdout(output),
        ):
            result = CODEXICON.doctor(ROOT, mode=CODEXICON.SHIP_MODE)

        warnings = [line for line in output.getvalue().splitlines() if line.startswith("WARN")]
        self.assertEqual(result, 0, output.getvalue())
        self.assertTrue(warnings, output.getvalue())
        self.assertTrue(
            all(
                "executable path is not tracked yet; stage it, then run sync-git-modes" in line
                for line in warnings
            ),
            output.getvalue(),
        )

    def test_python310_toml_fallback_rejects_malformed_config_and_agent(self) -> None:
        root = self.temp_dir / "project"
        agents = root / ".codex" / "agents"
        agents.mkdir(parents=True)
        (root / ".codex" / "config.toml").write_text(
            'project_root_markers = [".git"]\n'
            'model = "unterminated\n'
            "[features]\n"
            "hooks = true\n"
            "multi_agent = true\n"
            "[agents]\n"
            "max_concurrent_threads_per_session = 2\n",
            encoding="utf-8",
        )
        (root / ".codex" / "hooks.json").write_text(
            json.dumps({"hooks": {}}),
            encoding="utf-8",
        )
        for name in ("implementer", "reviewer", "researcher"):
            content = (
                f'name = "{name}"\n'
                'description = "valid"\n'
                'developer_instructions = "unterminated\n'
                if name == "implementer"
                else (
                    f'name = "{name}"\n'
                    'description = "valid"\n'
                    'developer_instructions = "valid"\n'
                )
            )
            (agents / f"{name}.toml").write_text(content, encoding="utf-8")
        output = io.StringIO()
        with (
            mock.patch.object(CODEXICON, "tomllib", None),
            contextlib.redirect_stdout(output),
        ):
            result = CODEXICON.doctor(root)

        self.assertEqual(result, 1)
        rendered = output.getvalue()
        self.assertIn("malformed .codex/config.toml", rendered)
        self.assertIn("malformed project agent implementer", rendered)
        parsed = CODEXICON.parse_toml_subset(
            "model = 'gpt-5' # valid literal string\n"
            "[features] # valid inline comment\n"
            "hooks = true\n"
            "multi_agent = true\n"
        )
        self.assertEqual(parsed["model"], "gpt-5")
        with self.assertRaises(ValueError):
            CODEXICON.parse_toml_subset(
                "[features]\nhooks = true\n[features]\nmulti_agent = true\n"
            )

    def test_verify_runs_native_checks_in_canonical_order_and_stops_on_failure(self) -> None:
        root = self.temp_dir / "project"
        (root / "scripts").mkdir(parents=True)
        suffix = "ps1" if os.name == "nt" else "sh"
        for name in CODEXICON.CANONICAL_CHECKS:
            (root / "scripts" / f"{name}.{suffix}").write_text("stub\n", encoding="utf-8")
        results = [
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 7),
        ]
        with (
            mock.patch.object(CODEXICON.subprocess, "run", side_effect=results) as run,
            mock.patch.object(CODEXICON.shutil, "which", return_value="powershell"),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = CODEXICON.verify(root, [])

        self.assertEqual(result, 7)
        self.assertEqual(run.call_count, 2)
        self.assertIn("lint", " ".join(run.call_args_list[0].args[0]))
        self.assertIn("test", " ".join(run.call_args_list[1].args[0]))

    def test_verify_reports_unexecutable_command_as_controlled_failure(self) -> None:
        root = self.temp_dir / "project"
        (root / "scripts").mkdir(parents=True)
        suffix = "ps1" if os.name == "nt" else "sh"
        (root / "scripts" / f"lint.{suffix}").write_text("stub\n", encoding="utf-8")
        with (
            mock.patch.object(CODEXICON.subprocess, "run", side_effect=PermissionError("denied")),
            mock.patch.object(CODEXICON.shutil, "which", return_value="powershell"),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            result = CODEXICON.verify(root, ["lint"])
        self.assertEqual(result, 126)

    def test_git_hook_installation_is_idempotent_and_refuses_existing_path(self) -> None:
        root = self.temp_dir / "repository"
        (root / ".githooks").mkdir(parents=True)
        (root / ".githooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
        (root / ".githooks" / "pre-push").write_text("#!/bin/sh\n", encoding="utf-8")
        run_fixture_git("init", "-q", str(root))

        self.assertEqual(self.run_quietly(CODEXICON.install_git_hooks, root), 0)
        self.assertEqual(self.run_quietly(CODEXICON.install_git_hooks, root), 0)
        configured = subprocess.run(
            ["git", "config", "--local", "--get", "core.hooksPath"],
            cwd=root,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(configured.stdout.strip(), ".githooks")
        subprocess.run(
            ["git", "config", "--local", "core.hooksPath", "organization-hooks"],
            cwd=root,
            check=True,
        )
        with self.assertRaises(CODEXICON.CodexiconError):
            CODEXICON.install_git_hooks(root)

        missing = self.temp_dir / "missing-hook-repository"
        (missing / ".githooks").mkdir(parents=True)
        (missing / ".githooks" / "pre-commit").write_text("#!/bin/sh\n", encoding="utf-8")
        run_fixture_git("init", "-q", str(missing))
        with self.assertRaises(CODEXICON.CodexiconError):
            CODEXICON.install_git_hooks(missing)

    def test_git_hook_installer_rejects_symlinked_hook(self) -> None:
        root = self.temp_dir / "repository"
        hooks = root / ".githooks"
        hooks.mkdir(parents=True)
        outside = self.temp_dir / "outside-hook"
        outside.write_text("#!/bin/sh\n", encoding="utf-8")
        try:
            (hooks / "pre-commit").symlink_to(outside)
        except OSError:
            self.skipTest("symbolic links are unavailable")
        (hooks / "pre-push").write_text("#!/bin/sh\n", encoding="utf-8")
        run_fixture_git("init", "-q", str(root))
        before = outside.stat().st_mode

        with self.assertRaises(CODEXICON.CodexiconError):
            CODEXICON.install_git_hooks(root)

        self.assertEqual(outside.stat().st_mode, before)

    def test_checkpoint_is_atomic_and_resume_selects_latest_compatible(self) -> None:
        root = self.temp_dir / "project"
        (root / "agent_docs" / "plans").mkdir(parents=True)
        (root / "agent_docs" / "plans" / "plan.md").write_text("# Plan\n", encoding="utf-8")
        args = argparse.Namespace(
            root=root,
            slug="handoff",
            title="Handoff",
            summary="Implementation is partial.",
            resume_note="Continue with the focused test.",
            next=["Run the focused test."],
            related=["agent_docs/plans/plan.md"],
            changed=["agent_docs/plans/plan.md"],
            verification=["`python -m unittest` — passed"],
            blocker=[],
            decision=["Keep the local manager."],
        )

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(CODEXICON.create_checkpoint(args), 0)
        candidates = CODEXICON.compatible_checkpoints(root)
        self.assertEqual(len(candidates), 1)
        (root / "agent_docs" / "plans" / "plan.md").write_text("# Changed\n", encoding="utf-8")
        output = io.StringIO()
        warning_output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(warning_output):
            self.assertEqual(CODEXICON.resume(root), 0)
        self.assertIn("# Checkpoint: Handoff", output.getvalue())
        self.assertIn("path evidence differs", warning_output.getvalue())

        second = argparse.Namespace(**{**vars(args), "slug": "atomic-failure"})
        original_replace = CODEXICON.os.replace

        def fail_checkpoint_replace(source, target):
            if str(target).endswith("atomic-failure.md"):
                raise OSError("interrupted")
            return original_replace(source, target)

        with (
            mock.patch.object(CODEXICON.os, "replace", side_effect=fail_checkpoint_replace),
            self.assertRaises(OSError),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            CODEXICON.create_checkpoint(second)
        self.assertEqual(
            list((root / "agent_docs" / "sessions").glob("*-atomic-failure.md")),
            [],
        )
        self.assertEqual(
            list((root / "agent_docs" / "sessions").glob("*atomic-failure*.tmp")),
            [],
        )

    def test_executable_intent_can_be_synchronized_in_git_index(self) -> None:
        source = self.make_source("source", {"tool.sh": ("managed", "#!/bin/sh\n")})
        manifest_path = source / ".codexicon.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"][0]["executable"] = True
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        target = self.temp_dir / "target"
        target.mkdir()
        run_fixture_git("init", "-q", cwd=target)

        self.run_quietly(
            CODEXICON.run_install, source, target, apply=True, update=False
        )
        lock = CODEXICON.load_lock(target, required=True)
        self.assertTrue(lock["files"]["tool.sh"]["executable"])
        if os.name != "nt":
            self.assertTrue((target / "tool.sh").stat().st_mode & 0o111)
        run_fixture_git("add", "--", "tool.sh", cwd=target)
        self.run_quietly(CODEXICON.sync_git_modes, target)
        self.assertEqual(CODEXICON.git_index_mode(target, "tool.sh"), "100755")

    def test_real_manifest_adoption_preserves_executable_intent(self) -> None:
        manifest = json.loads((ROOT / ".codexicon.json").read_text(encoding="utf-8"))
        source = self.temp_dir / "release-source"
        source.mkdir()
        shutil.copyfile(ROOT / "TEMPLATE_VERSION", source / "TEMPLATE_VERSION")
        shutil.copyfile(ROOT / ".codexicon.json", source / ".codexicon.json")
        target = self.temp_dir / "target"
        target.mkdir()
        for item in manifest["files"]:
            relative = item["path"]
            if relative == ".codexicon.json":
                continue
            if item["policy"] != "project":
                destination = source / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
            else:
                destination = target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, destination)
        run_fixture_git("init", "-q", cwd=target)
        run_fixture_git("config", "core.autocrlf", "false", cwd=target)

        result = self.run_quietly(
            CODEXICON.run_install, source, target, apply=True, update=False
        )

        self.assertEqual(result, 0)
        run_fixture_git("add", "--all", cwd=target)
        self.run_quietly(CODEXICON.sync_git_modes, target)
        for relative in (
            ".githooks/pre-commit",
            ".githooks/pre-push",
            "scripts/install-git-hooks.sh",
            "scripts/lint.sh",
            "scripts/test.sh",
            "scripts/security.sh",
        ):
            self.assertEqual(CODEXICON.git_index_mode(target, relative), "100755")

    def test_repository_identity_falls_back_when_git_is_unavailable(self) -> None:
        root = self.temp_dir / "project"
        root.mkdir()
        with mock.patch.object(CODEXICON.subprocess, "run", side_effect=FileNotFoundError) as run:
            identity = CODEXICON.repository_identity(root)
        expected = CODEXICON.hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:20]
        self.assertEqual(identity, expected)
        run.assert_not_called()

    def test_ship_dirty_paths_parses_fixture_rename_pairs(self) -> None:
        root = self.temp_dir / "repository"
        root.mkdir()
        run_fixture_git("init", "-q", cwd=root)
        run_fixture_git("config", "user.name", "Codexicon Test", cwd=root)
        run_fixture_git("config", "user.email", "codexicon@example.invalid", cwd=root)
        (root / "old-name.txt").write_text("content\n", encoding="utf-8")
        run_fixture_git("add", "old-name.txt", cwd=root)
        run_fixture_git("commit", "-qm", "fixture", cwd=root)
        run_fixture_git("mv", "old-name.txt", "new-name.txt", cwd=root)

        self.assertEqual(
            CODEXICON.ship_dirty_paths(root),
            ["new-name.txt", "old-name.txt"],
        )

    def test_build_checkpoint_resume_and_doctor_do_not_call_git(self) -> None:
        root = self.temp_dir / "git-free-build"
        (root / "agent_docs" / "sessions").mkdir(parents=True)
        args = argparse.Namespace(
            root=root,
            slug="git-free",
            title="Git-free Build",
            summary="Local checkpoint.",
            resume_note="Continue locally.",
            next=["Run the focused test."],
            related=[],
            changed=[],
            verification=[],
            blocker=[],
            decision=[],
        )
        with mock.patch.object(
            CODEXICON.subprocess, "run", side_effect=AssertionError("Git is forbidden")
        ):
            self.assertEqual(CODEXICON.create_checkpoint(args), 0)
            self.assertEqual(CODEXICON.resume(root), 0)
            self.assertEqual(CODEXICON.doctor(root), 1)

    def test_doctor_reports_checkpoint_damage_and_ignores_retrospectives(self) -> None:
        root = self.temp_dir / "project"
        sessions = root / "agent_docs" / "sessions"
        sessions.mkdir(parents=True)
        (sessions / "retro.md").write_text("# Retrospective\n", encoding="utf-8")
        (sessions / "broken.md").write_text(
            "<!-- codexicon-checkpoint: { -->\n# Broken\n",
            encoding="utf-8",
        )
        metadata = {
            "schema_version": 1,
            "checkpoint_id": "a" * 16,
            "created_at": CODEXICON.utc_now(),
            "repository_id": CODEXICON.repository_identity(root),
            "branch": "none",
            "head": "stale-head",
            "related": [],
            "contract_identity": "sha256:" + ("0" * 64),
            "task_identity": "missing",
            "path_identity": CODEXICON.local_path_evidence_identity({}),
            "path_evidence": {},
            "changed": [],
        }
        (sessions / "stale.md").write_text(
            f"<!-- codexicon-checkpoint: {json.dumps(metadata)} -->\n# Stale\n",
            encoding="utf-8",
        )
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = CODEXICON.doctor(root)

        self.assertEqual(result, 1)
        rendered = output.getvalue()
        self.assertIn("checkpoint broken.md", rendered)
        self.assertIn("SPEC.md identity differs", rendered)
        self.assertNotIn("retro.md", rendered)

    def test_checkpoint_validator_rejects_schema_timestamp_and_unsafe_related(self) -> None:
        root = self.temp_dir / "project"
        sessions = root / "agent_docs" / "sessions"
        sessions.mkdir(parents=True)
        base = {
            "schema_version": 1,
            "checkpoint_id": "b" * 16,
            "created_at": CODEXICON.utc_now(),
            "repository_id": CODEXICON.repository_identity(root),
            "branch": "none",
            "head": "none",
            "related": [],
        }
        cases = {
            "schema.md": {**base, "schema_version": 2},
            "timestamp.md": {**base, "created_at": "2026-07-26T10:00:00"},
            "related.md": {**base, "related": ["../outside"]},
            "repository.md": {**base, "repository_id": "c" * 20},
        }
        for name, metadata in cases.items():
            (sessions / name).write_text(
                f"<!-- codexicon-checkpoint: {json.dumps(metadata)} -->\n",
                encoding="utf-8",
            )
        self.assertIn("unsupported checkpoint schema", CODEXICON.validate_checkpoint(root, sessions / "schema.md")[2])
        self.assertIn("lacks a timezone", CODEXICON.validate_checkpoint(root, sessions / "timestamp.md")[2])
        self.assertIn("unsafe", CODEXICON.validate_checkpoint(root, sessions / "related.md")[2])
        candidates = CODEXICON.compatible_checkpoints(root)
        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
