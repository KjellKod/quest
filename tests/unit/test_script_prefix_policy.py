from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / ".quest-manifest"
INSTALLER = REPO_ROOT / "scripts" / "quest_installer.sh"

LEGACY_REFERENCE_ALLOWED_FILES = {
    PurePosixPath("scripts/quest_installer.sh"),
    PurePosixPath("scripts/quest_validate-quest-config.sh"),
    PurePosixPath("tests/test-quest-runtime.sh"),
    PurePosixPath("tests/unit/test_script_prefix_policy.py"),
}
HISTORICAL_REFERENCE_ROOTS = {
    PurePosixPath(".quest"),
    PurePosixPath("docs/implementation/history"),
    PurePosixPath("docs/quest-journal"),
    PurePosixPath("ideas/archive"),
}

EXPECTED_MIGRATIONS = {
    (
        "scripts/check_quest_checksum_drift.py",
        "scripts/quest_check_checksum_drift.py",
    ),
    ("scripts/claude_bg_run.py", "scripts/quest_claude_bg_run.py"),
    (
        "scripts/pr_shepherd_annotate_scope.py",
        "scripts/quest_pr_shepherd_annotate_scope.py",
    ),
    (
        "scripts/pr_shepherd_checkout.py",
        "scripts/quest_pr_shepherd_checkout.py",
    ),
    (
        "scripts/pr_shepherd_collect_intake.py",
        "scripts/quest_pr_shepherd_collect_intake.py",
    ),
    (
        "scripts/pr_shepherd_fetch_failed_logs.py",
        "scripts/quest_pr_shepherd_fetch_failed_logs.py",
    ),
    (
        "scripts/pr_shepherd_post_reply.py",
        "scripts/quest_pr_shepherd_post_reply.py",
    ),
    (
        "scripts/pr_sync_default_branch.py",
        "scripts/quest_pr_sync_default_branch.py",
    ),
    ("scripts/claude_cli_bridge.py", "scripts/quest_claude_bridge.py"),
    (
        "scripts/validate-handoff-contracts.sh",
        "scripts/quest_validate-handoff-contracts.sh",
    ),
    ("scripts/validate-manifest.sh", "scripts/quest_validate-manifest.sh"),
    (
        "scripts/validate-quest-config.sh",
        "scripts/quest_validate-quest-config.sh",
    ),
    (
        "scripts/validate-quest-state.sh",
        "scripts/quest_validate-quest-state.sh",
    ),
}


def _installed_manifest_paths(manifest: Path = MANIFEST) -> list[PurePosixPath]:
    installed_sections = {"copy-as-is", "user-customized", "merge-carefully"}
    section = ""
    paths: list[PurePosixPath] = []
    for raw_line in manifest.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if section in installed_sections:
            paths.append(PurePosixPath(line))
    return paths


def _unprefixed_top_level_python_entries(scripts_dir: Path) -> list[str]:
    return sorted(
        entry.name
        for entry in scripts_dir.glob("*.py")
        if not entry.name.startswith("quest_")
    )


def _migration_pairs(installer: Path = INSTALLER) -> set[tuple[str, str]]:
    text = installer.read_text(encoding="utf-8")
    match = re.search(
        r"^RENAMED_SCRIPT_MIGRATIONS=\(\n(?P<body>.*?)^\)\n",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match, "RENAMED_SCRIPT_MIGRATIONS registry is missing"
    entries = re.findall(r'^\s*"([^"|]+)\|([^"|]+)"\s*$', match["body"], re.MULTILINE)
    return set(entries)


def _source_only_migration_destinations(installer: Path = INSTALLER) -> set[str]:
    text = installer.read_text(encoding="utf-8")
    match = re.search(
        r"^SOURCE_ONLY_RENAMED_SCRIPT_DESTINATIONS=\(\n(?P<body>.*?)^\)\n",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match, "SOURCE_ONLY_RENAMED_SCRIPT_DESTINATIONS registry is missing"
    return set(re.findall(r'^\s*"([^"]+)"\s*$', match["body"], re.MULTILINE))


def _active_legacy_filename_references() -> list[str]:
    legacy_patterns = []
    for old_path, _ in EXPECTED_MIGRATIONS:
        path = PurePosixPath(old_path)
        if path.suffix == ".py":
            legacy_patterns.append(rf"{re.escape(path.stem)}(?:\.py)?")
        else:
            legacy_patterns.append(re.escape(path.name))
    pattern = re.compile(
        rf"(?<![A-Za-z0-9_-])(?:{'|'.join(legacy_patterns)})(?![A-Za-z0-9_.-])"
    )
    references: list[str] = []

    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.split("\0")

    for tracked_path in tracked:
        if not tracked_path:
            continue
        relative = PurePosixPath(tracked_path)
        path = REPO_ROOT / relative
        if not path.is_file():
            continue
        if relative in LEGACY_REFERENCE_ALLOWED_FILES:
            continue
        if any(
            root == relative or root in relative.parents
            for root in HISTORICAL_REFERENCE_ROOTS
        ):
            continue

        content = path.read_bytes()
        if b"\0" in content:
            continue
        text = content.decode("utf-8", errors="ignore")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                references.append(f"{relative}:{line_number}:{line.strip()}")

    return references


def test_manifest_top_level_python_entrypoints_start_with_quest_prefix_and_exist() -> (
    None
):
    entries = _installed_manifest_paths()
    top_level_python = [
        path
        for path in entries
        if path.parent == PurePosixPath("scripts") and path.suffix == ".py"
    ]
    unprefixed = sorted(
        str(path) for path in top_level_python if not path.name.startswith("quest_")
    )
    missing = sorted(
        str(path) for path in top_level_python if not (REPO_ROOT / path).is_file()
    )

    assert not unprefixed, f"unprefixed installed Python entrypoints: {unprefixed}"
    assert not missing, f"manifest entries missing from source: {missing}"


def test_source_top_level_python_entries_start_with_quest_prefix() -> None:
    unprefixed = _unprefixed_top_level_python_entries(REPO_ROOT / "scripts")
    assert not unprefixed, f"unprefixed top-level Python entries: {unprefixed}"


def test_source_policy_rejects_unprefixed_symlink(tmp_path: Path) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    target = tmp_path / "target.py"
    target.write_text("pass\n", encoding="utf-8")
    (scripts_dir / "legacy.py").symlink_to(target)

    assert _unprefixed_top_level_python_entries(scripts_dir) == ["legacy.py"]


def test_migration_registry_contains_all_supported_pairs() -> None:
    assert _migration_pairs() == EXPECTED_MIGRATIONS


def test_source_only_migration_destination_is_explicit() -> None:
    assert _source_only_migration_destinations() == {
        "scripts/quest_check_checksum_drift.py"
    }


def test_migration_registry_new_paths_resolve() -> None:
    manifest_paths = {str(path) for path in _installed_manifest_paths()}
    missing = sorted(
        new_path
        for _, new_path in _migration_pairs()
        if new_path not in manifest_paths and not (REPO_ROOT / new_path).is_file()
    )
    unresolved = sorted(
        new_path
        for _, new_path in _migration_pairs()
        if new_path in manifest_paths and not (REPO_ROOT / new_path).is_file()
    )

    assert (
        not missing
    ), f"migration destinations not found in source or manifest: {missing}"
    assert (
        not unresolved
    ), f"manifested migration destinations missing from source: {unresolved}"


def test_active_files_do_not_reference_legacy_script_names() -> None:
    references = _active_legacy_filename_references()
    assert not references, "active legacy script references:\n" + "\n".join(references)
