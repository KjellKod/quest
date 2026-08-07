"""Source-only formatting policy and installer-boundary tests."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


BLACK_PIN = "black==26.3.1"
PYTEST_PIN = "pytest==9.0.3"
PYYAML_PIN = "pyyaml==6.0.3"
INSTALL_REMEDIATION = "python3 -m pip install -e '.[dev]'"
FORMAT_REMEDIATION = "python3 -m black ."


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _hook_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    fixture_root = tmp_path / "source-repository"
    hook = fixture_root / ".githooks" / "pre-commit"
    hook.parent.mkdir(parents=True)
    shutil.copy2(_repo_root() / ".githooks" / "pre-commit", hook)

    call_log = fixture_root / "calls.log"
    _write_executable(
        fixture_root / "scripts" / "quest_validate-quest-config.sh",
        """#!/bin/sh
printf 'validator|%s\n' "$PWD" >> "$CALL_LOG"
exit "${VALIDATOR_EXIT:-0}"
""",
    )
    _write_executable(
        fixture_root / "fake-bin" / "python3",
        """#!/bin/sh
printf 'python3|%s|%s\n' "$PWD" "$*" >> "$CALL_LOG"
case "$*" in
  *--version*) exit "${BLACK_PROBE_EXIT:-0}" ;;
esac
exit "${BLACK_EXIT:-0}"
""",
    )

    nested_directory = fixture_root / "nested" / "working-directory"
    nested_directory.mkdir(parents=True)
    return hook, call_log, nested_directory


def _hook_environment(fixture_root: Path, call_log: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PATH"] = f"{fixture_root / 'fake-bin'}:{environment['PATH']}"
    environment["CALL_LOG"] = str(call_log)
    return environment


def _manifest_file_entries() -> set[str]:
    entries: set[str] = set()
    section = ""
    for raw_line in (
        (_repo_root() / ".quest-manifest").read_text(encoding="utf-8").splitlines()
    ):
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if line and not line.startswith("#") and section != "directories":
            entries.add(line)
    return entries


def _checksum_entries() -> set[str]:
    entries: set[str] = set()
    for raw_line in (
        (_repo_root() / ".quest-checksums").read_text(encoding="utf-8").splitlines()
    ):
        line = raw_line.strip()
        if line and not line.startswith("#"):
            _, path = line.split(maxsplit=1)
            entries.add(path)
    return entries


def test_pyproject_declares_exact_pinned_development_dependencies() -> None:
    with (_repo_root() / "pyproject.toml").open("rb") as pyproject_file:
        pyproject = tomllib.load(pyproject_file)

    assert pyproject["project"]["optional-dependencies"]["dev"] == [
        BLACK_PIN,
        PYTEST_PIN,
        PYYAML_PIN,
    ]
    assert pyproject["tool"]["black"] == {
        "target-version": ["py310"],
        "line-length": 88,
    }


def test_source_hook_is_executable_and_check_only() -> None:
    hook = _repo_root() / ".githooks" / "pre-commit"
    hook_text = hook.read_text(encoding="utf-8")

    assert hook.stat().st_mode & stat.S_IXUSR
    assert "./scripts/quest_validate-quest-config.sh" in hook_text
    assert hook_text.count('"$python3_bin" -m black --check .') == 1
    assert hook_text.count("${python3_bin} -m black .") == 1
    assert "  ${python3_bin} -m black ." in hook_text


def test_source_hook_resolves_root_and_runs_validation_before_black(
    tmp_path: Path,
) -> None:
    hook, call_log, nested_directory = _hook_fixture(tmp_path)
    fixture_root = hook.parents[1]

    result = subprocess.run(
        [str(hook.resolve())],
        cwd=nested_directory,
        env=_hook_environment(fixture_root, call_log),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        f"validator|{fixture_root}",
        f"python3|{fixture_root}|-m black --version",
        f"python3|{fixture_root}|-m black --check .",
    ]


def test_source_hook_failure_is_non_mutating_and_prints_exact_remediation(
    tmp_path: Path,
) -> None:
    hook, call_log, nested_directory = _hook_fixture(tmp_path)
    fixture_root = hook.parents[1]
    unformatted_file = fixture_root / "unformatted.py"
    unformatted_file.write_text("value=  1\n", encoding="utf-8")
    before = unformatted_file.read_bytes()
    environment = _hook_environment(fixture_root, call_log)
    environment["BLACK_EXIT"] = "1"

    result = subprocess.run(
        [str(hook.resolve())],
        cwd=nested_directory,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert unformatted_file.read_bytes() == before
    assert FORMAT_REMEDIATION in result.stderr
    assert INSTALL_REMEDIATION not in result.stderr
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        f"validator|{fixture_root}",
        f"python3|{fixture_root}|-m black --version",
        f"python3|{fixture_root}|-m black --check .",
    ]


def test_source_hook_reports_missing_black_without_formatting_noise(
    tmp_path: Path,
) -> None:
    hook, call_log, nested_directory = _hook_fixture(tmp_path)
    fixture_root = hook.parents[1]
    environment = _hook_environment(fixture_root, call_log)
    environment["BLACK_PROBE_EXIT"] = "1"

    result = subprocess.run(
        [str(hook.resolve())],
        cwd=nested_directory,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "black is not installed" in result.stderr
    assert INSTALL_REMEDIATION in result.stderr
    assert FORMAT_REMEDIATION not in result.stderr
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        f"validator|{fixture_root}",
        f"python3|{fixture_root}|-m black --version",
    ]


def test_source_hook_prefers_project_virtualenv_python(tmp_path: Path) -> None:
    hook, call_log, nested_directory = _hook_fixture(tmp_path)
    fixture_root = hook.parents[1]
    _write_executable(
        fixture_root / ".venv" / "bin" / "python3",
        """#!/bin/sh
