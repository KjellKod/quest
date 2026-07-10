#!/usr/bin/env python3
"""Automate quest completion: journal entry creation, README update, and archival.

Usage:
    python3 scripts/quest_complete.py --quest-dir .quest/<id>

This script is called by the orchestrator during Step 7 of the quest workflow.
It reads quest artifacts, generates a journal entry with embedded celebration_data,
updates the journal README index, and moves the quest to the archive.

The celebration animation itself is NOT handled here — it runs via the /celebrate
skill or the Python celebrate.py script before this script is called.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

# Add scripts/ to path so we can import quest_celebrate
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quest_celebrate.quest_data import (
    QuestData,
    friendly_model_name,
    load_quest_data,
)
from quest_celebrate.persist import CelebrationWriteResult, write_celebration_file
from quest_runtime.claude_runner import sweep_left_survivor
from quest_runtime.quest_ids import parse_quest_id


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _build_celebration_json(data: QuestData) -> dict:
    """Build the celebration_data JSON block from QuestData."""
    metrics = [
        {"icon": "📊", "label": f"Plan iterations: {data.plan_iterations}"},
        {"icon": "🔧", "label": f"Fix iterations: {data.fix_iterations}"},
        {"icon": "📝", "label": f"Review rounds: {data.review_count}"},
    ]
    if data.claude_transport_counts:
        # Only when Codex called Claude — silent empty state otherwise.
        breakdown = ", ".join(
            f"{transport} ×{count}"
            for transport, count in sorted(data.claude_transport_counts.items())
        )
        metrics.append({"icon": "🚌", "label": f"Claude transport: {breakdown}"})
    return {
        "quest_mode": data.quest_mode or "unknown",
        "agents": [
            (
                {"name": a.name, "model": a.model, "role": a.role_title}
                | ({"transport": a.transport} if a.transport else {})
            )
            for a in data.agents
        ],
        "claude_transport_counts": data.claude_transport_counts,
        "achievements": [
            {"icon": a.icon, "title": a.title, "desc": a.description}
            for a in data.achievements
        ],
        "metrics": metrics,
        "quality": {
            "tier": data.quality_tier,
            "grade": data.quality_tier[0] if data.quality_tier else "?",
        },
        "inherited_findings_used": {
            "count": data.inherited_findings_used.count,
            "summaries": data.inherited_findings_used.summaries,
        },
        "findings_left_for_future_quests": {
            "count": data.findings_left_for_future_quests.count,
            "summaries": data.findings_left_for_future_quests.summaries,
        },
        "test_count": data.test_count,
        "tests_added": data.tests_added,
        "files_changed": len(data.files_changed),
    }


def _celebration_link_for_result(
    celebration_result: CelebrationWriteResult,
    data: QuestData,
) -> Path | None:
    """Return a journal link only for the current quest's celebration artifact."""
    if not celebration_result.path.exists():
        return None
    if celebration_result.created:
        return celebration_result.rel_path
    if _celebration_file_matches_quest(celebration_result.path, data.quest_id):
        return celebration_result.rel_path
    return None


def _celebration_file_matches_quest(path: Path, quest_id: str) -> bool:
    if not quest_id:
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    match = re.search(r"<!--\s*quest-id:\s*(.*?)\s*-->", text)
    return bool(match and match.group(1) == quest_id)


def _journal_outcome(data: QuestData) -> str:
    """Return the best short journal outcome summary."""
    plan_summary = data.plan_summary.strip()
    preferred = (
        plan_summary
        if plan_summary and not re.match(r"^\*{0,2}problem\*{0,2}:", plan_summary, re.IGNORECASE)
        else (data.brief_summary or "Completed successfully.")
    )
    collapsed = re.sub(r"(?m)^\s*>\s?", "", preferred)
    return re.sub(r"\s+", " ", collapsed).strip()


def build_quest_brief_section(data: QuestData) -> str:
    """Build the reader-facing quest brief section."""
    body = (data.brief_body or data.brief_summary).strip()
    if not body:
        return ""

    lines = ["## Quest Brief", ""]
    if data.brief_source != "original_prompt":
        lines.append(
            "Full original prompt was not recorded for this quest. "
            "This is the best available brief context."
        )
        lines.append("")
    lines.append(body)
    lines.append("")
    return "\n".join(lines)


