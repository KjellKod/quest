"""Source-only tests for the installed Quest manifest contract."""

from __future__ import annotations

import fnmatch
import re
import shutil
from pathlib import Path
from urllib.parse import unquote, urlsplit


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


def _manifest_file_entries() -> list[str]:
    manifest = _repo_root() / ".quest-manifest"
    entries: list[str] = []
    section = ""
    for raw_line in manifest.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            continue
        if not line or line.startswith("#") or section == "directories":
            continue
        entries.append(line)
    return entries


def _inline_markdown_targets(markdown: str) -> list[str]:
    targets: list[str] = []
    for match in re.finditer(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", markdown):
        raw_target = match.group(1).strip()
        if raw_target.startswith("<") and ">" in raw_target:
            target = raw_target[1 : raw_target.index(">")]
        else:
            target = raw_target.split(maxsplit=1)[0]
        targets.append(target)
    return targets


def _guide_heading_slugs(markdown: str) -> set[str]:
    slugs: set[str] = set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*$", markdown, flags=re.MULTILINE):
        slug = re.sub(r"[^\w\s-]", "", heading.lower())
        slugs.add(re.sub(r"\s+", "-", slug.strip()))
    return slugs


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


def test_installed_setup_guide_relative_links_resolve_to_manifest_owned_files(
    tmp_path: Path,
) -> None:
    repo_root = _repo_root()
    owned_files = set(_manifest_file_entries())
    for entry in owned_files:
        source = repo_root / entry
        if not source.is_file():
            continue
        destination = tmp_path / entry
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    guide_entry = "docs/guides/quest_setup.md"
    installed_guide = tmp_path / guide_entry
    guide_text = installed_guide.read_text(encoding="utf-8")
    local_targets = [
        target
        for target in _inline_markdown_targets(guide_text)
        if not urlsplit(target).scheme and not target.startswith("//")
    ]

    assert local_targets, "expected at least one installed-guide local link"
    assert "#optional-codex-mcp-for-dual-model-reviews" in local_targets

    resolved_targets: list[str] = []
    for target in local_targets:
        path_text, _, fragment = target.partition("#")
        relative_path = Path(unquote(path_text)) if path_text else Path(guide_entry)
        if path_text:
            target_path = (installed_guide.parent / relative_path).resolve()
        else:
            target_path = installed_guide.resolve()
        try:
            installed_entry = target_path.relative_to(tmp_path.resolve()).as_posix()
        except ValueError:
            raise AssertionError(f"local guide link escapes installed fixture: {target}")

        assert installed_entry in owned_files, (
            f"local guide link is not Quest-owned: {target} -> {installed_entry}"
        )
        assert target_path.is_file(), f"local guide link is not installed: {target}"
        if not path_text and fragment:
            assert fragment in _guide_heading_slugs(guide_text), (
                f"local guide fragment does not match a heading: {target}"
            )
        resolved_targets.append(target)

    assert len(resolved_targets) == len(local_targets)


def test_guide_heading_slugs_strip_github_anchor_punctuation() -> None:
    markdown = "### What's next? Ready, set... go!"

    assert _guide_heading_slugs(markdown) == {"whats-next-ready-set-go"}


def test_installed_setup_guide_has_no_unchecked_relative_reference_links() -> None:
    guide = (_repo_root() / "docs/guides/quest_setup.md").read_text(encoding="utf-8")
    relative_definitions: list[str] = []
    for target in re.findall(
        r"^\s{0,3}\[[^\]]+\]:\s*(\S+)", guide, flags=re.MULTILINE
    ):
        normalized = (
            target[1:-1]
            if target.startswith("<") and target.endswith(">")
            else target
        )
        if not urlsplit(normalized).scheme and not normalized.startswith("//"):
            relative_definitions.append(normalized)

    assert relative_definitions == [], (
        "relative reference-style links are not covered by the installed-guide "
        "resolver; extend it deliberately before using this syntax: "
        + ", ".join(relative_definitions)
    )


def test_manifest_does_not_own_quest_presentation() -> None:
    entries = set(_manifest_file_entries())

    assert "docs/guides/quest_presentation.md" not in entries
    assert "quest_presentation.md" not in entries


def test_manifest_validator_does_not_scan_repo_tests() -> None:
    patterns = _validator_patterns()

    leaked_patterns = sorted(
        pattern for pattern in patterns if pattern.startswith("tests/")
    )
    assert leaked_patterns == [], (
        "The manifest validator must not require repo tests to be installed: "
        + ", ".join(leaked_patterns)
    )