printf 'venv-python3|%s|%s\n' "$PWD" "$*" >> "$CALL_LOG"
case "$*" in
  *--version*) exit "${BLACK_PROBE_EXIT:-0}" ;;
esac
exit "${BLACK_EXIT:-0}"
""",
    )

    result = subprocess.run(
        [str(hook.resolve())],
        cwd=nested_directory,
        env=_hook_environment(fixture_root, call_log),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        f"validator|{fixture_root}",
        f"venv-python3|{fixture_root}|-m black --version",
        f"venv-python3|{fixture_root}|-m black --check .",
    ]


def test_source_hook_venv_failure_remediation_names_the_venv_interpreter(
    tmp_path: Path,
) -> None:
    hook, call_log, nested_directory = _hook_fixture(tmp_path)
    fixture_root = hook.parents[1]
    _write_executable(
        fixture_root / ".venv" / "bin" / "python3",
        """#!/bin/sh
printf 'venv-python3|%s|%s\n' "$PWD" "$*" >> "$CALL_LOG"
case "$*" in
  *--version*) exit "${BLACK_PROBE_EXIT:-0}" ;;
esac
exit "${BLACK_EXIT:-0}"
""",
    )
    environment = _hook_environment(fixture_root, call_log)
    environment["BLACK_EXIT"] = "1"

    result = subprocess.run(
        [str(hook.resolve())],
        cwd=nested_directory,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "  .venv/bin/python3 -m black ." in result.stderr
    assert f"  {FORMAT_REMEDIATION}" not in result.stderr


def test_source_hook_stops_before_black_when_configuration_is_invalid(
    tmp_path: Path,
) -> None:
    hook, call_log, nested_directory = _hook_fixture(tmp_path)
    fixture_root = hook.parents[1]
    environment = _hook_environment(fixture_root, call_log)
    environment["VALIDATOR_EXIT"] = "1"

    result = subprocess.run(
        [str(hook.resolve())],
        cwd=nested_directory,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        f"validator|{fixture_root}"
    ]


def test_python_ci_keeps_tests_and_enforces_pinned_black_unconditionally() -> None:
    workflow_path = _repo_root() / ".github" / "workflows" / "test-python.yml"
    workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["test"]["steps"]
    steps_by_name = {step["name"]: step for step in steps}

    assert "if" not in steps_by_name["Set up Python"]
    assert steps_by_name["Create virtual environment"]["run"] == (
        "python3 -m venv .venv"
    )
    assert steps_by_name["Install development dependencies"]["run"] == (
        ".venv/bin/python3 -m pip install -e '.[dev]'"
    )
    assert steps_by_name["Check Python formatting"]["run"] == (
        ".venv/bin/python3 -m black --check ."
    )
    for step_name in (
        "Create virtual environment",
        "Install development dependencies",
        "Check Python formatting",
    ):
        assert "if" not in steps_by_name[step_name]
        assert "continue-on-error" not in steps_by_name[step_name]

    assert steps_by_name["Run tests"]["run"] == ".venv/bin/python3 -m pytest tests/ -v"


def test_source_formatting_files_remain_outside_installer_ownership() -> None:
    manifest_entries = _manifest_file_entries()
    checksum_entries = _checksum_entries()
    forbidden_paths = {
        ".githooks/pre-commit",
        "pyproject.toml",
        "CONTRIBUTING.md",
        ".github/workflows/test-python.yml",
        "tests/unit/test_source_python_formatting.py",
    }

    assert forbidden_paths.isdisjoint(manifest_entries)
    assert forbidden_paths.isdisjoint(checksum_entries)
    assert not any(path.startswith(".githooks/") for path in manifest_entries)
    assert not any(path.startswith(".githooks/") for path in checksum_entries)
    assert not any(path.startswith(".github/") for path in manifest_entries)
    assert not any(path.startswith(".github/") for path in checksum_entries)


def test_temporary_installed_consumer_has_no_source_formatting_policy(
    tmp_path: Path,
) -> None:
    repo_root = _repo_root()
    installer = repo_root / "scripts" / "quest_installer.sh"
    installer_text = installer.read_text(encoding="utf-8")
    assert 'COPY_AS_IS+=("scripts/quest_installer.sh")' in installer_text

    installed_files = _manifest_file_entries() | {"scripts/quest_installer.sh"}
    consumer_root = tmp_path / "consumer"
    for entry in installed_files:
        source = repo_root / entry
        if source.is_file():
            destination = consumer_root / entry
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    forbidden_paths = (
        ".githooks",
        "pyproject.toml",
        "CONTRIBUTING.md",
        ".github/workflows/test-python.yml",
    )
    for path in forbidden_paths:
        assert not (consumer_root / path).exists()

    installed_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in consumer_root.rglob("*")
        if path.is_file()
    )
    for source_policy in (
        BLACK_PIN,
        "[tool.black]",
        "python3 -m black",
        "core.hooksPath .githooks",
    ):
        assert source_policy not in installed_text

    for source_only_path in forbidden_paths:
        assert source_only_path not in installer_text
