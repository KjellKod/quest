"""Tests for scripts/quest_artifact_postflight.py.

Plan reference: ``.quest/wrong-location-guardrails_2026-05-18__0003/phase_01_plan/plan.md``
§7.2.

Tests in this file:

* Slice B (happy path): #1, #7, #10.
* Slice C (failure branches): #2, #3, #4, #5, #6, #8, #9.
* Slice D (latency, perf-marker-gated): #11, #12.
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

import pytest

# Ensure ``scripts/`` is on sys.path before importing the validator module.
import subprocess
import sys

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import quest_artifact_postflight as postflight  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Return a temp repo root that contains a ``.quest/<id>/`` tree."""

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    return repo_root


def _make_planner_handoff(
    *,
    repo_root: Path,
    quest_id: str = "test-quest_2026-05-18__0001",
    artifacts: list[str] | None = None,
    create_artifact_files: bool = True,
) -> tuple[Path, Path, Path]:
    """Create a planner-phase quest dir, optional artifact files, and the
    handoff.json. Returns ``(quest_dir, handoff_path, log_path)``."""

    quest_dir = repo_root / ".quest" / quest_id
    phase_dir = quest_dir / "phase_01_plan"
    phase_dir.mkdir(parents=True, exist_ok=True)
    log_path = quest_dir / "logs" / "path_compliance.log"

    if artifacts is None:
        artifacts = [
            str(phase_dir / "plan.md"),
            str(phase_dir / "handoff.json"),
        ]

    if create_artifact_files:
        for entry in artifacts:
            p = Path(entry)
            if not p.is_absolute():
                p = repo_root / entry
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("seed", encoding="utf-8")

    handoff_path = phase_dir / "handoff.json"
    handoff_payload = {
        "status": "complete",
        "artifacts": artifacts,
        "next": "plan-reviewer-a",
        "summary": "test handoff",
    }
    handoff_path.write_text(json.dumps(handoff_payload), encoding="utf-8")
    return quest_dir, handoff_path, log_path


# ---------------------------------------------------------------------------
# Slice B — Happy-path tests (#1, #7, #10)
# ---------------------------------------------------------------------------


class TestHappyPath:
    """Plan §7.2 #1, #7, #10."""

    def test_all_declared_artifacts_present_and_inside_boundary_passes(
        self, workspace: Path
    ) -> None:
        """#1: exit 0; log file absent or empty."""

        quest_dir, handoff_path, log_path = _make_planner_handoff(repo_root=workspace)
        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 0
        # Log file MUST be absent or empty on a clean pass.
        if log_path.exists():
            assert log_path.read_text(encoding="utf-8") == ""

    def test_no_expected_artifacts_role_passes_with_no_log(self, workspace: Path) -> None:
        """#7: role whose expected_artifacts_for_role(...) returns empty
        → exit 0 and the log file is left untouched."""

        # plan-reviewer-b is solo-disabled; in ``quest_mode='solo'`` the
        # helper returns an empty list and the validator passes through.
        quest_id = "test-quest_2026-05-18__0001"
        quest_dir = workspace / ".quest" / quest_id
        phase_dir = quest_dir / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        handoff_path = phase_dir / "handoff_plan-reviewer-b.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [],
                    "next": "arbiter",
                    "summary": "n/a",
                }
            ),
            encoding="utf-8",
        )

        # Seed an existing log line to prove the validator does NOT touch it
        # on a pass-through role.
        log_path.parent.mkdir(parents=True, exist_ok=True)
        sentinel = '{"sentinel":"preserved"}\n'
        log_path.write_text(sentinel, encoding="utf-8")

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_01_plan",
            role="plan-reviewer-b",
            handoff=handoff_path,
            quest_mode="solo",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 0
        assert log_path.read_text(encoding="utf-8") == sentinel

    def test_run_returns_nonzero_int_on_any_mismatch(self, workspace: Path) -> None:
        """#10: pin the ``run(...)`` Python contract directly.

        Pass case returns ``0``; mismatch case returns ``1``.
        """

        # Pass case.
        quest_dir, handoff_path, log_path = _make_planner_handoff(repo_root=workspace)
        assert (
            postflight.run(
                quest_dir=quest_dir,
                phase="phase_01_plan",
                role="planner",
                handoff=handoff_path,
                quest_mode="workflow",
                log=log_path,
                repo_root=workspace,
            )
            == 0
        )

        # Mismatch case: declared path missing on disk.
        quest_id = "test-quest_2026-05-18__0002"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path_b = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"
        handoff_path_b = phase_dir / "handoff.json"
        handoff_payload = {
            "status": "complete",
            "artifacts": [
                str(phase_dir / "plan.md"),  # never written to disk
                str(phase_dir / "handoff.json"),
            ],
            "next": "plan-reviewer-a",
            "summary": "missing-plan case",
        }
        handoff_path_b.write_text(json.dumps(handoff_payload), encoding="utf-8")

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path_b,
            quest_mode="workflow",
            log=log_path_b,
            repo_root=workspace,
        )
        assert isinstance(rc, int)
        assert rc == 1


# ---------------------------------------------------------------------------
# Slice C — Failure branches + mismatch records (#2 – #6, #8, #9)
# ---------------------------------------------------------------------------


def _read_log_lines(log_path: Path) -> list[dict[str, str]]:
    """Return the JSON-decoded mismatch records from ``log_path``."""

    if not log_path.exists():
        return []
    raw = log_path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


