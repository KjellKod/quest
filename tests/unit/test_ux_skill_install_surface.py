"""Regression tests for the ux-review / ux-context install surface."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_ux_context_canonical_skill_exists() -> None:
    root = _repo_root()
    assert (root / ".skills" / "ux-context" / "SKILL.md").exists()
    assert (root / ".skills" / "ux-context" / "resources" / "ux-guidebook.md").exists()
    assert (root / ".skills" / "ux-context" / "resources" / "ux-stress-test.md").exists()


def test_ux_review_canonical_and_wrappers_exist() -> None:
    root = _repo_root()
    assert (root / ".skills" / "ux-review" / "SKILL.md").exists()
    assert (root / ".claude" / "skills" / "ux-review" / "SKILL.md").exists()
    assert (root / ".agents" / "skills" / "ux-review" / "SKILL.md").exists()


def test_ux_review_wrappers_delegate_to_canonical() -> None:
    root = _repo_root()
    for mirror in (".claude/skills/ux-review", ".agents/skills/ux-review"):
        wrapper_text = (root / mirror / "SKILL.md").read_text(encoding="utf-8")
        assert "Read and follow the instructions in `.skills/ux-review/SKILL.md`." in wrapper_text
        assert "name: ux-review" in wrapper_text


def test_ux_context_not_user_invocable() -> None:
    """ux-context is agent-internal and must not appear in user-invocable wrapper trees."""
    root = _repo_root()
    assert not (root / ".claude" / "skills" / "ux-context").exists()
    assert not (root / ".agents" / "skills" / "ux-context").exists()


def test_ux_skills_listed_in_quest_manifest() -> None:
    root = _repo_root()
    manifest = (root / ".quest-manifest").read_text(encoding="utf-8")
    for required in (
        ".skills/ux-context/SKILL.md",
        ".skills/ux-context/resources/ux-guidebook.md",
        ".skills/ux-context/resources/ux-stress-test.md",
        ".skills/ux-review/SKILL.md",
        ".claude/skills/ux-review/SKILL.md",
        ".agents/skills/ux-review/SKILL.md",
    ):
        assert required in manifest, f"{required} missing from .quest-manifest"
