from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from quest_dashboard.loaders import (  # noqa: E402
    DashboardDataError,
    load_active_quests,
    load_completed_quests,
    load_dashboard_data,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_active_quests_reads_state_and_brief_fields(tmp_path: Path) -> None:
    state_path = tmp_path / ".quest" / "alpha" / "state.json"
    _write_state(
        state_path,
        {
            "quest_id": "alpha_2026-02-10__1111",
            "slug": "alpha",
            "phase": "building",
            "status": "in_progress",
            "updated_at": "2026-02-10T19:12:00Z",
        },
    )

    _write(
        tmp_path / ".quest" / "alpha" / "quest_brief.md",
        """# Quest Brief: Alpha Launch

## Original Prompt

Deliver the first alpha launch dashboard with clear status visibility.

### Requirements

- Must be fast.
""",
    )

    records = load_active_quests(tmp_path)

    assert len(records) == 1
    record = records[0]
    assert record.quest_id == "alpha_2026-02-10__1111"
    assert record.slug == "alpha"
    assert record.name == "Alpha Launch"
    assert record.phase == "Building"
    assert record.status == "In Progress"
    assert record.updated_at.isoformat() == "2026-02-10T19:12:00+00:00"
    assert record.elevator_pitch == "Deliver the first alpha launch dashboard with clear status visibility."


def test_load_active_quests_excludes_archive_state_files(tmp_path: Path) -> None:
    _write_state(
        tmp_path / ".quest" / "active" / "state.json",
        {
            "quest_id": "active_quest",
            "slug": "active-quest",
            "phase": "building",
            "status": "in_progress",
            "updated_at": "2026-02-10T10:00:00Z",
        },
    )
    _write(
        tmp_path / ".quest" / "active" / "quest_brief.md",
        "# Quest Brief: Active Quest\n\n## Original Prompt\n\nThis quest is active.\n",
    )

    _write_state(
        tmp_path / ".quest" / "archive" / "old" / "state.json",
        {
            "quest_id": "archived_quest",
            "slug": "archived-quest",
            "phase": "complete",
            "status": "done",
            "updated_at": "2026-01-01T00:00:00Z",
        },
    )
    _write(
        tmp_path / ".quest" / "archive" / "old" / "quest_brief.md",
        "# Quest Brief: Archived Quest\n\n## Original Prompt\n\nArchived quest text.\n",
    )

    records = load_active_quests(tmp_path)

    assert [record.quest_id for record in records] == ["active_quest"]


def test_load_active_quests_ignores_nested_state_files_outside_contract(tmp_path: Path) -> None:
    _write_state(
        tmp_path / ".quest" / "contract-match" / "state.json",
        {
            "quest_id": "contract_match",
            "slug": "contract-match",
            "phase": "building",
            "status": "in_progress",
            "updated_at": "2026-02-10T10:00:00Z",
        },
    )
    _write(
        tmp_path / ".quest" / "contract-match" / "quest_brief.md",
        "# Quest Brief: Contract Match\n\n## Original Prompt\n\nThis one should be discovered.\n",
    )

    _write_state(
        tmp_path / ".quest" / "contract-match" / "nested" / "state.json",
        {
            "quest_id": "nested_state",
            "slug": "nested-state",
            "phase": "review",
            "status": "in_progress",
            "updated_at": "2026-02-10T11:00:00Z",
        },
    )
    _write(
        tmp_path / ".quest" / "contract-match" / "nested" / "quest_brief.md",
        "# Quest Brief: Nested\n\n## Original Prompt\n\nThis should not be discovered.\n",
    )

    records = load_active_quests(tmp_path)

    assert [record.quest_id for record in records] == ["contract_match"]


def test_load_completed_quests_extracts_summary_and_completed_date_variants(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "quest-journal" / "first_2026-02-07.md",
        """# Quest Journal: First Quest

**Quest ID:** first_quest
**Completed:** 2026-02-07

## Summary

The first completed quest shipped a resilient parser.
""",
    )

    _write(
        tmp_path / "docs" / "quest-journal" / "second_2026-02-08.md",
        """# Quest Journal: Second Quest

**Quest ID**: second_quest
**Completed**: 2026-02-08

## Summary

Second quest focused on visual polish.
""",
    )

    _write(
        tmp_path / "docs" / "quest-journal" / "fallback_2026-02-09.md",
        """# Quest Journal: Fallback Date Quest

**Quest ID:** fallback_quest

## Summary

Fallback date should come from the filename.
""",
    )

    records = load_completed_quests(tmp_path)

    assert [record.quest_id for record in records] == [
        "fallback_quest",
        "second_quest",
        "first_quest",
    ]
    assert records[0].updated_on.isoformat() == "2026-02-09"
    assert records[1].updated_on.isoformat() == "2026-02-08"
    assert records[2].updated_on.isoformat() == "2026-02-07"
    assert records[2].elevator_pitch == "The first completed quest shipped a resilient parser."


def test_load_completed_quests_parses_status_and_defaults_to_completed(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "quest-journal" / "abandoned_2026-02-05.md",
        """# Quest Journal: Abandoned Quest

**Quest ID:** abandoned_quest
**Date:** 2026-02-05
**Status:** Abandoned (plan approved, never built)

## Summary

Abandoned quests still appear in the completed area.
""",
    )

    _write(
        tmp_path / "docs" / "quest-journal" / "default_2026-02-04.md",
        """# Quest Journal: Default Status Quest

**Quest ID:** default_quest
**Completed:** 2026-02-04

## Summary

Missing status should default to Completed.
""",
    )

    records = load_completed_quests(tmp_path)
    by_id = {record.quest_id: record for record in records}

    assert by_id["abandoned_quest"].status == "Abandoned (plan approved, never built)"
    assert by_id["default_quest"].status == "Completed"


def test_load_completed_quests_parses_backticked_quest_id_variant(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "quest-journal" / "backtick_2026-02-03.md",
        """# Quest Journal: Backtick Quest

**Quest ID:** `backtick_quest_2026-02-03__1001`
**Completed:** 2026-02-03

## Summary

Backtick quest id should be parsed without backticks.
""",
    )

    records = load_completed_quests(tmp_path)

    assert len(records) == 1
    assert records[0].quest_id == "backtick_quest_2026-02-03__1001"


def test_loaders_apply_deterministic_sorting_for_active_and_completed(tmp_path: Path) -> None:
    _write_state(
        tmp_path / ".quest" / "q-a" / "state.json",
        {
            "quest_id": "a_quest",
            "slug": "a-quest",
            "phase": "review",
            "status": "in_progress",
            "updated_at": "2026-02-10T10:00:00Z",
        },
    )
    _write(tmp_path / ".quest" / "q-a" / "quest_brief.md", "# Quest Brief: A\n")

    _write_state(
        tmp_path / ".quest" / "q-b" / "state.json",
        {
            "quest_id": "b_quest",
            "slug": "b-quest",
            "phase": "review",
            "status": "in_progress",
            "updated_at": "2026-02-10T10:00:00Z",
        },
    )
    _write(tmp_path / ".quest" / "q-b" / "quest_brief.md", "# Quest Brief: B\n")

    _write_state(
        tmp_path / ".quest" / "q-c" / "state.json",
        {
            "quest_id": "c_quest",
            "slug": "c-quest",
            "phase": "review",
            "status": "in_progress",
            "updated_at": "2026-02-10T11:00:00Z",
        },
    )
    _write(tmp_path / ".quest" / "q-c" / "quest_brief.md", "# Quest Brief: C\n")

    _write(
        tmp_path / "docs" / "quest-journal" / "z_2026-02-04.md",
        "# Quest Journal: Z\n\n**Quest ID:** z_quest\n**Completed:** 2026-02-04\n\n## Summary\n\nZ.\n",
    )
    _write(
        tmp_path / "docs" / "quest-journal" / "a_2026-02-05.md",
        "# Quest Journal: A\n\n**Quest ID:** a_quest\n**Completed:** 2026-02-05\n\n## Summary\n\nA.\n",
    )
    _write(
        tmp_path / "docs" / "quest-journal" / "b_2026-02-05.md",
        "# Quest Journal: B\n\n**Quest ID:** b_quest\n**Completed:** 2026-02-05\n\n## Summary\n\nB.\n",
    )

    active = load_active_quests(tmp_path)
    completed = load_completed_quests(tmp_path)

    assert [record.quest_id for record in active] == ["c_quest", "a_quest", "b_quest"]
    assert [record.quest_id for record in completed] == ["a_quest", "b_quest", "z_quest"]


def test_build_fails_with_actionable_error_on_malformed_state_json(tmp_path: Path) -> None:
    state_path = tmp_path / ".quest" / "bad" / "state.json"
    _write(state_path, '{"quest_id": "bad", "updated_at": "2026-02-10T00:00:00Z", "token": "super-secret"')

    script_path = REPO_ROOT / "scripts" / "build_quest_dashboard.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--repo-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Build failed:" in result.stderr
    assert str(state_path) in result.stderr
    assert "Malformed JSON" in result.stderr
    assert "Traceback" not in result.stderr
    assert "super-secret" not in result.stderr


def test_build_handles_missing_active_quest_brief_with_actionable_output(tmp_path: Path) -> None:
    _write_state(
        tmp_path / ".quest" / "missing-brief" / "state.json",
        {
            "quest_id": "quest_without_brief",
            "slug": "fallback-slug",
            "phase": "building",
            "status": "in_progress",
            "updated_at": "2026-02-10T10:00:00Z",
        },
    )

    script_path = REPO_ROOT / "scripts" / "build_quest_dashboard.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--repo-root",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    output_path = tmp_path / "docs" / "dashboard" / "index.html"

    assert result.returncode == 0
    assert output_path.exists()
    assert "Warning: Missing quest brief" in result.stderr
    assert ".quest/missing-brief/quest_brief.md" in result.stderr
    assert str(tmp_path) not in result.stderr
    assert "Traceback" not in result.stderr

    html = output_path.read_text(encoding="utf-8")
    assert "fallback-slug" in html
    assert "Quest brief unavailable." in html
    assert str(tmp_path) not in html


def test_load_active_quests_raises_on_invalid_timestamp(tmp_path: Path) -> None:
    _write_state(
        tmp_path / ".quest" / "bad-ts" / "state.json",
        {
            "quest_id": "bad_ts",
            "slug": "bad-ts",
            "phase": "building",
            "status": "in_progress",
            "updated_at": "not-a-time",
        },
    )

    with pytest.raises(DashboardDataError) as exc_info:
        load_active_quests(tmp_path)

    assert "Invalid updated_at timestamp" in str(exc_info.value)


def test_load_dashboard_data_includes_warnings_for_missing_briefs(tmp_path: Path) -> None:
    _write_state(
        tmp_path / ".quest" / "quest-a" / "state.json",
        {
            "quest_id": "quest_a",
            "slug": "quest-a",
            "phase": "building",
            "status": "in_progress",
            "updated_at": "2026-02-10T12:00:00Z",
        },
    )

    data = load_dashboard_data(tmp_path)

    assert len(data.active_quests) == 1
    assert data.active_quests[0].name == "quest-a"
    assert any("Missing quest brief" in warning for warning in data.warnings)
    assert any(".quest/quest-a/quest_brief.md" in warning for warning in data.warnings)
    assert all(str(tmp_path) not in warning for warning in data.warnings)