class TestFailureBranches:
    """Plan §7.2 #2 – #6, #8, #9."""

    def test_missing_artifact_records_missing_mismatch(self, workspace: Path) -> None:
        """#2: declared artifact does not exist on disk → reason=missing."""

        # plan.md is declared but not written; handoff.json is written.
        quest_id = "test-quest_missing"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(phase_dir / "plan.md"),  # NOT written
                        str(phase_dir / "handoff.json"),
                    ],
                    "next": "plan-reviewer-a",
                    "summary": "missing plan.md",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        assert len(records) == 1
        assert records[0]["reason"] == "missing"
        assert records[0]["declared"].endswith("plan.md")

    def test_outside_boundary_records_outside_boundary(self, workspace: Path) -> None:
        """#3: declared artifact lives inside ``.quest/<id>/`` but in the
        wrong phase directory → reason=outside_boundary.

        Workspace paths outside ``.quest/<id>/`` (changed source/test files
        declared by builder/fixer) are NOT flagged — see
        ``test_workspace_files_outside_quest_pass_through`` below.
        """

        quest_id = "test-quest_outside"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # Declared path is inside .quest/<id>/ but in a different phase
        # directory (phase_03_review) than the planner's boundary
        # (phase_01_plan). Quest-artifact classification applies the
        # boundary check.
        rogue_phase = workspace / ".quest" / quest_id / "phase_03_review"
        rogue_phase.mkdir(parents=True, exist_ok=True)
        rogue = rogue_phase / "plan.md"
        rogue.write_text("rogue", encoding="utf-8")
        (phase_dir / "plan.md").write_text("seed", encoding="utf-8")
        good_handoff = phase_dir / "handoff.json"
        good_handoff.write_text("seed", encoding="utf-8")

        handoff_path = good_handoff
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(phase_dir / "plan.md"),
                        str(rogue),
                    ],
                    "next": "plan-reviewer-a",
                    "summary": "outside boundary (wrong phase dir)",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        assert any(r["reason"] == "outside_boundary" for r in records)

    def test_workspace_files_outside_quest_pass_through(
        self, workspace: Path
    ) -> None:
        """Builder/fixer ARTIFACTS legitimately include changed workspace
        files (source, tests, configs, docs) alongside the canonical
        deliverables. Paths outside ``.quest/<id>/`` are classified as
        workspace files: only traversal applies — boundary and canonical
        name do NOT — and no mismatch should be recorded.

        Regression: the prior contract treated every declared path as a
        quest artifact and flagged real source files on every successful
        build (16 false positives on the wrong-location-guardrails
        build itself).
        """

        quest_id = "test-quest_workspace-files"
        quest_dir = workspace / ".quest" / quest_id
        phase_dir = quest_dir / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        # Canonical builder deliverables — these are the quest artifacts.
        (phase_dir / "pr_description.md").write_text("seed", encoding="utf-8")
        (phase_dir / "builder_feedback_discussion.md").write_text(
            "seed", encoding="utf-8"
        )

        # Workspace files the builder declares as changed. These look just
        # like the real wrong-location-guardrails builder handoff.
        for rel in [
            ".claude/hooks/branch-dir-context.sh",
            "scripts/quest_artifact_postflight.py",
            "tests/unit/test_quest_artifact_postflight.py",
            "AGENTS.md",
            "pyproject.toml",
        ]:
            p = workspace / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("seed", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(phase_dir / "pr_description.md"),
                        str(phase_dir / "builder_feedback_discussion.md"),
                        str(workspace / ".claude/hooks/branch-dir-context.sh"),
                        str(workspace / "scripts/quest_artifact_postflight.py"),
                        str(workspace / "tests/unit/test_quest_artifact_postflight.py"),
                        str(workspace / "AGENTS.md"),
                        str(workspace / "pyproject.toml"),
                    ],
                    "next": "code_review",
                    "summary": "builder declares canonical + workspace files",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_02_implementation",
            role="builder",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 0
        if log_path.exists():
            assert log_path.read_text(encoding="utf-8") == ""

    def test_workspace_file_missing_on_disk_records_missing(
        self, workspace: Path
    ) -> None:
        """A declared workspace file (outside ``.quest/``) that was never
        written to disk is path drift — the validator must flag it as
        ``missing``, not silently accept it.
        """

        quest_id = "test-quest_workspace-missing"
        quest_dir = workspace / ".quest" / quest_id
        phase_dir = quest_dir / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        # Canonical deliverables exist on disk so they don't pollute the log.
        (phase_dir / "pr_description.md").write_text("seed", encoding="utf-8")
        (phase_dir / "builder_feedback_discussion.md").write_text(
            "seed", encoding="utf-8"
        )

        # Declared workspace file that does NOT exist.
        ghost = workspace / "scripts" / "nonexistent_helper.py"

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(phase_dir / "pr_description.md"),
                        str(phase_dir / "builder_feedback_discussion.md"),
                        str(ghost),
                    ],
                    "next": "code_review",
                    "summary": "builder declared a workspace file that doesn't exist",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_02_implementation",
            role="builder",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        missing = [r for r in records if r["reason"] == "missing"]
        assert len(missing) == 1
        assert Path(missing[0]["actual"]).name == "nonexistent_helper.py"

    def test_sibling_quest_artifact_records_outside_boundary(
        self, workspace: Path
    ) -> None:
        """A declared path under ``.quest/`` that belongs to a DIFFERENT
        quest (sibling quest dir) is the precise wrong-location failure
        this validator exists to catch. Must record ``outside_boundary``.
        """

        quest_id = "test-quest_self"
        other_quest_id = "test-quest_other"
        quest_dir = workspace / ".quest" / quest_id
        phase_dir = quest_dir / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        (phase_dir / "pr_description.md").write_text("seed", encoding="utf-8")
        (phase_dir / "builder_feedback_discussion.md").write_text(
            "seed", encoding="utf-8"
        )

        # The sibling quest's directory — a file that DOES exist (so the
        # ``missing`` branch can't shadow this case) but belongs to another
        # quest entirely.
        sibling_phase = workspace / ".quest" / other_quest_id / "phase_01_plan"
        sibling_phase.mkdir(parents=True, exist_ok=True)
        sibling_file = sibling_phase / "plan.md"
        sibling_file.write_text("sibling", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(phase_dir / "pr_description.md"),
                        str(phase_dir / "builder_feedback_discussion.md"),
                        str(sibling_file),
                    ],
                    "next": "code_review",
                    "summary": "builder reaches into a sibling quest's dir",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_02_implementation",
            role="builder",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        outside = [r for r in records if r["reason"] == "outside_boundary"]
        assert len(outside) == 1
        assert other_quest_id in outside[0]["actual"]

    def test_sibling_quest_missing_on_disk_still_outside_boundary(
        self, workspace: Path
    ) -> None:
        """A declared path under a sibling quest's directory must record
        ``outside_boundary`` even if the file was never written. The
        wrong-location classification fires before the existence check —
        the real failure is the cross-quest declaration, not whether the
        write actually happened.
        """

        quest_id = "test-quest_self"
        other_quest_id = "test-quest_other"
        quest_dir = workspace / ".quest" / quest_id
        phase_dir = quest_dir / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        (phase_dir / "pr_description.md").write_text("seed", encoding="utf-8")
        (phase_dir / "builder_feedback_discussion.md").write_text(
            "seed", encoding="utf-8"
        )

        # Sibling quest path that DOES NOT EXIST on disk.
        ghost_sibling = (
            workspace
            / ".quest"
            / other_quest_id
            / "phase_01_plan"
            / "plan.md"
        )

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(phase_dir / "pr_description.md"),
                        str(phase_dir / "builder_feedback_discussion.md"),
                        str(ghost_sibling),
                    ],
                    "next": "code_review",
                    "summary": "builder declared a sibling-quest path that wasn't written",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_02_implementation",
            role="builder",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        # MUST be outside_boundary, NOT missing — the wrong-location
        # classification fires first.
        assert any(r["reason"] == "outside_boundary" for r in records)
        assert not any(
            r["reason"] == "missing" and other_quest_id in r["actual"]
            for r in records
        )

    def test_shared_dot_quest_paths_pass_through(self, workspace: Path) -> None:
        """Builder/fixer declarations under shared ``.quest/`` infrastructure
        paths (``cache/``, ``backlog/``, ``audit.log``) are NOT sibling-quest
        cross-writes. The validator must let them through without flagging
        ``outside_boundary`` — these are cross-quest by design.
        """

        quest_id = "test-quest_shared"
        quest_dir = workspace / ".quest" / quest_id
        phase_dir = quest_dir / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        (phase_dir / "pr_description.md").write_text("seed", encoding="utf-8")
        (phase_dir / "builder_feedback_discussion.md").write_text(
            "seed", encoding="utf-8"
        )

        # Three shared-infrastructure paths a build might legitimately
        # touch: a preflight cache file, the deferred-findings backlog,
        # and the persistent audit log.
        shared_paths = [
            workspace / ".quest" / "cache" / "claude_bridge_codex.json",
            workspace / ".quest" / "backlog" / "deferred_findings.jsonl",
            workspace / ".quest" / "audit.log",
        ]
        for p in shared_paths:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("seed", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(phase_dir / "pr_description.md"),
                        str(phase_dir / "builder_feedback_discussion.md"),
                        *[str(p) for p in shared_paths],
                    ],
                    "next": "code_review",
                    "summary": "builder declares shared .quest/ infra paths",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_02_implementation",
            role="builder",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 0
        if log_path.exists():
            assert log_path.read_text(encoding="utf-8") == ""

    def test_worktree_mode_workspace_files_resolve_against_worktree(
        self, tmp_path: Path
    ) -> None:
        """Worktree mode: ``.quest/<id>/`` stays in the original repo while
        the builder edits files in the worktree. A declared relative
        workspace-file path must resolve against ``workspace_root`` (the
        worktree), and the resulting absolute path must satisfy traversal
        + existence. Without ``--workspace-root``, the same handoff would
        falsely flag ``traversal_outside_repo``.
        """

        # Two distinct trees:
        # ``repo`` contains .quest/<id>/   ← quest-artifact tree
        # ``worktree`` contains scripts/foo.py ← workspace-file tree
        repo = tmp_path / "main-repo"
        repo.mkdir()
        worktree = tmp_path / "main-repo-worktree"
        worktree.mkdir()

        quest_id = "test-quest_worktree"
        quest_dir = repo / ".quest" / quest_id
        phase_dir = quest_dir / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        # Canonical deliverables in the original repo's .quest tree.
        (phase_dir / "pr_description.md").write_text("seed", encoding="utf-8")
        (phase_dir / "builder_feedback_discussion.md").write_text(
            "seed", encoding="utf-8"
        )

        # Workspace file in the worktree (NOT in the original repo).
        worktree_file = worktree / "scripts" / "foo.py"
        worktree_file.parent.mkdir(parents=True, exist_ok=True)
        worktree_file.write_text("seed", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        # Absolute quest-artifact paths (per workflow doctrine).
                        str(phase_dir / "pr_description.md"),
                        str(phase_dir / "builder_feedback_discussion.md"),
                        # Workspace-relative path — must resolve against
                        # the worktree, not the repo.
                        "scripts/foo.py",
                    ],
                    "next": "code_review",
                    "summary": "worktree-mode builder handoff",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_02_implementation",
            role="builder",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=repo,
            workspace_root=worktree,
        )
        assert rc == 0
        if log_path.exists():
            assert log_path.read_text(encoding="utf-8") == ""

    def test_worktree_mode_without_workspace_root_flag_breaks(
        self, tmp_path: Path
    ) -> None:
        """Negative pin: the same worktree-mode handoff WITHOUT the
        ``--workspace-root`` flag would fail. This documents why the flag
        matters and guards against accidental removal of the
        workspace-root threading.
        """

        repo = tmp_path / "main-repo"
        repo.mkdir()
        worktree = tmp_path / "main-repo-worktree"
        worktree.mkdir()

        quest_id = "test-quest_worktree_no_flag"
        quest_dir = repo / ".quest" / quest_id
        phase_dir = quest_dir / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        (phase_dir / "pr_description.md").write_text("seed", encoding="utf-8")
        (phase_dir / "builder_feedback_discussion.md").write_text(
            "seed", encoding="utf-8"
        )

        worktree_file = worktree / "scripts" / "foo.py"
        worktree_file.parent.mkdir(parents=True, exist_ok=True)
        worktree_file.write_text("seed", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(phase_dir / "pr_description.md"),
                        str(phase_dir / "builder_feedback_discussion.md"),
                        # Absolute worktree path — would be outside the
                        # original repo without workspace-root threading.
                        str(worktree_file),
                    ],
                    "next": "code_review",
                    "summary": "worktree-mode without --workspace-root flag",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_02_implementation",
            role="builder",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=repo,
            # workspace_root deliberately omitted — defaults to repo_root.
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        assert any(
            r["reason"] == "traversal_outside_repo"
            and "foo.py" in r["actual"]
            for r in records
        )

    def test_worktree_mode_shared_dot_quest_paths_pass(
        self, tmp_path: Path
    ) -> None:
        """In worktree mode, paths under ``<repo>/.quest/`` shared
        infrastructure directories (``cache/``, ``backlog/``,
        ``audit.log``) MUST anchor to ``repo_root``, not
        ``workspace_root``. Otherwise the traversal check would falsely
        flag them because the worktree sits outside the original repo's
        directory tree.
        """

        repo = tmp_path / "main-repo"
        repo.mkdir()
        worktree = tmp_path / "main-repo-worktree"
        worktree.mkdir()

        quest_id = "test-quest_worktree_shared"
        quest_dir = repo / ".quest" / quest_id
        phase_dir = quest_dir / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        (phase_dir / "pr_description.md").write_text("seed", encoding="utf-8")
        (phase_dir / "builder_feedback_discussion.md").write_text(
            "seed", encoding="utf-8"
        )

        # Shared .quest paths in the original repo (NOT in the worktree).
        shared_paths = [
            repo / ".quest" / "cache" / "claude_bridge_codex.json",
            repo / ".quest" / "backlog" / "deferred_findings.jsonl",
            repo / ".quest" / "audit.log",
        ]
        for p in shared_paths:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("seed", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(phase_dir / "pr_description.md"),
                        str(phase_dir / "builder_feedback_discussion.md"),
                        *[str(p) for p in shared_paths],
                    ],
                    "next": "code_review",
                    "summary": "worktree-mode shared .quest paths",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_02_implementation",
            role="builder",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=repo,
            workspace_root=worktree,
        )
        assert rc == 0
        if log_path.exists():
            assert log_path.read_text(encoding="utf-8") == ""

    def test_worktree_mode_sibling_quest_records_outside_boundary(
        self, tmp_path: Path
    ) -> None:
        """In worktree mode, a sibling-quest path (under
        ``<repo>/.quest/<OTHER-id>/``) MUST still be flagged as
        ``outside_boundary``, not falsely flagged as
        ``traversal_outside_repo`` just because the path sits in the
        original repo and not the worktree.
        """

        repo = tmp_path / "main-repo"
        repo.mkdir()
        worktree = tmp_path / "main-repo-worktree"
        worktree.mkdir()

        quest_id = "test-quest_worktree_self"
        other_quest_id = "test-quest_worktree_other"
        quest_dir = repo / ".quest" / quest_id
        phase_dir = quest_dir / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        (phase_dir / "pr_description.md").write_text("seed", encoding="utf-8")
        (phase_dir / "builder_feedback_discussion.md").write_text(
            "seed", encoding="utf-8"
        )

        sibling = repo / ".quest" / other_quest_id / "phase_01_plan" / "plan.md"
        sibling.parent.mkdir(parents=True, exist_ok=True)
        sibling.write_text("sibling", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(phase_dir / "pr_description.md"),
                        str(phase_dir / "builder_feedback_discussion.md"),
                        str(sibling),
                    ],
                    "next": "code_review",
                    "summary": "worktree-mode sibling quest cross-write",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_02_implementation",
            role="builder",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=repo,
            workspace_root=worktree,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        # MUST be outside_boundary, NOT traversal_outside_repo.
        assert any(r["reason"] == "outside_boundary" for r in records)
        assert not any(
            r["reason"] == "traversal_outside_repo" for r in records
        )

    def test_worktree_mode_quest_artifact_via_symlinked_mount(
        self, tmp_path: Path
    ) -> None:
        """In worktree mode, an agent may declare a quest artifact via the
        ``<worktree>/.quest`` symlink — either as an absolute worktree
        path or as a worktree-relative path that ``_load_declared_artifacts``
        resolves against ``workspace_root``. The coverage check must
        canonicalize through the symlink so the worktree mount and the
        repo mount produce the SAME identity for the SAME on-disk inode;
        otherwise a valid handoff fires a false ``missing``.

        Regression pin for the failure mode Codex flagged on ``eff55b3``.
        """

        repo = tmp_path / "main-repo"
        repo.mkdir()
        worktree = tmp_path / "main-repo-worktree"
        worktree.mkdir()

        # Quest's worktree invariant.
        (repo / ".quest").mkdir(parents=True, exist_ok=True)
        (worktree / ".quest").symlink_to(repo / ".quest", target_is_directory=True)

        quest_id = "test-quest_worktree_symlinked_declare"
        quest_dir = repo / ".quest" / quest_id
        phase_dir = quest_dir / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        (phase_dir / "pr_description.md").write_text("seed", encoding="utf-8")
        (phase_dir / "builder_feedback_discussion.md").write_text(
            "seed", encoding="utf-8"
        )

        # Declare quest artifacts the "wrong" way: via the worktree
        # symlink. One absolute worktree path, one worktree-relative path
        # (which _load_declared_artifacts will resolve against worktree).
        worktree_absolute = (
            worktree / ".quest" / quest_id
            / "phase_02_implementation" / "pr_description.md"
        )
        worktree_relative = (
            f".quest/{quest_id}/phase_02_implementation"
            f"/builder_feedback_discussion.md"
        )

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(worktree_absolute),
                        worktree_relative,
                    ],
                    "next": "code_review",
                    "summary": "agent declared via the worktree .quest symlink",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_02_implementation",
            role="builder",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=repo,
            workspace_root=worktree,
        )
        # The symlink-mounted declarations resolve to the canonical repo
        # inode; coverage must NOT emit ``missing``.
        assert rc == 0, _read_log_lines(log_path)
        if log_path.exists():
            assert log_path.read_text(encoding="utf-8") == ""

    def test_worktree_mode_combined_smoke(self, tmp_path: Path) -> None:
        """Combined worktree-mode smoke test exercising all four
        classifications in a single handoff, with Quest's ``.quest``
        symlink invariant in place:

        1. **Our canonical quest artifact** — agent declares the absolute
           repo path (per the ``workflow.md`` contract that orchestrators
           pass canonical quest paths even in worktree mode). Passes the
           quest-artifact check set.
        2. **True workspace file in the worktree** — ``scripts/foo.py``;
           anchors to ``workspace_root``, exists, passes.
        3. **Shared ``.quest/`` infrastructure path** — ``.quest/cache/...``;
           anchors to ``repo_root`` because it's under ``.quest/``,
           exists, passes (shared-name allowlist).
        4. **Sibling-quest path** — ``.quest/<OTHER-id>/...``; anchors to
           ``repo_root``, present on disk so the ``missing`` branch can't
           shadow this case, fires ``outside_boundary``.

        The worktree's ``.quest`` symlink is provisioned as part of the
        Quest invariant. Even though the orchestrator passes canonical
        repo paths, the symlink remains present in the worktree (the
        agent's tooling uses it for filesystem navigation). The test
        confirms the validator handles the structural symlink without
        false positives.

        Pins the four classifications acting together (not just
        individually) so a future change that reshuffles classification
        order cannot silently break one path while another still passes.
        """

        repo = tmp_path / "main-repo"
        repo.mkdir()
        worktree = tmp_path / "main-repo-worktree"
        worktree.mkdir()

        # Quest's worktree invariant: <worktree>/.quest symlinks to <repo>/.quest.
        (repo / ".quest").mkdir(parents=True, exist_ok=True)
        (worktree / ".quest").symlink_to(repo / ".quest", target_is_directory=True)

        quest_id = "test-quest_combined-self"
        other_quest_id = "test-quest_combined-other"
        quest_dir = repo / ".quest" / quest_id
        phase_dir = quest_dir / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        # (1) Canonical deliverables under repo's .quest/<id>/.
        (phase_dir / "pr_description.md").write_text("seed", encoding="utf-8")
        (phase_dir / "builder_feedback_discussion.md").write_text(
            "seed", encoding="utf-8"
        )

        # (2) Workspace file in the worktree (NOT under repo).
        workspace_file = worktree / "scripts" / "foo.py"
        workspace_file.parent.mkdir(parents=True, exist_ok=True)
        workspace_file.write_text("seed", encoding="utf-8")

        # (3) Shared .quest/cache/ path under the repo.
        shared_cache = repo / ".quest" / "cache" / "claude_bridge_codex.json"
        shared_cache.parent.mkdir(parents=True, exist_ok=True)
        shared_cache.write_text("seed", encoding="utf-8")

        # (4) Sibling-quest path that exists on disk.
        sibling = repo / ".quest" / other_quest_id / "phase_01_plan" / "plan.md"
        sibling.parent.mkdir(parents=True, exist_ok=True)
        sibling.write_text("sibling", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        # (1) Canonical quest artifacts — per workflow.md
                        # contract, orchestrators pass canonical repo
                        # paths even in worktree mode.
                        str(phase_dir / "pr_description.md"),
                        str(phase_dir / "builder_feedback_discussion.md"),
                        # (2) Workspace file (worktree-rooted).
                        str(workspace_file),
                        # (3) Shared .quest/ infra path.
                        str(shared_cache),
                        # (4) Sibling-quest cross-write (should fail).
                        str(sibling),
                    ],
                    "next": "code_review",
                    "summary": "combined worktree smoke covering all classifications",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_02_implementation",
            role="builder",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=repo,
            workspace_root=worktree,
        )
        # Sibling-quest cross-write fires; everything else passes.
        assert rc == 1
        records = _read_log_lines(log_path)
        outside = [r for r in records if r["reason"] == "outside_boundary"]
        assert len(outside) == 1
        assert other_quest_id in outside[0]["actual"]
        # No traversal/missing/noncanonical_name false positives from
        # canonical quest artifacts, workspace file, or shared-infra path.
        for r in records:
            assert r["reason"] == "outside_boundary", (
                f"unexpected mismatch {r!r} — combined smoke expects ONLY "
                f"the sibling-quest case to fire"
            )

    def test_nested_quest_path_records_nested_quest(self, workspace: Path) -> None:
        """#4: path contains .quest/<id>/.quest/ → reason=nested_quest."""

        quest_id = "test-quest_nested"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # Pathologic nested .quest/<id>/.quest/<id>/phase_01_plan/plan.md
        nested = (
            workspace
            / ".quest"
            / quest_id
            / ".quest"
            / quest_id
            / "phase_01_plan"
            / "plan.md"
        )
        nested.parent.mkdir(parents=True, exist_ok=True)
        nested.write_text("nested", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [str(nested), str(phase_dir / "handoff.json")],
                    "next": "plan-reviewer-a",
                    "summary": "nested .quest",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        assert any(r["reason"] == "nested_quest" for r in records)

    def test_path_traversal_records_traversal_outside_repo(
        self, workspace: Path
    ) -> None:
        """#5: declared path with ``..`` resolves outside repo_root →
        reason=traversal_outside_repo."""

        quest_id = "test-quest_traversal"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # Resolve outside the repo by walking up via ``..``. We construct an
        # absolute path so the resolve() escapes ``workspace``.
        outside = workspace.parent / "elsewhere" / "plan.md"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("rogue", encoding="utf-8")

        # Reference outside via a relative-with-``..`` form so the validator
        # has to resolve it.
        traversal_relative = "../elsewhere/plan.md"

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [traversal_relative, str(phase_dir / "handoff.json")],
                    "next": "plan-reviewer-a",
                    "summary": "traversal",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        assert any(r["reason"] == "traversal_outside_repo" for r in records)

    def test_noncanonical_filename_records_noncanonical_name(
        self, workspace: Path
    ) -> None:
        """#6: declared filename is not in the canonical set →
        reason=noncanonical_name."""

        quest_id = "test-quest_noncanon"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # ``rogue.md`` is inside the boundary (the phase directory) but the
        # name is not one of {plan.md, handoff.json}.
        rogue = phase_dir / "rogue.md"
        rogue.write_text("rogue", encoding="utf-8")
        good_handoff = phase_dir / "handoff.json"
        good_handoff.write_text("seed", encoding="utf-8")
        good_plan = phase_dir / "plan.md"
        good_plan.write_text("seed", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(rogue),
                        str(good_plan),
                        str(good_handoff),
                    ],
                    "next": "plan-reviewer-a",
                    "summary": "noncanonical name",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        assert any(r["reason"] == "noncanonical_name" for r in records)
        # The other declared paths (plan.md, handoff.json) should pass and
        # NOT add records.
        canonical_failures = [
            r for r in records if r["declared"].endswith(("plan.md", "handoff.json"))
        ]
        assert canonical_failures == []

    def test_multiple_mismatches_append_one_line_per_mismatch(
        self, workspace: Path
    ) -> None:
        """#8: two declared bad paths → two JSON lines; exit non-zero."""

        quest_id = "test-quest_multi"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # Two missing artifacts.
        plan_missing = phase_dir / "plan.md"
        handoff_missing = phase_dir / "handoff.json"
        # NOTE: handoff.json is written for the validator to read, but plan.md
        # stays missing. We write handoff.json then list a DIFFERENT path
        # also (with a noncanonical name) so we get two mismatches.
        handoff_missing.write_text("seed", encoding="utf-8")
        rogue = phase_dir / "rogue.md"
        # rogue path: exists but noncanonical name.
        rogue.write_text("rogue", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(plan_missing),  # missing -> reason=missing
                        str(rogue),  # noncanonical name
                        str(handoff_missing),  # OK
                    ],
                    "next": "plan-reviewer-a",
                    "summary": "two mismatches",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        # Exactly TWO mismatches recorded.
        assert len(records) == 2
        reasons = {r["reason"] for r in records}
        assert reasons == {"missing", "noncanonical_name"}

    def test_log_lines_are_valid_json_with_required_fields(
        self, workspace: Path
    ) -> None:
        """#9: each log line parses; required fields present."""

        quest_id = "test-quest_json_fields"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # One missing artifact -> exactly one log line.
        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(phase_dir / "plan.md"),  # missing
                        str(phase_dir / "handoff.json"),
                    ],
                    "next": "plan-reviewer-a",
                    "summary": "single missing",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=workspace / ".quest" / quest_id,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1

        # The file contains valid JSON lines with required fields.
        required = {"timestamp", "phase", "role", "declared", "actual", "reason"}
        raw = log_path.read_text(encoding="utf-8").splitlines()
        assert raw, "log should contain at least one line"
        for line in raw:
            assert line.strip(), "no blank lines"
            record = json.loads(line)
            assert required.issubset(record.keys()), record
            assert record["phase"] == "phase_01_plan"
            assert record["role"] == "planner"
            assert isinstance(record["timestamp"], str) and record["timestamp"]
            assert record["reason"] in {
                "missing",
                "outside_boundary",
                "noncanonical_name",
                "nested_quest",
                "traversal_outside_repo",
                "unsupported_role_or_phase",
            }


