from __future__ import annotations

import io
import subprocess

import pytest

import quest_claude_bg_run as bg
import quest_claude_bridge as bridge

EXACT_PROMPT = "  indented\nline\n\n"


def _argv_for_source(source: str, tmp_path, monkeypatch, text: str) -> list[str]:
    if source == "direct":
        return ["--prompt", text]
    if source == "file":
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text(text, encoding="utf-8")
        return ["--prompt-file", str(prompt_file)]

    monkeypatch.setattr(bridge.sys, "stdin", io.StringIO(text))
    if source == "stdin_file":
        return ["--prompt-file", "-"]
    return []


@pytest.mark.parametrize("source", ["direct", "file", "stdin_file", "stdin"])
def test_read_prompt_preserves_nonempty_source_exactly(
    source, tmp_path, monkeypatch
) -> None:
    args = bridge.parse_args(
        _argv_for_source(source, tmp_path, monkeypatch, EXACT_PROMPT)
    )

    assert bridge.read_prompt(args) == EXACT_PROMPT


@pytest.mark.parametrize("source", ["direct", "file", "stdin_file", "stdin"])
def test_whitespace_only_source_is_rejected_before_dispatch(
    source, tmp_path, monkeypatch, capsys
) -> None:
    argv = _argv_for_source(source, tmp_path, monkeypatch, " \t\n")
    dispatched = False

    def fake_run_claude(*_args, **_kwargs):
        nonlocal dispatched
        dispatched = True
        raise AssertionError("Claude must not be called for an empty prompt")

    monkeypatch.setattr(bridge, "run_claude", fake_run_claude)

    assert bridge.main(argv) == 2
    assert dispatched is False
    assert "Prompt is empty" in capsys.readouterr().err


def test_run_claude_places_prompt_unchanged_in_argv(monkeypatch) -> None:
    captured: list[str] = []

    def fake_run(cmd, **_kwargs):
        captured.extend(cmd)
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)

    result = bridge.run_claude(
        prompt=EXACT_PROMPT,
        output_format="json",
        timeout=10.0,
        model="",
        system_prompt="",
        append_system_prompt="",
        permission_mode="default",
        max_budget_usd=None,
        add_dirs=[],
        allowed_tools="",
        disallowed_tools="",
    )

    assert result["status"] == "ok"
    assert captured[2] == EXACT_PROMPT


@pytest.mark.parametrize(
    ("text", "expected_rejection"),
    [
        ("There's an issue with the selected model (claude-fake-model).", True),
        ("There is a problem with the selected model: claude-fake-model", True),
        ("There is a problem with the selected model: claude-fake-model.", True),
        ("Unsupported selected model (claude-fake-model)", True),
        ("There is an issue with the data model: claude-fake-model", False),
        ("The selected model documentation explains an issue.", False),
        ("Model claude-fake-model was selected for this data migration.", False),
    ],
)
def test_bridge_model_rejection_phrases_match_background_classifier(
    text, expected_rejection
) -> None:
    bridge_rejection = bridge._classify_model_rejection("", text)
    background_rejection = bg._classify_limit_or_model(text)

    assert (bridge_rejection is not None) is expected_rejection
    assert (
        background_rejection is not None and background_rejection[0] == "model_rejected"
    ) is expected_rejection
    if expected_rejection:
        assert background_rejection is not None
        assert bridge_rejection == background_rejection[3]


def test_run_claude_classifies_completed_model_rejection(monkeypatch) -> None:
    original_stdout = "agent output"
    original_stderr = "There's an issue with the selected model (claude-fake-model)."

    monkeypatch.setattr(
        bridge.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 1, original_stdout, original_stderr
        ),
    )

    result = bridge.run_claude(
        prompt="test",
        output_format="text",
        timeout=10.0,
        model="claude-fake-model",
        system_prompt="",
        append_system_prompt="",
        permission_mode="default",
        max_budget_usd=None,
        add_dirs=[],
        allowed_tools="",
        disallowed_tools="",
    )

    assert result["status"] == "model_rejected"
    assert result["rejected_model"] == "claude-fake-model"
    assert result["stdout"] == original_stdout
    assert result["stderr"] == original_stderr


def test_run_claude_omits_sentinel_from_model_rejection(monkeypatch) -> None:
    monkeypatch.setattr(
        bridge.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 1, "", "Invalid selected model"
        ),
    )

    result = bridge.run_claude(
        prompt="test",
        output_format="text",
        timeout=10.0,
        model="claude",
        system_prompt="",
        append_system_prompt="",
        permission_mode="default",
        max_budget_usd=None,
        add_dirs=[],
        allowed_tools="",
        disallowed_tools="",
    )

    assert result["status"] == "model_rejected"
    assert result["rejected_model"] is None


def test_model_rejection_in_early_long_stdout_is_ignored(monkeypatch) -> None:
    stdout = "There's an issue with the selected model (claude-fake-model).\n" + (
        "ordinary agent response\n" * 500
    )
    monkeypatch.setattr(
        bridge.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, stdout, ""),
    )

    result = bridge.run_claude(
        prompt="test",
        output_format="text",
        timeout=10.0,
        model="claude-fake-model",
        system_prompt="",
        append_system_prompt="",
        permission_mode="default",
        max_budget_usd=None,
        add_dirs=[],
        allowed_tools="",
        disallowed_tools="",
    )

    assert result["status"] == "error"


def test_model_rejection_in_stdout_tail_is_classified(monkeypatch) -> None:
    stdout = ("ordinary agent response\n" * 500) + (
        "There is a problem with the selected model: claude-fake-model."
    )
    monkeypatch.setattr(
        bridge.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, stdout, ""),
    )

    result = bridge.run_claude(
        prompt="test",
        output_format="text",
        timeout=10.0,
        model="",
        system_prompt="",
        append_system_prompt="",
        permission_mode="default",
        max_budget_usd=None,
        add_dirs=[],
        allowed_tools="",
        disallowed_tools="",
    )

    assert result["status"] == "model_rejected"
    assert result["rejected_model"] == "claude-fake-model"


@pytest.mark.parametrize(
    ("failure", "expected_status", "expected_exit"),
    [
        (
            FileNotFoundError("missing"),
            "error",
            127,
        ),
        (
            subprocess.TimeoutExpired(
                ["claude"],
                10,
                output="There's an issue with the selected model.",
            ),
            "timeout",
            124,
        ),
    ],
)
def test_non_completed_failures_preserve_status_despite_rejection_text(
    monkeypatch, failure, expected_status, expected_exit
) -> None:
    def raise_failure(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(bridge.subprocess, "run", raise_failure)

    result = bridge.run_claude(
        prompt="test",
        output_format="text",
        timeout=10.0,
        model="claude-fake-model",
        system_prompt="",
        append_system_prompt="",
        permission_mode="default",
        max_budget_usd=None,
        add_dirs=[],
        allowed_tools="",
        disallowed_tools="",
    )

    assert result["status"] == expected_status
    assert result["exit_code"] == expected_exit


def test_main_returns_exit_9_for_model_rejection(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        bridge,
        "run_claude",
        lambda **kwargs: {
            "status": "model_rejected",
            "exit_code": 1,
            "stdout": "",
            "stderr": "Unsupported selected model",
            "command": ["claude"],
            "rejected_model": "claude-fake-model",
        },
    )

    assert (
        bridge.main(["--prompt", "test", "--model", "claude-fake-model"])
        == bridge.EXIT_MODEL_REJECTED
    )
    assert "Unsupported selected model" in capsys.readouterr().err
