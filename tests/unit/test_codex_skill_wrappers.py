from __future__ import annotations

from pathlib import Path

EXPECTED_QUEST_WRAPPERS = {
    "celebrate",
    "git-commit-assistant",
    "pr-assistant",
    "pr-shepherd",
    "quest",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_codex_wrapper_surface_includes_required_project_skills() -> None:
    wrappers_root = _repo_root() / ".agents" / "skills"
    wrapper_names = {
        path.name
        for path in wrappers_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    }

    assert EXPECTED_QUEST_WRAPPERS <= wrapper_names


def test_codex_wrappers_delegate_to_matching_project_skills() -> None:
    wrappers_root = _repo_root() / ".agents" / "skills"

    for skill_name in EXPECTED_QUEST_WRAPPERS:
        wrapper_path = wrappers_root / skill_name / "SKILL.md"
        content = wrapper_path.read_text(encoding="utf-8")
        assert f"name: {skill_name}" in content
        assert f"Read and follow the instructions in `.skills/{skill_name}/SKILL.md`." in content


def test_codex_wrapper_surface_intentionally_excludes_gpt() -> None:
    wrapper_path = _repo_root() / ".agents" / "skills" / "gpt" / "SKILL.md"
    assert not wrapper_path.exists()
