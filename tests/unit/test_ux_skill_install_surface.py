"""Regression tests for the ux-review / ux-context install surface."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_ux_context_canonical_skill_exists() -> None:
    root = _repo_root()
    assert (root / ".skills" / "ux-context" / "SKILL.md").exists()
    assert (root / ".skills" / "ux-context" / "resources" / "ux-guidebook.md").exists()
    assert (
        root / ".skills" / "ux-context" / "resources" / "ux-stress-test.md"
    ).exists()


def test_ux_review_canonical_and_wrappers_exist() -> None:
    root = _repo_root()
    assert (root / ".skills" / "ux-review" / "SKILL.md").exists()
    assert (root / ".claude" / "skills" / "ux-review" / "SKILL.md").exists()
    assert (root / ".agents" / "skills" / "ux-review" / "SKILL.md").exists()


def test_ux_review_wrappers_delegate_to_canonical() -> None:
    root = _repo_root()
    for mirror in (".claude/skills/ux-review", ".agents/skills/ux-review"):
        wrapper_text = (root / mirror / "SKILL.md").read_text(encoding="utf-8")
        assert (
            "Read and follow the instructions in `.skills/ux-review/SKILL.md`."
            in wrapper_text
        )
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


def test_ux_context_uses_progressive_resource_loading() -> None:
    root = _repo_root()
    skill = (root / ".skills" / "ux-context" / "SKILL.md").read_text(encoding="utf-8")
    assert "Do not read the whole guidebook by default" in skill
    assert "Find your row in the table and read those sections only" in skill
    assert "Read `resources/ux-guidebook.md` in full" not in skill
    for required_role in (
        "Planner",
        "Builder",
        "Fixer",
        "Plan-reviewer",
        "Code-reviewer",
    ):
        assert required_role in skill, f"role {required_role} missing from Step 1 table"


def test_ux_guidebook_stays_portable() -> None:
    root = _repo_root()
    guidebook = (
        root / ".skills" / "ux-context" / "resources" / "ux-guidebook.md"
    ).read_text(encoding="utf-8")

    assert "## 6. Case studies" not in guidebook
    for repo_local_term in (
        "sketch2md",
        "shadcn",
        "zustand",
        "sonner",
        "PersonaLogo",
        "CatLogo",
    ):
        assert repo_local_term not in guidebook


def test_ux_guidebook_has_no_stale_field_or_principle_counts() -> None:
    root = _repo_root()
    ux_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            root / ".skills" / "ux-context" / "SKILL.md",
            root / ".skills" / "ux-context" / "resources" / "ux-guidebook.md",
            root / ".skills" / "ux-review" / "SKILL.md",
            root / ".skills" / "sharpen" / "SKILL.md",
        )
    )

    assert "five fields" not in ux_text
    assert "12 principles" not in ux_text


def test_ux_review_has_visual_evidence_path_without_quest_mutation() -> None:
    root = _repo_root()
    skill = (root / ".skills" / "ux-review" / "SKILL.md").read_text(encoding="utf-8")
    assert "Visual evidence path" in skill
    assert "Capture screenshots at `375px`, `768px`, `1280px`, and `1920px`" in skill
    assert "Quest-pipeline invocations are review-only" in skill


def test_plan_review_uses_ux_intent_pass_not_rendered_stress_test() -> None:
    root = _repo_root()
    files = [
        root / ".skills" / "quest" / "agents" / "plan-reviewer.md",
        root / ".claude" / "agents" / "plan-reviewer.md",
        root / ".opencode" / "agents" / "plan-reviewer.md",
        root / ".skills" / "ux-review" / "SKILL.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "plan-phase UX intent pass" in combined
    assert "stress test against the plan" not in combined


def test_quest_skill_discloses_ui_work_routing_to_user() -> None:
    root = _repo_root()
    skill = (root / ".skills" / "quest" / "SKILL.md").read_text(encoding="utf-8")

    assert "ui_work, ui_work_evidence" in skill
    assert "UI work: yes" in skill
    assert "UI work: no" in skill


def test_ux_defaults_contract_uses_canonical_order_and_state_sentence_limit() -> None:
    root = _repo_root()
    ux_context = (root / ".skills" / "ux-context" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    ux_guidebook = (
        root / ".skills" / "ux-context" / "resources" / "ux-guidebook.md"
    ).read_text(encoding="utf-8")
    ux_review = (root / ".skills" / "ux-review" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    canonical_order = "mobile, gray ramp, density, ratio, accent, destructive actions"
    assert canonical_order in ux_context
    assert canonical_order in ux_guidebook
    assert canonical_order in ux_review
    assert (
        "exactly one sentence each for empty, loading, and error states" in ux_context
    )
    assert "exactly one sentence each for empty/loading/error states" in ux_guidebook
    assert "exactly one sentence each" in ux_review
