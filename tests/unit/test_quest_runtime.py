"""Unit tests for Quest runtime host selection and bridge result normalization."""

from __future__ import annotations

import stat
import subprocess
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
from quest_runtime.orchestration import runtime_for_model


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


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
    assert "runtime=claude entrypoint=scripts/quest_claude_runner.py" in selection.reason


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
        bridge_script="scripts/quest_claude_bridge.py",
        cwd=str(tmp_path),
        add_dir=[],
    )
    captured: dict[str, object] = {}

    def fake_expected_artifacts_for_role(*, quest_dir, phase, agent):
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
        bridge_script="scripts/quest_claude_bridge.py",
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
    expected_bridge_script = (tmp_path / "repo" / "scripts/quest_claude_bridge.py").resolve()

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
        bridge_script="scripts/quest_claude_bridge.py",
        cwd="repo",
        add_dir=[],
    )
    captured: dict[str, object] = {}

    def fake_expected_artifacts_for_role(*, quest_dir, phase, agent):
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
    expected_bridge_script = (tmp_path / "repo" / "scripts/quest_claude_bridge.py").resolve()

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
        bridge_script="scripts/quest_claude_bridge.py",
        cwd=str(tmp_path),
        add_dir=[],
    )

    monkeypatch.setattr(quest_claude_runner, "parse_args", lambda: args)

    exit_code = quest_claude_runner.main()
    payload = capsys.readouterr().out.strip()

    assert exit_code == 1
    assert '"result_kind": "invocation_error"' in payload
    assert '"handoff_state": "missing"' in payload
    assert "not valid for phase" in payload
