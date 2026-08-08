"""Unit tests for Quest runtime host selection and bridge result normalization."""

from __future__ import annotations

import stat
import subprocess
import json
from argparse import Namespace
from pathlib import Path

import quest_claude_probe
import quest_claude_runner
import quest_runtime.claude_runner as claude_runner_module
from quest_runtime.claude_runner import (
    CODEX_LED_CODEX_VIOLATION_GUIDANCE,
    run_bridge_probe,
    run_claude_role,
    select_role_runtime,
)
from quest_runtime.orchestration import (
    is_antigravity_model,
    is_model_available,
    is_model_available_for_orchestrator,
    runtime_for_model,
    validate_or_remap_models_for_orchestrator,
)


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _write_planner_state(quest_dir: Path) -> None:
    (quest_dir / "state.json").write_text(
        json.dumps({"phase": "plan", "plan_iteration": 1}),
        encoding="utf-8",
    )


def test_select_role_runtime_keeps_native_claude_for_claude_led_hosts():
    selection = select_role_runtime(
        orchestrator="claude",
        target_runtime="claude",
        native_claude_available=True,
        claude_bridge_available=False,
    )

    assert selection.runtime == "claude"
    assert selection.entrypoint == "Task(...)"
    assert selection.requires_probe is False
    assert "native Claude task execution" in selection.reason


def test_select_role_runtime_uses_subagent_for_codex_led_codex_roles():
    selection = select_role_runtime(
        orchestrator="codex",
        target_runtime="codex",
        native_claude_available=False,
        claude_bridge_available=False,
    )

    assert selection.runtime == "codex"
    assert selection.entrypoint == "subagent"
    assert selection.requires_probe is False
    assert "local Codex subagents" in selection.reason
    assert "inherits the active Codex model" in selection.reason
    assert "runtime=codex entrypoint=subagent" in selection.reason
    assert "Codex MCP is only valid for Claude-led sessions" in selection.reason
    # A correct selection must not log violation language, or the log line
    # itself becomes the misdiagnosis trap this contract exists to prevent.
    assert "Orchestration violation" not in selection.reason
    assert "gpt-5" not in selection.reason


def test_codex_led_codex_violation_guidance_names_the_correction():
    assert CODEX_LED_CODEX_VIOLATION_GUIDANCE.startswith("Orchestration violation")
    assert "local Codex subagents" in CODEX_LED_CODEX_VIOLATION_GUIDANCE
    assert "inherit the active Codex model" in CODEX_LED_CODEX_VIOLATION_GUIDANCE
    assert "Claude-led sessions" in CODEX_LED_CODEX_VIOLATION_GUIDANCE


def test_select_role_runtime_uses_codex_mcp_for_claude_led_codex_roles():
    selection = select_role_runtime(
        orchestrator="claude",
        target_runtime="codex",
        native_claude_available=True,
        claude_bridge_available=False,
    )

    assert selection.runtime == "codex"
    assert selection.entrypoint == "codex_mcp"
    assert selection.requires_probe is False
    assert "Claude-led session" in selection.reason
    assert "runtime=codex entrypoint=codex_mcp" in selection.reason


def test_select_role_runtime_uses_bridge_runner_for_codex_led_claude_roles():
    selection = select_role_runtime(
        orchestrator="codex",
        target_runtime="claude",
        native_claude_available=False,
        claude_bridge_available=True,
    )

    assert selection.runtime == "claude"
    assert selection.entrypoint == "scripts/quest_claude_runner.py"
    assert selection.requires_probe is True
    assert "additive bridge-backed Quest runner" in selection.reason
    assert (
        "runtime=claude entrypoint=scripts/quest_claude_runner.py" in selection.reason
    )


def test_select_role_runtime_blocks_codex_led_claude_role_without_bridge():
    selection = select_role_runtime(
        orchestrator="codex",
        target_runtime="claude",
        native_claude_available=False,
        claude_bridge_available=False,
    )

    assert selection.runtime == "blocked"
    assert selection.entrypoint == ""
    assert selection.requires_probe is True
    assert "requires the Quest Claude bridge runner" in selection.reason
    assert "runtime=claude entrypoint=blocked" in selection.reason


def test_select_role_runtime_rejects_unknown_orchestrator():
    try:
        select_role_runtime(orchestrator="unknown", target_runtime="codex")
    except ValueError as exc:
        assert "Unsupported orchestrator" in str(exc)
    else:
        raise AssertionError("Expected unsupported orchestrator to raise ValueError")


def test_runtime_for_model_maps_model_ids_to_runtime_families():
    assert runtime_for_model("claude") == "claude"
    assert runtime_for_model("claude-opus-4-6") == "claude"
    assert runtime_for_model("Claude-Opus-4-6") == "claude"
    assert runtime_for_model("opencode/claude-opus-4-6") == "claude"
    assert runtime_for_model("opencode/claude") == "claude"
    assert runtime_for_model("codex") == "codex"
    assert runtime_for_model("gpt-5.5") == "codex"
    assert runtime_for_model("opencode/gpt-5.4") == "codex"

    for invalid in ("   ", "opencode/"):
        try:
            runtime_for_model(invalid)
        except ValueError:
            continue
        raise AssertionError(f"Expected ValueError for model ID {invalid!r}")


def test_model_availability_classifies_provider_qualified_ids_like_dispatch():
    # Codex-led session: a provider-qualified Claude ID needs the Claude bridge.
    assert (
        is_model_available_for_orchestrator(
            "opencode/claude-opus-4-6",
            orchestrator="codex",
            codex_available=True,
            claude_available=True,
        )
        is True
    )
    assert (
        is_model_available_for_orchestrator(
            "opencode/claude-opus-4-6",
            orchestrator="codex",
            codex_available=True,
            claude_available=False,
        )
        is False
    )
    # Claude-led session: provider-qualified Claude ID is native; a Codex-backed
    # ID still requires Codex availability.
    assert (
        is_model_available_for_orchestrator(
            "opencode/claude-opus-4-6",
            orchestrator="claude",
            codex_available=False,
            claude_available=True,
        )
        is True
    )
    assert (
        is_model_available_for_orchestrator(
            "opencode/gpt-5.4",
            orchestrator="claude",
            codex_available=False,
            claude_available=True,
        )
        is False
    )


def test_is_antigravity_model_accepts_sentinel_and_concrete_slugs():
    assert is_antigravity_model("gemini") is True
    assert is_antigravity_model("gemini-3.6-flash-high") is True
    # Unreleased slugs must classify without a code change (see plan D1).
    assert is_antigravity_model("gemini-3.5-pro-high") is True

    assert is_antigravity_model("claude-opus-5") is False
    assert is_antigravity_model("gpt-5.6-sol") is False
    # Substring, not prefix: must not capture an unrelated family.
    assert is_antigravity_model("not-gemini-3.6") is False


def test_runtime_for_model_maps_gemini_ids_to_antigravity():
    assert runtime_for_model("gemini") == "antigravity"
    assert runtime_for_model("gemini-3.6-flash-high") == "antigravity"
    assert runtime_for_model("Gemini-3.6-Flash-High") == "antigravity"
    assert runtime_for_model("antigravity/gemini-3.6-flash-low") == "antigravity"
    # A slug that does not exist yet still routes correctly.
    assert runtime_for_model("gemini-3.5-pro-high") == "antigravity"

    # Existing families keep their mapping.
    assert runtime_for_model("claude-opus-5") == "claude"
    assert runtime_for_model("gpt-5.6-sol") == "codex"


def test_antigravity_availability_is_gated_on_the_probe_for_both_orchestrators():
    for orchestrator in ("claude", "codex"):
        assert (
            is_model_available_for_orchestrator(
                "gemini-3.6-flash-high",
                orchestrator=orchestrator,
                codex_available=True,
                claude_available=True,
                antigravity_available=True,
            )
            is True
        )
        assert (
            is_model_available_for_orchestrator(
                "gemini-3.6-flash-high",
                orchestrator=orchestrator,
                codex_available=True,
                claude_available=True,
                antigravity_available=False,
            )
            is False
        )


def test_antigravity_defaults_to_unavailable_for_callers_predating_it():
    # Callers that never pass the new flag must reject Gemini roles at chooser
    # time rather than persisting config that can only fail at dispatch.
    assert (
        is_model_available_for_orchestrator(
            "gemini-3.6-flash-high",
            orchestrator="claude",
            codex_available=True,
            claude_available=True,
        )
        is False
    )
    assert is_model_available("gemini-3.6-flash-high", codex_available=True) is False
    # The legacy wrapper still answers unchanged for the original families.
    assert is_model_available("claude-opus-5", codex_available=False) is True
    assert is_model_available("gpt-5.6-sol", codex_available=False) is False


def test_validate_or_remap_rejects_unprobed_gemini_role():
    models = dict.fromkeys(
        (
            "planner",
            "plan-reviewer-a",
            "plan-reviewer-b",
            "arbiter",
            "builder",
            "code-reviewer-a",
            "code-reviewer-b",
            "review-arbiter",
            "fixer",
        ),
        "claude",
    )
    models["code-reviewer-b"] = "gemini-3.6-flash-high"

    try:
        validate_or_remap_models_for_orchestrator(
            models,
            orchestrator="claude",
            codex_available=False,
            claude_available=True,
            quest_mode="full",
            antigravity_available=False,
        )
    except ValueError as exc:
        assert "code-reviewer-b" in str(exc)
    else:
        raise AssertionError("Expected an unprobed Gemini role to be rejected")

    # With the probe green the same map validates untouched.
    validated, remapped = validate_or_remap_models_for_orchestrator(
        models,
        orchestrator="claude",
        codex_available=False,
        claude_available=True,
        quest_mode="full",
        antigravity_available=True,
    )
    assert validated["code-reviewer-b"] == "gemini-3.6-flash-high"
    assert remapped == []


