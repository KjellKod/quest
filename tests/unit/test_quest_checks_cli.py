"""Unit tests for the installed quest_checks CLI contract."""

from __future__ import annotations

import importlib.util
import runpy
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_cli_module():
    module_path = _repo_root() / "scripts" / "quest_checks" / "cli.py"
    spec = importlib.util.spec_from_file_location("quest_checks_cli", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_references_installed_commands_that_exist() -> None:
    module = _load_cli_module()
    missing_paths: list[str] = []

    for _, command in module.COMMANDS:
        for token in command[1:]:
            if (
                token.startswith(("scripts/", "tests/"))
                and not (_repo_root() / token).exists()
            ):
                missing_paths.append(token)

    assert missing_paths == []


def test_cli_main_runs_all_installed_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_cli_module()
    calls: list[tuple[list[str], Path, bool]] = []

    def fake_run(command: list[str], cwd: Path, check: bool) -> SimpleNamespace:
        calls.append((command, cwd, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert module.main() == 0
    assert [command for _, command in module.COMMANDS] == [
        command for command, _, _ in calls
    ]
    assert all(cwd == module.REPO_ROOT and check is False for _, cwd, check in calls)


def test_cli_uses_consumer_safe_default_manifest_validation() -> None:
    module = _load_cli_module()
    manifest_commands = [
        command for label, command in module.COMMANDS if label == "validate manifest"
    ]

    assert manifest_commands == [["bash", "scripts/quest_validate-manifest.sh"]]


def test_cli_entrypoint_executes_main(monkeypatch: pytest.MonkeyPatch) -> None:
    script_path = _repo_root() / "scripts" / "quest_checks" / "cli.py"
    calls: list[tuple[list[str], Path, bool]] = []

    def fake_run(command: list[str], cwd: Path, check: bool) -> SimpleNamespace:
        calls.append((command, cwd, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(str(script_path), run_name="__main__")

    assert exc_info.value.code == 0
    assert [command for _, command in _load_cli_module().COMMANDS] == [
        command for command, _, _ in calls
    ]