def build_celebration_section(
    journal_rel_path: Path | None,
    celebration_rel_path: Path | None = None,
) -> str:
    """Build the reader-facing celebration section."""
    if journal_rel_path is None:
        return ""

    journal_ref = journal_rel_path.as_posix()
    lines = [
        "## Celebration",
        "",
        "This journal embeds the celebration payload used by `/celebrate`.",
        "",
    ]
    if celebration_rel_path is not None:
        celebration_ref = celebration_rel_path.as_posix()
        lines.append(f"- Full celebration: [`{celebration_ref}`]({celebration_ref})")
    lines.extend(
        [
            "- [Jump to Celebration Data](#celebration-data)",
            f"- Replay locally: `/celebrate {journal_ref}`",
            "",
        ]
    )
    return "\n".join(lines)


def _build_carryover_journal_section(title: str, count: int, summaries: list[str]) -> str:
    """Build one reader-facing carry-over findings section."""
    if count <= 0:
        return ""

    lines = [f"## {title}", "", f"- Count: **{count}**"]
    for summary in summaries[:3]:
        lines.append(f"- {summary}")
    lines.append("")
    return "\n".join(lines)


def _build_empty_carryover_journal_section() -> str:
    """Build the explicit empty-state carry-over section."""
    return "\n".join(
        [
            "## Carry-Over Findings",
            "",
            "- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.",
            "",
        ]
    )


def build_celebration_data_section(data: QuestData) -> str:
    """Build the machine-readable celebration payload section."""
    celebration = _build_celebration_json(data)
    return "\n".join(
        [
            "## Celebration Data",
            "",
            "<!-- celebration-data-start -->",
            "```json",
            json.dumps(celebration, indent=2, ensure_ascii=False),
            "```",
            "<!-- celebration-data-end -->",
            "",
        ]
    )


def build_journal_entry(
    data: QuestData,
    completion_date: date,
    journal_rel_path: Path | None = None,
    celebration_rel_path: Path | None = None,
) -> str:
    """Generate a markdown journal entry from quest data."""
    lines = []

    # Title
    title = data.name or data.slug or data.quest_id
    lines.append(f"# Quest Journal: {title}")
    lines.append("")

    # Metadata
    lines.append(f"- Quest ID: `{data.quest_id}`")
    if data.slug:
        lines.append(f"- Slug: {data.slug}")
    lines.append(f"- Completed: {completion_date.isoformat()}")
    if data.quest_mode:
        lines.append(f"- Mode: {data.quest_mode}")
    if data.quality_tier:
        lines.append(f"- Quality: {data.quality_tier}")
    if celebration_rel_path is not None:
        celebration_ref = celebration_rel_path.as_posix()
        lines.append(f"- Celebration: [`{celebration_ref}`]({celebration_ref})")
    lines.append(f"- Outcome: {_journal_outcome(data)}")
    lines.append("")

    # What shipped
    if data.plan_summary:
        lines.append("## What Shipped")
        lines.append("")
        lines.append(data.plan_summary)
        lines.append("")

    # Files changed
    if data.files_changed:
        lines.append("## Files Changed")
        lines.append("")
        for f in data.files_changed:
            lines.append(f"- `{f}`")
        lines.append("")

    # Iterations
    lines.append("## Iterations")
    lines.append("")
    lines.append(f"- Plan iterations: {data.plan_iterations}")
    lines.append(f"- Fix iterations: {data.fix_iterations}")
    lines.append("")

    # Agents
    if data.agents:
        lines.append("## Agents")
        lines.append("")
        for agent in data.agents:
            model_label = friendly_model_name(agent.model)
            lines.append(f"- **{agent.role_title}** ({agent.name}): {model_label}")
        lines.append("")

    quest_brief_section = build_quest_brief_section(data)
    if quest_brief_section:
        lines.append(quest_brief_section.rstrip())
        lines.append("")

    inherited_section = _build_carryover_journal_section(
        "Inherited Findings Used",
        data.inherited_findings_used.count,
        data.inherited_findings_used.summaries,
    )
    if inherited_section:
        lines.append(inherited_section.rstrip())
        lines.append("")

    carryforward_section = _build_carryover_journal_section(
        "Findings Left For Future Quests",
        data.findings_left_for_future_quests.count,
        data.findings_left_for_future_quests.summaries,
    )
    if carryforward_section:
        lines.append(carryforward_section.rstrip())
        lines.append("")
    elif data.inherited_findings_used.count <= 0:
        lines.append(_build_empty_carryover_journal_section().rstrip())
        lines.append("")

    celebration_section = build_celebration_section(
        journal_rel_path,
        celebration_rel_path,
    )
    if celebration_section:
        lines.append(celebration_section.rstrip())
        lines.append("")

    lines.append(build_celebration_data_section(data).rstrip())
    lines.append("")

    return "\n".join(lines)