def test_validate_or_remap_falls_back_to_native_model_for_gemini_role():
    models = dict.fromkeys(
        (
            "planner",
            "plan-reviewer-a",
            "plan-reviewer-b",
            "arbiter",
            "builder",
            "code-reviewer-a",
            "code-reviewer-b",
            "review-arbiter",
            "fixer",
        ),
        "claude",
    )
    models["code-reviewer-b"] = "gemini-3.6-flash-high"

    validated, remapped = validate_or_remap_models_for_orchestrator(
        models,
        orchestrator="claude",
        codex_available=False,
        claude_available=True,
        quest_mode="full",
        remap_unavailable=True,
        antigravity_available=False,
    )
    assert validated["code-reviewer-b"] == "claude"
    assert remapped == ["code-reviewer-b"]


def test_select_role_runtime_routes_gemini_through_the_antigravity_runner():
    for orchestrator in ("claude", "codex"):
        selection = select_role_runtime(
            orchestrator=orchestrator,
            target_runtime="gemini-3.6-flash-high",
            antigravity_available=True,
        )
        assert selection.runtime == "antigravity"
        assert selection.entrypoint == "scripts/quest_antigravity_runner.py"
        assert selection.requires_probe is True


def test_select_role_runtime_blocks_gemini_when_the_probe_is_unavailable():
    selection = select_role_runtime(
        orchestrator="claude",
        target_runtime="gemini-3.6-flash-high",
        antigravity_available=False,
    )
    assert selection.runtime == "blocked"
    assert selection.entrypoint == ""
    assert "quest_antigravity_runner.py" in selection.reason
    assert selection.requires_probe is True


def test_select_role_runtime_accepts_persisted_model_ids():
    codex_selection = select_role_runtime(
        orchestrator="codex",
        target_runtime="gpt-5.5",
        native_claude_available=False,
        claude_bridge_available=False,
    )
    assert codex_selection.runtime == "codex"
    assert codex_selection.entrypoint == "subagent"

    claude_selection = select_role_runtime(
        orchestrator="codex",
        target_runtime="claude-opus-4-6",
        native_claude_available=False,
        claude_bridge_available=True,
    )
    assert claude_selection.runtime == "claude"
    assert claude_selection.entrypoint == "scripts/quest_claude_runner.py"

    provider_qualified_selection = select_role_runtime(
        orchestrator="codex",
        target_runtime="opencode/claude-opus-4-6",
        native_claude_available=False,
        claude_bridge_available=True,
    )
    assert provider_qualified_selection.runtime == "claude"
    assert provider_qualified_selection.entrypoint == "scripts/quest_claude_runner.py"


def test_run_claude_role_reports_timeout_result_kind(tmp_path):
    bridge_script = tmp_path / "fake_bridge_timeout.py"
    _write_executable(
        bridge_script,
        """#!/usr/bin/env python3
import time
time.sleep(10.0)
""",
    )
    prompt_file = tmp_path / "prompt.txt"
    handoff_file = tmp_path / "handoff.json"
    prompt_file.write_text("timeout test\n", encoding="utf-8")

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        bridge_script=bridge_script,
        model="claude-opus-4-6",
        timeout=0.1,
        permission_mode="bypassPermissions",
        poll_interval=0.01,
        exit_grace_seconds=0.01,
    )

    assert result.exit_code != 0
    assert result.handoff_state == "missing"
    assert result.result_kind == "timeout"
    assert result.source is None


def test_run_claude_role_reports_invocation_error_result_kind(tmp_path):
    prompt_file = tmp_path / "prompt.txt"
    handoff_file = tmp_path / "handoff.json"
    prompt_file.write_text("invocation error test\n", encoding="utf-8")

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan_review",
        agent="plan-reviewer-a",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        bridge_script=tmp_path / "missing_bridge.py",
        model="claude-opus-4-6",
        timeout=0.1,
        permission_mode="bypassPermissions",
        poll_interval=0.01,
        exit_grace_seconds=0.01,
    )

    assert result.exit_code != 0
    assert result.handoff_state == "missing"
    assert result.result_kind == "invocation_error"
    assert result.source is None


def test_run_bridge_probe_treats_found_handoff_as_success_even_on_nonzero_exit(
    tmp_path, monkeypatch
):
    completed = subprocess.CompletedProcess(
        args=["bridge"],
        returncode=1,
        stdout="",
        stderr="Timed out after 30.0s",
    )

    def fake_run(*args, **kwargs):
        probe_dir = tmp_path / "logs" / "bridge_probe"
        artifact_file = probe_dir / "probe_artifact.txt"
        handoff_file = probe_dir / "probe_handoff.json"
        artifact_file.write_text("ok", encoding="utf-8")
        handoff_file.write_text(
            '{"status":"complete","artifacts":["probe_artifact.txt"],"next":null,"summary":"probe ok"}',
            encoding="utf-8",
        )
        return completed

    monkeypatch.setattr(claude_runner_module.subprocess, "run", fake_run)

    result = run_bridge_probe(
        cwd=tmp_path,
        quest_dir=tmp_path,
        bridge_script=tmp_path / "bridge.py",
        model="opus",
        timeout=30.0,
        permission_mode="bypassPermissions",
    )

    assert result.exit_code == 0
    assert result.handoff_state == "found"
    assert result.result_kind == "handoff_json"
    assert result.source == "handoff_json"
    assert result.stderr == "Timed out after 30.0s"
    assert result.status is None
    assert result.rejected_model is None


def test_run_bridge_probe_found_handoff_wins_over_exit_9(tmp_path, monkeypatch):
    completed = subprocess.CompletedProcess(
        args=["bridge"],
        returncode=9,
        stdout="",
        stderr="model rejected after artifacts were written",
    )

    def fake_run(*args, **kwargs):
        probe_dir = tmp_path / "logs" / "bridge_probe"
        artifact_file = probe_dir / "probe_artifact.txt"
        handoff_file = probe_dir / "probe_handoff.json"
        artifact_file.write_text("ok", encoding="utf-8")
        handoff_file.write_text(
            '{"status":"complete","artifacts":["probe_artifact.txt"],"next":null,"summary":"probe ok"}',
            encoding="utf-8",
        )
        return completed

    monkeypatch.setattr(claude_runner_module.subprocess, "run", fake_run)

    result = run_bridge_probe(
        cwd=tmp_path,
        quest_dir=tmp_path,
        bridge_script=tmp_path / "bridge.py",
        model="opus",
        timeout=30.0,
        permission_mode="bypassPermissions",
    )

    assert result.exit_code == 0
    assert result.handoff_state == "found"
    assert result.result_kind == "handoff_json"
    assert result.source == "handoff_json"
    assert result.stderr == "model rejected after artifacts were written"
    assert result.status is None
    assert result.rejected_model is None


def test_run_bridge_probe_requires_artifact_not_just_handoff(tmp_path, monkeypatch):
    # Same contract as the bg probe: a handoff alone must not prove the
    # transport — the declared artifact write is the point of the probe.
    completed = subprocess.CompletedProcess(
        args=["bridge"], returncode=0, stdout="", stderr=""
    )

    def fake_run(*args, **kwargs):
        probe_dir = tmp_path / "logs" / "bridge_probe"
        handoff_file = probe_dir / "probe_handoff.json"
        handoff_file.write_text(
            '{"status":"complete","artifacts":[],"next":null,"summary":"probe ok"}',
            encoding="utf-8",
        )
        # probe_artifact.txt deliberately NOT written
        return completed

    monkeypatch.setattr(claude_runner_module.subprocess, "run", fake_run)

    result = run_bridge_probe(
        cwd=tmp_path,
        quest_dir=tmp_path,
        bridge_script=tmp_path / "bridge.py",
        model="claude",
        timeout=30.0,
        permission_mode="bypassPermissions",
    )

    assert result.exit_code != 0
    assert result.result_kind == "artifact_missing"
    assert result.source is None


def test_run_bridge_probe_classifies_failure_exit_9_as_model_rejected(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(
        claude_runner_module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            9,
            "",
            "claude CLI not found-looking text must not win",
        ),
    )

    result = run_bridge_probe(
        cwd=tmp_path,
        quest_dir=tmp_path,
        bridge_script=tmp_path / "bridge.py",
        model="claude-fake-model",
        timeout=30.0,
        permission_mode="bypassPermissions",
    )

    assert result.exit_code == 9
    assert result.result_kind == "model_rejected"
    assert result.status == "model_rejected"
    assert result.rejected_model == "claude-fake-model"


def test_run_bridge_probe_model_rejected_omits_claude_sentinel(tmp_path, monkeypatch):
    monkeypatch.setattr(
        claude_runner_module.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 9, "", ""),
    )

    result = run_bridge_probe(
        cwd=tmp_path,
        quest_dir=tmp_path,
        bridge_script=tmp_path / "bridge.py",
        model="claude",
        timeout=30.0,
        permission_mode="bypassPermissions",
    )

    assert result.result_kind == "model_rejected"
    assert result.status == "model_rejected"
    assert result.rejected_model is None


def test_migration_fails_closed_on_missing_role_instead_of_writing_null(tmp_path):
    from quest_runtime.orchestration import migrate_from_snapshot

    orch = tmp_path / "orchestration.json"
    # Missing a non-legacy canonical role (builder) AND missing the transport
    # keys, so the migration has a reason to rewrite the file.
    orch.write_text(
        json.dumps(
            {
                "version": 1,
                "models": {
                    "planner": "claude",
                    "plan-reviewer-a": "claude",
                    "plan-reviewer-b": "gpt-5.5",
                    "arbiter": "claude",
                    # builder missing
                    "code-reviewer-a": "claude",
                    "code-reviewer-b": "gpt-5.5",
                    "fixer": "gpt-5.5",
                },
            }
        ),
        encoding="utf-8",
    )

    import pytest as _pytest

    with _pytest.raises(ValueError, match="builder"):
        migrate_from_snapshot(tmp_path)
    # The malformed file must not have been rewritten with null roles.
    persisted = json.loads(orch.read_text(encoding="utf-8"))
    assert "builder" not in persisted["models"]


