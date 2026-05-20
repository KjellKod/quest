"""Verify the quest brief template includes a Router Classification section."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_quest_brief_template_has_router_classification_section() -> None:
    root = _repo_root()
    # The template path may vary; find it.
    candidates = list(root.glob("**/templates/quest_brief.md"))
    candidates = [p for p in candidates if ".quest" not in p.parts]
    assert candidates, "No quest_brief.md template found"
    template = candidates[0].read_text(encoding="utf-8")
    assert "Router Classification" in template or "router_classification" in template, (
        f"{candidates[0]} must include a Router Classification section so downstream agents "
        f"can find ui_work and ui_work_evidence"
    )


def test_quest_brief_template_documents_boolean_ui_work_contract() -> None:
    root = _repo_root()
    candidates = list(root.glob("**/templates/quest_brief.md"))
    candidates = [p for p in candidates if ".quest" not in p.parts]
    assert candidates, "No quest_brief.md template found"
    template = candidates[0].read_text(encoding="utf-8")

    assert "parsed JSON value is the boolean `true`" in template
    assert 'placeholder strings, and `"true"` string values are false' in template
