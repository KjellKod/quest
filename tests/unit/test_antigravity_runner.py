"""Unit tests for the Quest Antigravity (agy) runtime helpers."""

from __future__ import annotations

import stat
from pathlib import Path

import json

from quest_runtime.antigravity_runner import (
    AGY_MODE_READ_ONLY,
    AGY_MODE_WRITE,
    MAX_PROMPT_ARGV_BYTES,
    agy_mode_for_agent,
    build_agy_cmd,
    classify_agy_result_kind,
    normalize_agy_cli_model,
    parse_agy_envelope,
    rejected_model_for,
    run_antigravity_role,
)


def _fake_agy(path: Path, body: str) -> str:
    """Write an executable stand-in for the agy binary and return its path."""
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def _error_envelope(message: str) -> dict:
    return {"conversation_id": "", "status": "ERROR", "response": "", "error": message}


def test_agy_mode_maps_read_only_roles_to_plan_mode():
    for role in (
        "plan-reviewer-a",
        "plan-reviewer-b",
        "arbiter",
        "code-reviewer-a",
        "code-reviewer-b",
        "review-arbiter",
    ):
        assert agy_mode_for_agent(role) == AGY_MODE_READ_ONLY

    for role in ("planner", "builder", "fixer"):
        assert agy_mode_for_agent(role) == AGY_MODE_WRITE


def test_normalize_model_passes_slugs_through_and_honours_the_sentinel():
    assert normalize_agy_cli_model("gemini-3.6-flash-high") == "gemini-3.6-flash-high"
    # An unreleased slug must not be filtered by Quest (plan D1).
    assert normalize_agy_cli_model("gemini-3.5-pro-high") == "gemini-3.5-pro-high"
    assert normalize_agy_cli_model("  gemini-3.1-pro-low  ") == "gemini-3.1-pro-low"
    # The sentinel omits --model entirely.
    assert normalize_agy_cli_model("gemini") is None

    for empty in ("", "   "):
        try:
            normalize_agy_cli_model(empty)
        except ValueError:
            continue
        raise AssertionError(f"Expected ValueError for model {empty!r}")


def test_build_agy_cmd_sets_the_flags_the_role_contract_depends_on():
    cmd = build_agy_cmd(
        prompt="do the thing",
        model="gemini-3.6-flash-high",
        timeout=1800,
        mode=AGY_MODE_READ_ONLY,
        add_dirs=["/tmp", "/tmp"],
        json_schema="/schema.json",
    )

    # The prompt is an argv value, not stdin: agy ignores piped stdin.
    assert cmd[1] == "--print"
    assert cmd[2] == "do the thing"
    assert "--output-format" in cmd and cmd[cmd.index("--output-format") + 1] == "json"
    assert cmd[cmd.index("--mode") + 1] == AGY_MODE_READ_ONLY
    assert cmd[cmd.index("--model") + 1] == "gemini-3.6-flash-high"
    assert cmd[cmd.index("--print-timeout") + 1] == "1800s"
    assert cmd[cmd.index("--json-schema") + 1] == "/schema.json"
    # Prompt content must not be able to expand agy slash commands/skills.
    assert "--disable-slash-commands" in cmd
    # Duplicate directories collapse to a single --add-dir.
    assert cmd.count("--add-dir") == 1


def test_build_agy_cmd_omits_model_flag_for_the_sentinel():
    cmd = build_agy_cmd(prompt="p", model="gemini", timeout=60, mode=AGY_MODE_WRITE)
    assert "--model" not in cmd


def test_build_agy_cmd_rejects_a_prompt_too_large_for_argv():
    try:
        build_agy_cmd(
            prompt="x" * (MAX_PROMPT_ARGV_BYTES + 1),
            model="gemini-3.6-flash-low",
            timeout=60,
            mode=AGY_MODE_WRITE,
        )
    except ValueError as exc:
        assert "argv limit" in str(exc)
    else:
        raise AssertionError("Expected an oversized prompt to raise ValueError")


def test_parse_agy_envelope_tolerates_non_json_stdout():
    assert parse_agy_envelope("") is None
    assert parse_agy_envelope("not json at all") is None
    # A bare JSON array is not an envelope.
    assert parse_agy_envelope("[1, 2]") is None
    assert parse_agy_envelope('{"status":"SUCCESS"}') == {"status": "SUCCESS"}