def test_run_claude_role_treats_found_handoff_as_success_even_after_timeout(
    tmp_path, monkeypatch
):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("timeout handoff test\n", encoding="utf-8")
    handoff_file = tmp_path / "handoff.json"

    class FakeProcess:
        def __init__(self):
            self.returncode = 1

        def communicate(self, timeout: float | None = None):
            handoff_file.write_text(
                '{"status":"complete","artifacts":[],"next":null,"summary":"ok"}',
                encoding="utf-8",
            )
            return "", "Timed out after 30.0s"

        def poll(self):
            return None

        def terminate(self):
            return None

        def kill(self):
            return None

    monkeypatch.setattr(
        claude_runner_module.subprocess, "Popen", lambda *args, **kwargs: FakeProcess()
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
        timeout=0.01,
        permission_mode="bypassPermissions",
        poll_interval=0.01,
        exit_grace_seconds=0.01,
    )

    assert result.exit_code == 0
    assert result.handoff_state == "found"
    assert result.result_kind == "handoff_json"
    assert result.source == "handoff_json"


def test_run_claude_role_does_not_treat_found_handoff_as_success_when_artifact_empty(
    tmp_path, monkeypatch
):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("timeout handoff test\n", encoding="utf-8")
    _write_planner_state(tmp_path)
    handoff_file = tmp_path / "handoff.json"
    artifact = tmp_path / "plan.md"

    class FakeProcess:
        def __init__(self):
            self.returncode = 1

        def communicate(self, timeout: float | None = None):
            handoff_file.write_text(
                '{"status":"complete","artifacts":["plan.md"],"next":null,"summary":"ok"}',
                encoding="utf-8",
            )
            return "", "Timed out after 30.0s"

        def poll(self):
            return None

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
        timeout=0.01,
        permission_mode="bypassPermissions",
        artifact_paths=[artifact],
        poll_interval=0.01,
        exit_grace_seconds=0.01,
    )

    assert result.exit_code != 0
    assert result.handoff_state == "found"
    assert result.result_kind != "handoff_json"
    assert result.source is None


def test_run_claude_role_logs_context_health_for_late_handoff_success(
    tmp_path, monkeypatch
):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("timeout handoff test\n", encoding="utf-8")
    handoff_file = tmp_path / "handoff.json"

    class FakeProcess:
        def __init__(self):
            self.returncode = 1

        def communicate(self, timeout: float | None = None):
            handoff_file.write_text(
                '{"status":"complete","artifacts":[],"next":null,"summary":"ok"}',
                encoding="utf-8",
            )
            return "", "Timed out after 30.0s"

        def poll(self):
            return None

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
        timeout=0.01,
        permission_mode="bypassPermissions",
        poll_interval=0.01,
        exit_grace_seconds=0.01,
    )

    log_file = tmp_path / "logs" / "context_health.log"

    assert result.exit_code == 0
    assert log_file.exists()
    assert "source=handoff_json" in log_file.read_text(encoding="utf-8")


def test_run_claude_role_does_not_short_circuit_to_text_fallback_before_retry(
    tmp_path, monkeypatch
):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("prompt", encoding="utf-8")
    _write_planner_state(tmp_path)
    handoff_file = tmp_path / "handoff.json"
    artifact = tmp_path / "artifact.md"

    class FakeProcess:
        def __init__(self, *, stdout: str, stderr: str, on_communicate=None):
            self.returncode = 1
            self._stdout = stdout
            self._stderr = stderr
            self._on_communicate = on_communicate

        def communicate(self, timeout: float | None = None):
            if self._on_communicate is not None:
                self._on_communicate()
            return self._stdout, self._stderr

        def poll(self):
            return self.returncode

        def terminate(self):
            return None

        def kill(self):
            return None

    popen_calls = {"count": 0}

    def make_handoff():
        artifact.write_text("ok", encoding="utf-8")
        handoff_file.write_text(
            '{"status":"complete","artifacts":["artifact.md"],"next":null,"summary":"ok"}',
            encoding="utf-8",
        )

    def fake_popen(*args, **kwargs):
        popen_calls["count"] += 1
        if popen_calls["count"] == 1:
            return FakeProcess(
                stdout="---HANDOFF---\nSTATUS: complete\nARTIFACTS: artifact.md\nNEXT: null\nSUMMARY: text fallback\n",
                stderr="Error: Permission denied writing artifact",
            )
        return FakeProcess(stdout="", stderr="", on_communicate=make_handoff)

    monkeypatch.setattr(claude_runner_module.subprocess, "Popen", fake_popen)

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

    assert popen_calls["count"] == 2
    assert result.result_kind == "handoff_json"
    assert result.source == "handoff_json"
    assert "Tier B retry:" in result.stderr


def test_tier_b_retry_preserves_bg_needs_human_metadata(tmp_path, monkeypatch):
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("prompt", encoding="utf-8")
    _write_planner_state(tmp_path)
    handoff_file = tmp_path / "handoff.json"
    artifact = tmp_path / "artifact.md"

    class FakeProcess:
        def __init__(
            self, *, returncode: int, stdout: str, stderr: str, on_communicate=None
        ):
            self.returncode = returncode
            self._stdout = stdout
            self._stderr = stderr
            self._on_communicate = on_communicate

        def communicate(self, timeout: float | None = None):
            if self._on_communicate is not None:
                self._on_communicate()
            return self._stdout, self._stderr

        def poll(self):
            return self.returncode

        def terminate(self):
            return None

        def kill(self):
            return None

    popen_calls = {"count": 0}

    def write_needs_human_handoff():
        handoff_file.write_text(
            '{"status":"needs_human","questions":["which path?"]}',
            encoding="utf-8",
        )

    def fake_popen(*args, **kwargs):
        popen_calls["count"] += 1
        if popen_calls["count"] == 1:
            return FakeProcess(
                returncode=1,
                stdout='{"status":"blocked","message":"first attempt"}',
                stderr="Permission denied writing artifact",
            )
        return FakeProcess(
            returncode=10,
            stdout=json.dumps(
                {
                    "status": "needs_human",
                    "short_id": "abc12345",
                    "session_id": "11111111-1111-1111-1111-111111111111",
                    "questions": ["which path?"],
                }
            ),
            stderr="",
            on_communicate=write_needs_human_handoff,
        )

    monkeypatch.setattr(claude_runner_module.subprocess, "Popen", fake_popen)

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        bridge_script=tmp_path / "bridge.py",
        model="claude",
        timeout=1.0,
        permission_mode="bypassPermissions",
        artifact_paths=[artifact],
        poll_interval=0.01,
        exit_grace_seconds=0.01,
        transport="background-agent",
    )

    assert popen_calls["count"] == 2
    assert result.result_kind == "handoff_json"
    assert result.status == "needs_human"
    assert result.session_id == "11111111-1111-1111-1111-111111111111"
    assert result.short_id == "abc12345"
    assert result.questions == ["which path?"]
    assert "Tier B retry:" in result.stderr


def test_quest_claude_runner_enables_text_fallback(monkeypatch, tmp_path, capsys):
    args = Namespace(
        quest_dir=str(tmp_path / ".quest" / "qid"),
        phase="plan",
        agent="planner",
        iter=1,
        prompt_file=str(tmp_path / "prompt.txt"),
        handoff_file=str(tmp_path / "handoff.json"),
        model="opus",
        timeout=90.0,
        permission_mode="bypassPermissions",
        transport="bridge",
        bridge_script="scripts/quest_claude_bridge.py",
        bg_runner_script="scripts/quest_claude_bg_run.py",
        cwd=str(tmp_path),
        add_dir=[],
        artifact_subset=None,
    )
    captured: dict[str, object] = {}

    def fake_expected_artifacts_for_role(
        *, quest_dir, phase, agent, artifact_subset=None
    ):
        assert artifact_subset is None
        return [Path(quest_dir) / "phase_01_plan" / "plan.md"]

    def fake_run_claude_role(**kwargs):
        captured.update(kwargs)
        return claude_runner_module.RunResult(
            exit_code=0,
            handoff_state="missing",
            result_kind="text_fallback",
            source="text_fallback",
            stdout="ok",
            stderr="",
        )

    monkeypatch.setattr(quest_claude_runner, "parse_args", lambda: args)
    monkeypatch.setattr(
        quest_claude_runner,
        "expected_artifacts_for_role",
        fake_expected_artifacts_for_role,
    )
    monkeypatch.setattr(quest_claude_runner, "run_claude_role", fake_run_claude_role)

    exit_code = quest_claude_runner.main()
    payload = capsys.readouterr().out.strip()

    assert exit_code == 0
    assert captured["allow_text_fallback"] is True
    assert '"result_kind": "text_fallback"' in payload


def test_cli_quest_claude_probe_relative_non_dot_cwd_resolves_bridge_script(
    monkeypatch, tmp_path, capsys
):
    repo_dir = tmp_path / "repo"
    bridge_script = repo_dir / "scripts" / "quest_claude_bridge.py"
    bridge_script.parent.mkdir(parents=True)
    bridge_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    args = Namespace(
        quest_dir=str(repo_dir / ".quest" / "qid"),
        model="opus",
        timeout=60.0,
        permission_mode="bypassPermissions",
        transport="bridge",
        bridge_script="scripts/quest_claude_bridge.py",
        bg_runner_script="scripts/quest_claude_bg_run.py",
        cwd="repo",
    )
    captured: dict[str, object] = {}

    def fake_run_bridge_probe(**kwargs):
        captured.update(kwargs)
        return claude_runner_module.RunResult(
            exit_code=0,
            handoff_state="missing",
            result_kind="text_fallback",
            source="text_fallback",
            stdout="ok",
            stderr="",
        )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(quest_claude_probe, "parse_args", lambda: args)
    monkeypatch.setattr(quest_claude_probe, "run_bridge_probe", fake_run_bridge_probe)

    exit_code = quest_claude_probe.main()
    payload = capsys.readouterr().out.strip()
    expected_bridge_script = (
        tmp_path / "repo" / "scripts/quest_claude_bridge.py"
    ).resolve()

    assert exit_code == 0
    assert captured["bridge_script"] == expected_bridge_script
    assert "repo/repo" not in str(captured["bridge_script"])
    assert '"result_kind": "text_fallback"' in payload


