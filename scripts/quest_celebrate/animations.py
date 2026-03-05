"""Animation renderers and quest stats for celebrations."""

import json
import re
import sys
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, TextIO, Tuple

from quest_celebrate.ascii_art import (
    block_letter_title,
    box_banner,
    get_credits_lines,
    get_movie_credits_lines,
    gremlin_battle_art,
    gremlin_retirement_art,
    render_achievements,
    render_impact_metrics,
    render_quality_score,
    rocket_launch_art,
    trophy_art,
)
from quest_celebrate.config import CelebrationConfig
from quest_celebrate.progress import animate_progress_bars, render_phase_progress, scroll_credits
from quest_celebrate.quest_data import QuestData, load_quest_data


@dataclass
class QuestStats:
    """Statistics about a completed quest (legacy, backwards-compatible)."""

    name: str = "Unknown Quest"
    quest_id: str = ""
    slug: str = ""
    tools_count: int = 0
    tests_count: int = 0
    bugs_fixed: int = 0
    pr_number: Optional[int] = None
    duration_hours: float = 0.0
    plan_iterations: int = 0
    fix_iterations: int = 0
    phases: Optional[List[Tuple[str, str]]] = None  # (phase_name, status)

    def __post_init__(self):
        if self.phases is None:
            self.phases = []


def load_quest_stats(quest_dir: Path) -> QuestStats:
    """Load quest statistics from quest directory.

    Reads state.json and quest_brief.md to extract quest information.
    Handles missing files gracefully, returning partial data.
    """
    stats = QuestStats()

    if not quest_dir.exists():
        return stats

    # Read state.json
    state_path = quest_dir / "state.json"
    if state_path.exists():
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)

            stats.quest_id = state.get("quest_id", "")
            stats.slug = state.get("slug", "")
            stats.plan_iterations = state.get("plan_iteration", 0)
            stats.fix_iterations = state.get("fix_iteration", 0)

            # Parse quest_id to get quest name
            if stats.quest_id:
                # Format: quest-name_YYYY-MM-DD__HHMM
                parts = stats.quest_id.split("_")
                if parts:
                    stats.name = parts[0].replace("-", " ").title()

        except json.JSONDecodeError:
            # Graceful degradation - use defaults
            pass

    # Read quest_brief.md for additional info
    brief_path = quest_dir / "quest_brief.md"
    if brief_path.exists():
        try:
            brief = brief_path.read_text(encoding="utf-8")
            # Try to extract quest name from brief
            title_match = re.search(r"^# Quest Brief:\s*(.+)$", brief, re.MULTILINE)
            if title_match:
                stats.name = title_match.group(1).strip()
        except IOError:
            pass

    # Count handoff files to estimate phases
    handoff_files = list(quest_dir.glob("**/handoff*.json"))
    if handoff_files:
        # Create phases based on handoff files found
        phases = []
        seen_phases = set()

        for handoff in sorted(handoff_files):
            # Extract phase from path or filename
            phase_name = _extract_phase_name(handoff, quest_dir)
            if phase_name and phase_name not in seen_phases:
                seen_phases.add(phase_name)
                phases.append((phase_name, "complete"))

        if phases:
            stats.phases = phases

    # Set defaults for standard phases if none found
    if not stats.phases:
        stats.phases = [
            ("Planning", "complete"),
            ("Implementation", "complete"),
            ("Review", "complete"),
            ("Completion", "complete"),
        ]

    return stats


def _extract_phase_name(handoff_path: Path, quest_dir: Path) -> str:
    """Extract phase name from handoff file path."""
    # Relative path from quest_dir
    try:
        rel = handoff_path.relative_to(quest_dir)
        parts = rel.parts

        # Look for phase directory patterns
        for part in parts:
            if "phase" in part.lower():
                # Extract readable name from directory
                name = part.replace("phase_", "").replace("_", " ").title()
                # Handle specific phase patterns
                if "01" in part or "plan" in part.lower():
                    return "Planning"
                elif (
                    "02" in part
                    or "build" in part.lower()
                    or "implement" in part.lower()
                ):
                    return "Building"
                elif "03" in part or "review" in part.lower():
                    return "Review"
                return name

        # Fallback: use filename
        return handoff_path.stem.replace("handoff_", "").replace("_", " ").title()
    except ValueError:
        return handoff_path.stem.replace("handoff_", "").replace("_", " ").title()


