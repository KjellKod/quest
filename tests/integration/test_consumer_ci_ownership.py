"""Consumer CI stays outside ordinary Quest installation and cleanup."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test_quest_effort_install import (
    BRANCH,
    REVISION,
    ROOT,
    run_interactive_installer,
    snapshot_tree,
    upgrade_fixture,
    valid_allowlist,
)

REVIEWER = ".skills/ci-code-reviewer/SKILL.md"
ORIGINAL = b"Consumer CI review baseline\n"
NOTICE = f"Released installer ownership: {REVIEWER}"


def seed_consumer(
    target: Path, state: str
) -> dict[str, tuple[bytes | str | None, int]]:
    """Seed consumer-owned policy independently of framework prose."""
    (target / ".ai/allowlist.json").write_text(json.dumps(valid_allowlist()))
    for name in (
        ".github/workflows/review.yml",
        ".github/review-prompt.md",
        ".github/review-validator.py",
        ".github/review-config.json",
        "policy/ci-review.md",
    ):
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"consumer-owned sentinel\n")
    reviewer = target / REVIEWER
    reviewer.parent.mkdir(parents=True)
    if state not in {"fresh", "missing"}:
        reviewer.write_bytes(ORIGINAL)
        reviewer.chmod(0o640)
        if state == "customized":
            reviewer.write_bytes(ORIGINAL + b"Stricter project policy\n")
        elif state == "symlink":
            reviewer.unlink()
            reviewer.symlink_to(target / "policy/ci-review.md")
    for suffix in (".quest_updated", ".quest_local_backup"):
        (target / (REVIEWER + suffix)).write_bytes(b"existing consumer sidecar\n")
    checksums = ""
    if state not in {"fresh", "unknown"}:
        checksums += f"{hashlib.sha256(ORIGINAL).hexdigest()}  {REVIEWER}\n"
    if state == "fresh":
        (target / ".quest-version").unlink()
    else:
        (target / "retired-framework.txt").write_bytes(b"retired\n")
        retired_checksum = hashlib.sha256(b"retired\n").hexdigest()
        checksums += f"{retired_checksum}  retired-framework.txt\n"
    (target / ".quest-checksums").write_text(checksums)
    return protected_snapshot(target)


def protected_snapshot(target: Path) -> dict[str, tuple[bytes | str | None, int]]:
    return {
        key: (value, (target / key).lstat().st_mode)
        for key, value in snapshot_tree(target).items()
        if key.startswith((".github/", "policy/", ".skills/ci-code-reviewer/"))
    }


@pytest.mark.parametrize(
    "name", [".github/review-prompt.md", REVIEWER + ".quest_updated"]
)
def test_protected_snapshot_detects_permission_changes(tmp_path: Path, name: str):
    path = tmp_path / name
    path.parent.mkdir(parents=True)
    path.write_text("Consumer-owned policy\n")
    path.chmod(0o640)
    before = protected_snapshot(tmp_path)

    path.chmod(0o600)

    assert protected_snapshot(tmp_path) != before


def install(
    target: Path,
    env: dict[str, str],
    mode: str,
) -> subprocess.CompletedProcess[str]:
    script = target / "scripts/quest_installer.sh"
    script.parent.mkdir(exist_ok=True)
    if not script.exists():
        shutil.copy2(ROOT / "scripts/quest_installer.sh", script)
    command = ["bash", str(script), "--branch", BRANCH]
    if mode == "force":
        command.append("--force")
    elif mode == "check":
        command.append("--check")
    if mode == "interactive":
        return run_interactive_installer(command, target, env)
    return subprocess.run(
        command,
        cwd=target,
        env=env,
        input="",
        text=True,
        capture_output=True,
        timeout=120,
    )


@pytest.mark.parametrize("mode", ["force", "unattended", "interactive"])
@pytest.mark.parametrize("state", ["fresh", "pristine", "customized"])
def test_normal_install_preserves_consumer_ci(upgrade_fixture, mode, state):
    target, upstream, env = upgrade_fixture
    before = seed_consumer(target, state)
    legacy_mode = (target / REVIEWER).lstat().st_mode if state != "fresh" else None
    result = install(target, env, mode)

    assert result.returncode == 0, result.stdout + result.stderr
    assert protected_snapshot(target) == before
    assert REVIEWER not in (target / ".quest-checksums").read_text()
    assert (target / ".quest-version").read_text().strip() == REVISION
    assert not (target / "retired-framework.txt").exists()
    assert (target / ".skills/code-reviewer/SKILL.md").read_bytes() == (
        upstream / ".skills/code-reviewer/SKILL.md"
    ).read_bytes()
    assert (NOTICE in result.stdout) == (state != "fresh")
    if legacy_mode is not None:
        assert (target / REVIEWER).lstat().st_mode == legacy_mode


@pytest.mark.parametrize("state", ["unknown", "missing", "symlink"])
def test_release_handles_unknown_missing_and_symlink_paths(upgrade_fixture, state):
    target, _, env = upgrade_fixture
    before = seed_consumer(target, state)
    result = install(target, env, "force")

    assert result.returncode == 0, result.stdout + result.stderr
    assert protected_snapshot(target) == before
    assert REVIEWER not in (target / ".quest-checksums").read_text()
    assert (NOTICE in result.stdout) == (state != "unknown")


def test_preview_does_not_persist_ownership_release(upgrade_fixture):
    target, _, env = upgrade_fixture
    seed_consumer(target, "pristine")
    script = target / "scripts/quest_installer.sh"
    script.parent.mkdir()
    shutil.copy2(ROOT / "scripts/quest_installer.sh", script)
    before = snapshot_tree(target)

    result = install(target, env, "check")

    assert result.returncode == 0, result.stdout + result.stderr
    assert snapshot_tree(target) == before
    assert f"Would release installer ownership: {REVIEWER}" in result.stdout


def test_next_upgrade_leaves_released_ci_alone(upgrade_fixture):
    target, upstream, env = upgrade_fixture
    before = seed_consumer(target, "pristine")
    first = install(target, env, "force")
    assert first.returncode == 0, first.stdout + first.stderr
    framework = ".skills/code-reviewer/SKILL.md"
    with (upstream / framework).open("a") as stream:
        stream.write("\nUpdated generic guidance\n")
    # A different prior version forces the ordinary update path on the next run.
    (target / ".quest-version").write_text("b" * 40 + "\n")

    second = install(target, env, "unattended")

    assert second.returncode == 0, second.stdout + second.stderr
    assert protected_snapshot(target) == before
    assert NOTICE not in second.stdout
    assert REVIEWER not in (target / ".quest-checksums").read_text()
    assert (target / framework).read_bytes() == (upstream / framework).read_bytes()
    assert (target / ".quest-version").read_text().strip() == REVISION