def _update_readme_index(journal_dir: Path, slug: str, completion_date: date, outcome: str) -> None:
    """Insert a row at the top of the journal README index table."""
    readme = journal_dir / "README.md"
    if not readme.exists():
        return

    content = readme.read_text()
    # Find the header row separator and insert after it
    # Format: | Date | Quest | Outcome |
    #         |------|-------|---------|
    #         | new row here |
    pattern = r"(\| Date \| Quest \| Outcome \|\n\|[-\s|]+\|\n)"
    new_row = f"| {completion_date.isoformat()} | [{slug}]({slug}_{completion_date.isoformat()}.md) | {outcome} |\n"

    if re.search(pattern, content):
        content = re.sub(pattern, lambda m: m.group(1) + new_row, content, count=1)
    else:
        # Fallback: append to end
        content += f"\n{new_row}"

    readme.write_text(content)


def _handoff_status_stats(archive_root: Path) -> dict:
    """Aggregate status= fields across archived quests' context_health logs.

    Counting contract: only lines that explicitly carry status= participate —
    legacy lines (which predate the field) are excluded from both numerator
    and denominator, never inferred as complete or needs_human.
    """
    status_counts: dict[str, int] = {}
    instrumented_quests = 0
    archived_quests = 0
    if archive_root.is_dir():
        for quest in sorted(archive_root.iterdir()):
            if not quest.is_dir():
                continue
            archived_quests += 1
            try:
                lines = (quest / "logs" / "context_health.log").read_text(
                    encoding="utf-8"
                ).splitlines()
            except (OSError, UnicodeDecodeError):
                # A malformed (non-UTF-8) archived log must not crash this
                # optional rollup; skip it, matching the graceful-degradation
                # contract used for celebration metadata.
                continue
            quest_has_status = False
            for line in lines:
                match = re.search(r"\bstatus=(\S+)", line)
                if not match:
                    continue
                quest_has_status = True
                status_counts[match.group(1)] = status_counts.get(match.group(1), 0) + 1
            if quest_has_status:
                instrumented_quests += 1
    return {
        "archived_quests": archived_quests,
        "status_instrumented_quests": instrumented_quests,
        "status_counts": status_counts,
        "needs_human": status_counts.get("needs_human", 0),
    }


def _archive_quest(quest_dir: Path) -> Path:
    """Move quest directory to archive. Returns archive path."""
    archive_root = quest_dir.parent / "archive"
    archive_root.mkdir(exist_ok=True)
    dest = archive_root / quest_dir.name
    if dest.exists():
        raise FileExistsError(f"Archive already exists: {dest}. Remove it manually to re-archive.")
    shutil.move(str(quest_dir), str(dest))
    return dest


