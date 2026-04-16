"""Unit tests for archive-backed quest journal backfill."""

from __future__ import annotations

import json
from pathlib import Path

from backfill_quest_journal import backfill_journal_entries


def _write_archive_quest(
    archive_dir: Path,
    quest_id: str,
    slug: str,
    prompt_section: str = "## User Input (Original Prompt)",
) -> None:
    archive_dir.mkdir(parents=True)
    (archive_dir / "state.json").write_text(
        json.dumps(
            {
                "quest_id": quest_id,
                "slug": slug,
                "status": "complete",
                "phase": "complete",
                "quest_mode": "solo",
                "plan_iteration": 1,
                "fix_iteration": 0,
                "created_at": "2026-04-13T17:01:47Z",
                "updated_at": "2026-04-13T17:25:04Z",
            }
        ),
        encoding="utf-8",
    )
    (archive_dir / "quest_brief.md").write_text(
        "\n".join(
            [
                "# Quest Brief: Prompt Surface / Instruction Architecture Consolidation",
                "",
                prompt_section,
                "",
                "> Full original prompt recovered from the archive.",
                "",
                "## Router Classification",
                "",
                "```json",
                '{"route": "solo"}',
                "```",
            ]
        ),
        encoding="utf-8",
    )
    phase_01 = archive_dir / "phase_01_plan"
    phase_01.mkdir()
    (phase_01 / "plan.md").write_text(
        "## Overview\n\nShipped a clearer proposal consolidation with preserved guardrails.\n",
        encoding="utf-8",
    )


