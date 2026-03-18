"""Unit tests for Quest artifact helpers and failure classification."""

from __future__ import annotations

from pathlib import Path

import pytest

import quest_runtime.claude_runner as claude_runner_module
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
from quest_runtime.claude_runner import RunResult, classify_failure_kind, run_claude_role


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
        assert names == ["pr_description.md", "builder_feedback_discussion.md", "handoff.json"]
        assert all("phase_02_implementation" in str(p) for p in paths)

    def test_code_reviewer_a_returns_correct_paths(self, tmp_path: Path):
        paths = expected_artifacts_for_role(tmp_path, "review", "code-reviewer-a")
        names = [p.name for p in paths]
        assert names == ["review_code-reviewer-a.md", "handoff_code-reviewer-a.json"]
        assert all("phase_03_review" in str(p) for p in paths)

    def test_fixer_returns_correct_paths(self, tmp_path: Path):
        paths = expected_artifacts_for_role(tmp_path, "review", "fixer")
        names = [p.name for p in paths]
        assert names == ["review_fix_feedback_discussion.md", "handoff_fixer.json"]

    def test_solo_mode_excludes_disabled_agents(self, tmp_path: Path):
        for agent in SOLO_DISABLED_AGENTS:
            paths = expected_artifacts_for_role(tmp_path, "plan", agent, quest_mode="solo")
            assert paths == [], f"Expected empty for solo-disabled agent {agent}"

    def test_solo_mode_keeps_enabled_agents(self, tmp_path: Path):
        paths = expected_artifacts_for_role(tmp_path, "plan", "planner", quest_mode="solo")
        assert len(paths) == 2

    def test_unknown_role_raises_value_error(self, tmp_path: Path):
        with pytest.raises(ValueError, match="Unsupported quest role"):
            expected_artifacts_for_role(tmp_path, "plan", "nonexistent-role")

    def test_all_roles_in_mapping_resolve(self, tmp_path: Path):
        for role in ROLE_ARTIFACTS:
            paths = expected_artifacts_for_role(tmp_path, "any", role)
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
        result = prepare_artifact_files(paths)
        assert len(result) == 2
        for p in result:
            assert p.exists()
            assert p.stat().st_size == 0

    def test_truncates_existing_files(self, tmp_path: Path):
        target = tmp_path / "existing.md"
        target.write_text("old content", encoding="utf-8")
        assert target.stat().st_size > 0

        prepare_artifact_files([target])
        assert target.stat().st_size == 0

    def test_idempotent(self, tmp_path: Path):
        paths = [tmp_path / "a.md", tmp_path / "b.json"]
        prepare_artifact_files(paths)
        result = prepare_artifact_files(paths)
        assert len(result) == 2
        assert all(p.exists() for p in result)

    def test_returns_resolved_paths(self, tmp_path: Path):
        relative_looking = tmp_path / "sub" / ".." / "file.md"
        result = prepare_artifact_files([relative_looking])
        assert len(result) == 1
        assert ".." not in str(result[0])


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

    def test_artifacts_missing_out_of_workspace_returns_write_boundary(self, tmp_path: Path):
        workspace = tmp_path / "repo"
        workspace.mkdir()
        external_artifact = tmp_path / "external" / "handoff.json"
        result = _make_result(result_kind="handoff_missing")
        assert classify_failure_kind(result, [external_artifact], workspace) == "write_boundary"

    def test_partial_write_out_of_workspace_returns_write_boundary(self, tmp_path: Path):
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
        assert classify_failure_kind(result, [plan, handoff], workspace) == "write_boundary"

    def test_permission_denied_in_stderr(self, tmp_path: Path):
        artifact = tmp_path / "handoff.json"
        # artifact missing but path is workspace-local → not write_boundary
        result = _make_result(stderr="Error: Permission denied writing to /foo/bar")
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

        def fake_prepare(paths: list[Path]) -> list[Path]:
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

        monkeypatch.setattr(claude_runner_module, "prepare_artifact_files", fake_prepare)
        monkeypatch.setattr(claude_runner_module.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())

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
