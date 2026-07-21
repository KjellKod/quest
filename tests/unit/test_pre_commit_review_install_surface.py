from __future__ import annotations

from pathlib import Path

NEW_INSTALLED_FILES = {
    ".claude/skills/pre-commit-review/SKILL.md",
    ".opencode/commands/pre-commit-review.md",
    ".agents/skills/pre-commit-review/SKILL.md",
    ".skills/pre-commit-review/SKILL.md",
}

DELEGATION_LINE = (
    "Read and follow the instructions in `.skills/pre-commit-review/SKILL.md`."
)


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


def test_pre_commit_review_catalog_entry_points_to_skill() -> None:
    catalog = _read(".skills/SKILLS.md")

    assert "### pre-commit-review" in catalog
    assert "Review local staged plus unstaged tracked-file changes" in catalog
    assert ".skills/pre-commit-review/SKILL.md" in catalog


def test_claude_pre_commit_review_wrapper_is_user_invocable_and_delegates() -> None:
    wrapper = _read(".claude/skills/pre-commit-review/SKILL.md")

    assert "name: pre-commit-review" in wrapper
    assert "user-invocable: true" in wrapper
    assert wrapper.split("---", maxsplit=2)[2].strip() == DELEGATION_LINE


def test_opencode_pre_commit_review_command_exists() -> None:
    command = _read(".opencode/commands/pre-commit-review.md")

    assert "pre-commit-review skill" in command
    assert "local working-tree diff before commit" in command


def test_new_installed_files_are_manifest_copy_as_is_entries() -> None:
    # The manifest validator does not scan .opencode/commands/*.md, so this
    # focused test is the authoritative check for the command manifest entry.
    assert NEW_INSTALLED_FILES <= _copy_as_is_manifest_entries()


def test_pre_commit_review_uses_git_resolved_operation_paths() -> None:
    skill = _read(".skills/pre-commit-review/SKILL.md")

    assert "git rev-parse --git-path MERGE_HEAD" in skill
    assert "git rev-parse --git-path CHERRY_PICK_HEAD" in skill
    assert "git rev-parse --git-path rebase-merge" in skill
    assert "git rev-parse --git-path rebase-apply" in skill
    assert "Check the resolved paths, not direct `.git/...` paths." in skill
    assert "Check for `.git/MERGE_HEAD`" not in skill