def render_minimal(stats: QuestStats, config: CelebrationConfig) -> str:
    """Render minimal one-line celebration."""
    emoji_check = "" if config.is_safe else ""
    emoji_pkg = "" if config.is_safe else ""
    emoji_test = "" if config.is_safe else ""

    tools = f"| {emoji_pkg}{stats.tools_count} tools" if stats.tools_count else ""
    tests = f"| {emoji_test}{stats.tests_count} tests" if stats.tests_count else ""

    return f"{emoji_check}Quest Complete: {stats.name} {tools} {tests}".strip()


def render_standard(stats: QuestStats, config: CelebrationConfig) -> str:
    """Render standard boxed banner celebration."""
    lines = []

    # Header banner
    if config.is_safe:
        lines.append("=" * 78)
        lines.append(f"  QUEST COMPLETE: {stats.name}")
        lines.append("=" * 78)
    else:
        lines.append(box_banner("QUEST COMPLETE", width=78, safe_mode=config.is_safe))
        lines.append(f"  {stats.name}")

    lines.append("")

    # Stats section
    if config.show_progress:
        lines.append("Stats:")
        if stats.tools_count:
            lines.append(f"  Tools: {stats.tools_count}")
        if stats.tests_count:
            lines.append(f"  Tests: {stats.tests_count}")
        if stats.bugs_fixed:
            lines.append(f"  Bugs Fixed: {stats.bugs_fixed}")
        if stats.pr_number:
            lines.append(f"  PR: #{stats.pr_number}")

    lines.append("")

    # Phase summary
    if stats.plan_iterations or stats.fix_iterations:
        lines.append(
            f"Iterations: {stats.plan_iterations} plan, {stats.fix_iterations} fix"
        )

    return "\n".join(lines)


def render_epic(
    stats: QuestStats,
    config: CelebrationConfig,
    output: TextIO = sys.stdout,
    quest_data: Optional[QuestData] = None,
) -> None:
    """Render epic celebration with block title, achievements, metrics, credits.

    If quest_data is provided (rich data), the full cinematic experience is shown.
    Otherwise falls back to the simpler stats-based rendering.
    """
    # Block-letter title
    if quest_data is not None:
        title_name = quest_data.name
    else:
        title_name = stats.name

    title_block = block_letter_title(
        title_name, safe_mode=config.is_safe, max_width=config.columns
    )
    output.write("\n")
    output.write(title_block + "\n")
    output.write("\n")

    # Brief summary
    if quest_data and quest_data.brief_summary:
        output.write(f"  {quest_data.brief_summary}\n\n")

    # Phase progress bars
    if config.show_progress and stats.phases:
        phases_for_bars = []
        for phase_name, status in stats.phases:
            percent = 100 if status == "complete" else 0
            phases_for_bars.append((phase_name, percent))

        animate_progress_bars(
            phases_for_bars,
            speed=config.speed,
            safe_mode=config.is_safe,
            output=output,
        )
        output.write("\n")

    # Impact metrics (rich data only)
    if quest_data is not None:
        output.write(render_impact_metrics(quest_data, safe_mode=config.is_safe) + "\n")

    # Achievements (rich data only)
    if quest_data is not None and quest_data.achievements:
        output.write(render_achievements(quest_data.achievements, safe_mode=config.is_safe) + "\n")

    # Quality score (rich data only)
    if quest_data is not None:
        output.write(render_quality_score(quest_data.quality_score, safe_mode=config.is_safe) + "\n")

    # Trophy art
    if config.ascii_art:
        output.write(
            trophy_art(title_name, stats.tools_count, safe_mode=config.is_safe)
        )
        output.write("\n")

    # Quest complete message
    banner = box_banner("QUEST COMPLETE", width=78, safe_mode=config.is_safe)
    output.write(banner + "\n")
    output.write(f"  {title_name}\n\n")

    # End credits with scrolling
    if config.show_credits:
        if quest_data is not None:
            credit_lines = get_movie_credits_lines(quest_data, safe_mode=config.is_safe)
        else:
            stats_dict = {
                "name": stats.name,
                "tools_count": stats.tools_count,
                "tests_count": stats.tests_count,
                "bugs_fixed": stats.bugs_fixed,
                "pr_number": stats.pr_number,
                "duration_hours": stats.duration_hours,
            }
            credit_lines = get_credits_lines(stats_dict, safe_mode=config.is_safe)

        scroll_credits(credit_lines, speed=config.speed, output=output)