# ---------------------------------------------------------------------------
# CLI stdout contract — current-run-only mismatch attribution
# ---------------------------------------------------------------------------


class TestCliStdoutContract:
    """The CLI prints current-run mismatches to stdout so the orchestrator
    can surface them without misattributing prior runs from the append-only
    ``path_compliance.log`` audit trail.
    """

    def _run_cli(
        self,
        *,
        quest_dir: Path,
        phase: str,
        role: str,
        handoff: Path,
        quest_mode: str,
        repo_root: Path | None = None,
    ) -> subprocess.CompletedProcess:
        import sys as _sys

        script = (
            Path(__file__).resolve().parent.parent.parent
            / "scripts"
            / "quest_artifact_postflight.py"
        )
        argv = [
            _sys.executable,
            str(script),
            "--quest-dir",
            str(quest_dir),
            "--phase",
            phase,
            "--role",
            role,
            "--handoff",
            str(handoff),
            "--quest-mode",
            quest_mode,
        ]
        if repo_root is not None:
            argv.extend(["--workspace-root", str(repo_root)])
        return subprocess.run(argv, capture_output=True, text=True, timeout=20)

    def test_clean_run_emits_no_stdout(self, workspace: Path) -> None:
        """Exit 0 → stdout is empty so the orchestrator can use stdout
        presence as a 'had mismatches' signal."""

        quest_dir, handoff_path, _ = _make_planner_handoff(repo_root=workspace)
        result = self._run_cli(
            quest_dir=quest_dir,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            repo_root=workspace,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == "", repr(result.stdout)

    def test_mismatch_run_emits_only_current_records_to_stdout(
        self, workspace: Path
    ) -> None:
        """Two sequential invocations: the second declares one undeclared
        canonical deliverable. Stdout from the second run must contain
        ONLY that run's mismatch, not earlier records from the first run.
        The persistent log retains BOTH runs' records (append-only audit).
        """

        # First invocation: builder omits builder_feedback_discussion.md.
        quest_id = "test-quest_stdout-attribution"
        quest_dir = workspace / ".quest" / quest_id
        phase_dir = quest_dir / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)

        (phase_dir / "pr_description.md").write_text("seed", encoding="utf-8")
        (phase_dir / "builder_feedback_discussion.md").write_text(
            "seed", encoding="utf-8"
        )

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [str(phase_dir / "pr_description.md")],
                    "next": "code_review",
                    "summary": "first run — omits feedback discussion",
                }
            ),
            encoding="utf-8",
        )

        first = self._run_cli(
            quest_dir=quest_dir,
            phase="phase_02_implementation",
            role="builder",
            handoff=handoff_path,
            quest_mode="workflow",
            repo_root=workspace,
        )
        assert first.returncode == 1
        first_stdout_lines = [
            json.loads(line) for line in first.stdout.splitlines() if line.strip()
        ]
        assert len(first_stdout_lines) == 1
        assert (
            Path(first_stdout_lines[0]["actual"]).name
            == "builder_feedback_discussion.md"
        )

        # Second invocation: planner role in the SAME quest. The role's
        # canonical artifacts differ from the first run; the mismatch
        # surfaced now must not be confused with the first run's record
        # that's still sitting in path_compliance.log.
        plan_phase = quest_dir / "phase_01_plan"
        plan_phase.mkdir(parents=True, exist_ok=True)
        (plan_phase / "plan.md").write_text("seed", encoding="utf-8")
        (plan_phase / "handoff.json").write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [],  # empty -> plan.md missing
                    "next": "plan-reviewer-a",
                    "summary": "second run — planner with empty artifacts",
                }
            ),
            encoding="utf-8",
        )
        second_handoff = plan_phase / "handoff.json"

        second = self._run_cli(
            quest_dir=quest_dir,
            phase="phase_01_plan",
            role="planner",
            handoff=second_handoff,
            quest_mode="workflow",
            repo_root=workspace,
        )
        assert second.returncode == 1
        second_stdout_lines = [
            json.loads(line) for line in second.stdout.splitlines() if line.strip()
        ]
        # Exactly one record from this run — plan.md missing.
        assert len(second_stdout_lines) == 1
        assert Path(second_stdout_lines[0]["actual"]).name == "plan.md"
        # The earlier run's builder_feedback record MUST NOT appear here.
        assert not any(
            Path(r["actual"]).name == "builder_feedback_discussion.md"
            for r in second_stdout_lines
        )

        # The persistent log retains BOTH runs (append-only audit).
        log_path = quest_dir / "logs" / "path_compliance.log"
        all_log_records = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(all_log_records) == 2
        log_names = {Path(r["actual"]).name for r in all_log_records}
        assert log_names == {"builder_feedback_discussion.md", "plan.md"}


