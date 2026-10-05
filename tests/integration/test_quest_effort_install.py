"""Effort-format upgrades refuse before changing the consuming repository."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REVISION = "a" * 40


def run_install(
    tmp_path: Path,
    target: Path,
    *,
    framework_files: dict[str, str] | None = None,
    copy_manifest: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Exercise run_install, replacing network reads and optional global setup."""
    source = tmp_path / "upstream"
    source.mkdir()
    files = {"payload.txt": "new runtime payload\n", **(framework_files or {})}
    (source / ".quest-manifest").write_text(
        "[copy-as-is]\n"
        + (".quest-manifest\n" if copy_manifest else "")
        + "\n".join(files)
        + "\n[user-customized]\n.ai/allowlist.json\n"
    )
    for name, content in files.items():
        destination = source / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)
    (source / ".ai").mkdir()
    (source / ".ai/allowlist.json").write_text('{"effort": {"builder": "medium"}}\n')
    functions = tmp_path / "installer-functions.sh"
    functions.write_text(
        (ROOT / "scripts/quest_installer.sh")
        .read_text()
        .split("# Store original args for re-exec after self-update")[0]
    )
    script = tmp_path / "run.sh"
    script.write_text(
        'source "$INSTALLER_FUNCTIONS"\n'
        "fetch_latest_release() { LATEST_RELEASE=fixture; }\n"
        'fetch_upstream_version() { UPSTREAM_SHA="$FIXTURE_SHA"; }\n'
        'fetch_file() { cat "$FIXTURE_UPSTREAM/$1"; }\n'
        'fetch_file_to_temp() { cp "$FIXTURE_UPSTREAM/$1" "$2"; }\n'
        "offer_codex_setup() { :; }\n"
        "parse_args --force --branch acceptance-fixture\n"
        "run_install\n"
    )
    return subprocess.run(
        ["bash", str(script)],
        cwd=target,
        env={
            **os.environ,
            "INSTALLER_FUNCTIONS": str(functions),
            "FIXTURE_UPSTREAM": str(source),
            "FIXTURE_SHA": REVISION,
        },
        text=True,
        capture_output=True,
        timeout=30,
    )


def snapshot_tree(root: Path) -> dict[str, bytes | str | None]:
    """Include empty directories and link targets without following symlinks."""
    snapshot: dict[str, bytes | str | None] = {}
    for path in root.rglob("*"):
        key = str(path.relative_to(root))
        if path.is_symlink():
            snapshot[key] = os.readlink(path)
        else:
            snapshot[key] = None if path.is_dir() else path.read_bytes()
    return snapshot


@pytest.mark.parametrize("allowlist", [{}, {"effort": None}, {"effort": "medium"}])
def test_old_effort_format_refuses_before_any_repository_write(
    tmp_path: Path, allowlist: dict[str, object]
) -> None:
    target = tmp_path / "consumer"
    target.mkdir()
    (target / ".ai").mkdir()
    (target / ".ai/allowlist.json").write_text(json.dumps(allowlist))
    (target / ".quest-version").write_text("old-version\n")
    (target / ".quest-checksums").write_text("# old checksums\n")
    (target / "payload.txt").write_text("old runtime payload\n")
    before = snapshot_tree(target)

    result = run_install(tmp_path, target)

    assert result.returncode != 0, result.stdout + result.stderr
    after = snapshot_tree(target)
    assert after == before
    assert "Installation Complete" not in result.stdout
    assert ".ai/allowlist.json" in result.stdout
    assert (
        f"https://raw.githubusercontent.com/KjellKod/quest/{REVISION}/.ai/allowlist.json"
        in result.stdout
    )
    assert "effort" in result.stdout
    assert "This installer pass stopped before changing files." in result.stdout
    assert "No installation files were changed" not in result.stdout


