"""Unit tests for quest_complete journal rendering."""

from datetime import date
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

import quest_complete
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


@pytest.mark.parametrize(
    ("payload", "category"),
    [("{bad", "decode"), ("[]", "shape"), ("null", "shape")],
)
def test_complete_rejects_malformed_state_cleanly(
    tmp_path, monkeypatch, capsys, payload, category
):
    quest_dir = tmp_path / "quest"
    quest_dir.mkdir()
    state_path = quest_dir / "state.json"
    state_path.write_text(payload, encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["quest_complete.py", "--quest-dir", str(quest_dir), "--skip-journal"],
    )

    assert quest_complete.main() == 1
    captured = capsys.readouterr()
    assert f"state_error[{category}]: {state_path.resolve()}" in captured.err
    assert "Traceback" not in captured.err


def test_complete_translates_state_read_failure(tmp_path, monkeypatch, capsys):
    quest_dir = tmp_path / "quest"
    quest_dir.mkdir()
    state_path = quest_dir / "state.json"
    state_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["quest_complete.py", "--quest-dir", str(quest_dir), "--skip-journal"],
    )

    def fail_read(*_args, **_kwargs):
        raise OSError("platform read detail")

    monkeypatch.setattr(quest_complete.Path, "read_text", fail_read)

    assert quest_complete.main() == 1
    captured = capsys.readouterr()
    assert captured.err == f"Error: state_error[read]: {state_path.resolve()}\n"
    assert "platform read detail" not in captured.err
    assert "Traceback" not in captured.err


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


def test_generate_journal_entry_includes_slug_metadata():
    data = QuestData(
        quest_id="2026-04-29_1430__portable-pre-commit-review",
        slug="portable-pre-commit-review",
        name="Portable Pre Commit Review",
    )

    entry = build_journal_entry(
        data,
        date(2026, 4, 29),
        Path("docs/quest-journal/portable-pre-commit-review_2026-04-29.md"),
    )

    assert "- Slug: portable-pre-commit-review" in entry


def test_build_journal_entry_includes_celebration_line_when_path_present():
    data = QuestData(
        quest_id="celebrate-me_2026-04-15__1200",
        slug="celebrate-me",
        name="Celebrate Me",
        quality_tier="Gold",
    )

    entry = build_journal_entry(
        data,
        date(2026, 4, 15),
        Path("docs/quest-journal/celebrate-me_2026-04-15.md"),
        Path("celebrations/celebrate-me_2026-04-15.md"),
    )

    assert (
        "- Celebration: [`celebrations/celebrate-me_2026-04-15.md`](celebrations/celebrate-me_2026-04-15.md)"
        in entry
    )
    assert (
        "- Full celebration: [`celebrations/celebrate-me_2026-04-15.md`](celebrations/celebrate-me_2026-04-15.md)"
        in entry
    )


def test_complete_date_first_quest_uses_parsed_slug(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path
    journal_dir = repo_root / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)
    (journal_dir / "README.md").write_text(
        "| Date | Quest | Outcome |\n|------|-------|---------|\n",
        encoding="utf-8",
    )
    quest_dir = repo_root / ".quest" / "2026-04-29_1430__portable-pre-commit-review"
    quest_dir.mkdir(parents=True)
    (quest_dir / "state.json").write_text(
        json.dumps(
            {
                "quest_id": "2026-04-29_1430__portable-pre-commit-review",
                "status": "complete",
            }
        ),
        encoding="utf-8",
    )
    (quest_dir / "quest_brief.md").write_text(
        "# Quest Brief: Portable Pre Commit Review\n\n## User Input\n\nDone.",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "quest_complete.py",
            "--quest-dir",
            str(quest_dir),
            "--skip-archive",
            "--date",
            "2026-04-29",
        ],
    )

    assert quest_complete.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip().splitlines()[-1])
    journal = journal_dir / "portable-pre-commit-review_2026-04-29.md"
    assert payload["slug"] == "portable-pre-commit-review"
    assert payload["celebration"].endswith(
        "docs/quest-journal/celebrations/portable-pre-commit-review_2026-04-29.md"
    )
    assert journal.exists()
    celebration = (
        journal_dir / "celebrations" / "portable-pre-commit-review_2026-04-29.md"
    )
    assert celebration.exists()
    journal_text = journal.read_text(encoding="utf-8")
    assert "- Slug: portable-pre-commit-review" in journal_text
    assert (
        "- Celebration: [`celebrations/portable-pre-commit-review_2026-04-29.md`]"
        in journal_text
    )
    assert "```text" in celebration.read_text(encoding="utf-8")


