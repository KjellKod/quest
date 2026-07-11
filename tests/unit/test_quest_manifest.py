"""Source-only tests for the installed Quest manifest contract."""

from __future__ import annotations

import fnmatch
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _manifest_entries() -> list[str]:
    manifest = _repo_root() / ".quest-manifest"
    entries: list[str] = []
    for raw_line in manifest.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        entries.append(line)
    return entries


def _validator_patterns() -> list[str]:
    validator = _repo_root() / "scripts" / "quest_validate-manifest.sh"
    patterns: list[str] = []
    in_patterns = False
    for raw_line in validator.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == "EXPECTED_PATTERNS=(":
            in_patterns = True
            continue
        if in_patterns and line == ")":
            break
        if in_patterns and line.startswith('"') and line.endswith('"'):
            patterns.append(line.strip('"'))
    return patterns


def test_manifest_does_not_install_repo_tests() -> None:
    entries = set(_manifest_entries())

    excluded_tests = {
        "tests/integration/test-enforce-allowlist.sh",
        "tests/test-quest-preflight.sh",
        "tests/test-quest-runtime.sh",
        "tests/test-validate-handoff-contracts.sh",
        "tests/test-validate-quest-state.sh",
        "tests/unit/test_allowlist_matcher.py",
        "tests/unit/test_review_intelligence.py",
        "tests/unit/test_codex_skill_wrappers.py",
        "tests/unit/test_quest_checks_cli.py",
        "tests/unit/test_quest_manifest.py",
    }
    leaked_tests = sorted(entry for entry in entries if entry.startswith("tests/"))
    assert leaked_tests == [], (
        "Repo tests do not belong in .quest-manifest or the Quest installer: "
        + ", ".join(leaked_tests)
    )
    assert excluded_tests.isdisjoint(entries)


def test_manifest_validator_patterns_cover_installed_quest_surface() -> None:
    patterns = _validator_patterns()
    expected_paths = {
        "docs/guides/quest_setup.md",
        "scripts/quest_backfill_journal.py",
        "scripts/quest_complete.py",
        "scripts/quest_preflight.sh",
        "scripts/quest_state.py",
        "scripts/quest_celebrate/celebrate.py",
        "scripts/quest_celebrate/quest-celebrate.sh",
        "scripts/quest_runtime/quest_ids.py",
    }

    uncovered = sorted(
        path
        for path in expected_paths
        if not any(fnmatch.fnmatch(path, pattern) for pattern in patterns)
    )

    assert uncovered == []


def test_manifest_includes_installed_quest_setup_guide() -> None:
    assert "docs/guides/quest_setup.md" in set(_manifest_entries())


def test_manifest_validator_does_not_scan_repo_tests() -> None:
    patterns = _validator_patterns()

    leaked_patterns = sorted(
        pattern for pattern in patterns if pattern.startswith("tests/")
    )
    assert leaked_patterns == [], (
        "The manifest validator must not require repo tests to be installed: "
        + ", ".join(leaked_patterns)
    )