# ---------------------------------------------------------------------------
# Coverage check — every canonical artifact must be declared and exist
# ---------------------------------------------------------------------------


class TestCanonicalCoverage:
    """The validator must compare resolved expected_paths to resolved
    declared_paths so an empty ``artifacts: []`` or a canonical-named file at a
    misplaced path cannot silently pass (AC4)."""

    def test_empty_artifacts_array_fails_for_role_with_expected_paths(
        self, workspace: Path
    ) -> None:
        """Planner role expects plan.md + handoff.json. An empty artifacts
        list omits plan.md → one ``missing`` record, exit 1.

        The handoff file is excluded from coverage by design: the validator
        was invoked on the --handoff path so that file's existence is
        implicit. Roles list deliverables in ``artifacts``, not the
        meta-handoff envelope.
        """

        quest_id = "test-quest_empty-artifacts"
        quest_dir = workspace / ".quest" / quest_id
        phase_dir = quest_dir / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [],
                    "next": "plan-reviewer-a",
                    "summary": "empty artifacts",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        missing = [r for r in records if r["reason"] == "missing"]
        assert len(missing) == 1
        assert Path(missing[0]["actual"]).name == "plan.md"
        assert missing[0]["declared"] == "(undeclared)"

    def test_omitted_canonical_deliverable_fails(self, workspace: Path) -> None:
        """Builder declares pr_description.md only — builder_feedback_discussion.md
        (also canonical) is omitted → one ``missing`` record for the omitted
        deliverable, exit 1. The handoff file is excluded from coverage.
        """

        quest_id = "test-quest_omitted-deliverable"
        quest_dir = workspace / ".quest" / quest_id
        phase_dir = quest_dir / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        (phase_dir / "pr_description.md").write_text("seed", encoding="utf-8")
        (phase_dir / "builder_feedback_discussion.md").write_text("seed", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [str(phase_dir / "pr_description.md")],
                    "next": "code_review",
                    "summary": "omitted builder_feedback_discussion.md",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_02_implementation",
            role="builder",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        missing = [r for r in records if r["reason"] == "missing"]
        assert len(missing) == 1
        assert Path(missing[0]["actual"]).name == "builder_feedback_discussion.md"
        assert missing[0]["declared"] == "(undeclared)"

    def test_undeclared_handoff_file_does_not_record_missing(
        self, workspace: Path
    ) -> None:
        """Real-world handoffs do not list the handoff file itself in their
        ``artifacts`` array — agents declare deliverables only. The validator
        must NOT emit a ``missing`` record for the handoff path it was
        invoked on. This is the case the in-tree builder/planner/reviewer
        contracts already produce."""

        quest_id = "test-quest_undeclared-handoff"
        quest_dir = workspace / ".quest" / quest_id
        phase_dir = quest_dir / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        (phase_dir / "plan.md").write_text("seed", encoding="utf-8")
        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [str(phase_dir / "plan.md")],
                    "next": "plan-reviewer-a",
                    "summary": "handoff not in artifacts (real-world shape)",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 0
        if log_path.exists():
            assert log_path.read_text(encoding="utf-8") == ""

    def test_misplaced_canonical_named_file_inside_boundary_fails(
        self, workspace: Path
    ) -> None:
        """Declared path is a canonical-named file at a nested subdir inside
        the phase boundary (e.g., ``phase_01_plan/nested/plan.md``). Per-path
        checks pass it (basename canonical, inside boundary), but the
        coverage check records the canonical path as ``missing`` because it
        was not declared at its expected location."""

        quest_id = "test-quest_misplaced"
        quest_dir = workspace / ".quest" / quest_id
        phase_dir = quest_dir / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = quest_dir / "logs" / "path_compliance.log"

        # Misplaced canonical-named file: phase_01_plan/nested/plan.md
        misplaced = phase_dir / "nested" / "plan.md"
        misplaced.parent.mkdir(parents=True, exist_ok=True)
        misplaced.write_text("seed", encoding="utf-8")
        (phase_dir / "handoff.json").write_text("seed", encoding="utf-8")

        handoff_path = phase_dir / "handoff.json"
        handoff_path.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [
                        str(misplaced),
                        str(phase_dir / "handoff.json"),
                    ],
                    "next": "plan-reviewer-a",
                    "summary": "misplaced plan.md",
                }
            ),
            encoding="utf-8",
        )

        rc = postflight.run(
            quest_dir=quest_dir,
            phase="phase_01_plan",
            role="planner",
            handoff=handoff_path,
            quest_mode="workflow",
            log=log_path,
            repo_root=workspace,
        )
        assert rc == 1
        records = _read_log_lines(log_path)
        missing = [r for r in records if r["reason"] == "missing"]
        # The canonical plan.md location (phase_01_plan/plan.md) was not
        # declared — one missing record for it.
        assert any(
            Path(r["actual"]).name == "plan.md"
            and Path(r["actual"]).parent.name == "phase_01_plan"
            and r["declared"] == "(undeclared)"
            for r in missing
        ), missing