def test_cli_quest_claude_runner_relative_non_dot_cwd_resolves_bridge_script(
    monkeypatch, tmp_path, capsys
):
    repo_dir = tmp_path / "repo"
    bridge_script = repo_dir / "scripts" / "quest_claude_bridge.py"
    bridge_script.parent.mkdir(parents=True)
    bridge_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    args = Namespace(
        quest_dir=str(repo_dir / ".quest" / "qid"),
        phase="plan",
        agent="planner",
        iter=1,
        prompt_file=str(repo_dir / "prompt.txt"),
        handoff_file=str(repo_dir / "handoff.json"),
        model="opus",
        timeout=90.0,
        permission_mode="bypassPermissions",
        transport="bridge",
        bridge_script="scripts/quest_claude_bridge.py",
        bg_runner_script="scripts/quest_claude_bg_run.py",
        cwd="repo",
        add_dir=[],
        artifact_subset=None,
    )
    captured: dict[str, object] = {}

    def fake_expected_artifacts_for_role(
        *, quest_dir, phase, agent, artifact_subset=None
    ):
        assert artifact_subset is None
        return [Path(quest_dir) / "phase_01_plan" / "plan.md"]

    def fake_run_claude_role(**kwargs):
        captured.update(kwargs)
        return claude_runner_module.RunResult(
            exit_code=0,
            handoff_state="missing",
            result_kind="text_fallback",
            source="text_fallback",
            stdout="ok",
            stderr="",
        )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(quest_claude_runner, "parse_args", lambda: args)
    monkeypatch.setattr(
        quest_claude_runner,
        "expected_artifacts_for_role",
        fake_expected_artifacts_for_role,
    )
    monkeypatch.setattr(quest_claude_runner, "run_claude_role", fake_run_claude_role)

    exit_code = quest_claude_runner.main()
    payload = capsys.readouterr().out.strip()
    expected_bridge_script = (
        tmp_path / "repo" / "scripts/quest_claude_bridge.py"
    ).resolve()

    assert exit_code == 0
    assert captured["bridge_script"] == expected_bridge_script
    assert "repo/repo" not in str(captured["bridge_script"])
    assert '"result_kind": "text_fallback"' in payload


def test_quest_claude_runner_returns_structured_invocation_error_on_bad_phase(
    monkeypatch, tmp_path, capsys
):
    args = Namespace(
        quest_dir=str(tmp_path / ".quest" / "qid"),
        phase="bad_phase",
        agent="planner",
        iter=1,
        prompt_file=str(tmp_path / "prompt.txt"),
        handoff_file=str(tmp_path / "handoff.json"),
        model="opus",
        timeout=90.0,
        permission_mode="bypassPermissions",
        transport="bridge",
        bridge_script="scripts/quest_claude_bridge.py",
        bg_runner_script="scripts/quest_claude_bg_run.py",
        cwd=str(tmp_path),
        add_dir=[],
        artifact_subset=None,
    )

    monkeypatch.setattr(quest_claude_runner, "parse_args", lambda: args)

    exit_code = quest_claude_runner.main()
    payload = capsys.readouterr().out.strip()

    assert exit_code == 1
    assert '"result_kind": "invocation_error"' in payload
    assert '"handoff_state": "missing"' in payload
    assert "not valid for phase" in payload


# ---- background-agent transport ---------------------------------------------


def test_build_bg_cmd_pins_argv_with_handoff_file_and_parks_needs_human(tmp_path):
    cmd = claude_runner_module.build_bg_cmd(
        cwd=tmp_path,
        bg_runner_script=tmp_path / "quest_claude_bg_run.py",
        prompt_file=tmp_path / "prompt.txt",
        name="quest-q1-planner-i2",
        model="claude-opus-4-6",
        timeout=900.0,
        permission_mode="bypassPermissions",
        handoff_file=tmp_path / "handoff.json",
        wait_for=[tmp_path / "handoff.json", tmp_path / "artifact.md"],
        add_dirs=[tmp_path],
    )
    joined = " ".join(cmd)
    assert "--json" in cmd
    assert "--no-protocol" in cmd
    assert cmd[cmd.index("--name") + 1] == "quest-q1-planner-i2"
    # --handoff-file makes needs_human terminal promptly. The runner now leaves
    # the bg session parked by default so Quest can resume it with the answer.
    assert cmd[cmd.index("--handoff-file") + 1] == str(tmp_path / "handoff.json")
    assert "--teardown-on-needs-human" not in cmd
    assert joined.count("--wait-for") == 2
    assert cmd[cmd.index("--wait-for") + 1] == str(tmp_path / "handoff.json")


def test_build_bg_cmd_can_opt_into_needs_human_teardown(tmp_path):
    cmd = claude_runner_module.build_bg_cmd(
        cwd=tmp_path,
        bg_runner_script=tmp_path / "quest_claude_bg_run.py",
        prompt_file=tmp_path / "prompt.txt",
        name="quest-q1-planner-i2",
        model="claude-opus-4-6",
        timeout=900.0,
        permission_mode="bypassPermissions",
        handoff_file=tmp_path / "handoff.json",
        wait_for=[tmp_path / "handoff.json"],
        teardown_on_needs_human=True,
    )
    assert "--teardown-on-needs-human" in cmd


def test_build_bg_cmd_omits_model_for_claude_sentinel(tmp_path):
    cmd = claude_runner_module.build_bg_cmd(
        cwd=tmp_path,
        bg_runner_script=tmp_path / "quest_claude_bg_run.py",
        prompt_file=tmp_path / "prompt.txt",
        name="quest-q1-planner-i2",
        model="claude",
        timeout=900.0,
        permission_mode="bypassPermissions",
        handoff_file=tmp_path / "handoff.json",
        wait_for=[tmp_path / "handoff.json"],
    )
    assert "--model" not in cmd


def test_build_bridge_cmd_omits_model_for_claude_sentinel(tmp_path):
    cmd = claude_runner_module.build_bridge_cmd(
        cwd=tmp_path,
        bridge_script=tmp_path / "quest_claude_bridge.py",
        prompt_file=tmp_path / "prompt.txt",
        model="claude",
        timeout=900.0,
        permission_mode="bypassPermissions",
    )
    assert "--model" not in cmd
    assert "--json-wrap" not in cmd


def test_concrete_claude_model_passthrough(tmp_path):
    bg_cmd = claude_runner_module.build_bg_cmd(
        cwd=tmp_path,
        bg_runner_script=tmp_path / "quest_claude_bg_run.py",
        prompt_file=tmp_path / "prompt.txt",
        name="quest-q1-planner-i2",
        model="claude-opus-4-6",
        timeout=900.0,
        permission_mode="bypassPermissions",
        handoff_file=tmp_path / "handoff.json",
        wait_for=[tmp_path / "handoff.json"],
    )
    bridge_cmd = claude_runner_module.build_bridge_cmd(
        cwd=tmp_path,
        bridge_script=tmp_path / "quest_claude_bridge.py",
        prompt_file=tmp_path / "prompt.txt",
        model="sonnet",
        timeout=900.0,
        permission_mode="bypassPermissions",
    )
    assert bg_cmd[bg_cmd.index("--model") + 1] == "claude-opus-4-6"
    assert bridge_cmd[bridge_cmd.index("--model") + 1] == "sonnet"


def test_run_bg_probe_dispatches_through_build_bg_cmd(tmp_path):
    # Regression (PR #137 review): build_bg_cmd gained a required handoff_file
    # arg; run_bg_probe must pass it, or the real bg preflight raises TypeError
    # (auto blocks for user decision, forced background-agent fails) even on a
    # correctly configured machine.
    argv_file = tmp_path / "argv.json"
    bg_runner = tmp_path / "fake_bg_runner.py"
    _write_executable(
        bg_runner,
        f"""#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
open({str(argv_file)!r}, "w").write(json.dumps(args))
handoff = args[args.index("--handoff-file") + 1]
waits = [args[i + 1] for i, a in enumerate(args) if a == "--wait-for"]
with open(handoff, "w") as fh:
    json.dump({{"status": "complete", "summary": "probe ok"}}, fh)
for w in waits:
    if w != handoff:
        with open(w, "w") as fh:
            fh.write("ok")
print(json.dumps({{"status": "ok"}}))
""",
    )

    result = claude_runner_module.run_bg_probe(
        cwd=tmp_path,
        quest_dir=tmp_path,
        bg_runner_script=bg_runner,
        model="claude-opus-4-6",
        timeout=5.0,
        permission_mode="bypassPermissions",
    )

    assert result.exit_code == 0
    assert result.result_kind == "handoff_json"
    assert result.handoff_state == "found"
    argv = json.loads(argv_file.read_text(encoding="utf-8"))
    assert "--teardown-on-needs-human" in argv


def test_run_bg_probe_requires_artifact_not_just_handoff(tmp_path):
    # Regression (PR #137 review): a handoff alone must NOT mark bg available.
    # If quest_claude_bg_run.py exits incomplete (artifact never written), the probe
    # must report failure so bg is not cached/selected on a machine that never
    # proved the artifact-write contract.
    bg_runner = tmp_path / "fake_bg_runner.py"
    _write_executable(
        bg_runner,
        """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
handoff = args[args.index("--handoff-file") + 1]
with open(handoff, "w") as fh:
    json.dump({"status": "complete", "summary": "probe ok"}, fh)
# Deliberately do NOT write the artifact, and report incomplete.
print(json.dumps({"status": "incomplete"}))
sys.exit(6)
""",
    )

    result = claude_runner_module.run_bg_probe(
        cwd=tmp_path,
        quest_dir=tmp_path,
        bg_runner_script=bg_runner,
        model="claude-opus-4-6",
        timeout=5.0,
        permission_mode="bypassPermissions",
    )

    assert result.exit_code != 0
    assert result.result_kind != "handoff_json"
    assert result.source is None


