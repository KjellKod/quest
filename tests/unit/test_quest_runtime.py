"""Unit tests for Quest runtime host selection and bridge result normalization."""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

import quest_runtime.claude_runner as claude_runner_module
from quest_runtime.claude_runner import run_bridge_probe, run_claude_role, select_role_runtime


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