def test_complete_omits_celebration_link_when_existing_file_is_different_quest(
    tmp_path,
    monkeypatch,
    capsys,
):
    repo_root = tmp_path
    journal_dir = repo_root / "docs" / "quest-journal"
    celebration = journal_dir / "celebrations" / "same-slug_2026-05-03.md"
    celebration.parent.mkdir(parents=True)
    celebration.write_text(
        "<!-- quest-id: different_2026-05-03__0900 -->\n\nsentinel",
        encoding="utf-8",
    )
    (journal_dir / "README.md").write_text(
        "| Date | Quest | Outcome |\n|------|-------|---------|\n",
        encoding="utf-8",
    )
    quest_dir = repo_root / ".quest" / "2026-05-03_1200__same-slug"
    quest_dir.mkdir(parents=True)
    (quest_dir / "state.json").write_text(
        json.dumps(
            {
                "quest_id": "2026-05-03_1200__same-slug",
                "status": "complete",
            }
        ),
        encoding="utf-8",
    )
    (quest_dir / "quest_brief.md").write_text(
        "# Quest Brief: Same Slug\n\n## User Input\n\nDone.",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "quest_complete.py",
            "--quest-dir",
            str(quest_dir),
            "--skip-archive",
            "--date",
            "2026-05-03",
        ],
    )

    assert quest_complete.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out.strip().splitlines()[-1])
    journal = journal_dir / "same-slug_2026-05-03.md"

    assert payload["celebration"] is None
    assert "Celebration link omitted" in captured.out
    assert celebration.read_text(encoding="utf-8").endswith("sentinel")
    assert "- Celebration:" not in journal.read_text(encoding="utf-8")


def test_quest_complete_sweeps_parked_bg_sessions_before_archive(
    tmp_path,
    monkeypatch,
    capsys,
):
    repo_root = tmp_path
    journal_dir = repo_root / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)
    (journal_dir / "README.md").write_text(
        "| Date | Quest | Outcome |\n|------|-------|---------|\n",
        encoding="utf-8",
    )
    quest_dir = repo_root / ".quest" / "bg-transport_2026-07-04__1043"
    quest_dir.mkdir(parents=True)
    (quest_dir / "state.json").write_text(
        json.dumps(
            {
                "quest_id": "bg-transport_2026-07-04__1043",
                "slug": "bg-transport",
                "status": "complete",
            }
        ),
        encoding="utf-8",
    )
    (quest_dir / "quest_brief.md").write_text(
        "# Quest Brief: BG Transport\n\n## User Input\n\nDone.",
        encoding="utf-8",
    )
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append([str(part) for part in cmd])
        return quest_complete.subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout="sweep complete",
            stderr="",
        )

    monkeypatch.setattr(quest_complete.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "quest_complete.py",
            "--quest-dir",
            str(quest_dir),
            "--skip-journal",
            "--date",
            "2026-07-04",
        ],
    )

    assert quest_complete.main() == 0
    assert calls
    assert calls[0][-2:] == ["--sweep", "quest-bg-transport_2026-07-04__1043-"]
    assert (repo_root / ".quest" / "archive" / quest_dir.name).exists()
    assert "Quest archived" in capsys.readouterr().out


def test_quest_complete_warns_when_sweep_spares_active_sessions(
    tmp_path,
    monkeypatch,
    capsys,
):
    # Exit 0 with "skipped active" rows is NOT a green cleanup: the human must
    # see the survivors and the exact include-active command, and archive
    # still proceeds (best-effort by design).
    repo_root = tmp_path
    journal_dir = repo_root / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)
    (journal_dir / "README.md").write_text(
        "| Date | Quest | Outcome |\n|------|-------|---------|\n",
        encoding="utf-8",
    )
    quest_dir = repo_root / ".quest" / "bg-active_2026-07-05__0900"
    quest_dir.mkdir(parents=True)
    (quest_dir / "state.json").write_text(
        json.dumps(
            {
                "quest_id": "bg-active_2026-07-05__0900",
                "slug": "bg-active",
                "status": "complete",
            }
        ),
        encoding="utf-8",
    )
    (quest_dir / "quest_brief.md").write_text(
        "# Quest Brief: BG Active\n\n## User Input\n\nDone.",
        encoding="utf-8",
    )

    def fake_run(cmd, **kwargs):
        return quest_complete.subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=(
                "skipped active abc12345 (quest-bg-active_2026-07-05__0900-builder-i1)\n"
                "sweep left 1 actively working session(s) alive "
                "(pass --sweep-include-active to stop sessions you own)\n"
                "sweep complete: 0 session(s) matching 'quest-bg-active_2026-07-05__0900-' stopped"
            ),
            stderr="",
        )

    monkeypatch.setattr(quest_complete.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "quest_complete.py",
            "--quest-dir",
            str(quest_dir),
            "--skip-journal",
            "--date",
            "2026-07-05",
        ],
    )

    assert quest_complete.main() == 0
    out = capsys.readouterr().out
    assert "WARNING: Claude bg sweep before archive incomplete" in out
    assert "--sweep quest-bg-active_2026-07-05__0900- --sweep-include-active" in out
    assert (repo_root / ".quest" / "archive" / quest_dir.name).exists()


