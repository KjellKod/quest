"""Verify runtime agent wrappers delegate to canonical role docs in `.skills/quest/agents/`."""

from __future__ import annotations

from pathlib import Path

ROLES = ("planner", "builder", "fixer", "plan-reviewer", "code-reviewer")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_claude_runtime_agents_reference_canonical() -> None:
    root = _repo_root()
    for role in ROLES:
        wrapper = (root / ".claude" / "agents" / f"{role}.md").read_text(
            encoding="utf-8"
        )
        canonical_ref = f".skills/quest/agents/{role}.md"
        assert canonical_ref in wrapper, (
            f".claude/agents/{role}.md does not reference {canonical_ref}; "
            f"conditional ui_work loading depends on this delegation"
        )


def test_opencode_runtime_agents_reference_canonical() -> None:
    root = _repo_root()
    for role in ROLES:
        wrapper_path = root / ".opencode" / "agents" / f"{role}.md"
        if not wrapper_path.exists():
            continue
        wrapper = wrapper_path.read_text(encoding="utf-8")
        canonical_ref = f".skills/quest/agents/{role}.md"
        assert canonical_ref in wrapper, (
            f".opencode/agents/{role}.md does not reference {canonical_ref}; "
            f"conditional ui_work loading depends on this delegation"
        )