def render_silly(
    stats: QuestStats,
    config: CelebrationConfig,
    output: TextIO = sys.stdout,
    quest_data: Optional[QuestData] = None,
) -> None:
    """Render silly over-the-top celebration."""
    # Block-letter title
    if quest_data is not None:
        title_name = quest_data.name
    else:
        title_name = stats.name

    title_block = block_letter_title(
        title_name, safe_mode=config.is_safe, max_width=config.columns
    )
    output.write("\n")
    output.write(title_block + "\n")
    output.write("\n")

    # Fun intro with extra flair
    if not config.is_safe:
        output.write("    !!!  ***  !!!  ***  !!!  ***  !!!  ***\n")
        output.write("\n")

    # Battle the code gremlin!
    if config.ascii_art:
        output.write(gremlin_battle_art(stats.bugs_fixed, safe_mode=config.is_safe))
        output.write("\n")

    # Silly message
    if config.is_safe:
        output.write("THE CODE GREMLIN HAS BEEN VANQUISHED!\n")
        output.write("Your quest is complete!\n")
    else:
        output.write("    THE CODE GREMLIN HAS BEEN VANQUISHED!\n")
        output.write("    Your quest is complete!\n")

    output.write("\n")

    # Show stats with extra flair
    if stats.tools_count:
        output.write(f"    Tools forged in battle: {stats.tools_count}\n")
    if stats.tests_count:
        output.write(f"    Tests that guard the realm: {stats.tests_count}\n")
    if stats.bugs_fixed:
        output.write(f"    Bugs squashed: {stats.bugs_fixed}\n")

    output.write("\n")

    # Achievements with silly descriptions (rich data)
    if quest_data is not None and quest_data.achievements:
        output.write(render_achievements(quest_data.achievements, safe_mode=config.is_safe) + "\n")

    # Rocket launch
    if config.ascii_art:
        output.write(rocket_launch_art(safe_mode=config.is_safe))
        output.write("\n")

    # Silly retirement
    if config.is_safe:
        output.write("The gremlin is now enjoying retirement...\n")
    else:
        output.write(gremlin_retirement_art(safe_mode=config.is_safe))
        output.write("\n")

    # Scrolling credits in silly mode too
    if config.show_credits and quest_data is not None:
        credit_lines = get_movie_credits_lines(quest_data, safe_mode=config.is_safe)
        scroll_credits(credit_lines, speed=config.speed, output=output)

    # Final celebration
    if not config.is_safe:
        output.write("    !!!  ***  QUEST COMPLETE!  ***  !!!\n")


def render_end_credits(
    stats: QuestStats,
    config: CelebrationConfig,
    output: TextIO = sys.stdout,
) -> None:
    """Render scrolling end credits."""
    stats_dict = {
        "name": stats.name,
        "tools_count": stats.tools_count,
        "tests_count": stats.tests_count,
        "bugs_fixed": stats.bugs_fixed,
        "pr_number": stats.pr_number,
        "duration_hours": stats.duration_hours,
    }

    for line in get_credits_lines(stats_dict, safe_mode=config.is_safe):
        output.write(line + "\n")


def celebrate(
    quest_dir: Path,
    config: CelebrationConfig,
    output: TextIO = sys.stdout,
) -> int:
    """Main celebration dispatch function.

    Args:
        quest_dir: Path to quest directory
        config: Celebration configuration
        output: Output stream

    Returns:
        Exit code (0 for success, 1 for error)
    """
    if not quest_dir.exists():
        print(f"Error: Quest directory not found: {quest_dir}", file=sys.stderr)
        return 1

    # Load quest stats (legacy, lightweight)
    stats = load_quest_stats(quest_dir)

    # Check if animations are disabled
    if not config.enabled:
        output.write(render_minimal(stats, config) + "\n")
        return 0

    # Dispatch to appropriate renderer
    if config.style == "minimal":
        output.write(render_minimal(stats, config) + "\n")
    elif config.style == "standard":
        output.write(render_standard(stats, config) + "\n")
    elif config.style == "epic":
        quest_data = load_quest_data(quest_dir)
        render_epic(stats, config, output, quest_data=quest_data)
    elif config.style == "silly":
        quest_data = load_quest_data(quest_dir)
        render_silly(stats, config, output, quest_data=quest_data)
    else:
        # Fallback to standard
        output.write(render_standard(stats, config) + "\n")

    return 0
