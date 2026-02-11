from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from quest_dashboard.models import (  # noqa: E402
    ActiveQuestRecord,
    CompletedQuestRecord,
    DashboardData,
)
from quest_dashboard.render import render_dashboard  # noqa: E402


def test_render_dashboard_contains_required_fields_for_each_card_type(tmp_path: Path) -> None:
    active = ActiveQuestRecord(
        quest_id="active_quest_1",
        slug="active-quest-1",
        name="Active Quest One",
        status="In Progress",
        phase="Building",
        updated_at=datetime(2026, 2, 10, 19, 12, tzinfo=timezone.utc),
        elevator_pitch="Create a polished dashboard for stakeholders.",
        state_path=tmp_path / ".quest" / "active_quest_1" / "state.json",
        brief_path=tmp_path / ".quest" / "active_quest_1" / "quest_brief.md",
    )

    completed = CompletedQuestRecord(
        quest_id="completed_quest_1",
        name="Completed Quest One",
        status="Completed",
        updated_on=date(2026, 2, 8),
        elevator_pitch="Delivered the first static dashboard iteration.",
        journal_path=Path("docs") / "quest-journal" / "completed_quest_1_2026-02-08.md",
        source_path=tmp_path / "docs" / "quest-journal" / "completed_quest_1_2026-02-08.md",
    )

    data = DashboardData(
        active_quests=[active],
        completed_quests=[completed],
        warnings=[],
        generated_at=datetime(2026, 2, 10, 20, 0, tzinfo=timezone.utc),
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    html = render_dashboard(data=data, output_path=output_path, repo_root=tmp_path)

    assert "Quest Dashboard" in html
    assert "Active Quests" in html
    assert "Completed Quests" in html

    assert "Active Quest One" in html
    assert "In Progress" in html
    assert "Phase: Building" in html
    assert "Last Updated: 2026-02-10 19:12 UTC" in html
    assert "Create a polished dashboard for stakeholders." in html

    assert "Completed Quest One" in html
    assert "Completed" in html
    assert "Last Updated: 2026-02-08" in html
    assert "Delivered the first static dashboard iteration." in html
    assert 'href="../quest-journal/completed_quest_1_2026-02-08.md"' in html


def test_render_dashboard_applies_abandoned_badge_and_warning_panel(tmp_path: Path) -> None:
    completed = CompletedQuestRecord(
        quest_id="abandoned_quest",
        name="Abandoned Quest",
        status="Abandoned (plan approved, never built)",
        updated_on=date(2026, 2, 5),
        elevator_pitch="Quest was paused after planning.",
        journal_path=Path("docs") / "quest-journal" / "abandoned_quest_2026-02-05.md",
        source_path=tmp_path / "docs" / "quest-journal" / "abandoned_quest_2026-02-05.md",
    )

    data = DashboardData(
        active_quests=[],
        completed_quests=[completed],
        warnings=["Missing quest brief for 'q1' at .quest/q1/quest_brief.md."],
        generated_at=datetime(2026, 2, 10, 20, 0, tzinfo=timezone.utc),
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"
    html = render_dashboard(data=data, output_path=output_path, repo_root=tmp_path)

    assert "badge--abandoned" in html
    assert "Abandoned (plan approved, never built)" in html
    assert "Build Warnings" in html
    assert "Missing quest brief" in html
    assert "/tmp/path" not in html
    assert "@media (max-width: 780px)" in html
