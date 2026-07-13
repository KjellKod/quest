from __future__ import annotations

import io
import subprocess

import pytest

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
