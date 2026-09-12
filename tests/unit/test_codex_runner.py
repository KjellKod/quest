"""Exercise the runner through an executable boundary, never a model call."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/quest_codex_runner.py"


@pytest.fixture
def cli(tmp_path, monkeypatch):
    executable = tmp_path / "bin" / "codex"
    executable.parent.mkdir()
    executable.write_text("#!" + sys.executable + "\n" + r"""
import hashlib, json, os, pathlib, signal, subprocess, sys, time
a = sys.argv[1:]
if a == ["exec", "--help"]:
    print("--json --cd --sandbox --model --config --add-dir --output-last-message --skip-git-repo-check")
elif a == ["login", "status"]:
    pathlib.Path(os.environ["CALLS"]).write_text("login")
    print(os.environ.get("LOGIN", "Logged in using ChatGPT"))
    sys.exit(1 if os.environ.get("LOGIN") == "none" else 0)
elif a == ["mcp", "list", "--json"]:
    print(os.environ.get("INVENTORY", "[]"))
else:
    p = sys.stdin.read()
    pathlib.Path(os.environ["CAPTURE"]).write_text(json.dumps({
        "args": a, "prompt": p, "key": os.environ.get("CODEX_API_KEY"),
        "openai_key": os.environ.get("OPENAI_API_KEY"), "pid": os.getpid()}))
    mode = os.environ.get("MODE", "ok")
    print(os.environ.get("DIAGNOSTIC", ""), file=sys.stderr)
    if mode == "orphan":
        child_code = "import os,pathlib,signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); pathlib.Path(os.environ['CHILD']).write_text(str(os.getpid())); time.sleep(60)"
        subprocess.Popen([sys.executable, "-c", child_code])
        while not pathlib.Path(os.environ["CHILD"]).exists(): time.sleep(0.01)
    if os.environ.get("REVIEW_INPUT"):
        prose = pathlib.Path(os.environ["REVIEW_INPUT"]).read_text()
        pathlib.Path(os.environ["REVIEW_CAPTURE"]).write_text(prose)
        if not prose: sys.exit(8)
    if mode in ("timeout", "silent", "ignore_term"):
        if mode == "ignore_term": signal.signal(signal.SIGTERM, signal.SIG_IGN)
        child_code = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)" if mode == "ignore_term" else "import time; time.sleep(60)"
        child = subprocess.Popen([sys.executable, "-c", child_code])
        pathlib.Path(os.environ["CHILD"]).write_text(str(child.pid))
        time.sleep(0.15 if mode == "silent" else 60)
        child.terminate(); child.wait()
    if mode in ("auth_failed", "model_rejected", "rate_limited"):
        print(json.dumps({"type":"turn.failed", "error":{"code": mode, "message": mode}}))
        sys.exit(1)
    if mode == "config_conflict":
        print(json.dumps({"type":"error", "message":"Authentication configuration conflicts with forced_login_method"}))
        sys.exit(1)
    if mode == "nonzero": sys.exit(7)
    if mode == "malformed": print("bad-json"); sys.exit(0)
    print(json.dumps({"type":"thread.started", "thread_id":"fixture-thread"}))
    print(json.dumps({"type":"turn.completed", "usage":{"input_tokens":1,"output_tokens":1}}))
    if mode != "empty_final": pathlib.Path(a[a.index("-o")+1]).write_text("done\n")
    if os.environ.get("ROLE_OUTPUTS") and mode != "missing":
        for name, text in json.loads(os.environ["ROLE_OUTPUTS"]).items():
            pathlib.Path(name).write_text(text)