def test_run_bg_probe_preserves_rate_limited_result_kind(tmp_path):
    bg_runner = tmp_path / "fake_bg_runner.py"
    _write_executable(
        bg_runner,
        """#!/usr/bin/env python3
import json, sys
print(json.dumps({
    "status": "rate_limited",
    "message": "Claude background session hit the account session limit",
    "reset_at": "2pm (America/Chicago)"
}))
sys.exit(4)
""",
    )

    result = claude_runner_module.run_bg_probe(
        cwd=tmp_path,
        quest_dir=tmp_path,
        bg_runner_script=bg_runner,
        model="claude-opus-4-6",
        timeout=5.0,
        permission_mode="bypassPermissions",
    )

    assert result.exit_code == 4
    assert result.result_kind == "rate_limited"


def test_bg_probe_failure_classifier_distinguishes_setup_failures():
    classify = claude_runner_module.classify_bg_probe_failure

    # The transport kinds (rate_limited/startup_dialog/model_rejected) are NOT
    # classified from stderr prose — run_bg_probe reads the structured envelope
    # status for them (see test_bg_probe_reports_rate_limited_result_kind), and
    # substring-matching would misclassify agent text that merely mentions
    # limits or models.
    assert (
        classify("agent output discussed the session limit and rate limit logic")
        is None
    )
    assert classify("prose mentioning an issue with the selected model naming") is None
    assert (
        classify(
            "bypassPermissions not accepted; run claude --dangerously-skip-permissions"
        )
        == "bypass_not_accepted"
    )
    assert (
        classify(
            "bg status=blocked; bg message=background session registered but did not consume the initial prompt (Claude CLI reported: send a prompt to start)"
        )
        == "bg_initial_prompt_not_consumed"
    )
    assert (
        classify("SessionStart:startup hook error: Permission denied")
        == "hook_startup_failed"
    )


def test_bg_session_name_scheme():
    assert (
        claude_runner_module.bg_session_name("my-quest_2026", "code-reviewer-a", 3)
        == "quest-my-quest_2026-code-reviewer-a-i3"
    )


def test_resolve_claude_transport_matrix():
    resolve = claude_runner_module.resolve_claude_transport

    assert resolve("background-agent") == "background-agent"
    assert resolve("bridge") == "bridge"

    # auto never silently chooses the API-metered bridge. Startup preflight
    # should already have proved bg; if it did not, runtime still attempts bg
    # and surfaces the bg failure instead of changing billing paths.
    assert resolve("auto") == "background-agent"

    import pytest as _pytest

    with _pytest.raises(ValueError):
        resolve("warp-drive")


def test_run_claude_role_bg_transport_success_logs_transport(tmp_path):
    bg_runner = tmp_path / "fake_bg_runner.py"
    _write_executable(
        bg_runner,
        """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
handoff = args[args.index("--wait-for") + 1]
with open(handoff, "w") as fh:
    json.dump({"status": "complete", "summary": "ok"}, fh)
print(json.dumps({"status": "ok"}))
""",
    )
    prompt_file = tmp_path / "prompt.txt"
    handoff_file = tmp_path / "handoff.json"
    prompt_file.write_text("bg success test\n", encoding="utf-8")

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        bridge_script=tmp_path / "unused_bridge.py",
        model="claude-opus-4-6",
        timeout=5.0,
        permission_mode="bypassPermissions",
        poll_interval=0.01,
        exit_grace_seconds=0.2,
        transport="background-agent",
        bg_runner_script=bg_runner,
    )

    assert result.exit_code == 0
    assert result.result_kind == "handoff_json"
    log_text = (tmp_path / "logs" / "context_health.log").read_text(encoding="utf-8")
    assert "runtime=claude" in log_text
    assert "transport=background-agent" in log_text


def test_run_claude_role_bg_waits_for_slow_teardown_without_killing(tmp_path):
    # Regression (PR #137): bg mode must let quest_claude_bg_run.py finish its own
    # teardown instead of killing it after exit_grace_seconds — killing the child
    # does NOT stop the detached supervisor session, so racing it would orphan
    # the session. The fake child writes the handoff, sleeps PAST exit_grace,
    # then writes an ".exited" marker as its last act; if the outer killed it
    # early (the pre-fix behavior), that marker would be missing.
    bg_runner = tmp_path / "slow_bg_runner.py"
    _write_executable(
        bg_runner,
        """#!/usr/bin/env python3
import json, sys, time
args = sys.argv[1:]
handoff = args[args.index("--wait-for") + 1]
with open(handoff, "w") as fh:
    json.dump({"status": "complete", "summary": "ok"}, fh)
time.sleep(1.0)  # well past exit_grace_seconds; stands in for session teardown
with open(handoff + ".exited", "w") as fh:
    fh.write("done")
print(json.dumps({"status": "ok"}))
""",
    )
    prompt_file = tmp_path / "prompt.txt"
    handoff_file = tmp_path / "handoff.json"
    prompt_file.write_text("slow bg teardown\n", encoding="utf-8")

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        bridge_script=tmp_path / "unused_bridge.py",
        model="claude-opus-4-6",
        timeout=5.0,
        permission_mode="bypassPermissions",
        poll_interval=0.01,
        exit_grace_seconds=0.2,  # pre-fix: child killed 0.2s after handoff appears
        transport="background-agent",
        bg_runner_script=bg_runner,
    )

    assert result.exit_code == 0
    assert result.result_kind == "handoff_json"
    # The child ran to completion (not SIGTERM'd mid-teardown).
    assert (tmp_path / "handoff.json.exited").exists()


def test_run_claude_role_bg_exit_codes_map_to_result_kinds(tmp_path):
    cases = [
        (2, "invocation_error"),
        (3, "invocation_error"),
        (4, "invocation_error"),
        (6, "handoff_missing"),
    ]
    for exit_code, expected_kind in cases:
        bg_runner = tmp_path / f"fake_bg_runner_{exit_code}.py"
        _write_executable(
            bg_runner,
            f"""#!/usr/bin/env python3
import json
print(json.dumps({{"status": "blocked", "message": "synthetic failure {exit_code}"}}))
raise SystemExit({exit_code})
""",
        )
        prompt_file = tmp_path / "prompt.txt"
        handoff_file = tmp_path / f"handoff_{exit_code}.json"
        prompt_file.write_text("bg failure test\n", encoding="utf-8")

        result = run_claude_role(
            cwd=tmp_path,
            quest_dir=tmp_path,
            phase="plan",
            agent="planner",
            iteration=1,
            prompt_file=prompt_file,
            handoff_file=handoff_file,
            bridge_script=tmp_path / "unused_bridge.py",
            model="claude-opus-4-6",
            timeout=5.0,
            permission_mode="bypassPermissions",
            poll_interval=0.01,
            exit_grace_seconds=0.2,
            transport="background-agent",
            bg_runner_script=bg_runner,
        )

        assert result.result_kind == expected_kind, (exit_code, result)
        # Envelope diagnostics surfaced for debuggability.
        assert f"synthetic failure {exit_code}" in result.stderr


def test_text_fallback_never_overrides_structured_result(tmp_path):
    # A found needs_human handoff on the bridge is a real terminal result;
    # a ---HANDOFF--- text block in stdout must not relabel it text_fallback
    # (dropping status/questions from the structured path).
    bridge = tmp_path / "fake_bridge.py"
    _write_executable(
        bridge,
        """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
prompt_path = args[args.index("--prompt-file") + 1]
handoff = prompt_path.replace("prompt.txt", "handoff.json")
with open(handoff, "w") as fh:
    json.dump({"status": "needs_human", "questions": ["which path?"]}, fh)
print("agent chatter")
print("---HANDOFF---")
print("STATUS: needs_human")
""",
    )
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("x\n", encoding="utf-8")
    _write_planner_state(tmp_path)
    artifact = tmp_path / "plan.md"  # declared but never written

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=tmp_path / "handoff.json",
        bridge_script=bridge,
        model="claude",
        timeout=5.0,
        permission_mode="bypassPermissions",
        artifact_paths=[artifact],
        allow_text_fallback=True,
        poll_interval=0.05,
        exit_grace_seconds=0.2,
        transport="bridge",
    )

    assert result.result_kind == "handoff_json"
    assert result.source == "handoff_json"


def test_classify_failure_kind_transport_kinds_never_escalate():
    # rate_limited/startup_dialog/model_rejected must not enter the Tier B
    # write-boundary escalation retry: the run never wrote anything because it
    # never ran, and escalation just burns a retry against the same failure.
    for kind in ("rate_limited", "startup_dialog", "model_rejected"):
        result = claude_runner_module.RunResult(
            exit_code=7,
            handoff_state="missing",
            result_kind=kind,
            source=None,
            stdout="",
            stderr="",
        )
        assert (
            claude_runner_module.classify_failure_kind(
                result, [Path("/outside/ws/artifact.md")], Path("/workspace")
            )
            == "invocation"
        )


