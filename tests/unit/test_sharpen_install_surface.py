from __future__ import annotations

from pathlib import Path


NEW_INSTALLED_FILES = {
    ".agents/skills/sharpen/SKILL.md",
    ".claude/skills/sharpen/SKILL.md",
    ".skills/sharpen/SKILL.md",
}

DELEGATION_LINE = "Read and follow the instructions in `.skills/sharpen/SKILL.md`."


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (_repo_root() / path).read_text(encoding="utf-8")


def _copy_as_is_manifest_entries() -> set[str]:
    entries: set[str] = set()
    in_copy_as_is = False

    for raw_line in _read(".quest-manifest").splitlines():
        line = raw_line.strip()
        if line == "[copy-as-is]":
            in_copy_as_is = True
            continue
        if line.startswith("[") and line.endswith("]"):
            in_copy_as_is = False
            continue
        if in_copy_as_is and line and not line.startswith("#"):
            entries.add(line)

    return entries


def test_sharpen_catalog_entry_points_to_skill() -> None:
    catalog = _read(".skills/SKILLS.md")

    assert "### sharpen" in catalog
    assert "Adversarial interview against a plan, design, or write-up" in catalog
    assert ".skills/sharpen/SKILL.md" in catalog


def test_sharpen_canonical_skill_is_standalone() -> None:
    skill = _read(".skills/sharpen/SKILL.md")

    assert "name: sharpen" in skill
    assert "Quest" not in skill


def test_claude_sharpen_wrapper_is_user_invocable_and_delegates() -> None:
    wrapper = _read(".claude/skills/sharpen/SKILL.md")

    assert "name: sharpen" in wrapper
    assert "user-invocable: true" in wrapper
    assert wrapper.split("---", maxsplit=2)[2].strip() == DELEGATION_LINE


def test_codex_sharpen_wrapper_delegates() -> None:
    wrapper = _read(".agents/skills/sharpen/SKILL.md")

    assert "name: sharpen" in wrapper
    assert wrapper.split("---", maxsplit=2)[2].strip() == DELEGATION_LINE


def test_sharpen_installed_files_are_manifest_copy_as_is_entries() -> None:
    assert NEW_INSTALLED_FILES <= _copy_as_is_manifest_entries()