def test_model_rejection_is_classified_from_stdout_not_stderr():
    # The key divergence from the Claude runner: agy reports a rejected model
    # in the stdout envelope and leaves stderr empty.
    envelope = _error_envelope(
        'invalid model selection (--model "gemini-nope"): model gemini-nope '
        "is not recognized as a known model or custom model in settings"
    )
    assert (
        classify_agy_result_kind(
            exit_code=1, envelope=envelope, handoff_state="missing", stderr=""
        )
        == "model_rejected"
    )


def test_a_written_handoff_outranks_a_nonzero_exit():
    envelope = _error_envelope("something went wrong late in the run")
    assert (
        classify_agy_result_kind(exit_code=1, envelope=envelope, handoff_state="found")
        == "handoff_json"
    )


def test_classify_covers_timeout_invocation_and_handoff_failures():
    assert (
        classify_agy_result_kind(exit_code=124, envelope=None, handoff_state="missing")
        == "timeout"
    )
    assert (
        classify_agy_result_kind(
            exit_code=1,
            envelope=None,
            handoff_state="missing",
            stderr="executable file not found in $PATH",
        )
        == "invocation_error"
    )
    assert (
        classify_agy_result_kind(
            exit_code=0, envelope={"status": "SUCCESS"}, handoff_state="unparsable"
        )
        == "handoff_unparsable"
    )
    assert (
        classify_agy_result_kind(
            exit_code=0, envelope={"status": "SUCCESS"}, handoff_state="missing"
        )
        == "handoff_missing"
    )


def test_rejected_model_is_omitted_for_the_sentinel():
    assert rejected_model_for("gemini-3.6-flash-high") == "gemini-3.6-flash-high"
    # The sentinel names no model, so there is nothing truthful to report.
    assert rejected_model_for("gemini") is None


def test_run_role_records_a_handoff_and_tags_the_runtime_in_context_health(tmp_path):
    quest_dir = tmp_path / ".quest" / "demo"
    quest_dir.mkdir(parents=True)
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the thing", encoding="utf-8")
    handoff_file = quest_dir / "handoff.json"

    agy = _fake_agy(
        tmp_path / "fake_agy.py",
        "#!/usr/bin/env python3\n"
        "import json, sys, pathlib\n"
        f"pathlib.Path({str(handoff_file)!r}).write_text("
        'json.dumps({"status": "complete", "summary": "done"}))\n'
        'print(json.dumps({"status": "SUCCESS", "response": "done"}))\n',
    )

    result = run_antigravity_role(
        cwd=tmp_path,
        quest_dir=quest_dir,
        phase="Plan",
        agent="code-reviewer-a",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff_file,
        model="gemini-3.6-flash-high",
        timeout=30,
        add_dirs=[quest_dir],
        agy_binary=agy,
    )

    assert result.result_kind == "handoff_json"
    assert result.handoff_state == "found"
    assert result.source == "handoff_json"
    assert result.status == "complete"

    log = (quest_dir / "logs" / "context_health.log").read_text(encoding="utf-8")
    assert "runtime=antigravity" in log
    assert "agent=code-reviewer-a" in log


def test_run_role_reports_model_rejection_with_the_slug(tmp_path):
    quest_dir = tmp_path / ".quest" / "demo"
    quest_dir.mkdir(parents=True)
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the thing", encoding="utf-8")

    agy = _fake_agy(
        tmp_path / "fake_agy.py",
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "print(json.dumps({'status': 'ERROR', 'response': '', 'error': "
        '\'invalid model selection (--model "gemini-nope"): model gemini-nope '
        "is not recognized as a known model'}))\n"
        "sys.exit(1)\n",
    )

    result = run_antigravity_role(
        cwd=tmp_path,
        quest_dir=quest_dir,
        phase="Plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=quest_dir / "handoff.json",
        model="gemini-nope",
        timeout=30,
        add_dirs=[quest_dir],
        agy_binary=agy,
    )

    assert result.result_kind == "model_rejected"
    assert result.rejected_model == "gemini-nope"
    assert result.exit_code == 1