def test_quest_complete_reports_incomplete_bg_sweep_but_archives(
    tmp_path,
    monkeypatch,
    capsys,
):
    repo_root = tmp_path
    journal_dir = repo_root / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)
    (journal_dir / "README.md").write_text(
        "| Date | Quest | Outcome |\n|------|-------|---------|\n",
        encoding="utf-8",
    )
    quest_dir = repo_root / ".quest" / "bg-transport_2026-07-04__1043"
    quest_dir.mkdir(parents=True)
    (quest_dir / "state.json").write_text(
        json.dumps(
            {
                "quest_id": "bg-transport_2026-07-04__1043",
                "slug": "bg-transport",
                "status": "complete",
            }
        ),
        encoding="utf-8",
    )
    (quest_dir / "quest_brief.md").write_text(
        "# Quest Brief: BG Transport\n\n## User Input\n\nDone.",
        encoding="utf-8",
    )

    def fake_run(cmd, **kwargs):
        return quest_complete.subprocess.CompletedProcess(
            args=cmd,
            returncode=4,
            stdout="teardown_failed aaa11111\nsweep incomplete",
            stderr="",
        )

    monkeypatch.setattr(quest_complete.subprocess, "run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "quest_complete.py",
            "--quest-dir",
            str(quest_dir),
            "--skip-journal",
            "--date",
            "2026-07-04",
        ],
    )

    assert quest_complete.main() == 0
    captured = capsys.readouterr()
    # Survivor warning is prominent (stdout) and actionable: nothing re-sweeps
    # an archived quest, so the human must get the exact manual command.
    assert "WARNING: Claude bg sweep before archive incomplete (exit 4)" in captured.out
    # The command must be runnable from ANY cwd (absolute runner path) and
    # asserted contiguously so a truncated/reordered command cannot pass.
    expected_runner = (
        Path(quest_complete.__file__).resolve().parent / "quest_claude_bg_run.py"
    )
    assert (
        f"run: python3 {expected_runner} --sweep quest-{quest_dir.name}- --sweep-include-active"
        in captured.out
    )
    assert (repo_root / ".quest" / "archive" / quest_dir.name).exists()


def test_complete_does_not_write_celebration_when_journal_already_exists(
    tmp_path,
    monkeypatch,
    capsys,
):
    repo_root = tmp_path
    journal_dir = repo_root / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)
    (journal_dir / "README.md").write_text(
        "| Date | Quest | Outcome |\n|------|-------|---------|\n",
        encoding="utf-8",
    )
    journal = journal_dir / "same-slug_2026-05-03.md"
    journal.write_text(
        "# Quest Journal: Existing\n\n- Quest ID: `different_2026-05-03__0900`\n",
        encoding="utf-8",
    )
    quest_dir = repo_root / ".quest" / "2026-05-03_1200__same-slug"
    quest_dir.mkdir(parents=True)
    (quest_dir / "state.json").write_text(
        json.dumps(
            {
                "quest_id": "2026-05-03_1200__same-slug",
                "status": "complete",
            }
        ),
        encoding="utf-8",
    )
    (quest_dir / "quest_brief.md").write_text(
        "# Quest Brief: Same Slug\n\n## User Input\n\nDone.",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "quest_complete.py",
            "--quest-dir",
            str(quest_dir),
            "--skip-archive",
            "--date",
            "2026-05-03",
        ],
    )

    assert quest_complete.main() == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])

    assert payload["celebration"] is None
    assert not (journal_dir / "celebrations" / "same-slug_2026-05-03.md").exists()


def test_celebration_file_match_handles_invalid_utf8(tmp_path):
    celebration = tmp_path / "bad.md"
    celebration.write_bytes(b"\xff\xfe\x00")

    assert quest_complete._celebration_file_matches_quest(celebration, "quest") is False


def test_main_reports_invalid_date(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    quest_dir = tmp_path / "quest"
    quest_dir.mkdir()
    (quest_dir / "state.json").write_text(
        json.dumps({"status": "complete"}, indent=2) + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(quest_complete, "load_quest_data", lambda _: SimpleNamespace())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "quest_complete.py",
            "--quest-dir",
            str(quest_dir),
            "--date",
            "2026-13-40",
        ],
    )

    assert quest_complete.main() == 1
    captured = capsys.readouterr()
    assert "invalid date" in captured.err