def _write_journal(journal_path: Path, quest_id: str) -> None:
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(
        "\n".join(
            [
                "# Quest Journal: Prompt Surface / Instruction Architecture Consolidation",
                "",
                f"- Quest ID: `{quest_id}`",
                "- Completed: 2026-04-13",
                "- Mode: solo",
                "- Quality: Platinum",
                "- Outcome: Old truncated quote",
                "",
                "## What Shipped",
                "",
                "Old body.",
                "",
                "## Celebration Data",
                "",
                "<!-- celebration-data-start -->",
                "```json",
                '{"quest_mode": "solo", "quality": {"tier": "Platinum", "grade": "P"}, "agents": [], "achievements": [], "metrics": [], "test_count": null, "tests_added": null, "files_changed": 1}',
                "```",
                "<!-- celebration-data-end -->",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_journal_with_old_brief_heading(journal_path: Path, quest_id: str) -> None:
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(
        "\n".join(
            [
                "# Quest Journal: Legacy Brief",
                "",
                f"- Quest ID: `{quest_id}`",
                "- Completed: 2026-04-13",
                "- Outcome: Preserve the rest of this document.",
                "",
                "## What Shipped",
                "",
                "Keep this handcrafted section.",
                "",
                "## This is where it all began...",
                "",
                "> Old truncated quote.",
                "",
                "## Iterations",
                "",
                "- Plan iterations: 1",
                "- Fix iterations: 0",
                "",
                "## Next Steps",
                "",
                "- Keep this section too.",
                "",
                "## Celebration Data",
                "",
                "<!-- celebration-data-start -->",
                "```json",
                '{"quest_mode": "solo", "quality": {"tier": "Platinum", "grade": "P"}, "agents": [], "achievements": [], "metrics": [], "test_count": null, "tests_added": null, "files_changed": 1}',
                "```",
                "<!-- celebration-data-end -->",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_journal_with_richer_existing_brief(journal_path: Path, quest_id: str) -> None:
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    journal_path.write_text(
        "\n".join(
            [
                "# Quest Journal: Rich Legacy Brief",
                "",
                f"- Quest ID: `{quest_id}`",
                "- Completed: 2026-04-13",
                "- Outcome: Preserve the deeper handcrafted context.",
                "",
                "## What Shipped",
                "",
                "Backfill should retain the richer reader-facing brief.",
                "",
                "## This is where it all began...",
                "",
                "What: Tighten validation before the launch scripts run.",
                "",
                "Why: Existing journal readers need the operational background, not just a short summary.",
                "",
                "Approach:",
                "- validate inputs before invoking side effects",
                "- fail early with actionable guidance",
                "- keep the old rollout notes intact",
                "",
                "## Celebration Data",
                "",
                "<!-- celebration-data-start -->",
                "```json",
                '{"quest_mode": "solo", "quality": {"tier": "Platinum", "grade": "P"}, "agents": [], "achievements": [], "metrics": [], "test_count": null, "tests_added": null, "files_changed": 1}',
                "```",
                "<!-- celebration-data-end -->",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_backfill_patches_matching_journal(tmp_path):
    repo_root = tmp_path
    archive_dir = repo_root / ".quest" / "archive" / "prompt-surface-consolidation_2026-04-13__1701"
    journal_path = repo_root / "docs" / "quest-journal" / "prompt-surface-consolidation_2026-04-13.md"

    _write_archive_quest(
        archive_dir,
        "prompt-surface-consolidation_2026-04-13__1701",
        "prompt-surface-consolidation",
    )
    _write_journal(journal_path, "prompt-surface-consolidation_2026-04-13__1701")

    result = backfill_journal_entries(repo_root)

    assert result["patched"] == ["prompt-surface-consolidation_2026-04-13.md"]
    updated = journal_path.read_text(encoding="utf-8")
    assert "- Outcome: Old truncated quote" in updated
    assert "Old body." in updated
    assert "## Quest Brief" in updated
    assert "Full original prompt recovered from the archive." in updated
    assert "## Celebration" in updated
    assert "`/celebrate docs/quest-journal/prompt-surface-consolidation_2026-04-13.md`" in updated


def test_backfill_skips_unmatched_archive(tmp_path):
    repo_root = tmp_path
    archive_dir = repo_root / ".quest" / "archive" / "missing-journal_2026-04-13__1701"
    (repo_root / "docs" / "quest-journal").mkdir(parents=True)
    _write_archive_quest(archive_dir, "missing-journal_2026-04-13__1701", "missing-journal")

    result = backfill_journal_entries(repo_root)

    assert result["patched"] == []
    assert result["unchanged"] == []
    assert any("no matching journal entry found" in warning for warning in result["skipped"])


def test_backfill_skips_slug_date_fallback_when_archive_date_is_unknown(tmp_path):
    repo_root = tmp_path
    archive_dir = repo_root / ".quest" / "archive" / "unknown-date_2026-04-13__1701"
    journal_dir = repo_root / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)
    _write_archive_quest(archive_dir, "unknown-date_2026-04-13__1701", "unknown-date")
    _write_journal(journal_dir / "unknown-date_2026-04-13.md", "different-quest-id_2026-04-13__1701")

    state_path = archive_dir / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["created_at"] = "not-a-date"
    state["updated_at"] = "still-not-a-date"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    result = backfill_journal_entries(repo_root)

    assert result["patched"] == []
    assert any("cannot use slug/date fallback" in warning for warning in result["skipped"])


def test_backfill_handles_missing_archive_directory(tmp_path):
    repo_root = tmp_path
    (repo_root / ".quest").mkdir(parents=True)
    (repo_root / "docs" / "quest-journal").mkdir(parents=True)

    result = backfill_journal_entries(repo_root)

    assert result == {"patched": [], "unchanged": [], "skipped": []}


def test_backfill_skips_ambiguous_slug_date_matches(tmp_path):
    repo_root = tmp_path
    archive_dir = repo_root / ".quest" / "archive" / "ambiguous_2026-04-13__1701"
    journal_dir = repo_root / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)
    _write_archive_quest(archive_dir, "ambiguous_2026-04-13__1701", "ambiguous")
    _write_journal(journal_dir / "ambiguous_2026-04-13-copy-a.md", "other-a_2026-04-13__1701")
    _write_journal(journal_dir / "ambiguous_2026-04-13-copy-b.md", "other-b_2026-04-13__1701")

    result = backfill_journal_entries(repo_root)

    assert result["patched"] == []
    assert any("ambiguous slug/date fallback" in warning for warning in result["skipped"])


def test_backfill_skips_duplicate_quest_id_matches(tmp_path):
    repo_root = tmp_path
    archive_dir = repo_root / ".quest" / "archive" / "duplicate_2026-04-13__1701"
    journal_dir = repo_root / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)
    _write_archive_quest(archive_dir, "duplicate_2026-04-13__1701", "duplicate")
    _write_journal(journal_dir / "duplicate-a_2026-04-13.md", "duplicate_2026-04-13__1701")
    _write_journal(journal_dir / "duplicate-b_2026-04-13.md", "duplicate_2026-04-13__1701")

    result = backfill_journal_entries(repo_root)

    assert result["patched"] == []
    assert any("duplicate Quest ID match" in warning for warning in result["skipped"])


def test_backfill_preserves_sections_after_legacy_brief_heading(tmp_path):
    repo_root = tmp_path
    archive_dir = repo_root / ".quest" / "archive" / "legacy-brief_2026-04-13__1701"
    journal_path = repo_root / "docs" / "quest-journal" / "legacy-brief_2026-04-13.md"

    _write_archive_quest(archive_dir, "legacy-brief_2026-04-13__1701", "legacy-brief")
    _write_journal_with_old_brief_heading(journal_path, "legacy-brief_2026-04-13__1701")

    result = backfill_journal_entries(repo_root)

    assert result["patched"] == ["legacy-brief_2026-04-13.md"]
    updated = journal_path.read_text(encoding="utf-8")
    assert "## Quest Brief" in updated
    assert "## Iterations" in updated
    assert "## Next Steps" in updated
    assert "Keep this handcrafted section." in updated
    assert "Keep this section too." in updated


def test_backfill_preserves_richer_existing_brief_context(tmp_path):
    repo_root = tmp_path
    archive_dir = repo_root / ".quest" / "archive" / "validate-and-launch_2026-04-13__1701"
    journal_path = repo_root / "docs" / "quest-journal" / "validate-and-launch_2026-04-13.md"

    _write_archive_quest(archive_dir, "validate-and-launch_2026-04-13__1701", "validate-and-launch")
    _write_journal_with_richer_existing_brief(journal_path, "validate-and-launch_2026-04-13__1701")

    result = backfill_journal_entries(repo_root)

    assert result["patched"] == ["validate-and-launch_2026-04-13.md"]
    updated = journal_path.read_text(encoding="utf-8")
    assert "## Quest Brief" in updated
    assert "What: Tighten validation before the launch scripts run." in updated
    assert "Existing journal readers need the operational background" in updated
    assert "### Archived Brief" in updated
    assert "Full original prompt recovered from the archive." in updated

    second = backfill_journal_entries(repo_root)
    assert second["patched"] == []
    updated_again = journal_path.read_text(encoding="utf-8")
    assert updated_again.count("### Archived Brief") == 1


def test_backfill_is_idempotent_on_rerun(tmp_path):
    repo_root = tmp_path
    archive_dir = repo_root / ".quest" / "archive" / "prompt-surface-consolidation_2026-04-13__1701"
    journal_path = repo_root / "docs" / "quest-journal" / "prompt-surface-consolidation_2026-04-13.md"

    _write_archive_quest(
        archive_dir,
        "prompt-surface-consolidation_2026-04-13__1701",
        "prompt-surface-consolidation",
    )
    _write_journal(journal_path, "prompt-surface-consolidation_2026-04-13__1701")

    first = backfill_journal_entries(repo_root)
    second = backfill_journal_entries(repo_root)

    assert first["patched"] == ["prompt-surface-consolidation_2026-04-13.md"]
    assert second["patched"] == []
    assert second["unchanged"] == ["prompt-surface-consolidation_2026-04-13.md"]