def test_run_claude_role_bridge_model_rejection_is_terminal_without_retry(tmp_path):
    attempts = tmp_path / "attempts.txt"
    bridge = tmp_path / "model_rejected_bridge.py"
    _write_executable(
        bridge,
        f"""#!/usr/bin/env python3
from pathlib import Path
attempts = Path({str(attempts)!r})
attempts.write_text(attempts.read_text() + "x" if attempts.exists() else "x")
raise SystemExit(9)
""",
    )
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("x\n", encoding="utf-8")
    _write_planner_state(tmp_path)
    artifact = tmp_path.parent / f"{tmp_path.name}-external-artifact.md"

    try:
        result = run_claude_role(
            cwd=tmp_path,
            quest_dir=tmp_path,
            phase="plan",
            agent="planner",
            iteration=1,
            prompt_file=prompt_file,
            handoff_file=tmp_path / "handoff.json",
            bridge_script=bridge,
            model="claude-fake-model",
            timeout=5.0,
            permission_mode="bypassPermissions",
            artifact_paths=[artifact],
            poll_interval=0.01,
            exit_grace_seconds=0.1,
            transport="bridge",
        )
    finally:
        artifact.unlink(missing_ok=True)

    assert result.exit_code == 9
    assert result.result_kind == "model_rejected"
    assert result.status == "model_rejected"
    assert result.rejected_model == "claude-fake-model"
    assert attempts.read_text(encoding="utf-8") == "x"


def test_run_claude_role_bridge_model_rejection_does_not_override_success(tmp_path):
    bridge = tmp_path / "successful_model_rejected_bridge.py"
    prompt_file = tmp_path / "prompt.txt"
    handoff_file = tmp_path / "handoff.json"
    artifact = tmp_path / "artifact.md"
    prompt_file.write_text("x\n", encoding="utf-8")
    _write_planner_state(tmp_path)
    _write_executable(
        bridge,
        f"""#!/usr/bin/env python3
import json
from pathlib import Path
Path({str(artifact)!r}).write_text("ok")
Path({str(handoff_file)!r}).write_text(json.dumps({{
    "status": "complete",
    "artifacts": [{str(artifact)!r}],
    "next": "code_review",
    "summary": "done",
}}))
raise SystemExit(9)
""",
    )

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        bridge_script=bridge,
        model="claude-fake-model",
        timeout=5.0,
        permission_mode="bypassPermissions",
        artifact_paths=[artifact],
        poll_interval=0.01,
        exit_grace_seconds=0.1,
        transport="bridge",
    )

    assert result.result_kind == "handoff_json"
    assert result.source == "handoff_json"
    assert result.status is None
    assert result.rejected_model is None


def test_run_claude_role_bridge_model_rejection_outranks_terminal_handoff_without_artifact(
    tmp_path,
):
    bridge = tmp_path / "rejected_with_handoff_bridge.py"
    prompt_file = tmp_path / "prompt.txt"
    handoff_file = tmp_path / "handoff.json"
    artifact = tmp_path / "artifact.md"
    prompt_file.write_text("x\n", encoding="utf-8")
    _write_planner_state(tmp_path)
    _write_executable(
        bridge,
        f"""#!/usr/bin/env python3
import json
from pathlib import Path
Path({str(handoff_file)!r}).write_text(json.dumps({{
    "status": "needs_human",
    "questions": ["stale question?"],
}}))
raise SystemExit(9)
""",
    )

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        bridge_script=bridge,
        model="claude-fake-model",
        timeout=5.0,
        permission_mode="bypassPermissions",
        artifact_paths=[artifact],
        poll_interval=0.01,
        exit_grace_seconds=0.1,
        transport="bridge",
    )

    assert result.result_kind == "model_rejected"
    assert result.source is None
    assert result.rejected_model == "claude-fake-model"


def test_run_claude_role_bridge_self_timeout_remains_retryable_timeout(tmp_path):
    bridge = tmp_path / "self_timeout_bridge.py"
    _write_executable(
        bridge,
        """#!/usr/bin/env python3
import sys
print("Timed out after 1s; there is an issue with the selected model", file=sys.stderr)
raise SystemExit(124)
""",
    )
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("x\n", encoding="utf-8")
    _write_planner_state(tmp_path)
    artifact = tmp_path / "artifact.md"

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=tmp_path / "handoff.json",
        bridge_script=bridge,
        model="claude-fake-model",
        timeout=5.0,
        permission_mode="bypassPermissions",
        artifact_paths=[artifact],
        poll_interval=0.01,
        exit_grace_seconds=0.1,
        transport="bridge",
    )

    assert result.exit_code == 124
    assert result.result_kind == "timeout"
    assert (
        claude_runner_module.classify_failure_kind(result, [artifact], tmp_path)
        == "timeout"
    )


def test_overrun_sweep_unverified_cleanup_is_reported(tmp_path, monkeypatch):
    # When the bg child overruns and is killed, the by-name sweep is the only
    # cleanup; an unverified sweep (nonzero, teardown_failed, or the exit-0
    # "sweep skipped:" path) must surface recovery guidance in stderr.
    bg_runner = tmp_path / "fake_bg_runner_overrun.py"
    _write_executable(
        bg_runner,
        """#!/usr/bin/env python3
import time
time.sleep(5)
""",
    )
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("x\n", encoding="utf-8")
    monkeypatch.setattr(claude_runner_module, "_BG_TEARDOWN_MARGIN_SECONDS", 0.1)

    real_run = claude_runner_module.subprocess.run

    def fake_sweep_run(cmd, **kwargs):
        assert "--sweep" in cmd and "--sweep-include-active" in cmd
        return claude_runner_module.subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="sweep skipped: claude CLI not found in PATH",
            stderr="",
        )

    monkeypatch.setattr(claude_runner_module.subprocess, "run", fake_sweep_run)
    try:
        result = run_claude_role(
            cwd=tmp_path,
            quest_dir=tmp_path,
            phase="plan",
            agent="planner",
            iteration=1,
            prompt_file=prompt_file,
            handoff_file=tmp_path / "handoff.json",
            bridge_script=tmp_path / "unused_bridge.py",
            model="claude",
            timeout=0.2,
            permission_mode="bypassPermissions",
            transport="background-agent",
            bg_runner_script=bg_runner,
        )
    finally:
        monkeypatch.setattr(claude_runner_module.subprocess, "run", real_run)

    assert result.result_kind == "timeout"
    assert "overrun cleanup incomplete" in result.stderr
    assert "--sweep-include-active" in result.stderr


def test_restored_stale_handoff_cannot_mask_bg_failure(tmp_path):
    # A failed resume restores the parked needs_human handoff; ANY terminal bg
    # failure (not just the three structured statuses) must outrank it —
    # otherwise the runner reports success and re-asks an answered question.
    for exit_code, status, expected_kind in (
        (3, "dispatch_failed", "invocation_error"),
        (5, "timeout", "timeout"),
        # Unmapped exits (130) must not sneak back to handoff_json through the
        # generic classifier seeing handoff_state="found".
        (130, "interrupted", "handoff_missing"),
    ):
        bg_runner = tmp_path / f"fake_bg_runner_mask_{exit_code}.py"
        _write_executable(
            bg_runner,
            f"""#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
handoff = args[args.index("--handoff-file") + 1]
with open(handoff, "w") as fh:
    json.dump({{"status": "needs_human", "questions": ["already answered?"]}}, fh)
print(json.dumps({{"status": "{status}", "message": "synthetic {status}"}}))
raise SystemExit({exit_code})
""",
        )
        prompt_file = tmp_path / f"prompt_mask_{exit_code}.txt"
        prompt_file.write_text("x\n", encoding="utf-8")

        result = run_claude_role(
            cwd=tmp_path,
            quest_dir=tmp_path,
            phase="plan",
            agent="planner",
            iteration=1,
            prompt_file=prompt_file,
            handoff_file=tmp_path / f"handoff_mask_{exit_code}.json",
            bridge_script=tmp_path / "unused_bridge.py",
            model="claude",
            timeout=5.0,
            permission_mode="bypassPermissions",
            transport="background-agent",
            bg_runner_script=bg_runner,
        )

        assert result.result_kind == expected_kind, (exit_code, status)
        assert result.exit_code != 0, (exit_code, status)


def test_run_claude_role_bg_status_takes_precedence_over_exit_code(tmp_path):
    cases = [
        (4, "rate_limited", "rate_limited", '"reset_at": "2pm (America/Chicago)"'),
        (4, "startup_dialog", "startup_dialog", ""),
        (2, "model_rejected", "model_rejected", '"rejected_model": "claude-bad-1"'),
    ]
    for exit_code, status, expected_kind, extra_json in cases:
        bg_runner = tmp_path / f"fake_bg_runner_{status}.py"
        extra = f", {extra_json}" if extra_json else ""
        _write_executable(
            bg_runner,
            f"""#!/usr/bin/env python3
import json
print(json.dumps({{"status": "{status}", "message": "synthetic {status}"{extra}}}))
raise SystemExit({exit_code})
""",
        )
        prompt_file = tmp_path / f"prompt_{status}.txt"
        handoff_file = tmp_path / f"handoff_{status}.json"
        prompt_file.write_text("bg failure test\n", encoding="utf-8")

        result = run_claude_role(
            cwd=tmp_path,
            quest_dir=tmp_path,
            phase="plan",
            agent="planner",
            iteration=1,
            prompt_file=prompt_file,
            handoff_file=handoff_file,
            bridge_script=tmp_path / "unused_bridge.py",
            model="claude-opus-4-6",
            timeout=5.0,
            permission_mode="bypassPermissions",
            poll_interval=0.01,
            exit_grace_seconds=0.2,
            transport="background-agent",
            bg_runner_script=bg_runner,
        )

        assert result.result_kind == expected_kind
        assert result.status == status
        if status == "model_rejected":
            assert result.rejected_model == "claude-bad-1"
        else:
            assert result.rejected_model is None


