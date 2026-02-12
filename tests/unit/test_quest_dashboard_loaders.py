"""Unit tests for quest_dashboard.loaders module."""

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from quest_dashboard.loaders import (
    _extract_iterations,
    _extract_metadata,
    _extract_summary_pitch,
    _normalize_status,
    _parse_active_quest,
    _parse_journal_entry,
    load_active_quests,
    load_dashboard_data,
    load_journal_entries,
)


def test_load_journal_entry_extracts_all_fields(tmp_path):
    """Test that journal entry parsing extracts all fields correctly."""
    journal_dir = tmp_path / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)

    journal_content = """# Quest Journal: Test Quest

**Quest ID:** test-quest-001
**Slug:** test-quest
**Status:** Completed
**Completed:** 2026-02-10
**PR:** #24
**Plan iterations:** 2
**Fix iterations:** 1

## Summary

This is the elevator pitch from the summary section. It should be extracted correctly.

## Details

More content here.
"""

    journal_path = journal_dir / "test-quest.md"
    journal_path.write_text(journal_content, encoding="utf-8")

    entry = _parse_journal_entry(journal_path, tmp_path)

    assert entry.quest_id == "test-quest-001"
    assert entry.slug == "test-quest"
    assert entry.title == "Test Quest"
    assert entry.status == "Completed"
    assert entry.completed_date == date(2026, 2, 10)
    assert entry.elevator_pitch == "This is the elevator pitch from the summary section. It should be extracted correctly."
    assert entry.pr_number == 24
    assert entry.plan_iterations == 2
    assert entry.fix_iterations == 1


def test_journal_elevator_pitch_from_summary_section(tmp_path):
    """Test that elevator pitch is extracted from Summary section, not title."""
    journal_dir = tmp_path / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)

    journal_content = """# Quest Journal: Test Quest

This is the first paragraph after the title. It should not be used.

## Summary

This is the correct elevator pitch from the Summary section.

## Other Section

More content.
"""

    journal_path = journal_dir / "test.md"
    journal_path.write_text(journal_content, encoding="utf-8")

    entry = _parse_journal_entry(journal_path, tmp_path)

    assert entry.elevator_pitch == "This is the correct elevator pitch from the Summary section."
    assert "first paragraph after the title" not in entry.elevator_pitch


def test_journal_entry_detects_abandoned_status(tmp_path):
    """Test that abandoned status is correctly detected and normalized."""
    journal_dir = tmp_path / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)

    # Test with prefix matching (BUILDER GUIDANCE NOTE #3)
    journal_content = """# Quest Journal: Abandoned Quest

**Status:** Abandoned (plan approved, never built)

## Summary

This quest was abandoned.
"""

    journal_path = journal_dir / "abandoned.md"
    journal_path.write_text(journal_content, encoding="utf-8")

    entry = _parse_journal_entry(journal_path, tmp_path)

    assert entry.status == "Abandoned"


def test_status_normalization_prefix_matching():
    """Test that status normalization uses prefix matching."""
    # BUILDER GUIDANCE NOTE #3
    assert _normalize_status("Completed") == "Completed"
    assert _normalize_status("Complete") == "Completed"  # Without 'd'
    assert _normalize_status("Finished") == "Completed"
    assert _normalize_status("Abandoned") == "Abandoned"
    assert _normalize_status("Abandoned (plan approved, never built)") == "Abandoned"
    assert _normalize_status("") == "Completed"  # Default


def test_iterations_extraction_bold_format():
    """Test iteration extraction from bold metadata format."""
    content = """
**Plan iterations:** 3
**Fix iterations:** 2
"""
    assert _extract_iterations(content, "plan") == 3
    assert _extract_iterations(content, "fix") == 2


def test_iterations_extraction_list_format():
    """Test iteration extraction from list-item format."""
    # BUILDER GUIDANCE NOTE #2: Handle list-item format
    content = """
- Plan iterations: 1
- Fix iterations: 0
"""
    assert _extract_iterations(content, "plan") == 1
    assert _extract_iterations(content, "fix") == 0