def _sweep_parked_bg_sessions(quest_dir: Path) -> subprocess.CompletedProcess | None:
    """Best-effort cleanup for parked Claude background sessions before archive."""
    runner = Path(__file__).resolve().parent / "claude_bg_run.py"
    if not runner.exists():
        print(f"Claude bg sweep skipped: runner not found at {runner}", file=sys.stderr)
        return None
    prefix = f"quest-{quest_dir.name}-"
    try:
        result = subprocess.run(
            [sys.executable, str(runner), "--sweep", prefix],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        print(f"Claude bg sweep failed before archive: {exc}", file=sys.stderr)
        return None
    if sweep_left_survivor(result.returncode, result.stdout):
        # Prominent, actionable, on STDOUT: after archive nothing ever
        # re-sweeps this quest's sessions, so an unverified cleanup leaks
        # until the human runs the command themselves.
        print(
            f"WARNING: Claude bg sweep before archive incomplete (exit {result.returncode}); "
            "session(s) may remain live and will NOT be cleaned up automatically. "
            f"If they are this quest's own leftovers, run: "
            f"python3 {runner} --sweep {prefix} --sweep-include-active"
        )
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
    else:
        print(f"Claude bg sweep before archive complete: {prefix}")
        if result.stdout.strip():
            print(result.stdout.strip())
    return result


def _slug_from_quest_dir(quest_dir: Path) -> str:
    parsed = parse_quest_id(quest_dir.name)
    if parsed is not None:
        return parsed.slug
    return quest_dir.name.split("_")[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Complete a quest: journal + archive")
    parser.add_argument("--quest-dir", required=True, help="Path to quest directory")
    parser.add_argument("--skip-archive", action="store_true", help="Skip archival step")
    parser.add_argument("--skip-journal", action="store_true", help="Skip journal creation")
    parser.add_argument("--date", default=None, help="Override completion date (YYYY-MM-DD)")
    args = parser.parse_args()

    quest_dir = Path(args.quest_dir)
    if not quest_dir.exists():
        print(f"Error: quest directory not found: {quest_dir}", file=sys.stderr)
        return 1

    state_file = quest_dir / "state.json"
    if not state_file.exists():
        print(f"Error: no state.json in {quest_dir}", file=sys.stderr)
        return 1

    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        print(f"Error: could not read state.json in {quest_dir}: {exc}", file=sys.stderr)
        return 1
    if state.get("status") != "complete":
        print(f"Error: quest status is '{state.get('status')}', not 'complete'. "
              "Transition to complete or abandoned first.", file=sys.stderr)
        return 1

    # Load quest data
    data = load_quest_data(quest_dir)
    try:
        completion_date = date.fromisoformat(args.date) if args.date else _today()
    except ValueError:
        print(
            f"Error: invalid date '{args.date}'. Expected YYYY-MM-DD.",
            file=sys.stderr,
        )
        return 1

    # Determine slug and outcome
    slug = data.slug or state.get("slug", _slug_from_quest_dir(quest_dir))
    data.slug = slug
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        print(f"Error: invalid slug '{slug}'. Must match [a-z0-9][a-z0-9-]*", file=sys.stderr)
        return 1
    outcome = _journal_outcome(data)
    # Sanitize outcome for README markdown table: collapse newlines, escape pipes
    outcome = re.sub(r"\s*\n\s*", " ", outcome).replace("|", "\\|")
    if len(outcome) > 120:
        outcome = outcome[:117] + "..."

    journal_path = None
    celebration_path = None
    if not args.skip_journal:
        # Find journal directory (walk up to repo root)
        repo_root = quest_dir.resolve()
        found = False
        for _ in range(5):
            if (repo_root / "docs" / "quest-journal").exists():
                found = True
                break
            parent = repo_root.parent
            if parent == repo_root:
                break
            repo_root = parent
        if not found:
            print(f"Error: could not find docs/quest-journal/ above {quest_dir}", file=sys.stderr)
            return 1
        journal_dir = repo_root / "docs" / "quest-journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal_file = journal_dir / f"{slug}_{completion_date.isoformat()}.md"
        journal_rel_path = journal_file.relative_to(repo_root)

        if journal_file.exists():
            print(f"Journal entry already exists: {journal_file}")
        else:
            celebration_result = write_celebration_file(
                journal_dir,
                data,
                completion_date,
                journal_rel_path,
            )
            celebration_rel_path = _celebration_link_for_result(celebration_result, data)
            if celebration_rel_path is not None:
                celebration_path = str(celebration_result.path)
            elif celebration_result.path.exists() and not celebration_result.created:
                print(
                    "Celebration link omitted: existing artifact does not match current quest-id"
                )
            print(celebration_result.message)

            entry = build_journal_entry(
                data,
                completion_date,
                journal_rel_path,
                celebration_rel_path,
            )
            journal_file.write_text(entry)
            print(f"Journal entry created: {journal_file}")

            # Update README index
            _update_readme_index(journal_dir, slug, completion_date, outcome)
            print(f"README index updated")
        journal_path = str(journal_file)

    archive_root = quest_dir.parent / "archive"
    if not args.skip_archive:
        _sweep_parked_bg_sessions(quest_dir)
        archive_path = _archive_quest(quest_dir)
        print(f"Quest archived: {archive_path}")

    # Historical needs_human rollup (runs after archival so this quest counts).
    # Feeds the measurement gate in ideas/2026-07-05-bg-claude-ask-policy-relaxation.md.
    status_stats = _handoff_status_stats(archive_root)
    print(
        f"needs_human across archive: {status_stats['needs_human']} occurrence(s) "
        f"in {status_stats['status_instrumented_quests']} status-instrumented "
        f"quest(s) of {status_stats['archived_quests']} archived "
        "(lines without status= are not counted)"
    )

    print(json.dumps({
        "slug": slug,
        "journal": journal_path,
        "celebration": celebration_path,
        "archived": not args.skip_archive,
        "quality_tier": data.quality_tier,
        "needs_human_stats": status_stats,
    }))

    return 0


if __name__ == "__main__":
    sys.exit(main())