def test_append_context_health_log_transport_field_is_optional(tmp_path):
    claude_runner_module.append_context_health_log(
        tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        handoff_state="found",
        source="handoff_json",
    )
    claude_runner_module.append_context_health_log(
        tmp_path,
        phase="plan",
        agent="planner",
        iteration=2,
        handoff_state="found",
        source="handoff_json",
        transport="bridge",
    )
    lines = (
        (tmp_path / "logs" / "context_health.log")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert "transport=" not in lines[0]
    assert lines[1].endswith(" | transport=bridge")


def test_quest_claude_runner_cli_resolves_and_echoes_transport(
    monkeypatch, tmp_path, capsys
):
    import json as _json

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("transport echo test\n", encoding="utf-8")
    captured_kwargs = {}

    def fake_expected_artifacts_for_role(
        *, quest_dir, phase, agent, artifact_subset=None
    ):
        assert artifact_subset is None
        return []

    def fake_run_claude_role(**kwargs):
        captured_kwargs.update(kwargs)
        return claude_runner_module.RunResult(
            exit_code=0,
            handoff_state="found",
            result_kind="handoff_json",
            source="handoff_json",
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(
        quest_claude_runner,
        "expected_artifacts_for_role",
        fake_expected_artifacts_for_role,
    )
    monkeypatch.setattr(quest_claude_runner, "run_claude_role", fake_run_claude_role)

    monkeypatch.setattr(
        "sys.argv",
        [
            "quest_claude_runner.py",
            "--quest-dir",
            str(tmp_path),
            "--phase",
            "plan",
            "--agent",
            "planner",
            "--iter",
            "1",
            "--prompt-file",
            str(prompt_file),
            "--handoff-file",
            str(tmp_path / "handoff.json"),
            "--model",
            "claude",
            "--cwd",
            str(tmp_path),
            "--transport",
            "auto",
        ],
    )
    rc = quest_claude_runner.main()
    payload = _json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert rc == 0
    assert payload["transport"] == "background-agent"
    assert payload["transport_downgraded"] is False
    assert captured_kwargs["transport"] == "background-agent"


def test_quest_claude_runner_cli_auto_uses_bg_without_cache(
    monkeypatch, tmp_path, capsys
):
    import json as _json

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("auto bg test\n", encoding="utf-8")
    captured_kwargs = {}

    def fake_expected_artifacts_for_role(
        *, quest_dir, phase, agent, artifact_subset=None
    ):
        assert artifact_subset is None
        return []

    def fake_run_claude_role(**kwargs):
        captured_kwargs.update(kwargs)
        return claude_runner_module.RunResult(
            exit_code=0,
            handoff_state="found",
            result_kind="handoff_json",
            source="handoff_json",
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(
        quest_claude_runner,
        "expected_artifacts_for_role",
        fake_expected_artifacts_for_role,
    )
    monkeypatch.setattr(quest_claude_runner, "run_claude_role", fake_run_claude_role)
    monkeypatch.setattr(
        "sys.argv",
        [
            "quest_claude_runner.py",
            "--quest-dir",
            str(tmp_path),
            "--phase",
            "plan",
            "--agent",
            "planner",
            "--iter",
            "1",
            "--prompt-file",
            str(prompt_file),
            "--handoff-file",
            str(tmp_path / "handoff.json"),
            "--model",
            "claude",
            "--cwd",
            str(tmp_path),
        ],
    )
    rc = quest_claude_runner.main()
    captured = capsys.readouterr()
    payload = _json.loads(captured.out.strip().splitlines()[-1])

    assert rc == 0
    assert payload["transport"] == "background-agent"
    assert payload["transport_downgraded"] is False
    assert captured_kwargs["transport"] == "background-agent"
    assert "downgraded to bridge" not in captured.err


def test_append_context_health_log_status_field_is_optional(tmp_path):
    claude_runner_module.append_context_health_log(
        tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        handoff_state="missing",
        source="text_fallback",
    )
    claude_runner_module.append_context_health_log(
        tmp_path,
        phase="plan",
        agent="planner",
        iteration=2,
        handoff_state="found",
        source="handoff_json",
        status="needs_human",
        transport="bridge",
    )
    lines = (
        (tmp_path / "logs" / "context_health.log")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert "status=" not in lines[0]
    assert lines[1].endswith(" | status=needs_human | transport=bridge")


def test_read_handoff_status_known_values_only(tmp_path):
    handoff = tmp_path / "handoff.json"

    handoff.write_text('{"status": "needs_human"}', encoding="utf-8")
    assert claude_runner_module.read_handoff_status(handoff) == "needs_human"

    handoff.write_text('{"status": "complete"}', encoding="utf-8")
    assert claude_runner_module.read_handoff_status(handoff) == "complete"

    # Unknown value, wrong shape, unparsable, missing → None (field omitted).
    handoff.write_text('{"status": "on-fire"}', encoding="utf-8")
    assert claude_runner_module.read_handoff_status(handoff) is None
    handoff.write_text("[1, 2]", encoding="utf-8")
    assert claude_runner_module.read_handoff_status(handoff) is None
    handoff.write_text("not json", encoding="utf-8")
    assert claude_runner_module.read_handoff_status(handoff) is None
    assert claude_runner_module.read_handoff_status(tmp_path / "absent.json") is None


def test_extract_text_status_known_values_only():
    text = "---HANDOFF---\nSTATUS: needs_human\nSUMMARY: question pending"
    assert claude_runner_module.extract_text_status(text) == "needs_human"
    assert claude_runner_module.extract_text_status("STATUS: weird") is None
    assert claude_runner_module.extract_text_status("no marker at all") is None


def test_run_claude_role_bg_needs_human_logs_status(tmp_path):
    bg_runner = tmp_path / "fake_bg_runner.py"
    _write_executable(
        bg_runner,
        """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
handoff = args[args.index("--wait-for") + 1]
with open(handoff, "w") as fh:
    json.dump({"status": "needs_human", "summary": "which auth flow?"}, fh)
print(json.dumps({"status": "ok"}))
""",
    )
    prompt_file = tmp_path / "prompt.txt"
    handoff_file = tmp_path / "handoff.json"
    prompt_file.write_text("bg needs_human test\n", encoding="utf-8")

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        bridge_script=tmp_path / "unused_bridge.py",
        model="claude-opus-4-6",
        timeout=5.0,
        permission_mode="bypassPermissions",
        poll_interval=0.01,
        exit_grace_seconds=0.2,
        transport="background-agent",
        bg_runner_script=bg_runner,
    )

    assert result.exit_code == 0
    log_text = (tmp_path / "logs" / "context_health.log").read_text(encoding="utf-8")
    assert "status=needs_human" in log_text
    assert "transport=background-agent" in log_text


def test_run_claude_role_bg_needs_human_with_artifacts_is_handoff_result(tmp_path):
    # PR #137 review: a needs_human handoff written WITHOUT the primary artifacts
    # must classify as a handoff result (not a handoff_missing failure), so the
    # orchestrator enters the human path instead of retrying/falling back, and
    # the status=needs_human health-log line is still recorded. Pre-fix this was
    # handoff_missing with no status= line.
    bg_runner = tmp_path / "fake_bg_runner.py"
    _write_executable(
        bg_runner,
        """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
handoff = args[args.index("--handoff-file") + 1]
with open(handoff, "w") as fh:
    json.dump({"status": "needs_human", "questions": ["which auth flow?"]}, fh)
print(json.dumps({"status": "needs_human"}))
sys.exit(10)
""",
    )
    prompt_file = tmp_path / "prompt.txt"
    handoff_file = tmp_path / "handoff.json"
    artifact = tmp_path / "review_findings.json"  # role asks instead of writing this
    prompt_file.write_text("bg needs_human with artifacts\n", encoding="utf-8")

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="review",
        agent="code-reviewer-a",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        bridge_script=tmp_path / "unused_bridge.py",
        model="claude-opus-4-6",
        timeout=5.0,
        permission_mode="bypassPermissions",
        artifact_paths=[artifact],
        poll_interval=0.01,
        exit_grace_seconds=0.2,
        transport="background-agent",
        bg_runner_script=bg_runner,
    )

    assert result.result_kind == "handoff_json"
    assert result.source == "handoff_json"
    assert result.exit_code == 0
    # The artifact is pre-created (truncated) but left EMPTY — the role asked a
    # question instead of producing it, yet this is still a handoff result.
    assert artifact.read_text(encoding="utf-8") == ""
    log_text = (tmp_path / "logs" / "context_health.log").read_text(encoding="utf-8")
    assert "status=needs_human" in log_text


def test_bg_needs_human_result_includes_session_and_questions_without_teardown(
    tmp_path,
):
    bg_runner = tmp_path / "fake_bg_runner.py"
    _write_executable(
        bg_runner,
        """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
handoff = args[args.index("--handoff-file") + 1]
with open(handoff, "w") as fh:
    json.dump({"status": "needs_human", "questions": ["which path?"]}, fh)
print(json.dumps({
    "status": "needs_human",
    "short_id": "abc12345",
    "session_id": "11111111-1111-1111-1111-111111111111",
    "questions": ["which path?"]
}))
sys.exit(10)
""",
    )
    prompt_file = tmp_path / "prompt.txt"
    handoff_file = tmp_path / "handoff.json"
    prompt_file.write_text("bg needs human relay\n", encoding="utf-8")

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        bridge_script=tmp_path / "unused_bridge.py",
        model="claude",
        timeout=5.0,
        permission_mode="bypassPermissions",
        transport="background-agent",
        bg_runner_script=bg_runner,
    )

    assert result.result_kind == "handoff_json"
    assert result.status == "needs_human"
    assert result.session_id == "11111111-1111-1111-1111-111111111111"
    assert result.short_id == "abc12345"
    assert result.questions == ["which path?"]


def test_runner_resume_uses_same_session_answer_file_and_updates_chained_session(
    tmp_path,
):
    argv_file = tmp_path / "argv.json"
    bg_runner = tmp_path / "fake_bg_runner.py"
    _write_executable(
        bg_runner,
        f"""#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
open({str(argv_file)!r}, "w").write(json.dumps(args))
handoff = args[args.index("--handoff-file") + 1]
with open(handoff, "w") as fh:
    json.dump({{"status": "complete", "summary": "ok"}}, fh)
print(json.dumps({{
    "status": "ok",
    "session_id": "22222222-2222-2222-2222-222222222222",
    "resumed_from": "11111111-1111-1111-1111-111111111111"
}}))
""",
    )
    prompt_file = tmp_path / "prompt.txt"
    answer_file = tmp_path / "answer.txt"
    handoff_file = tmp_path / "handoff.json"
    prompt_file.write_text("fallback task\n", encoding="utf-8")
    answer_file.write_text("use path A\n", encoding="utf-8")

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        bridge_script=tmp_path / "unused_bridge.py",
        model="claude",
        timeout=5.0,
        permission_mode="bypassPermissions",
        transport="background-agent",
        bg_runner_script=bg_runner,
        resume="11111111-1111-1111-1111-111111111111",
        answer_file=answer_file,
    )

    argv = json.loads(argv_file.read_text(encoding="utf-8"))
    assert argv[argv.index("--resume") + 1] == "11111111-1111-1111-1111-111111111111"
    assert argv[argv.index("--answer-file") + 1] == str(answer_file)
    assert result.session_id == "22222222-2222-2222-2222-222222222222"
    assert result.resumed_from == "11111111-1111-1111-1111-111111111111"


