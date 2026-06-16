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
from quest_runtime.orchestration import (
    is_model_available_for_orchestrator,
    runtime_for_model,
)


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
        transport="bridge",
        bridge_script="scripts/quest_claude_bridge.py",
        bg_runner_script="scripts/claude_bg_run.py",
        bg_cache_file=".quest/cache/claude_bg_codex.json",
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
        transport="bridge",
        bridge_script="scripts/quest_claude_bridge.py",
        bg_runner_script="scripts/claude_bg_run.py",
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
        transport="bridge",
        bridge_script="scripts/quest_claude_bridge.py",
        bg_runner_script="scripts/claude_bg_run.py",
        bg_cache_file=".quest/cache/claude_bg_codex.json",
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
        transport="bridge",
        bridge_script="scripts/quest_claude_bridge.py",
        bg_runner_script="scripts/claude_bg_run.py",
        bg_cache_file=".quest/cache/claude_bg_codex.json",
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


# ---- background-agent transport ---------------------------------------------


def test_build_bg_cmd_pins_argv_with_handoff_file_and_needs_human_teardown(tmp_path):
    cmd = claude_runner_module.build_bg_cmd(
        cwd=tmp_path,
        bg_runner_script=tmp_path / "claude_bg_run.py",
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
    # --handoff-file makes needs_human terminal promptly; --teardown-on-needs-human
    # tears the session down (Quest has no resume loop yet) so it behaves like the
    # bridge instead of blocking until --timeout. The handoff also stays in
    # --wait-for for the success (status=complete) path.
    assert cmd[cmd.index("--handoff-file") + 1] == str(tmp_path / "handoff.json")
    assert "--teardown-on-needs-human" in cmd
    assert joined.count("--wait-for") == 2
    assert cmd[cmd.index("--wait-for") + 1] == str(tmp_path / "handoff.json")


def test_run_bg_probe_dispatches_through_build_bg_cmd(tmp_path):
    # Regression (PR #137 review): build_bg_cmd gained a required handoff_file
    # arg; run_bg_probe must pass it, or the real bg preflight raises TypeError
    # (auto silently downgrades, forced background-agent fails) even on a
    # correctly configured machine.
    bg_runner = tmp_path / "fake_bg_runner.py"
    _write_executable(
        bg_runner,
        """#!/usr/bin/env python3
import json, sys
args = sys.argv[1:]
handoff = args[args.index("--handoff-file") + 1]
waits = [args[i + 1] for i, a in enumerate(args) if a == "--wait-for"]
with open(handoff, "w") as fh:
    json.dump({"status": "complete", "summary": "probe ok"}, fh)
for w in waits:
    if w != handoff:
        with open(w, "w") as fh:
            fh.write("ok")
print(json.dumps({"status": "ok"}))
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


def test_bg_session_name_scheme():
    assert (
        claude_runner_module.bg_session_name("my-quest_2026", "code-reviewer-a", 3)
        == "quest-my-quest_2026-code-reviewer-a-i3"
    )


def _write_bg_cache(path: Path, *, available: bool = True, expired: bool = False) -> None:
    import json as _json
    import time as _time

    now = int(_time.time())
    cached_at = now - 7200 if expired else now
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _json.dumps(
            {
                "cached_at_epoch": cached_at,
                "ttl_seconds": 3600,
                "payload": {"available": available},
            }
        ),
        encoding="utf-8",
    )


def test_resolve_claude_transport_matrix(tmp_path):
    resolve = claude_runner_module.resolve_claude_transport
    cache = tmp_path / "bg_cache.json"

    # Forced values pass through, no downgrade flag.
    assert resolve("background-agent", bg_cache_file=cache) == ("background-agent", False)
    assert resolve("bridge", bg_cache_file=cache) == ("bridge", False)

    # auto + no cache → bridge, downgraded.
    assert resolve("auto", bg_cache_file=cache) == ("bridge", True)

    # auto + valid cache → background-agent.
    _write_bg_cache(cache, available=True)
    assert resolve("auto", bg_cache_file=cache) == ("background-agent", False)

    # auto + expired cache → bridge, downgraded.
    _write_bg_cache(cache, available=True, expired=True)
    assert resolve("auto", bg_cache_file=cache) == ("bridge", True)

    # auto + cache that proves UNavailability → bridge, downgraded.
    _write_bg_cache(cache, available=False)
    assert resolve("auto", bg_cache_file=cache) == ("bridge", True)

    import pytest as _pytest

    with _pytest.raises(ValueError):
        resolve("warp-drive", bg_cache_file=cache)


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
    # Regression (PR #137): bg mode must let claude_bg_run.py finish its own
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
    lines = (tmp_path / "logs" / "context_health.log").read_text(encoding="utf-8").splitlines()
    assert "transport=" not in lines[0]
    assert lines[1].endswith(" | transport=bridge")


def test_quest_claude_runner_cli_resolves_and_echoes_transport(
    monkeypatch, tmp_path, capsys
):
    import json as _json

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("transport echo test\n", encoding="utf-8")
    captured_kwargs = {}

    def fake_expected_artifacts_for_role(*, quest_dir, phase, agent):
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

    bg_cache = tmp_path / "bg_cache.json"
    _write_bg_cache(bg_cache, available=True)
    monkeypatch.setattr(
        "sys.argv",
        [
            "quest_claude_runner.py",
            "--quest-dir", str(tmp_path),
            "--phase", "plan",
            "--agent", "planner",
            "--iter", "1",
            "--prompt-file", str(prompt_file),
            "--handoff-file", str(tmp_path / "handoff.json"),
            "--cwd", str(tmp_path),
            "--transport", "auto",
            "--bg-cache-file", str(bg_cache),
        ],
    )
    rc = quest_claude_runner.main()
    payload = _json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert rc == 0
    assert payload["transport"] == "background-agent"
    assert payload["transport_downgraded"] is False
    assert captured_kwargs["transport"] == "background-agent"


def test_quest_claude_runner_cli_auto_downgrades_without_cache(
    monkeypatch, tmp_path, capsys
):
    import json as _json

    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("downgrade test\n", encoding="utf-8")

    def fake_expected_artifacts_for_role(*, quest_dir, phase, agent):
        return []

    def fake_run_claude_role(**kwargs):
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
            "--quest-dir", str(tmp_path),
            "--phase", "plan",
            "--agent", "planner",
            "--iter", "1",
            "--prompt-file", str(prompt_file),
            "--handoff-file", str(tmp_path / "handoff.json"),
            "--cwd", str(tmp_path),
            "--bg-cache-file", str(tmp_path / "missing_cache.json"),
        ],
    )
    rc = quest_claude_runner.main()
    captured = capsys.readouterr()
    payload = _json.loads(captured.out.strip().splitlines()[-1])

    assert rc == 0
    assert payload["transport"] == "bridge"
    assert payload["transport_downgraded"] is True
    assert "downgraded to bridge" in captured.err


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
    # its own scripts/ dir still finds the bridge / bg-runner. Project state
    # stays cwd-relative. See ideas/2026-06-15-bug-report-... bg-transport-step2.
    import os

    from quest_runtime.claude_runner import (
        DEFAULT_BG_CACHE_FILE,
        DEFAULT_BG_RUNNER_SCRIPT,
        DEFAULT_BRIDGE_SCRIPT,
    )

    for path in (DEFAULT_BRIDGE_SCRIPT, DEFAULT_BG_RUNNER_SCRIPT):
        assert os.path.isabs(path), f"{path} should be absolute"
        assert os.path.exists(path), f"{path} should exist next to the package"
    assert DEFAULT_BRIDGE_SCRIPT.endswith("scripts/quest_claude_bridge.py")
    assert DEFAULT_BG_RUNNER_SCRIPT.endswith("scripts/claude_bg_run.py")
    # Project cache path is intentionally cwd-relative.
    assert not os.path.isabs(DEFAULT_BG_CACHE_FILE)


def test_cli_probe_default_bridge_script_is_absolute():
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
        ns = quest_claude_probe.parse_args()
    finally:
        sys.argv = saved
    assert os.path.isabs(ns.bridge_script)
    assert ns.bridge_script.endswith("scripts/quest_claude_bridge.py")