def test_run_role_recovers_a_text_handoff_when_no_file_was_written(tmp_path):
    quest_dir = tmp_path / ".quest" / "demo"
    quest_dir.mkdir(parents=True)
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the thing", encoding="utf-8")

    response = "preamble\n---HANDOFF---\nSTATUS: complete\nSUMMARY: ok\n"
    agy = _fake_agy(
        tmp_path / "fake_agy.py",
        "#!/usr/bin/env python3\n"
        "import json\n"
        f"print(json.dumps({{'status': 'SUCCESS', 'response': {response!r}}}))\n",
    )

    result = run_antigravity_role(
        cwd=tmp_path,
        quest_dir=quest_dir,
        phase="Plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=quest_dir / "handoff.json",
        model="gemini-3.6-flash-low",
        timeout=30,
        add_dirs=[quest_dir],
        agy_binary=agy,
    )

    assert result.handoff_state == "found"
    assert result.source == "text_fallback"
    assert result.status == "complete"


def test_run_role_reports_invocation_error_when_the_binary_is_missing(tmp_path):
    quest_dir = tmp_path / ".quest" / "demo"
    quest_dir.mkdir(parents=True)
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the thing", encoding="utf-8")

    result = run_antigravity_role(
        cwd=tmp_path,
        quest_dir=quest_dir,
        phase="Plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=quest_dir / "handoff.json",
        model="gemini-3.6-flash-low",
        timeout=30,
        add_dirs=[quest_dir],
        agy_binary=str(tmp_path / "definitely-not-here"),
    )

    assert result.result_kind == "invocation_error"
    assert result.exit_code == 1


def test_run_role_refuses_to_dispatch_with_no_scoping(tmp_path):
    # agy does not refuse an out-of-scope write, it redirects it to its own
    # scratch dir and reports SUCCESS. Dispatching unscoped would surface as
    # an unexplained handoff_missing, so refuse up front instead.
    quest_dir = tmp_path / ".quest" / "demo"
    quest_dir.mkdir(parents=True)
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the thing", encoding="utf-8")

    result = run_antigravity_role(
        cwd=tmp_path,
        quest_dir=quest_dir,
        phase="Plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=quest_dir / "handoff.json",
        model="gemini-3.6-flash-low",
        timeout=30,
        add_dirs=[],
    )

    assert result.result_kind == "invocation_error"
    assert "no --add-dir" in result.stderr


def test_run_role_refuses_scoping_that_excludes_the_handoff_directory(tmp_path):
    quest_dir = tmp_path / ".quest" / "demo"
    quest_dir.mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the thing", encoding="utf-8")

    result = run_antigravity_role(
        cwd=tmp_path,
        quest_dir=quest_dir,
        phase="Plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=quest_dir / "handoff.json",
        model="gemini-3.6-flash-low",
        timeout=30,
        add_dirs=[elsewhere],
    )

    assert result.result_kind == "invocation_error"
    assert "does not cover the handoff directory" in result.stderr


def test_run_role_reports_invocation_error_for_an_unreadable_prompt(tmp_path):
    quest_dir = tmp_path / ".quest" / "demo"
    quest_dir.mkdir(parents=True)

    result = run_antigravity_role(
        cwd=tmp_path,
        quest_dir=quest_dir,
        phase="Plan",
        agent="planner",
        iteration=1,
        prompt_file=tmp_path / "no-such-prompt.txt",
        handoff_file=quest_dir / "handoff.json",
        model="gemini-3.6-flash-low",
        timeout=30,
        add_dirs=[quest_dir],
    )

    assert result.result_kind == "invocation_error"
    assert "could not read prompt file" in result.stderr