def test_resume_preserves_parked_artifacts(tmp_path):
    # AC10 intent: the parked agent's completed artifacts must survive a resume.
    # quest_claude_bg_run.py resume mode deliberately keeps --wait-for files; the
    # quest layer must not truncate them first via prepare_artifact_files.
    bg_runner = tmp_path / "fake_bg_runner.py"
    _write_executable(
        bg_runner,
        """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
handoff = args[args.index("--handoff-file") + 1]
with open(handoff, "w") as fh:
    json.dump({"status": "complete", "summary": "answered"}, fh)
print(json.dumps({"status": "ok", "session_id": "22222222-2222-2222-2222-222222222222"}))
""",
    )
    prompt_file = tmp_path / "prompt.txt"
    answer_file = tmp_path / "answer.txt"
    handoff_file = tmp_path / "handoff.json"
    parked_artifact = tmp_path / "plan.md"
    prompt_file.write_text("task\n", encoding="utf-8")
    answer_file.write_text("use path A\n", encoding="utf-8")
    parked_artifact.write_text("# plan written before the question\n", encoding="utf-8")

    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        bridge_script=tmp_path / "unused_bridge.py",
        model="claude",
        timeout=5.0,
        permission_mode="bypassPermissions",
        transport="background-agent",
        bg_runner_script=bg_runner,
        artifact_paths=[parked_artifact],
        resume="11111111-1111-1111-1111-111111111111",
        answer_file=answer_file,
    )

    assert (
        parked_artifact.read_text(encoding="utf-8")
        == "# plan written before the question\n"
    )
    assert result.result_kind == "handoff_json"


def test_empty_resume_reference_is_invocation_error(tmp_path):
    # Presence means intent: `resume=""` must fail loudly, never silently
    # coerce into a fresh (artifact-truncating) dispatch.
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("x\n", encoding="utf-8")
    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=tmp_path / "handoff.json",
        bridge_script=tmp_path / "unused_bridge.py",
        model="claude",
        timeout=5.0,
        permission_mode="bypassPermissions",
        transport="background-agent",
        bg_runner_script=tmp_path / "unused_bg_runner.py",
        resume="  ",
    )
    assert result.result_kind == "invocation_error"
    assert "resume" in result.stderr


def test_bridge_never_passes_model_claude_sentinel(monkeypatch, tmp_path):
    # Defense-in-depth at the bridge entrypoint: the sentinel means
    # account-default and must never reach the CLI as --model claude.
    import quest_claude_bridge

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd

        class CP:
            returncode = 0
            stdout = ""
            stderr = ""

        return CP()

    monkeypatch.setattr(quest_claude_bridge.subprocess, "run", fake_run)
    quest_claude_bridge.run_claude(
        prompt="x",
        output_format="text",
        timeout=1.0,
        model="claude",
        system_prompt="",
        append_system_prompt="",
        permission_mode="default",
        max_budget_usd=None,
        add_dirs=[],
        allowed_tools="",
        disallowed_tools="",
    )
    assert "--model" not in captured["cmd"]


def test_validate_or_remap_treats_unset_active_model_as_unavailable():
    from quest_runtime.orchestration import validate_or_remap_models_for_orchestrator

    models = {"planner": None, "builder": "", "arbiter": "claude"}

    # Reject mode: unset/empty active-role models fail fast.
    import pytest as _pytest

    with _pytest.raises(ValueError) as exc:
        validate_or_remap_models_for_orchestrator(
            models,
            orchestrator="claude",
            quest_mode="workflow",
            codex_available=True,
            claude_available=True,
            remap_unavailable=False,
        )
    assert "planner" in str(exc.value)
    assert "builder" in str(exc.value)

    # Remap mode: unset/empty active-role models remap to the native fallback.
    remapped_models, remapped_roles = validate_or_remap_models_for_orchestrator(
        models,
        orchestrator="claude",
        quest_mode="workflow",
        codex_available=True,
        claude_available=True,
        remap_unavailable=True,
    )
    assert "planner" in remapped_roles and "builder" in remapped_roles
    assert remapped_models["planner"] == "claude"
    assert remapped_models["builder"] == "claude"


def test_default_helper_script_paths_are_absolute_and_resolve_off_package():
    # Regression: helper-script defaults must be absolute (resolved next to the
    # scripts/ package), so a Claude role dispatched from a target repo without
    # its own scripts/ dir still finds the bridge / bg-runner. See
    # ideas/2026-06-15-bug-report-... bg-transport-step2.
    import os

    from quest_runtime.claude_runner import (
        DEFAULT_BG_RUNNER_SCRIPT,
        DEFAULT_BRIDGE_SCRIPT,
    )

    for path in (DEFAULT_BRIDGE_SCRIPT, DEFAULT_BG_RUNNER_SCRIPT):
        assert os.path.isabs(path), f"{path} should be absolute"
        assert os.path.exists(path), f"{path} should exist next to the package"
    assert DEFAULT_BRIDGE_SCRIPT.endswith("scripts/quest_claude_bridge.py")
    assert DEFAULT_BG_RUNNER_SCRIPT.endswith("scripts/quest_claude_bg_run.py")


def test_cli_probe_requires_explicit_model_and_default_bridge_script_is_absolute():
    # The probe's argparse default must be the absolute sibling path, not the
    # legacy cwd-relative "scripts/quest_claude_bridge.py".
    import os

    import sys

    import quest_claude_probe

    # parse_args reads sys.argv; feed it only the required flag and inspect the
    # default it fills in for --bridge-script.
    saved = sys.argv
    try:
        sys.argv = ["quest_claude_probe.py", "--quest-dir", "/tmp/x"]
        try:
            quest_claude_probe.parse_args()
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("Expected --model to be required")
        sys.argv = [
            "quest_claude_probe.py",
            "--quest-dir",
            "/tmp/x",
            "--model",
            "claude",
        ]
        ns = quest_claude_probe.parse_args()
    finally:
        sys.argv = saved
    assert os.path.isabs(ns.bridge_script)
    assert ns.bridge_script.endswith("scripts/quest_claude_bridge.py")


def test_run_claude_role_empty_model_returns_invocation_error(tmp_path):
    # Library callers bypass the CLI argparse guards; an empty model must
    # come back as a structured invocation_error, never a ValueError traceback.
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("x\n", encoding="utf-8")
    result = run_claude_role(
        cwd=tmp_path,
        quest_dir=tmp_path,
        phase="plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=tmp_path / "handoff.json",
        bridge_script=tmp_path / "unused_bridge.py",
        model="   ",
        timeout=5.0,
        permission_mode="bypassPermissions",
        transport="background-agent",
        bg_runner_script=tmp_path / "unused_bg_runner.py",
    )
    assert result.result_kind == "invocation_error"
    assert result.exit_code == 1
    assert "model" in result.stderr.lower()


def test_cli_resume_and_answer_file_require_each_other():
    import sys

    saved = sys.argv
    base = [
        "quest_claude_runner.py",
        "--quest-dir",
        "/tmp/x",
        "--phase",
        "plan",
        "--agent",
        "planner",
        "--iter",
        "1",
        "--prompt-file",
        "/tmp/p",
        "--handoff-file",
        "/tmp/h",
        "--model",
        "claude",
        "--transport",
        "background-agent",
    ]
    try:
        for extra in (["--resume", "abc12345"], ["--answer-file", "/tmp/a"]):
            sys.argv = base + extra
            try:
                quest_claude_runner.parse_args()
            except SystemExit as exc:
                assert exc.code == 2
            else:
                raise AssertionError(
                    f"Expected {extra[0]} without its pair to be rejected"
                )
    finally:
        sys.argv = saved


def test_cli_rejects_empty_or_whitespace_model():
    # An empty models.<role> value must die at argparse with a clear message,
    # not surface later as an unhandled ValueError traceback the orchestrator
    # cannot parse.
    import sys

    import quest_claude_probe

    saved = sys.argv
    try:
        for argv in (
            ["quest_claude_probe.py", "--quest-dir", "/tmp/x", "--model", "  "],
            ["quest_claude_probe.py", "--quest-dir", "/tmp/x", "--model", ""],
        ):
            sys.argv = argv
            try:
                quest_claude_probe.parse_args()
            except SystemExit as exc:
                assert exc.code == 2
            else:
                raise AssertionError("Expected empty --model to be rejected")
        for model in ("", "  "):
            sys.argv = [
                "quest_claude_runner.py",
                "--quest-dir",
                "/tmp/x",
                "--phase",
                "plan",
                "--agent",
                "planner",
                "--iter",
                "1",
                "--prompt-file",
                "/tmp/p",
                "--handoff-file",
                "/tmp/h",
                "--model",
                model,
            ]
            try:
                quest_claude_runner.parse_args()
            except SystemExit as exc:
                assert exc.code == 2
            else:
                raise AssertionError("Expected empty --model to be rejected")
    finally:
        sys.argv = saved