""")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(executable.parent) + os.pathsep + os.environ["PATH"])
    for key in ("CAPTURE", "CALLS", "CHILD"):
        monkeypatch.setenv(key, str(tmp_path / key))
    monkeypatch.delenv("CODEX_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return tmp_path


def invoke(cli, *args, prompt="hello"):
    result = subprocess.run(
        [sys.executable, str(RUNNER), *args, "--cwd", str(cli)],
        input=prompt,
        capture_output=True,
        text=True,
    )
    assert result.stdout, result.stderr
    return json.loads(result.stdout)


def task(cli, *args, prompt="hello"):
    return invoke(
        cli,
        "task",
        "--allow-non-git",
        "--output-dir",
        str(cli / "external outputs"),
        *args,
        prompt=prompt,
    )


def test_claude_dispatch_requires_runner():
    from quest_runtime.claude_runner import select_role_runtime

    result = select_role_runtime(orchestrator="claude", target_runtime="codex")
    assert result.runtime == "blocked"


@pytest.mark.parametrize("controls,match", [(False, True), (True, False)])
def test_native_codex_cannot_fall_back_to_cli(controls, match):
    from quest_runtime.claude_runner import select_role_runtime

    result = select_role_runtime(
        orchestrator="codex",
        target_runtime="codex",
        native_codex_available=controls,
        native_codex_settings_match=match,
        codex_runner_available=True,
    )
    assert result.runtime == "blocked" and result.entrypoint == ""


def role_fixture(cli, monkeypatch, agent="builder", phase="building"):
    from quest_runtime.artifacts import expected_artifacts_for_role

    quest = cli.with_name(cli.name + " quest artifacts")
    quest.mkdir(exist_ok=True)
    (quest / "orchestration.json").write_text(
        json.dumps(
            {
                "models": {agent: "gpt-saved"},
                "codex_reasoning_effort": "high",
                "codex_auth_mode": "api-key",
            }
        )
    )
    (quest / "state.json").write_text(json.dumps({"phase": phase, "plan_iteration": 1}))
    paths = expected_artifacts_for_role(quest, phase, agent)
    next_role = {
        "builder": "code_review",
        "planner": "plan_review",
        "plan-reviewer-a": "arbiter",
        "plan-reviewer-b": "arbiter",
        "arbiter": "builder",
    }.get(agent)
    handoff = {
        "status": "complete",
        "next": next_role,
        "artifacts": [str(p) for p in paths if not p.name.startswith("handoff")],
        "summary": "Fixture result",
        "plan_iteration": 1,
        "user_replan_generation": None,
    }
    outputs = {
        str(path): (
            json.dumps(handoff)
            if path.name.startswith("handoff")
            else "[]" if "findings" in path.name else "artifact\n"
        )
        for path in paths
    }
    monkeypatch.setenv("ROLE_OUTPUTS", json.dumps(outputs))
    monkeypatch.setenv("CODEX_API_KEY", "fixture-key")
    return quest, paths, outputs


def run_role(cli, quest, agent="builder", phase="building", *extra):
    return invoke(
        cli,
        "role",
        "--allow-non-git",
        "--quest-dir",
        str(quest),
        "--phase",
        phase,
        "--agent",
        agent,
        "--iter",
        "1",
        *extra,
    )


def test_role_requires_current_valid_outputs(cli, monkeypatch):
    quest, paths, outputs = role_fixture(cli, monkeypatch)
    result = run_role(cli, quest)
    assert result["result_kind"] == "complete"
    assert result["auth_mode"] == "api-key"
    capture = json.loads((cli / "CAPTURE").read_text())
    assert capture["args"][capture["args"].index("-m") + 1] == "gpt-saved"
    assert 'model_reasoning_effort="high"' in capture["args"]
    assert str(quest) in capture["args"]
    monkeypatch.setenv("MODE", "missing")
    assert run_role(cli, quest)["result_kind"] == "artifact_missing"
    assert all(p.read_text() == "" for p in paths)
    monkeypatch.setenv("MODE", "ok")
    handoff_path = next(p for p in paths if p.name.startswith("handoff"))
    handoff = json.loads(outputs[str(handoff_path)])
    for change in ({"status": "needs_human"}, {"next": "builder"}, {"artifacts": []}):
        updated = dict(handoff, **change)
        monkeypatch.setenv(
            "ROLE_OUTPUTS",
            json.dumps(dict(outputs, **{str(handoff_path): json.dumps(updated)})),
        )
        assert run_role(cli, quest)["result_kind"] == "malformed_output"
    monkeypatch.setenv(
        "ROLE_OUTPUTS",
        json.dumps(
            dict(
                outputs,
                **{str(handoff_path): json.dumps(dict(handoff, status="blocked"))},
            )
        ),
    )
    assert run_role(cli, quest)["result_kind"] == "blocked"


def test_planner_predecessor_prevents_truncation_and_dispatch(cli, monkeypatch):
    quest, paths, outputs = role_fixture(cli, monkeypatch, "planner", "plan")
    for path in paths:
        path.parent.mkdir(exist_ok=True)
        path.write_text("preserved")
    (quest / "state.json").write_text(
        json.dumps({"phase": "plan", "plan_iteration": 2})
    )
    result = run_role(cli, quest, "planner", "plan")
    assert result["result_kind"] == "precondition_failed"
    assert all(path.read_text() == "preserved" for path in paths)
    assert not (cli / "CAPTURE").exists()


def test_plan_identity_and_findings_schema_are_validated(cli, monkeypatch):
    quest, paths, outputs = role_fixture(cli, monkeypatch, "arbiter", "plan_review")
    handoff_path = next(p for p in paths if p.name.startswith("handoff"))
    handoff = json.loads(outputs[str(handoff_path)])
    outputs[str(handoff_path)] = json.dumps(dict(handoff, plan_iteration=99))
    monkeypatch.setenv("ROLE_OUTPUTS", json.dumps(outputs))
    assert (
        run_role(cli, quest, "arbiter", "plan_review")["result_kind"]
        == "malformed_output"
    )
    outputs[str(handoff_path)] = json.dumps(handoff)
    outputs[str(next(p for p in paths if "findings" in p.name))] = (
        '[{"kind":"invented"}]'
    )
    monkeypatch.setenv("ROLE_OUTPUTS", json.dumps(outputs))
    assert (
        run_role(cli, quest, "arbiter", "plan_review")["result_kind"]
        == "malformed_output"
    )


def test_findings_retry_preserves_canonical_inputs(cli, monkeypatch):
    from quest_runtime.artifacts import expected_artifacts_for_role

    quest, ordinary, _ = role_fixture(cli, monkeypatch, "arbiter", "plan_review")
    for path in ordinary:
        path.parent.mkdir(exist_ok=True)
        path.write_text("canonical input")
    paths = expected_artifacts_for_role(
        quest, "plan_review", "arbiter", artifact_subset="findings-only"
    )
    handoff = {
        "status": "complete",
        "next": "builder",
        "artifacts": [str(paths[0])],
        "summary": "Repaired findings",
        "plan_iteration": 1,
        "user_replan_generation": None,
    }
    monkeypatch.setenv(
        "ROLE_OUTPUTS",
        json.dumps({str(paths[0]): "[]", str(paths[1]): json.dumps(handoff)}),
    )
    result = run_role(
        cli, quest, "arbiter", "plan_review", "--artifact-subset", "findings-only"
    )
    assert result["result_kind"] == "complete"
    assert all(path.read_text() == "canonical input" for path in ordinary)


def test_planner_runs_against_valid_sealed_predecessor(cli, monkeypatch):
    from quest_runtime.plan_iterations import snapshot_plan_iteration
    from test_plan_iteration_lifecycle import _write_completed_iteration

    quest, paths, outputs = role_fixture(cli, monkeypatch, "planner", "plan")
    phase = _write_completed_iteration(quest, decision="planner")
    snapshot = snapshot_plan_iteration(quest, 1)
    before = {p.name: p.read_bytes() for p in snapshot.iterdir() if p.is_file()}
    (quest / "state.json").write_text(
        json.dumps({"phase": "plan", "plan_iteration": 2, "quest_mode": "workflow"})
    )
    binding = json.loads((phase / "refinement_binding.json").read_text())
    handoff_path = next(p for p in paths if p.name.startswith("handoff"))
    handoff = json.loads(outputs[str(handoff_path)])
    handoff.update(
        plan_iteration=2,
        refinement_source_plan_iteration=1,
        refinement_verdict_sha256=binding["verdict_sha256"],
    )
    outputs[str(handoff_path)] = json.dumps(handoff)
    monkeypatch.setenv("ROLE_OUTPUTS", json.dumps(outputs))
    assert run_role(cli, quest, "planner", "plan")["result_kind"] == "complete"
    assert before == {p.name: p.read_bytes() for p in snapshot.iterdir() if p.is_file()}


def test_cancellation_reaps_descendants(cli, monkeypatch):
    monkeypatch.setenv("MODE", "timeout")
    process = subprocess.Popen(
        [
            sys.executable,
            str(RUNNER),
            "task",
            "--allow-non-git",
            "--cwd",
            str(cli),
            "--output-dir",
            str(cli / "out"),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    process.stdin.write("hello")
    process.stdin.close()
    deadline = time.monotonic() + 5
    while not (cli / "CHILD").exists() and time.monotonic() < deadline:
        time.sleep(0.03)
    assert (cli / "CHILD").exists()
    process.terminate()
    process.wait(timeout=5)
    result = json.loads(process.stdout.read())
    assert result["result_kind"] == "cancelled"
    assert result["cleanup"] == "complete"
    check = subprocess.run(
        ["ps", "-o", "stat=", "-p", (cli / "CHILD").read_text()],
        capture_output=True,
        text=True,
    )
    assert not check.stdout.strip() or check.stdout.strip().startswith("Z")


def test_parallel_review_roles_use_separate_attempts(cli, monkeypatch):
    quest, paths_a, outputs_a = role_fixture(
        cli, monkeypatch, "plan-reviewer-a", "plan_review"
    )
    _, paths_b, outputs_b = role_fixture(
        cli, monkeypatch, "plan-reviewer-b", "plan_review"
    )
    saved = json.loads((quest / "orchestration.json").read_text())
    saved["models"]["plan-reviewer-a"] = "gpt-saved"
    (quest / "orchestration.json").write_text(json.dumps(saved))
    processes = []
    for agent, outputs in (
        ("plan-reviewer-a", outputs_a),
        ("plan-reviewer-b", outputs_b),
    ):
        env = dict(os.environ, ROLE_OUTPUTS=json.dumps(outputs))
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    str(RUNNER),
                    "role",
                    "--cwd",
                    str(cli),
                    "--quest-dir",
                    str(quest),
                    "--agent",
                    agent,
                    "--phase",
                    "plan_review",
                    "--iter",
                    "1",
                    "--allow-non-git",
                ],
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )
    results = [json.loads(p.communicate("review", timeout=5)[0]) for p in processes]
    assert all(r["result_kind"] == "complete" for r in results)
    assert results[0]["attempt_dir"] != results[1]["attempt_dir"]
    assert all(
        p.read_text() == (outputs_a | outputs_b)[str(p)] for p in paths_a + paths_b
    )


def test_api_only_preflight_selection_is_persisted_and_dispatched(cli, monkeypatch):
    from quest_runtime.orchestration import (
        DEFAULT_MODELS,
        write_default_from_allowlist,
        migrate_from_snapshot,
    )

    quest, _, _ = role_fixture(cli, monkeypatch)
    monkeypatch.setenv("LOGIN", "none")
    monkeypatch.setenv("CODEX_API_KEY", "fixture-key")
    (cli / ".ai").mkdir()
    (cli / ".ai/allowlist.json").write_text(json.dumps({"codex_auth_mode": "api-key"}))
    cp = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/quest_preflight.sh"),
            "--orchestrator",
            "claude",
        ],
        cwd=cli,
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0, cp.stderr
    probe = json.loads(cp.stdout)
    assert probe["available"] is True
    selected = probe["checks"]["codex_auth_mode"]
    write_default_from_allowlist(
        quest / "orchestration.json",
        DEFAULT_MODELS,
        orchestrator="claude",
        codex_available=probe["available"],
        codex_auth_mode=selected,
    )
    assert migrate_from_snapshot(quest) is False
    result = run_role(cli, quest)
    assert result["result_kind"] == "complete"
    assert result["auth_mode"] == selected == "api-key"
    assert not (cli / "CALLS").exists()
    saved = json.loads((quest / "orchestration.json").read_text())
    saved["codex_auth_mode"] = "accidental-billing"
    (quest / "orchestration.json").write_text(json.dumps(saved))
    with pytest.raises(ValueError, match="codex_auth_mode"):
        migrate_from_snapshot(quest)


def test_missing_credentials_and_cli_are_distinct(cli, monkeypatch):
    assert task(cli, "--auth", "api-key")["result_kind"] == "auth_failed"
    monkeypatch.setenv("LOGIN", "none")
    monkeypatch.setenv("OPENAI_API_KEY", "ambient-key")
    assert task(cli)["result_kind"] == "auth_failed"
    monkeypatch.setenv("PATH", str(cli / "empty-bin"))
    assert task(cli)["result_kind"] == "missing_cli"


def test_conflicting_auth_configuration_blocks_without_mutation_or_fallback(
    cli, monkeypatch
):
    config = cli / "config.toml"
    config.write_text('model_provider="custom-provider"\n')
    before = config.read_bytes()
    monkeypatch.setenv("MODE", "config_conflict")
    result = task(cli)
    assert result["result_kind"] == "auth_failed"
    assert result["auth_mode"] == "cached" and result["auth_kind"] == "chatgpt"
    assert result["retry_eligible"] is False
    assert config.read_bytes() == before
    assert len(list((cli / "external outputs/task/iter-1").iterdir())) == 1
    args = json.loads((cli / "CAPTURE").read_text())["args"]
    assert not any("model_provider=" in arg for arg in args)
    assert 'forced_login_method="chatgpt"' in args


def test_saved_api_identity_and_openai_key_mapping_are_explicit(cli, monkeypatch):
    monkeypatch.setenv("LOGIN", "Logged in using an API key")
    result = task(cli)
    assert result["result_kind"] == "complete"
    assert result["auth_mode"] == "cached" and result["auth_kind"] == "api-key"
    assert (
        'forced_login_method="api"' in json.loads((cli / "CAPTURE").read_text())["args"]
    )
    monkeypatch.setenv("OPENAI_API_KEY", "openai-boundary-key")
    assert task(cli, "--auth", "api-key")["result_kind"] == "complete"
    capture = json.loads((cli / "CAPTURE").read_text())
    assert capture["key"] == "openai-boundary-key" and capture["openai_key"] is None


def test_term_resistant_parent_and_child_are_killed_and_reaped(cli, monkeypatch):
    monkeypatch.setenv("MODE", "ignore_term")
    result = task(cli, "--timeout", "0.3")
    assert result["result_kind"] == "timeout" and result["cleanup"] == "complete"
    parent = json.loads((cli / "CAPTURE").read_text())["pid"]
    child = int((cli / "CHILD").read_text())
    for pid in (parent, child):
        check = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True
        )
        assert not check.stdout.strip() or check.stdout.strip().startswith("Z")
    assert result["retry_eligible"] is False


def test_unverifiable_cleanup_blocks_retry(cli, monkeypatch):
    # Simulate an unavailable OS process-inventory boundary, after still doing
    # real TERM/KILL and reaping. Unknown survivors must never permit retry.
    ps = cli / "bin/ps"
    ps.write_text("#!" + sys.executable + "\nimport sys; sys.exit(1)\n")
    ps.chmod(0o755)
    monkeypatch.setenv("MODE", "ignore_term")
    result = task(cli, "--timeout", "0.3")
    assert result["result_kind"] == "teardown_failed"
    assert result["cleanup"] == "failed" and result["retry_eligible"] is False
    parent = json.loads((cli / "CAPTURE").read_text())["pid"]
    child = int((cli / "CHILD").read_text())
    for pid in (parent, child):
        check = subprocess.run(
            ["/bin/ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True
        )
        assert not check.stdout.strip() or check.stdout.strip().startswith("Z")


def test_auth_mode_selects_only_requested_credentials(cli, monkeypatch):
    monkeypatch.setenv("CODEX_API_KEY", "boundary-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "other-secret")
    result = task(cli)
    assert result["result_kind"] == "complete"
    capture = json.loads((cli / "CAPTURE").read_text())
    assert capture["key"] is None and capture["openai_key"] is None
    assert 'forced_login_method="chatgpt"' in capture["args"]
    (cli / "CALLS").unlink()
    monkeypatch.setenv("LOGIN", "none")
    result = task(cli, "--auth", "api-key")
    assert result["result_kind"] == "complete"
    assert not (cli / "CALLS").exists()
    capture = json.loads((cli / "CAPTURE").read_text())
    assert capture["key"] == "boundary-secret"
    assert "boundary-secret" not in json.dumps(result)
    assert "boundary-secret" not in json.dumps(capture["args"])


def test_exec_propagates_settings_and_stdin(cli):
    prompt = "long unicode λ\n" * 20000
    result = task(
        cli,
        "--model",
        "gpt-fixture",
        "--effort",
        "high",
        "--sandbox",
        "workspace-write",
        prompt=prompt,
    )
    assert result["result_kind"] == "complete"
    capture = json.loads((cli / "CAPTURE").read_text())
    assert capture["prompt"] == prompt
    args = capture["args"]
    for flag, expected in [
        ("--cd", str(cli)),
        ("-m", "gpt-fixture"),
        ("--sandbox", "workspace-write"),
    ]:
        assert args[args.index(flag) + 1] == expected
    assert 'model_reasoning_effort="high"' in args
    assert args[-1] == "-" and prompt not in args
    assert "--ignore-user-config" not in args
    assert result["effective_model"] is None
    result = invoke(cli, "task", "--output-dir", str(cli / "out"))
    assert result["result_kind"] == "precondition_failed"


@pytest.mark.parametrize(
    "mode,kind",
    [
        ("nonzero", "invocation_error"),
        ("auth_failed", "auth_failed"),
        ("model_rejected", "model_rejected"),
        ("rate_limited", "rate_limited"),
        ("malformed", "malformed_output"),
        ("empty_final", "malformed_output"),
    ],
)
def test_failure_kinds_are_classified_distinctly(cli, monkeypatch, mode, kind):
    monkeypatch.setenv("MODE", mode)
    result = task(cli)
    assert result["result_kind"] == kind
    assert result["retry_eligible"] == (kind == "malformed_output")


def test_known_self_servers_are_disabled_without_changing_other_tools(cli, monkeypatch):
    monkeypatch.setenv(
        "INVENTORY",
        json.dumps(
            [
                {
                    "name": "odd.name",
                    "transport": {
                        "type": "stdio",
                        "command": "npx",
                        "args": ["-y", "codex-mcp-server"],
                    },
                },
                {
                    "name": "codex-cli",
                    "transport": {
                        "type": "stdio",
                        "command": "other",
                        "args": [],
                        "env": {"TOKEN": "secret"},
                    },
                },
            ]
        ),
    )
    result = task(cli)
    assert result["result_kind"] == "complete"
    assert result["disabled_self_servers"] == ["odd.name"]
    args = json.loads((cli / "CAPTURE").read_text())["args"]
    assert 'mcp_servers={"odd.name"={enabled=false}}' in args
    assert not any('"codex-cli"' in arg for arg in args)
    assert "secret" not in " ".join(args)
    monkeypatch.setenv("INVENTORY", "invalid")
    assert task(cli)["result_kind"] == "precondition_failed"


def test_timeout_and_silence_reap_descendants(cli, monkeypatch):
    monkeypatch.setenv("MODE", "timeout")
    result = task(cli, "--timeout", "0.2")
    assert result["result_kind"] == "timeout"
    assert result["cleanup"] == "complete"
    child = int((cli / "CHILD").read_text())
    check = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(child)], capture_output=True, text=True
    )
    assert not check.stdout.strip() or check.stdout.strip().startswith("Z")
    monkeypatch.setenv("MODE", "silent")
    assert task(cli, "--timeout", "2")["result_kind"] == "complete"


def test_recovered_stderr_does_not_reject_valid_role(cli, monkeypatch):
    quest, _, _ = role_fixture(cli, monkeypatch)
    monkeypatch.setenv(
        "DIAGNOSTIC", "WARN stream error: rate limit reached; retrying after 2s"
    )
    result = run_role(cli, quest)
    assert result["result_kind"] == "complete"
    assert result["exit_code"] == 0


@pytest.mark.parametrize(
    "diagnostic,expected",
    [
        ("request id 401429 could not connect", "invocation_error"),
        ("HTTP 401 Unauthorized", "auth_failed"),
        ("unexpected status 429", "rate_limited"),
    ],
)
def test_failed_attempt_classifies_http_status_in_context(
    cli, monkeypatch, diagnostic, expected
):
    monkeypatch.setenv("MODE", "nonzero")
    monkeypatch.setenv("DIAGNOSTIC", diagnostic)
    assert task(cli)["result_kind"] == expected


@pytest.mark.parametrize("inventory", ["missing", "timeout"])
def test_inventory_exception_blocks_success_and_kills_resistant_child(
    cli, monkeypatch, inventory
):
    quest, _, _ = role_fixture(cli, monkeypatch)
    monkeypatch.setenv("MODE", "orphan")
    if inventory == "timeout":
        ps = cli / "bin/ps"
        ps.write_text("#!" + sys.executable + "\nimport time; time.sleep(60)\n")
        ps.chmod(0o755)
    monkeypatch.setenv("PATH", str(cli / "bin"))
    try:
        result = run_role(cli, quest)
        child = int((cli / "CHILD").read_text())
        check = subprocess.run(
            ["/bin/ps", "-o", "stat=", "-p", str(child)],
            capture_output=True,
            text=True,
        )
        assert result["result_kind"] == "teardown_failed"
        assert result["cleanup"] == "failed"
        assert result["exit_code"] != 0
        assert result["retry_eligible"] is False
        assert not check.stdout.strip() or check.stdout.strip().startswith("Z")
    finally:
        # A failing regression must not leak the real resistant subprocess.
        if (cli / "CHILD").exists():
            try:
                os.kill(int((cli / "CHILD").read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_external_quest_accepts_quest_relative_artifact_declarations(cli, monkeypatch):
    quest, paths, outputs = role_fixture(cli, monkeypatch)
    handoff_path = next(p for p in paths if p.name.startswith("handoff"))
    handoff = json.loads(outputs[str(handoff_path)])
    handoff["artifacts"] = [
        str(p.relative_to(quest)) for p in paths if p != handoff_path
    ]
    outputs[str(handoff_path)] = json.dumps(handoff)
    monkeypatch.setenv("ROLE_OUTPUTS", json.dumps(outputs))
    result = run_role(cli, quest)
    assert result["result_kind"] == "complete"
    assert result["exit_code"] == 0


@pytest.mark.parametrize("agent", ["code-reviewer-a", "code-reviewer-b"])
@pytest.mark.parametrize("prior_findings", [None, "{broken"])
def test_reviewer_findings_repair_preserves_prose_and_requires_new_outputs(
    cli, monkeypatch, agent, prior_findings
):
    quest, paths, outputs = role_fixture(cli, monkeypatch, agent, "code_review")
    prose = next(p for p in paths if p.suffix == ".md")
    findings = next(p for p in paths if "findings" in p.name)
    prose.parent.mkdir(parents=True)
    original = b"Review complete: no correctness findings.\n"
    prose.write_bytes(original)
    if prior_findings is not None:
        findings.write_text(prior_findings)
    outputs.pop(str(prose))
    monkeypatch.setenv("ROLE_OUTPUTS", json.dumps(outputs))
    monkeypatch.setenv("REVIEW_INPUT", str(prose))
    monkeypatch.setenv("REVIEW_CAPTURE", str(cli / "read-prose"))
    result = run_role(
        cli, quest, agent, "code_review", "--artifact-subset", "findings-only"
    )
    assert result["result_kind"] == "complete"
    assert prose.read_bytes() == original
    assert (cli / "read-prose").read_bytes() == original
    assert findings.read_text() == "[]"
    monkeypatch.setenv("MODE", "missing")
    result = run_role(
        cli, quest, agent, "code_review", "--artifact-subset", "findings-only"
    )
    assert result["result_kind"] == "artifact_missing"
    assert prose.read_bytes() == original
