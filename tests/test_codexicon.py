from __future__ import annotations

import argparse
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
MANAGER_PATH = ROOT / "scripts" / "codexicon.py"
TEST_TEMP_ROOT = ROOT / ".codex-state" / "codexicon-tests"
SPEC = importlib.util.spec_from_file_location("codexicon_manager", MANAGER_PATH)
assert SPEC and SPEC.loader
CODEXICON = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CODEXICON
SPEC.loader.exec_module(CODEXICON)


class CodexiconManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TEST_TEMP_ROOT / uuid.uuid4().hex
        self.temp_dir.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.temp_dir, True)

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
        subprocess.run(["git", "init", "-q", str(root)], check=True)

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
        subprocess.run(["git", "init", "-q", str(missing)], check=True)
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
        subprocess.run(["git", "init", "-q", str(root)], check=True)
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
            verification=["`python -m unittest` — passed"],
            blocker=[],
            decision=["Keep the local manager."],
        )

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(CODEXICON.create_checkpoint(args), 0)
        candidates = CODEXICON.compatible_checkpoints(root)
        self.assertEqual(len(candidates), 1)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(CODEXICON.resume(root), 0)
        self.assertIn("# Checkpoint: Handoff", output.getvalue())

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
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)

        self.run_quietly(
            CODEXICON.run_install, source, target, apply=True, update=False
        )
        lock = CODEXICON.load_lock(target, required=True)
        self.assertTrue(lock["files"]["tool.sh"]["executable"])
        if os.name != "nt":
            self.assertTrue((target / "tool.sh").stat().st_mode & 0o111)
        subprocess.run(["git", "add", "--", "tool.sh"], cwd=target, check=True)
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
        subprocess.run(["git", "init", "-q"], cwd=target, check=True)

        result = self.run_quietly(
            CODEXICON.run_install, source, target, apply=True, update=False
        )

        self.assertEqual(result, 0)
        subprocess.run(["git", "add", "--all"], cwd=target, check=True)
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
        with mock.patch.object(CODEXICON.subprocess, "run", side_effect=FileNotFoundError):
            identity = CODEXICON.repository_identity(root)
        expected = CODEXICON.hashlib.sha256(str(root.resolve()).encode("utf-8")).hexdigest()[:20]
        self.assertEqual(identity, expected)

    def test_dirty_paths_parses_staged_rename_pairs(self) -> None:
        root = self.temp_dir / "repository"
        root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Codexicon Test"], cwd=root, check=True)
        subprocess.run(
            ["git", "config", "user.email", "codexicon@example.invalid"],
            cwd=root,
            check=True,
        )
        (root / "old-name.txt").write_text("content\n", encoding="utf-8")
        subprocess.run(["git", "add", "old-name.txt"], cwd=root, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=root, check=True)
        subprocess.run(["git", "mv", "old-name.txt", "new-name.txt"], cwd=root, check=True)

        self.assertEqual(
            CODEXICON.dirty_paths(root),
            ["new-name.txt", "old-name.txt"],
        )

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
        self.assertIn("stale HEAD", rendered)
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