def test_prompt_guard_measures_utf8_bytes_not_characters():
    # argv limits are byte limits: a multibyte prompt that passes a character
    # count would still fail exec with an unstructured E2BIG.
    multibyte = "日" * (MAX_PROMPT_ARGV_BYTES // 2)  # 3 bytes each
    assert len(multibyte) < MAX_PROMPT_ARGV_BYTES
    try:
        build_agy_cmd(
            prompt=multibyte,
            model="gemini-3.6-flash-low",
            timeout=60,
            mode=AGY_MODE_WRITE,
        )
    except ValueError as exc:
        assert "UTF-8 bytes" in str(exc)
    else:
        raise AssertionError("Expected a multibyte prompt over the byte limit to raise")


def test_generator_add_dirs_still_reaches_the_command(tmp_path):
    # A generator would be drained by the containment check, leaving the
    # dispatch with no --add-dir despite having just validated one.
    quest_dir = tmp_path / ".quest" / "demo"
    quest_dir.mkdir(parents=True)
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the thing", encoding="utf-8")
    captured = {}

    agy = _fake_agy(
        tmp_path / "fake_agy.py",
        "#!/usr/bin/env python3\n"
        "import json, sys, pathlib\n"
        f"pathlib.Path({str(quest_dir / 'argv.json')!r}).write_text(json.dumps(sys.argv))\n"
        f"pathlib.Path({str(quest_dir / 'handoff.json')!r}).write_text("
        'json.dumps({"status": "complete"}))\n'
        'print(json.dumps({"status": "SUCCESS", "response": "done"}))\n',
    )

    result = run_antigravity_role(
        cwd=tmp_path,
        quest_dir=quest_dir,
        phase="Plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=quest_dir / "handoff.json",
        model="gemini-3.6-flash-low",
        timeout=30,
        add_dirs=(d for d in [quest_dir]),  # generator, deliberately
        agy_binary=agy,
    )

    assert result.result_kind == "handoff_json"
    captured = json.loads((quest_dir / "argv.json").read_text())
    assert "--add-dir" in captured, "generator was exhausted before dispatch"


def test_handoff_without_its_declared_artifacts_is_not_success(tmp_path):
    # A handoff alone is not completion: later stages read the declared
    # artifacts, so an empty artifact must not be reported as handoff_json.
    quest_dir = tmp_path / ".quest" / "demo"
    review_dir = quest_dir / "phase_03_review"
    review_dir.mkdir(parents=True)
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the thing", encoding="utf-8")
    handoff = review_dir / "handoff_code-reviewer-b.json"
    artifact = review_dir / "review_code-reviewer-b.md"

    agy = _fake_agy(
        tmp_path / "fake_agy.py",
        "#!/usr/bin/env python3\n"
        "import json, pathlib\n"
        f"pathlib.Path({str(handoff)!r}).write_text("
        'json.dumps({"status": "complete"}))\n'
        'print(json.dumps({"status": "SUCCESS", "response": "done"}))\n',
    )

    result = run_antigravity_role(
        cwd=tmp_path,
        quest_dir=quest_dir,
        phase="code_review",
        agent="code-reviewer-b",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=handoff,
        model="gemini-3.6-flash-low",
        timeout=30,
        artifact_paths=[artifact],
        add_dirs=[quest_dir],
        agy_binary=agy,
    )

    assert result.handoff_state == "found"
    assert result.result_kind == "artifact_missing"


def test_recovered_text_handoff_reports_a_distinct_result_kind(tmp_path):
    # Consumers routing on result_kind must be able to tell a recovered
    # ---HANDOFF--- block apart from a real handoff.json, as Claude does.
    quest_dir = tmp_path / ".quest" / "demo"
    quest_dir.mkdir(parents=True)
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the thing", encoding="utf-8")

    response = "preamble\n---HANDOFF---\nSTATUS: complete\nSUMMARY: ok\n"
    agy = _fake_agy(
        tmp_path / "fake_agy.py",
        "#!/usr/bin/env python3\n"
        "import json\n"
        f"print(json.dumps({{'status': 'SUCCESS', 'response': {response!r}}}))\n",
    )

    result = run_antigravity_role(
        cwd=tmp_path,
        quest_dir=quest_dir,
        phase="Plan",
        agent="planner",
        iteration=1,
        prompt_file=prompt_file,
        handoff_file=quest_dir / "handoff.json",
        model="gemini-3.6-flash-low",
        timeout=30,
        add_dirs=[quest_dir],
        agy_binary=agy,
    )

    assert result.source == "text_fallback"
    assert result.result_kind == "text_fallback"