def test_active_quest_skips_archive(tmp_path):
    """Test that archived quests are excluded from active quest results."""
    quest_dir = tmp_path / ".quest"
    archive_dir = quest_dir / "archive" / "old-quest"
    archive_dir.mkdir(parents=True)

    # Create state.json in archive
    state = {
        "quest_id": "archived-quest",
        "slug": "archived-quest",
        "status": "complete",
        "phase": "done",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    (archive_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    # Create quest_brief.md in archive
    (archive_dir / "quest_brief.md").write_text("# Quest Brief: Archived", encoding="utf-8")

    quests, warnings = load_active_quests(quest_dir)

    assert len(quests) == 0  # Archive should be skipped
    assert len(warnings) == 0


def test_active_quest_pitch_from_original_prompt(tmp_path):
    """Test that active quest elevator pitch comes from Original Prompt section."""
    quest_dir = tmp_path / ".quest" / "test-quest"
    quest_dir.mkdir(parents=True)

    state = {
        "quest_id": "test-quest",
        "slug": "test-quest",
        "status": "in_progress",
        "phase": "building",
        "updated_at": "2026-02-12T10:00:00Z",
    }
    (quest_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")

    brief_content = """# Quest Brief: Test Quest

## User Input (Original Prompt)

This is the elevator pitch from the original prompt section.

## Requirements

Some requirements here.
"""
    (quest_dir / "quest_brief.md").write_text(brief_content, encoding="utf-8")

    quest, quest_warnings = _parse_active_quest(quest_dir / "state.json")

    assert quest.elevator_pitch == "This is the elevator pitch from the original prompt section."
    assert len(quest_warnings) == 0


def test_malformed_state_json_produces_warning(tmp_path):
    """Test that malformed state.json produces a warning without crashing."""
    quest_dir = tmp_path / ".quest" / "bad-quest"
    quest_dir.mkdir(parents=True)

    # Write invalid JSON
    (quest_dir / "state.json").write_text("{ invalid json", encoding="utf-8")

    quests, warnings = load_active_quests(tmp_path / ".quest")

    assert len(quests) == 0
    assert len(warnings) == 1
    assert "bad-quest" in warnings[0].lower() or "state.json" in warnings[0].lower()


def test_missing_quest_brief_produces_warning(tmp_path):
    """Test that missing quest_brief.md produces a warning without crashing (AC #10)."""
    quest_dir = tmp_path / ".quest" / "no-brief-quest"
    quest_dir.mkdir(parents=True)

    state = {
        "quest_id": "no-brief-quest",
        "slug": "no-brief-quest",
        "status": "in_progress",
        "phase": "building",
        "updated_at": "2026-02-12T10:00:00Z",
    }
    (quest_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    # Intentionally NOT creating quest_brief.md

    quests, warnings = load_active_quests(tmp_path / ".quest")

    assert len(quests) == 1
    assert quests[0].quest_id == "no-brief-quest"
    assert quests[0].title == "no-brief-quest"  # Falls back to slug
    assert quests[0].elevator_pitch == ""
    assert len(warnings) == 1
    assert "quest_brief.md" in warnings[0].lower() or "missing" in warnings[0].lower()


def test_active_quests_sorted_by_phase_then_date(tmp_path):
    """Test that active quests are sorted by phase order, then by date."""
    quest_dir = tmp_path / ".quest"

    # Create three quests with different phases
    quests_data = [
        ("building-new", "building", "2026-02-12T12:00:00Z"),
        ("building-old", "building", "2026-02-10T10:00:00Z"),
        ("plan-quest", "plan", "2026-02-13T15:00:00Z"),
    ]

    for slug, phase, updated_at in quests_data:
        quest_path = quest_dir / slug
        quest_path.mkdir(parents=True)

        state = {
            "quest_id": slug,
            "slug": slug,
            "status": "in_progress",
            "phase": phase,
            "updated_at": updated_at,
        }
        (quest_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
        (quest_path / "quest_brief.md").write_text(f"# Quest Brief: {slug}", encoding="utf-8")

    quests, warnings = load_active_quests(quest_dir)

    assert len(quests) == 3
    assert len(warnings) == 0

    # Building should come before plan (lower phase order)
    # Within building, newer should come first
    assert quests[0].slug == "building-new"
    assert quests[1].slug == "building-old"
    assert quests[2].slug == "plan-quest"


def test_load_journal_entries_skips_readme(tmp_path):
    """Test that README.md in journal directory is skipped."""
    # BUILDER GUIDANCE NOTE #1: Skip README.md
    journal_dir = tmp_path / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)

    # Create README.md
    (journal_dir / "README.md").write_text("# Quest Journal Index", encoding="utf-8")

    # Create valid journal
    valid_journal = """# Quest Journal: Valid Quest

## Summary

This is a valid quest.
"""
    (journal_dir / "valid-quest.md").write_text(valid_journal, encoding="utf-8")

    entries, warnings = load_journal_entries(journal_dir, tmp_path)

    # Should have only 1 entry (README.md skipped)
    assert len(entries) == 1
    assert entries[0].title == "Valid Quest"
    assert len(warnings) == 0


def test_quest_id_backtick_stripping(tmp_path):
    """Test that backticks are stripped from Quest ID values.

    Arbiter guidance: some journals wrap Quest ID in backticks.
    """
    journal_dir = tmp_path / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)

    journal_content = """# Quest Journal: Backtick Quest

**Quest ID:** `backtick-quest_2026-02-04__1841`

## Summary

A quest with backtick-wrapped quest ID.
"""

    journal_path = journal_dir / "backtick-quest.md"
    journal_path.write_text(journal_content, encoding="utf-8")

    entry = _parse_journal_entry(journal_path, tmp_path)

    assert entry.quest_id == "backtick-quest_2026-02-04__1841"
    assert "`" not in entry.quest_id


def test_colon_outside_bold_metadata(tmp_path):
    """Test that metadata with colon outside bold markers is extracted.

    Arbiter guidance: handle **Key**: value (colon outside **).
    """
    content = """**Completed**: 2026-02-04
**Quest ID**: ci-validation
"""
    # Colon-outside-bold format
    assert _extract_metadata(content, "completed") == "2026-02-04"
    assert _extract_metadata(content, "quest id") == "ci-validation"


def test_dedup_active_quests_against_journal_entries(tmp_path):
    """Test that active quests matching journal entries are excluded.

    Arbiter guidance: prevents a quest from appearing in both
    Finished/Abandoned and In Progress sections.
    """
    # Create journal directory with one completed quest
    journal_dir = tmp_path / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)

    journal_content = """# Quest Journal: Completed Quest

**Quest ID:** completed-quest-001

## Summary

This quest is already completed.
"""
    (journal_dir / "completed-quest.md").write_text(journal_content, encoding="utf-8")

    # Create .quest directory with an active quest that has the same quest_id
    quest_dir = tmp_path / ".quest" / "completed-quest"
    quest_dir.mkdir(parents=True)

    state = {
        "quest_id": "completed-quest-001",
        "slug": "completed-quest",
        "status": "in_progress",
        "phase": "building",
        "updated_at": "2026-02-12T10:00:00Z",
    }
    (quest_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (quest_dir / "quest_brief.md").write_text(
        "# Quest Brief: Completed Quest\n\n## User Input (Original Prompt)\n\nTest.",
        encoding="utf-8",
    )

    # Also create a genuinely active quest
    active_dir = tmp_path / ".quest" / "new-quest"
    active_dir.mkdir(parents=True)
    active_state = {
        "quest_id": "new-quest-002",
        "slug": "new-quest",
        "status": "in_progress",
        "phase": "plan",
        "updated_at": "2026-02-12T12:00:00Z",
    }
    (active_dir / "state.json").write_text(json.dumps(active_state), encoding="utf-8")
    (active_dir / "quest_brief.md").write_text(
        "# Quest Brief: New Quest\n\n## User Input (Original Prompt)\n\nNew quest.",
        encoding="utf-8",
    )

    data = load_dashboard_data(tmp_path, github_url="https://github.com/test/repo")

    # The completed quest should appear in finished, NOT in active
    assert len(data.finished_quests) == 1
    assert data.finished_quests[0].quest_id == "completed-quest-001"

    # Only the genuinely new quest should be in active
    assert len(data.active_quests) == 1
    assert data.active_quests[0].quest_id == "new-quest-002"