def test_build_celebration_json_includes_transport_when_present():
    from quest_celebrate.quest_data import AgentInfo
    from quest_complete import _build_celebration_json

    data = QuestData()
    data.agents = [
        AgentInfo(
            name="plan-reviewer-a",
            model="claude-opus-4-6",
            role_title="The A Plan Critic",
            summary="",
            phase="Planning",
            transport="background-agent",
        ),
        AgentInfo(
            name="builder",
            model="gpt-5.5",
            role_title="The Implementer",
            summary="",
            phase="Implementation",
        ),
    ]
    data.claude_transport_counts = {"background-agent": 2, "bridge": 1}

    payload = _build_celebration_json(data)

    reviewer = next(a for a in payload["agents"] if a["name"] == "plan-reviewer-a")
    builder = next(a for a in payload["agents"] if a["name"] == "builder")
    assert reviewer["transport"] == "background-agent"
    assert "transport" not in builder
    assert payload["claude_transport_counts"] == {"background-agent": 2, "bridge": 1}
    transport_metrics = [
        m for m in payload["metrics"] if "Claude transport" in m["label"]
    ]
    assert transport_metrics == [
        {"icon": "🚌", "label": "Claude transport: background-agent ×2, bridge ×1"}
    ]


def test_build_celebration_json_silent_when_no_transport_data():
    from quest_complete import _build_celebration_json

    payload = _build_celebration_json(QuestData())

    assert payload["claude_transport_counts"] == {}
    assert not any("Claude transport" in m["label"] for m in payload["metrics"])


def test_handoff_status_stats_counts_only_explicit_status_lines(tmp_path):
    archive = tmp_path / "archive"
    # Legacy quest: log predates the status field — excluded from the stats.
    legacy = archive / "legacy-quest_2026-03-01__0900" / "logs"
    legacy.mkdir(parents=True)
    (legacy / "context_health.log").write_text(
        "2026-03-01T09:00:00Z | phase=plan | agent=planner | runtime=claude | "
        "iter=1 | handoff_json=found | source=handoff_json\n",
        encoding="utf-8",
    )
    # Instrumented quest: one needs_human round-trip, then complete.
    fresh = archive / "fresh-quest_2026-06-12__1000" / "logs"
    fresh.mkdir(parents=True)
    (fresh / "context_health.log").write_text(
        "2026-06-12T10:00:00Z | phase=plan | agent=planner | runtime=claude | "
        "iter=1 | handoff_json=found | source=handoff_json | "
        "status=needs_human | transport=background-agent\n"
        "2026-06-12T10:05:00Z | phase=plan | agent=planner | runtime=claude | "
        "iter=1 | handoff_json=found | source=handoff_json | "
        "status=complete | transport=background-agent\n",
        encoding="utf-8",
    )
    # Archived quest with no context_health.log at all.
    (archive / "no-log-quest_2026-05-01__1200").mkdir(parents=True)

    stats = quest_complete._handoff_status_stats(archive)

    assert stats == {
        "archived_quests": 3,
        "status_instrumented_quests": 1,
        "status_counts": {"needs_human": 1, "complete": 1},
        "needs_human": 1,
    }


def test_handoff_status_stats_empty_when_archive_missing(tmp_path):
    stats = quest_complete._handoff_status_stats(tmp_path / "archive")
    assert stats["archived_quests"] == 0
    assert stats["status_instrumented_quests"] == 0
    assert stats["needs_human"] == 0


def test_complete_reports_needs_human_rollup(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path
    journal_dir = repo_root / "docs" / "quest-journal"
    journal_dir.mkdir(parents=True)
    (journal_dir / "README.md").write_text(
        "| Date | Quest | Outcome |\n|------|-------|---------|\n",
        encoding="utf-8",
    )
    quest_dir = repo_root / ".quest" / "rollup-check_2026-06-12__1100"
    quest_dir.mkdir(parents=True)
    (quest_dir / "state.json").write_text(
        json.dumps({"quest_id": "rollup-check_2026-06-12__1100", "status": "complete"}),
        encoding="utf-8",
    )
    archive_logs = (
        repo_root / ".quest" / "archive" / "old-quest_2026-06-01__0900" / "logs"
    )
    archive_logs.mkdir(parents=True)
    (archive_logs / "context_health.log").write_text(
        "2026-06-01T09:00:00Z | phase=plan | agent=planner | runtime=claude | "
        "iter=1 | handoff_json=found | source=handoff_json | status=needs_human\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "quest_complete.py",
            "--quest-dir",
            str(quest_dir),
            "--skip-archive",
            "--date",
            "2026-06-12",
        ],
    )

    assert quest_complete.main() == 0
    captured = capsys.readouterr()
    assert "needs_human across archive: 1 occurrence(s)" in captured.out
    payload = json.loads(captured.out.strip().splitlines()[-1])
    assert payload["needs_human_stats"]["needs_human"] == 1
    assert payload["needs_human_stats"]["status_instrumented_quests"] == 1
    assert payload["needs_human_stats"]["archived_quests"] == 1