@pytest.mark.parametrize("existing", [False, True])
def test_fresh_or_current_effort_format_installs(
    tmp_path: Path, existing: bool
) -> None:
    target = tmp_path / "consumer"
    target.mkdir()
    if existing:
        (target / ".ai").mkdir()
        (target / ".ai/allowlist.json").write_text('{"effort": {"builder": "low"}}\n')

    result = run_install(tmp_path, target)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "payload.txt").read_text() == "new runtime payload\n"
    assert (target / ".quest-version").read_text().strip() == REVISION
    saved = json.loads((target / ".ai/allowlist.json").read_text())
    assert saved["effort"]["builder"] == ("low" if existing else "medium")


@pytest.mark.parametrize(
    "case",
    [
        "changed_custom",
        "unknown_checksum",
        "pristine",
        "symlink_pristine",
        "already_current",
        "unchanged_custom",
    ],
)
def test_framework_upgrade_never_leaves_changed_custom_dispatch_behind(
    tmp_path: Path, case: str
) -> None:
    target = tmp_path / "consumer"
    target.mkdir()
    (target / ".ai").mkdir()
    (target / ".ai/allowlist.json").write_text('{"effort": {"builder": "medium"}}\n')
    (target / ".quest-version").write_text("old-version\n")
    path = (
        ".claude/agents/arbiter.md"
        if case == "unchanged_custom"
        else ".skills/quest/delegation/workflow.md"
    )
    old = "Native role instructions\n"
    upstream = old if case == "unchanged_custom" else "Background role instructions\n"
    local = old + "Local customization\n"
    if case == "pristine":
        local = old
    elif case == "already_current":
        local = upstream
    destination = target / path
    destination.parent.mkdir(parents=True)
    external = tmp_path / "external-workflow.md"
    if case == "symlink_pristine":
        external.write_text(old)
        destination.symlink_to(external)
    else:
        destination.write_text(local)
    checksum = hashlib.sha256(old.encode()).hexdigest()
    (target / ".quest-checksums").write_text(
        "" if case == "unknown_checksum" else f"{checksum}  {path}\n"
    )
    before = snapshot_tree(target)

    result = run_install(tmp_path, target, framework_files={path: upstream})

    if case in {"changed_custom", "unknown_checksum", "symlink_pristine"}:
        assert result.returncode != 0, result.stdout + result.stderr
        after = snapshot_tree(target)
        assert after == before
        if case == "symlink_pristine":
            assert external.read_text() == old
            assert destination.is_symlink()
        assert path in result.stdout
        assert (
            f"https://raw.githubusercontent.com/KjellKod/quest/{REVISION}/{path}"
            in result.stdout
        )
        assert "Installation Complete" not in result.stdout
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert destination.read_text() == (
            local if case == "unchanged_custom" else upstream
        )
        assert (target / ".quest-version").read_text().strip() == REVISION


def test_modified_manifest_is_backed_up_and_replaced_during_upgrade(
    tmp_path: Path,
) -> None:
    target = tmp_path / "consumer"
    target.mkdir()
    (target / ".ai").mkdir()
    (target / ".ai/allowlist.json").write_text('{"effort": {"builder": "medium"}}\n')
    old_manifest = "[copy-as-is]\nold-runtime.txt\n"
    custom_manifest = old_manifest + "# local bookkeeping customization\n"
    (target / ".quest-manifest").write_text(custom_manifest)
    checksum = hashlib.sha256(old_manifest.encode()).hexdigest()
    (target / ".quest-checksums").write_text(f"{checksum}  .quest-manifest\n")

    result = run_install(tmp_path, target, copy_manifest=True)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        target / ".quest-manifest.quest_local_backup"
    ).read_text() == custom_manifest
    assert (target / ".quest-manifest").read_bytes() == (
        tmp_path / "upstream/.quest-manifest"
    ).read_bytes()
    assert (target / "payload.txt").read_text() == "new runtime payload\n"
    assert (target / ".quest-version").read_text().strip() == REVISION