# ---------------------------------------------------------------------------
# Slice D — Latency tests (#11, #12), perf-marker-gated
# ---------------------------------------------------------------------------


def _median_run_ms(
    *,
    quest_dir: Path,
    handoff_path: Path,
    log_path: Path,
    workspace: Path,
    iterations: int = 5,
    role: str = "planner",
    phase: str = "phase_01_plan",
    quest_mode: str = "workflow",
) -> float:
    """Run ``postflight.run(...)`` ``iterations`` times and return median ms."""

    timings: list[float] = []
    for _ in range(iterations):
        # Truncate the log between runs so the latency picture isn't biased
        # by append-only growth.
        if log_path.exists():
            log_path.unlink()
        t0 = time.perf_counter()
        postflight.run(
            quest_dir=quest_dir,
            phase=phase,
            role=role,
            handoff=handoff_path,
            quest_mode=quest_mode,
            log=log_path,
            repo_root=workspace,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        timings.append(elapsed_ms)
    return statistics.median(timings)


class TestLatency:
    """Plan §7.2 #11, #12 — perf-marker-gated."""

    @pytest.mark.perf
    def test_latency_under_target_for_typical_role(self, workspace: Path) -> None:
        """#11: typical 3-artifact happy path. Median of 5 runs < 50 ms."""

        # The planner expected_artifacts_for_role returns 2 entries; declare
        # 3 paths (the 2 canonical + 1 sibling) so the workload matches the
        # plan's 3-artifact figure. Sibling has noncanonical name, so we
        # only use canonical-named files.
        quest_id = "test-quest_perf_3"
        phase_dir = workspace / ".quest" / quest_id / "phase_01_plan"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        # All canonical names so the run passes (latency = pass-path cost).
        plan_md = phase_dir / "plan.md"
        handoff_json = phase_dir / "handoff.json"
        plan_md.write_text("seed", encoding="utf-8")
        handoff_json.write_text("seed", encoding="utf-8")

        # Use the builder role to bump up to 3 artifacts in one phase.
        # Builder canonical: pr_description.md, builder_feedback_discussion.md, handoff.json.
        builder_phase_dir = workspace / ".quest" / quest_id / "phase_02_implementation"
        builder_phase_dir.mkdir(parents=True, exist_ok=True)
        pr_md = builder_phase_dir / "pr_description.md"
        fb_md = builder_phase_dir / "builder_feedback_discussion.md"
        b_handoff = builder_phase_dir / "handoff.json"
        for p in (pr_md, fb_md, b_handoff):
            p.write_text("seed", encoding="utf-8")

        b_handoff.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": [str(pr_md), str(fb_md), str(b_handoff)],
                    "next": "code-reviewer-a",
                    "summary": "perf-3",
                }
            ),
            encoding="utf-8",
        )

        median_ms = _median_run_ms(
            quest_dir=workspace / ".quest" / quest_id,
            handoff_path=b_handoff,
            log_path=log_path,
            workspace=workspace,
            role="builder",
            phase="phase_02_implementation",
        )
        assert median_ms < 50.0, f"median latency {median_ms:.2f} ms >= 50 ms target"

    @pytest.mark.perf
    def test_latency_under_regression_cap_for_stress_case(
        self, workspace: Path
    ) -> None:
        """#12: 20-declared-artifact stress case. Median of 5 runs < 200 ms."""

        # Use the builder role: 3 canonical names. Declare 20 paths (each
        # one of the 3 canonical names, all inside the phase directory).
        quest_id = "test-quest_perf_20"
        phase_dir = workspace / ".quest" / quest_id / "phase_02_implementation"
        phase_dir.mkdir(parents=True, exist_ok=True)
        log_path = workspace / ".quest" / quest_id / "logs" / "path_compliance.log"

        canonical = ["pr_description.md", "builder_feedback_discussion.md", "handoff.json"]
        for name in canonical:
            (phase_dir / name).write_text("seed", encoding="utf-8")

        # 20 declared paths cycling through canonical files (all valid).
        declared = [str(phase_dir / canonical[i % 3]) for i in range(20)]

        b_handoff = phase_dir / "handoff.json"
        b_handoff.write_text(
            json.dumps(
                {
                    "status": "complete",
                    "artifacts": declared,
                    "next": "code-reviewer-a",
                    "summary": "perf-20",
                }
            ),
            encoding="utf-8",
        )

        median_ms = _median_run_ms(
            quest_dir=workspace / ".quest" / quest_id,
            handoff_path=b_handoff,
            log_path=log_path,
            workspace=workspace,
            role="builder",
            phase="phase_02_implementation",
        )
        assert median_ms < 200.0, (
            f"median latency {median_ms:.2f} ms >= 200 ms regression cap"
        )
