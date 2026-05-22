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
    forbidden_dependencies = [
        ".quest/",
        "quest_state.py",
        ".skills/quest",
        "planner agent",
        "builder agent",
        "reviewer agent",
        "requires planner",
        "requires builder",
        "requires reviewer",
    ]
    lowered = skill.lower()
    for token in forbidden_dependencies:
        assert token not in lowered


def test_sharpen_grounding_default_caps_5_reads_3_searches() -> None:
    skill = _read(".skills/sharpen/SKILL.md").lower()

    assert "5 targeted reads" in skill
    assert "3 targeted searches" in skill


def test_sharpen_grounding_anchor_extraction_and_no_local_surface_fallback() -> None:
    skill = _read(".skills/sharpen/SKILL.md").lower()

    assert "extract anchors" in skill
    assert "paths, commands, scripts, tests, modules, acceptance criteria" in skill
    assert "if no repo/local surface exists" in skill
    assert "ground on artifact-only evidence" in skill


def test_sharpen_grounding_over_50_hits_allows_partial_with_uncertainty() -> None:
    skill = _read(".skills/sharpen/SKILL.md").lower()

    assert "more than 50 hits" in skill
    assert "accept partial grounding" in skill
    assert "disclose that uncertainty" in skill


def test_sharpen_grounding_requires_grounded_on_block_when_local_facts_matter() -> None:
    skill = _read(".skills/sharpen/SKILL.md")

    assert "Per-question grounding." in skill
    assert "Grounded on:" in skill


def test_sharpen_take_a_position_cites_grounding_facts() -> None:
    skill = _read(".skills/sharpen/SKILL.md").lower()

    assert "when local facts support that recommendation, cite the grounding facts directly" in skill


def test_sharpen_contradiction_handling_q1_template_and_resolved_path() -> None:
    skill = _read(".skills/sharpen/SKILL.md")

    assert "The plan says X. I found Y in path:line. Which is correct?" in skill
    assert "If a contradiction is fully resolved by local evidence, log it under `Resolved`" in skill


def test_sharpen_includes_generic_portable_smoke_runner_before_after_example() -> None:
    skill = _read(".skills/sharpen/SKILL.md").lower()

    assert "example: grounding smoke runner (portable)" in skill
    assert "before (ungrounded):" in skill
    assert "after (grounded):" in skill


def test_sharpen_interview_shape_preserved_one_question_cap12_progress_and_exit_summary() -> None:
    skill = _read(".skills/sharpen/SKILL.md")

    assert "One at a time." in skill
    assert "Hard cap at 12." in skill
    assert "Footer every question" in skill
    assert "Resolved" in skill
    assert "Open" in skill
    assert "Next" in skill
    assert "recommended answer" in skill.lower()


def test_sharpen_portability_and_role_drift_guardrails() -> None:
    skill = _read(".skills/sharpen/SKILL.md").lower()

    assert "adversarial interview" in skill
    assert "implementation planning deliverables" in skill
    assert "pr review findings" in skill
    assert "primary output" not in skill or "instead of adversarial interview questions" in skill


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
