from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_codex_wrapper_surface_matches_expected_project_skills() -> None:
    wrappers_root = _repo_root() / ".agents" / "skills"
    wrapper_names = sorted(
        path.name
        for path in wrappers_root.iterdir()
        if path.is_dir() and (path / "SKILL.md").exists()
    )

    assert wrapper_names == [
        "celebrate",
        "git-commit-assistant",
        "pr-assistant",
        "pr-shepherd",
        "quest",
    ]


def test_codex_wrappers_delegate_to_matching_project_skills() -> None:
    wrappers_root = _repo_root() / ".agents" / "skills"
    expected = {
        "celebrate",
        "git-commit-assistant",
        "pr-assistant",
        "pr-shepherd",
        "quest",
    }

    for skill_name in expected:
        wrapper_path = wrappers_root / skill_name / "SKILL.md"
        content = wrapper_path.read_text(encoding="utf-8")
        assert f"name: {skill_name}" in content
        assert f"Read and follow the instructions in `.skills/{skill_name}/SKILL.md`." in content


def test_codex_wrapper_surface_intentionally_excludes_gpt() -> None:
    wrapper_path = _repo_root() / ".agents" / "skills" / "gpt" / "SKILL.md"
    assert not wrapper_path.exists()
