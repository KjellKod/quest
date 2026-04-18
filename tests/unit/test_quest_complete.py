"""Unit tests for quest_complete journal rendering."""

from datetime import date
import json
from pathlib import Path

from quest_complete import build_journal_entry
from quest_celebrate.quest_data import QuestData


def test_generate_journal_entry_prefers_full_original_prompt():
    data = QuestData(
        quest_id="prompt-fix_2026-04-15__1200",
        slug="prompt-fix",
        name="Prompt Fix",
        quest_mode="workflow",
        brief_summary="Short summary",
        brief_body="> Full original prompt line one.\n>\n> Full original prompt line two.",
        brief_source="original_prompt",
        plan_summary="Shipped the fix cleanly.",
        quality_tier="Gold",
    )

    entry = build_journal_entry(
        data,
        date(2026, 4, 15),
        Path("docs/quest-journal/prompt-fix_2026-04-15.md"),
    )

    assert "## Quest Brief" in entry
    assert "Full original prompt line one." in entry
    assert "Full original prompt line two." in entry
    assert "Full original prompt was not recorded" not in entry
    assert "- Outcome: Shipped the fix cleanly." in entry


def test_generate_journal_entry_avoids_problem_statement_as_outcome():
    data = QuestData(
        quest_id="problem-first_2026-04-15__1200",
        slug="problem-first",
        name="Problem First",
        brief_summary="Use the brief summary instead.",
        brief_body="Use the brief summary instead.",
        brief_source="brief_section",
        plan_summary="**Problem:** This summary describes the bug, not the shipped result.",
    )

    entry = build_journal_entry(
        data,
        date(2026, 4, 15),
        Path("docs/quest-journal/problem-first_2026-04-15.md"),
    )

    assert "- Outcome: Use the brief summary instead." in entry


def test_generate_journal_entry_avoids_old_problem_statement_as_outcome():
    data = QuestData(
        quest_id="old-problem-style_2026-04-15__1200",
        slug="old-problem-style",
        name="Old Problem Style",
        brief_summary="Use the brief summary instead.",
        brief_body="Use the brief summary instead.",
        brief_source="brief_section",
        plan_summary="**Problem**: This summary describes the bug, not the shipped result.",
    )

    entry = build_journal_entry(
        data,
        date(2026, 4, 15),
        Path("docs/quest-journal/old-problem-style_2026-04-15.md"),
    )

    assert "- Outcome: Use the brief summary instead." in entry


def test_generate_journal_entry_avoids_problem_statement_without_brief_summary():
    data = QuestData(
        quest_id="problem-no-brief_2026-04-15__1200",
        slug="problem-no-brief",
        name="Problem No Brief",
        plan_summary="**Problem:** This summary describes the bug, not the shipped result.",
    )

    entry = build_journal_entry(
        data,
        date(2026, 4, 15),
        Path("docs/quest-journal/problem-no-brief_2026-04-15.md"),
    )

    assert "- Outcome: Completed successfully." in entry


def test_generate_journal_entry_collapses_multiline_plan_summary_in_outcome():
    data = QuestData(
        quest_id="multiline-outcome_2026-04-15__1200",
        slug="multiline-outcome",
        name="Multiline Outcome",
        brief_summary="Fallback summary",
        brief_body="Fallback summary",
        brief_source="brief_section",
        plan_summary="> Primary shipped result\n>\n> with extra wrapped detail",
    )

    entry = build_journal_entry(
        data,
        date(2026, 4, 15),
        Path("docs/quest-journal/multiline-outcome_2026-04-15.md"),
    )

    assert "- Outcome: Primary shipped result with extra wrapped detail" in entry
    assert "- Outcome: >" not in entry


def test_generate_journal_entry_adds_celebration_section_when_replayable():
    data = QuestData(
        quest_id="celebrate-me_2026-04-15__1200",
        slug="celebrate-me",
        name="Celebrate Me",
        brief_summary="Replay this",
        brief_body="Replay this",
        brief_source="brief_section",
        quality_tier="Platinum",
    )

    entry = build_journal_entry(
        data,
        date(2026, 4, 15),
        Path("docs/quest-journal/celebrate-me_2026-04-15.md"),
    )

    assert "## Celebration" in entry
    assert "[Jump to Celebration Data](#celebration-data)" in entry
    assert "`/celebrate docs/quest-journal/celebrate-me_2026-04-15.md`" in entry


def test_generate_journal_entry_falls_back_to_best_available_brief_context():
    data = QuestData(
        quest_id="legacy-brief_2026-04-15__1200",
        slug="legacy-brief",
        name="Legacy Brief",
        brief_summary="Best available summary",
        brief_body="Legacy brief details from the first recorded section.",
        brief_source="brief_section",
    )

    entry = build_journal_entry(
        data,
        date(2026, 4, 15),
        Path("docs/quest-journal/legacy-brief_2026-04-15.md"),
    )

    assert "Legacy brief details from the first recorded section." in entry
    assert "Full original prompt was not recorded for this quest." in entry


def test_generate_journal_entry_includes_carryover_sections_and_payload():
    data = QuestData(
        quest_id="carryover_2026-04-16__1200",
        slug="carryover",
        name="Carryover",
    )
    data.inherited_findings_used.count = 2
    data.inherited_findings_used.summaries = [
        "Deferred auth cleanup was pulled into scope.",
        "Legacy validation gap was revisited.",
    ]
    data.findings_left_for_future_quests.count = 1
    data.findings_left_for_future_quests.summaries = [
        "Follow up on dashboard backlog rendering.",
    ]

    entry = build_journal_entry(
        data,
        date(2026, 4, 16),
        Path("docs/quest-journal/carryover_2026-04-16.md"),
    )

    assert "## Inherited Findings Used" in entry
    assert "- Count: **2**" in entry
    assert "Deferred auth cleanup was pulled into scope." in entry
    assert "## Findings Left For Future Quests" in entry
    assert "Follow up on dashboard backlog rendering." in entry

    start = entry.index("```json\n") + len("```json\n")
    end = entry.index("\n```", start)
    payload = json.loads(entry[start:end])
    assert payload["inherited_findings_used"]["count"] == 2
    assert payload["findings_left_for_future_quests"]["count"] == 1


def test_generate_journal_entry_includes_empty_carryover_status_when_absent():
    data = QuestData(
        quest_id="carryover-empty_2026-04-16__1200",
        slug="carryover-empty",
        name="Carryover Empty",
    )

    entry = build_journal_entry(
        data,
        date(2026, 4, 16),
        Path("docs/quest-journal/carryover-empty_2026-04-16.md"),
    )

    assert "## Carry-Over Findings" in entry
    assert "nothing was inherited from earlier quests" in entry
    assert "## Inherited Findings Used" not in entry
