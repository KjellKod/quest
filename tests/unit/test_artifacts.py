"""Unit tests for Quest artifact helpers and failure classification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import quest_runtime.claude_runner as claude_runner_module
from quest_runtime.plan_iterations import PlanIterationError
from quest_runtime.state import StateError
from quest_runtime.artifacts import (
    ROLE_ARTIFACTS,
    SOLO_DISABLED_AGENTS,
    any_artifact_missing_or_empty,
    check_artifact_paths,
    default_quest_dir,
    expected_artifacts_for_role,
    is_workspace_local,
    prepare_artifact_files,
)
from quest_runtime.claude_runner import (
    RunResult,
    classify_failure_kind,
    classify_result_kind,
    run_claude_role,
)

# ---------------------------------------------------------------------------
# Artifact resolution
# ---------------------------------------------------------------------------


class TestExpectedArtifactsForRole:
    def test_planner_returns_correct_paths(self, tmp_path: Path):
        paths = expected_artifacts_for_role(tmp_path, "plan", "planner")
        names = [p.name for p in paths]
        assert names == ["plan.md", "handoff.json"]
        assert all(p.is_absolute() for p in paths)
        assert all("phase_01_plan" in str(p) for p in paths)

    def test_builder_returns_correct_paths(self, tmp_path: Path):
        paths = expected_artifacts_for_role(tmp_path, "implementation", "builder")
        names = [p.name for p in paths]
        assert names == [
            "pr_description.md",
            "builder_feedback_discussion.md",
            "handoff.json",
        ]
        assert all("phase_02_implementation" in str(p) for p in paths)

    def test_code_reviewer_a_returns_correct_paths(self, tmp_path: Path):
        paths = expected_artifacts_for_role(tmp_path, "review", "code-reviewer-a")
        names = [p.name for p in paths]
        assert names == [
            "review_code-reviewer-a.md",
            "review_findings_code-reviewer-a.json",
            "handoff_code-reviewer-a.json",
        ]
        assert all("phase_03_review" in str(p) for p in paths)

    def test_fixer_returns_correct_paths(self, tmp_path: Path):
        paths = expected_artifacts_for_role(tmp_path, "fix", "fixer")
        names = [p.name for p in paths]
        assert names == ["review_fix_feedback_discussion.md", "handoff_fixer.json"]

    def test_arbiter_uses_next_artifacts_and_no_backlog(self, tmp_path: Path):
        paths = expected_artifacts_for_role(tmp_path, "plan_review", "arbiter")
        names = [p.name for p in paths]
        assert names == [
            "arbiter_verdict.md.next",
            "review_findings.json.next",
            "handoff_arbiter.json",
        ]

    def test_arbiter_findings_only_subset_excludes_verdict(self, tmp_path: Path):
        paths = expected_artifacts_for_role(
            tmp_path,
            "plan_review",
            "arbiter",
            artifact_subset="findings-only",
        )

        assert [path.name for path in paths] == [
            "review_findings.json.next",
            "handoff_arbiter.json",
        ]

    def test_findings_only_subset_is_rejected_for_other_roles(self, tmp_path: Path):
        with pytest.raises(ValueError, match="artifact subset"):
            expected_artifacts_for_role(
                tmp_path,
                "plan",
                "planner",
                artifact_subset="findings-only",
            )

    def test_review_arbiter_uses_next_artifacts_in_review_phase(self, tmp_path: Path):
        paths = expected_artifacts_for_role(tmp_path, "code_review", "review-arbiter")
        names = [p.name for p in paths]
        assert names == [
            "review_arbiter_verdict.md.next",
            "review_findings.json.next",
            "handoff_review-arbiter.json",
        ]
        assert all("phase_03_review" in str(p) for p in paths)

    def test_review_arbiter_returns_empty_in_solo_mode(self, tmp_path: Path):
        paths = expected_artifacts_for_role(
            tmp_path, "code_review", "review-arbiter", quest_mode="solo"
        )
        assert paths == []

    def test_solo_mode_excludes_disabled_agents(self, tmp_path: Path):
        for agent in SOLO_DISABLED_AGENTS:
            paths = expected_artifacts_for_role(
                tmp_path, "plan", agent, quest_mode="solo"
            )
            assert paths == [], f"Expected empty for solo-disabled agent {agent}"

    def test_solo_mode_keeps_enabled_agents(self, tmp_path: Path):
        paths = expected_artifacts_for_role(
            tmp_path, "plan", "planner", quest_mode="solo"
        )
        assert len(paths) == 2

    def test_unknown_role_raises_value_error(self, tmp_path: Path):
        with pytest.raises(ValueError, match="Unsupported quest role"):
            expected_artifacts_for_role(tmp_path, "plan", "nonexistent-role")

    def test_invalid_phase_for_role_raises_value_error(self, tmp_path: Path):
        with pytest.raises(ValueError, match="not valid for phase"):
            expected_artifacts_for_role(tmp_path, "build", "planner")

    def test_every_role_accepts_its_own_artifact_directory_as_the_phase(
        self, tmp_path: Path
    ):
        # The directory name is what a caller sees on disk, so passing it is
        # the natural mistake. It must resolve to the same paths as the alias.
        for agent, (phase_dir, _) in ROLE_ARTIFACTS.items():
            by_dir = expected_artifacts_for_role(tmp_path, phase_dir, agent)
            assert by_dir, f"{agent} resolved no artifacts via {phase_dir}"
            assert all(p.parent.name == phase_dir for p in by_dir)

        # Equivalence with the canonical alias, spot-checked on one role.
        assert expected_artifacts_for_role(
            tmp_path, "phase_03_review", "code-reviewer-b"
        ) == expected_artifacts_for_role(tmp_path, "code_review", "code-reviewer-b")

    def test_another_roles_directory_is_still_rejected(self, tmp_path: Path):
        # Accepting the *own* directory must not turn into accepting any
        # directory — a planner asked to run in the review phase is still wrong.
        with pytest.raises(ValueError, match="not valid for phase"):
            expected_artifacts_for_role(tmp_path, "phase_03_review", "planner")

    def test_rejection_message_lists_the_directory_alias(self, tmp_path: Path):
        with pytest.raises(ValueError, match="phase_01_plan"):
            expected_artifacts_for_role(tmp_path, "nonsense_phase", "planner")

    def test_all_roles_in_mapping_resolve(self, tmp_path: Path):
        valid_phases = {
            "planner": "plan",
            "plan-reviewer-a": "plan_review",
            "plan-reviewer-b": "plan_review",
            "arbiter": "plan_review",
            "builder": "implementation",
            "code-reviewer-a": "code_review",
            "code-reviewer-b": "code_review",
            "review-arbiter": "code_review",
            "fixer": "fix",
        }
        for role in ROLE_ARTIFACTS:
            paths = expected_artifacts_for_role(tmp_path, valid_phases[role], role)
            assert len(paths) > 0, f"Role {role} returned no artifacts"


# ---------------------------------------------------------------------------
# Artifact preparation
# ---------------------------------------------------------------------------


class TestPrepareArtifactFiles:
    def test_creates_directories_and_files(self, tmp_path: Path):
        paths = [
            tmp_path / "deep" / "nested" / "file.md",
            tmp_path / "deep" / "another.json",
        ]
        result = prepare_artifact_files(paths, quest_dir=tmp_path, role="probe")
        assert len(result) == 2
        for p in result:
            assert p.exists()
            assert p.stat().st_size == 0

    def test_truncates_existing_files(self, tmp_path: Path):
        target = tmp_path / "existing.md"
        target.write_text("old content", encoding="utf-8")
        assert target.stat().st_size > 0

        prepare_artifact_files([target], quest_dir=tmp_path, role="probe")
        assert target.stat().st_size == 0

    def test_idempotent(self, tmp_path: Path):
        paths = [tmp_path / "a.md", tmp_path / "b.json"]
        prepare_artifact_files(paths, quest_dir=tmp_path, role="probe")
        result = prepare_artifact_files(paths, quest_dir=tmp_path, role="probe")
        assert len(result) == 2
        assert all(p.exists() for p in result)

    def test_returns_resolved_paths(self, tmp_path: Path):
        relative_looking = tmp_path / "sub" / ".." / "file.md"
        result = prepare_artifact_files(
            [relative_looking], quest_dir=tmp_path, role="probe"
        )
        assert len(result) == 1
        assert ".." not in str(result[0])

    def test_arbiter_prepare_touches_next_files_not_canonical_artifacts(
        self, tmp_path: Path
    ):
        quest_dir = tmp_path / "quest"
        canonical = quest_dir / "phase_01_plan" / "review_findings.json"
        verdict = quest_dir / "phase_01_plan" / "arbiter_verdict.md"
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text('[{"finding_id":"stable"}]\n', encoding="utf-8")
        verdict.write_text("APPROVED\n", encoding="utf-8")
        original = canonical.read_text(encoding="utf-8")
        original_verdict = verdict.read_text(encoding="utf-8")

        artifacts = expected_artifacts_for_role(quest_dir, "plan_review", "arbiter")
        prepare_artifact_files(artifacts, quest_dir=quest_dir, role="arbiter")

        assert canonical.read_text(encoding="utf-8") == original
        assert verdict.read_text(encoding="utf-8") == original_verdict
        assert (quest_dir / "phase_01_plan" / "arbiter_verdict.md.next").exists()
        assert (quest_dir / "phase_01_plan" / "review_findings.json.next").exists()

    def test_arbiter_prepare_creates_missing_verdict_scratch(self, tmp_path: Path):
        quest_dir = tmp_path / "quest"
        verdict = quest_dir / "phase_01_plan" / "arbiter_verdict.md"
        verdict_next = quest_dir / "phase_01_plan" / "arbiter_verdict.md.next"

        artifacts = expected_artifacts_for_role(quest_dir, "plan_review", "arbiter")
        prepare_artifact_files(artifacts, quest_dir=quest_dir, role="arbiter")

        assert not verdict.exists()
        assert verdict_next.exists()
        assert verdict_next.read_text(encoding="utf-8") == ""

    def test_requires_explicit_quest_and_role_context(self, tmp_path: Path):
        with pytest.raises(TypeError):
            prepare_artifact_files([tmp_path / "plan.md"])

    def test_planner_missing_state_preserves_existing_artifacts(self, tmp_path: Path):
        quest_dir = tmp_path / "quest"
        plan_dir = quest_dir / "phase_01_plan"
        plan_dir.mkdir(parents=True)
        plan = plan_dir / "plan.md"
        handoff = plan_dir / "handoff.json"
        plan.write_bytes(b"CURRENT PLAN\n")
        handoff.write_bytes(b"CURRENT HANDOFF\n")
        before = (plan.read_bytes(), handoff.read_bytes())

        with pytest.raises(StateError, match=r"state_error\[read\]"):
            prepare_artifact_files([plan, handoff], quest_dir=quest_dir, role="planner")

        assert (plan.read_bytes(), handoff.read_bytes()) == before

    @pytest.mark.parametrize("iteration", [True, 0, -1])
    def test_planner_invalid_iteration_preserves_existing_artifacts(
        self,
        tmp_path: Path,
        iteration: object,
    ):
        quest_dir = tmp_path / "quest"
        plan_dir = quest_dir / "phase_01_plan"
        plan_dir.mkdir(parents=True)
        (quest_dir / "state.json").write_text(
            json.dumps({"phase": "plan", "plan_iteration": iteration}),
            encoding="utf-8",
        )
        plan = plan_dir / "plan.md"
        handoff = plan_dir / "handoff.json"
        plan.write_bytes(b"CURRENT PLAN\n")
        handoff.write_bytes(b"CURRENT HANDOFF\n")
        before = (plan.read_bytes(), handoff.read_bytes())

        with pytest.raises(StateError, match=r"state_error\[shape\]"):
            prepare_artifact_files([plan, handoff], quest_dir=quest_dir, role="planner")

        assert (plan.read_bytes(), handoff.read_bytes()) == before

    def test_padded_planner_role_still_verifies_predecessor_before_truncation(
        self, tmp_path: Path
    ):
        quest_dir = tmp_path / "quest"
        plan_dir = quest_dir / "phase_01_plan"
        plan_dir.mkdir(parents=True)
        (quest_dir / "state.json").write_text(
            json.dumps({"phase": "plan", "plan_iteration": 2}),
            encoding="utf-8",
        )
        plan = plan_dir / "plan.md"
        handoff = plan_dir / "handoff.json"
        plan.write_bytes(b"CURRENT PLAN\n")
        handoff.write_bytes(b"CURRENT HANDOFF\n")
        before = (plan.read_bytes(), handoff.read_bytes())

        with pytest.raises(PlanIterationError, match="snapshot_unsealed"):
            prepare_artifact_files(
                [plan, handoff], quest_dir=quest_dir, role=" planner "
            )

        assert (plan.read_bytes(), handoff.read_bytes()) == before

    def test_planner_malformed_iteration_returns_structured_invocation_error(
        self,
        tmp_path: Path,
    ):
        quest_dir = tmp_path / "quest"
        plan_dir = quest_dir / "phase_01_plan"
        plan_dir.mkdir(parents=True)
        (quest_dir / "state.json").write_text(
            json.dumps({"phase": "plan", "plan_iteration": "3"}),
            encoding="utf-8",
        )
        prompt = quest_dir / "prompt.md"
        prompt.write_text("Planner prompt\n", encoding="utf-8")
        plan = plan_dir / "plan.md"
        handoff = plan_dir / "handoff.json"
        plan.write_bytes(b"CURRENT PLAN\n")
        handoff.write_bytes(b"CURRENT HANDOFF\n")
        before = (plan.read_bytes(), handoff.read_bytes())

        result = run_claude_role(
            cwd=quest_dir,
            quest_dir=quest_dir,
            phase="plan",
            agent="planner",
            iteration=3,
            prompt_file=prompt,
            handoff_file=handoff,
            bridge_script=quest_dir / "unused-bridge.py",
            model="claude",
            timeout=1,
            permission_mode="bypassPermissions",
            artifact_paths=[plan, handoff],
        )

        assert result.exit_code == 1
        assert result.handoff_state == "missing"
        assert result.result_kind == "invocation_error"
        assert "state_error[shape]" in result.stderr
        assert (plan.read_bytes(), handoff.read_bytes()) == before

    def test_findings_only_arbiter_retry_preserves_verdict_scratch(
        self, tmp_path: Path
    ):
        quest_dir = tmp_path / "quest"
        plan_dir = quest_dir / "phase_01_plan"
        plan_dir.mkdir(parents=True)
        verdict_next = plan_dir / "arbiter_verdict.md.next"
        findings_next = plan_dir / "review_findings.json.next"
        handoff = plan_dir / "handoff_arbiter.json"
        verdict_next.write_bytes(b"VALID VERDICT\n")
        findings_next.write_text("stale findings\n", encoding="utf-8")
        handoff.write_text("stale handoff\n", encoding="utf-8")

        before = (
            verdict_next.read_bytes(),
            verdict_next.stat().st_ino,
            verdict_next.stat().st_mtime_ns,
        )
        prepared = prepare_artifact_files(
            [findings_next, handoff], quest_dir=quest_dir, role="arbiter"
        )

        assert prepared == [findings_next.resolve(), handoff.resolve()]
        assert findings_next.read_bytes() == b""
        assert handoff.read_bytes() == b""
        assert (
            verdict_next.read_bytes(),
            verdict_next.stat().st_ino,
            verdict_next.stat().st_mtime_ns,
        ) == before


# ---------------------------------------------------------------------------
# Workspace-local check
# ---------------------------------------------------------------------------


class TestIsWorkspaceLocal:
    def test_path_under_workspace(self, tmp_path: Path):
        child = tmp_path / "sub" / "file.md"
        child.parent.mkdir(parents=True, exist_ok=True)
        child.touch()
        assert is_workspace_local(child, tmp_path) is True

    def test_path_outside_workspace(self, tmp_path: Path):
        outside = tmp_path.parent / "elsewhere" / "file.md"
        assert is_workspace_local(outside, tmp_path) is False

    def test_workspace_root_itself(self, tmp_path: Path):
        assert is_workspace_local(tmp_path, tmp_path) is True

    def test_symlink_under_workspace(self, tmp_path: Path):
        real_file = tmp_path / "real.md"
        real_file.touch()
        link = tmp_path / "link.md"
        link.symlink_to(real_file)
        assert is_workspace_local(link, tmp_path) is True


# ---------------------------------------------------------------------------
# Path partitioning
# ---------------------------------------------------------------------------


class TestCheckArtifactPaths:
    def test_mixed_paths_split_correctly(self, tmp_path: Path):
        local = tmp_path / "inside.md"
        external = tmp_path.parent / "outside.md"
        local_list, external_list = check_artifact_paths([local, external], tmp_path)
        assert len(local_list) == 1
        assert len(external_list) == 1

    def test_all_local(self, tmp_path: Path):
        paths = [tmp_path / "a.md", tmp_path / "b.md"]
        local_list, external_list = check_artifact_paths(paths, tmp_path)
        assert len(local_list) == 2
        assert len(external_list) == 0

    def test_all_external(self, tmp_path: Path):
        paths = [tmp_path.parent / "x.md"]
        local_list, external_list = check_artifact_paths(paths, tmp_path)
        assert len(local_list) == 0
        assert len(external_list) == 1


# ---------------------------------------------------------------------------
# any_artifact_missing_or_empty
# ---------------------------------------------------------------------------


class TestAnyArtifactMissingOrEmpty:
    def test_missing_file(self, tmp_path: Path):
        assert any_artifact_missing_or_empty([tmp_path / "nope.md"]) is True

    def test_empty_file(self, tmp_path: Path):
        f = tmp_path / "empty.md"
        f.write_text("", encoding="utf-8")
        assert any_artifact_missing_or_empty([f]) is True

    def test_non_empty_file(self, tmp_path: Path):
        f = tmp_path / "ok.md"
        f.write_text("content", encoding="utf-8")
        assert any_artifact_missing_or_empty([f]) is False

    def test_mixed_present_and_missing(self, tmp_path: Path):
        present = tmp_path / "present.md"
        present.write_text("content", encoding="utf-8")
        missing = tmp_path / "missing.md"
        assert any_artifact_missing_or_empty([present, missing]) is True


# ---------------------------------------------------------------------------
# default_quest_dir
# ---------------------------------------------------------------------------


class TestDefaultQuestDir:
    def test_returns_repo_local_path(self, tmp_path: Path):
        result = default_quest_dir(tmp_path, "my-quest_2026-01-01__0000")
        assert result == tmp_path / ".quest" / "my-quest_2026-01-01__0000"
        assert result.is_absolute()


# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------


def _make_result(
    *,
    exit_code: int = 1,
    result_kind: str = "error",
    stderr: str = "",
) -> RunResult:
    return RunResult(
        exit_code=exit_code,
        handoff_state="missing",
        result_kind=result_kind,
        source=None,
        stdout="",
        stderr=stderr,
    )


class TestClassifyFailureKind:
    def test_timeout(self, tmp_path: Path):
        result = _make_result(result_kind="timeout")
        assert classify_failure_kind(result, [], tmp_path) == "timeout"

    def test_invocation_error(self, tmp_path: Path):
        result = _make_result(result_kind="invocation_error")
        assert classify_failure_kind(result, [], tmp_path) == "invocation"

    def test_artifacts_exist_and_nonempty_returns_model(self, tmp_path: Path):
        artifact = tmp_path / "handoff.json"
        artifact.write_text('{"status":"complete"}', encoding="utf-8")
        result = _make_result(result_kind="handoff_missing")
        assert classify_failure_kind(result, [artifact], tmp_path) == "model"

    def test_artifacts_missing_out_of_workspace_returns_write_boundary(
        self, tmp_path: Path
    ):
        workspace = tmp_path / "repo"
        workspace.mkdir()
        external_artifact = tmp_path / "external" / "handoff.json"
        result = _make_result(result_kind="handoff_missing")
        assert (
            classify_failure_kind(result, [external_artifact], workspace)
            == "write_boundary"
        )

    def test_partial_write_out_of_workspace_returns_write_boundary(
        self, tmp_path: Path
    ):
        """Arbiter-mandated: plan.md written but handoff.json missing, external path."""
        workspace = tmp_path / "repo"
        workspace.mkdir()
        external_dir = tmp_path / "external" / "phase_01_plan"
        external_dir.mkdir(parents=True)
        plan = external_dir / "plan.md"
        plan.write_text("# Plan\ncontent", encoding="utf-8")
        handoff = external_dir / "handoff.json"
        # handoff.json does NOT exist
        result = _make_result(result_kind="handoff_missing")
        assert (
            classify_failure_kind(result, [plan, handoff], workspace)
            == "write_boundary"
        )

    def test_permission_denied_in_stderr(self, tmp_path: Path):
        artifact = tmp_path / "handoff.json"
        # artifact missing but path is workspace-local → not write_boundary
        result = _make_result(stderr="Error: Permission denied writing to /foo/bar")
        assert classify_failure_kind(result, [artifact], tmp_path) == "permission"

    def test_permission_denied_after_result_classification_returns_permission(
        self, tmp_path: Path
    ):
        artifact = tmp_path / "handoff.json"
        result = _make_result(
            result_kind=classify_result_kind(
                1,
                "Error: Permission denied writing to /foo/bar",
                "missing",
            ),
            stderr="Error: Permission denied writing to /foo/bar",
        )
        assert classify_failure_kind(result, [artifact], tmp_path) == "permission"

    def test_default_is_model(self, tmp_path: Path):
        artifact = tmp_path / "handoff.json"
        # missing, workspace-local, no permission error → model
        result = _make_result(result_kind="handoff_missing")
        assert classify_failure_kind(result, [artifact], tmp_path) == "model"

    def test_empty_artifact_list_returns_model(self, tmp_path: Path):
        result = _make_result(result_kind="handoff_missing")
        assert classify_failure_kind(result, [], tmp_path) == "model"


class TestRunClaudeRole:
    def test_planner_dispatch_rejects_when_immediate_predecessor_is_unsealed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        quest_dir = tmp_path / "quest"
        plan_dir = quest_dir / "phase_01_plan"
        plan_dir.mkdir(parents=True)
        (quest_dir / "state.json").write_text(
            json.dumps(
                {
                    "phase": "plan",
                    "status": "in_progress",
                    "quest_mode": "workflow",
                    "plan_iteration": 3,
                }
            )
            + "\n",
            encoding="utf-8",
        )

        # Iteration 1 exists, but Planner iteration 3 must require its immediate
        # predecessor, iteration 2. Accepting any older seal is an off-by-one
        # data-loss bug.
        old_history = quest_dir / "history" / "plan" / "iteration-0001"
        old_history.mkdir(parents=True)
        old_plan = old_history / "plan.md"
        old_plan.write_text("# Iteration 1\n", encoding="utf-8")
        old_digest = hashlib.sha256(old_plan.read_bytes()).hexdigest()
        (old_history / "snapshot.json").write_text(
            json.dumps(
                {
                    "plan_iteration": 1,
                    "quest_mode": "workflow",
                    "decision": "planner",
                    "reason": "automatic_refinement",
                    "bootstrap_snapshot": True,
                    "files": {"plan.md": old_digest},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        prompt_file = quest_dir / "logs" / "planner_prompt.md"
        prompt_file.parent.mkdir(parents=True)
        prompt_file.write_text("plan", encoding="utf-8")
        plan_file = plan_dir / "plan.md"
        handoff_file = plan_dir / "handoff.json"
        plan_file.write_bytes(b"ITERATION 2 PLAN\n")
        handoff_file.write_bytes(b'{"status":"complete"}\n')
        before = {
            plan_file: plan_file.read_bytes(),
            handoff_file: handoff_file.read_bytes(),
        }

        monkeypatch.setattr(
            claude_runner_module.subprocess,
            "Popen",
            lambda *args, **kwargs: pytest.fail(
                "planner dispatch started before predecessor verification"
            ),
        )

        result = None
        try:
            result = run_claude_role(
                cwd=tmp_path,
                quest_dir=quest_dir,
                phase="plan",
                agent="planner",
                iteration=3,
                prompt_file=prompt_file,
                handoff_file=handoff_file,
                bridge_script=tmp_path / "bridge.py",
                model="opus",
                timeout=1.0,
                permission_mode="bypassPermissions",
                artifact_paths=[plan_file, handoff_file],
                poll_interval=0.01,
                exit_grace_seconds=0.01,
            )
        finally:
            assert {path: path.read_bytes() for path in before} == before

        assert result is not None
        assert result.exit_code != 0
        assert result.result_kind == "invocation_error"

    def test_artifact_preparation_error_returns_structured_invocation_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("prompt", encoding="utf-8")
        handoff_file = tmp_path / "handoff.json"
        artifact = tmp_path / "plan.md"

        def fake_prepare(
            paths: list[Path], *, quest_dir: Path, role: str
        ) -> list[Path]:
            assert quest_dir == tmp_path
            assert role == "planner"
            raise OSError("disk full")

        monkeypatch.setattr(
            claude_runner_module, "prepare_artifact_files", fake_prepare
        )

        result = run_claude_role(
            cwd=tmp_path,
            quest_dir=tmp_path,
            phase="plan",
            agent="planner",
            iteration=1,
            prompt_file=prompt_file,
            handoff_file=handoff_file,
            bridge_script=tmp_path / "bridge.py",
            model="opus",
            timeout=1.0,
            permission_mode="bypassPermissions",
            artifact_paths=[artifact],
            poll_interval=0.01,
            exit_grace_seconds=0.01,
        )

        assert result.exit_code == 1
        assert result.handoff_state == "missing"
        assert result.result_kind == "invocation_error"
        assert result.source is None
        assert "disk full" in result.stderr

    def test_artifact_preparation_permission_error_retries_without_crashing(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        workspace = tmp_path / "repo"
        workspace.mkdir()
        prompt_file = workspace / "prompt.txt"
        prompt_file.write_text("prompt", encoding="utf-8")
        handoff_file = workspace / "handoff.json"
        external_artifact = tmp_path / "external" / "plan.md"
        prepare_calls = {"count": 0}

        def fake_prepare(
            paths: list[Path], *, quest_dir: Path, role: str
        ) -> list[Path]:
            assert quest_dir == workspace
            assert role == "planner"
            prepare_calls["count"] += 1
            raise PermissionError("Permission denied")

        class FakeProcess:
            returncode = 0

            def communicate(self, timeout: float | None = None):
                external_artifact.parent.mkdir(parents=True, exist_ok=True)
                external_artifact.write_text("ok", encoding="utf-8")
                handoff_file.write_text(
                    '{"status":"complete","artifacts":["plan.md"],"next":null,"summary":"ok"}',
                    encoding="utf-8",
                )
                return "", ""

            def poll(self):
                return None

            def terminate(self):
                return None

            def kill(self):
                return None

        monkeypatch.setattr(
            claude_runner_module, "prepare_artifact_files", fake_prepare
        )
        monkeypatch.setattr(
            claude_runner_module.subprocess,
            "Popen",
            lambda *args, **kwargs: FakeProcess(),
        )

        result = run_claude_role(
            cwd=workspace,
            quest_dir=workspace,
            phase="plan",
            agent="planner",
            iteration=1,
            prompt_file=prompt_file,
            handoff_file=handoff_file,
            bridge_script=workspace / "bridge.py",
            model="opus",
            timeout=1.0,
            permission_mode="bypassPermissions",
            artifact_paths=[external_artifact],
            poll_interval=0.01,
            exit_grace_seconds=0.01,
        )

        assert prepare_calls["count"] == 1
        assert result.exit_code == 0
        assert result.result_kind == "handoff_json"
        assert "Tier B retry:" in result.stderr

    def test_handoff_without_required_artifact_content_is_not_success(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("prompt", encoding="utf-8")
        (tmp_path / "state.json").write_text(
            '{"phase":"plan","plan_iteration":1}', encoding="utf-8"
        )
        handoff_file = tmp_path / "handoff.json"
        artifact = tmp_path / "plan.md"

        class FakeProcess:
            returncode = 1

            def communicate(self, timeout: float | None = None):
                handoff_file.write_text(
                    '{"status":"complete","artifacts":["plan.md"],"next":null,"summary":"ok"}',
                    encoding="utf-8",
                )
                return "", ""

            def poll(self):
                return 1

            def terminate(self):
                return None

            def kill(self):
                return None

        monkeypatch.setattr(
            claude_runner_module.subprocess,
            "Popen",
            lambda *args, **kwargs: FakeProcess(),
        )

        result = run_claude_role(
            cwd=tmp_path,
            quest_dir=tmp_path,
            phase="plan",
            agent="planner",
            iteration=1,
            prompt_file=prompt_file,
            handoff_file=handoff_file,
            bridge_script=tmp_path / "bridge.py",
            model="opus",
            timeout=1.0,
            permission_mode="bypassPermissions",
            artifact_paths=[artifact],
            poll_interval=0.01,
            exit_grace_seconds=0.01,
        )

        assert result.exit_code != 0
        assert result.handoff_state == "found"
        assert result.result_kind != "handoff_json"
        assert result.source is None

    def test_external_artifact_dir_only_added_on_permission_retry(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        workspace = tmp_path / "repo"
        workspace.mkdir()
        (workspace / "state.json").write_text(
            '{"phase":"plan","plan_iteration":1}', encoding="utf-8"
        )
        prompt_file = workspace / "prompt.txt"
        prompt_file.write_text("prompt", encoding="utf-8")
        handoff_file = workspace / "handoff.json"
        external_artifact = tmp_path / "external" / "plan.md"
        captured_add_dirs: list[list[str]] = []
        popen_calls = {"count": 0}

        def fake_build_bridge_cmd(**kwargs):
            captured_add_dirs.append(list(kwargs["add_dirs"]))
            return ["bridge"]

        class FakeProcess:
            def __init__(self, *, on_communicate=None):
                self.returncode = 1
                self._on_communicate = on_communicate

            def communicate(self, timeout: float | None = None):
                if self._on_communicate is not None:
                    self._on_communicate()
                return "", "Permission denied writing artifact"

            def poll(self):
                return 1

            def terminate(self):
                return None

            def kill(self):
                return None

        def complete_second_attempt():
            external_artifact.write_text("ok", encoding="utf-8")
            handoff_file.write_text(
                '{"status":"complete","artifacts":["plan.md"],"next":null,"summary":"ok"}',
                encoding="utf-8",
            )

        def fake_popen(*args, **kwargs):
            popen_calls["count"] += 1
            if popen_calls["count"] == 1:
                return FakeProcess()
            return FakeProcess(on_communicate=complete_second_attempt)

        monkeypatch.setattr(
            claude_runner_module, "build_bridge_cmd", fake_build_bridge_cmd
        )
        monkeypatch.setattr(
            claude_runner_module.subprocess,
            "Popen",
            lambda *args, **kwargs: fake_popen(),
        )

        result = run_claude_role(
            cwd=workspace,
            quest_dir=workspace,
            phase="plan",
            agent="planner",
            iteration=1,
            prompt_file=prompt_file,
            handoff_file=handoff_file,
            bridge_script=workspace / "bridge.py",
            model="opus",
            timeout=1.0,
            permission_mode="bypassPermissions",
            artifact_paths=[external_artifact],
            poll_interval=0.01,
            exit_grace_seconds=0.01,
        )

        assert result.exit_code == 0
        assert len(captured_add_dirs) == 2
        assert external_artifact.parent.resolve() not in captured_add_dirs[0]
        assert external_artifact.parent.resolve() in captured_add_dirs[1]
        assert "Tier B retry:" in result.stderr

    def test_permission_escalation_retry_does_not_reprepare_artifacts(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("prompt", encoding="utf-8")
        handoff_file = tmp_path / "handoff.json"
        handoff_file.write_text('{"status":"complete"}', encoding="utf-8")
        artifact = tmp_path / "plan.md"
        artifact.write_text("keep me", encoding="utf-8")

        prepare_calls: list[list[Path]] = []

        def fake_prepare(
            paths: list[Path], *, quest_dir: Path, role: str
        ) -> list[Path]:
            assert quest_dir == tmp_path
            assert role == "planner"
            prepare_calls.append([Path(path) for path in paths])
            return [Path(path) for path in paths]

        class FakeProcess:
            returncode = 0

            def communicate(self, timeout: float | None = None):
                return "", ""

            def poll(self):
                return None

            def terminate(self):
                return None

            def kill(self):
                return None

        monkeypatch.setattr(
            claude_runner_module, "prepare_artifact_files", fake_prepare
        )
        monkeypatch.setattr(
            claude_runner_module.subprocess,
            "Popen",
            lambda *args, **kwargs: FakeProcess(),
        )

        result = run_claude_role(
            cwd=tmp_path,
            quest_dir=tmp_path,
            phase="plan",
            agent="planner",
            iteration=1,
            prompt_file=prompt_file,
            handoff_file=handoff_file,
            bridge_script=tmp_path / "bridge.py",
            model="opus",
            timeout=1.0,
            permission_mode="bypassPermissions",
            artifact_paths=[artifact],
            permission_escalation=True,
        )

        assert result.result_kind == "handoff_json"
        assert prepare_calls == []
        assert artifact.read_text(encoding="utf-8") == "keep me"
