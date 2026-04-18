"""Animation renderers and quest stats for celebrations."""

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, TextIO, Tuple

from quest_celebrate.ascii_art import (
    block_letter_title,
    get_credits_lines,
    get_movie_credits_lines,
    gremlin_battle_art,
    gremlin_retirement_art,
    render_achievements,
    render_quality_score,
    rocket_launch_art,
    trophy_art,
)
from quest_celebrate.config import CelebrationConfig
from quest_celebrate.progress import (
    animate_progress_bars,
    render_phase_progress,
    scroll_credits,
)
from quest_celebrate.quest_data import QUALITY_TIERS, QuestData, load_quest_data


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


def _build_reliability_lines(quest_data: Optional[QuestData]) -> List[str]:
    """Build concise handoff/reliability lines from quest artifacts."""
    if quest_data is None:
        return []

    handoff_count = len(quest_data.agents)
    reviewer_handoffs = len(
        [agent for agent in quest_data.agents if "reviewer" in agent.name.lower()]
    )
    fixer_handoffs = len(
        [agent for agent in quest_data.agents if "fixer" in agent.name.lower()]
    )

    reliability = "high"
    if quest_data.plan_iterations > 2 or quest_data.fix_iterations > 1:
        reliability = "medium"
    if quest_data.fix_iterations > 2:
        reliability = "recovering"

    return [
        f"Handoffs parsed: {handoff_count}",
        f"Reviewer handoffs: {reviewer_handoffs}",
        f"Fixer handoffs: {fixer_handoffs}",
        f"Review findings tracked: {len(quest_data.review_findings)}",
        f"Stability: plan={quest_data.plan_iterations}, fix={quest_data.fix_iterations}",
        f"Reliability signal: {reliability}",
    ]


def _carryover_sections_markdown(quest_data: Optional[QuestData]) -> str:
    """Render artifact-backed carry-over findings for markdown-first outputs."""
    if quest_data is None:
        return ""

    inherited = quest_data.inherited_findings_used
    future = quest_data.findings_left_for_future_quests
    if inherited.count <= 0 and future.count <= 0:
        return "\n".join(
            [
                "## Carry-Over Findings",
                "",
                "- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.",
                "",
            ]
        )

    sections: List[str] = []
    carryover_sets = (
        ("Inherited Findings Used", inherited),
        (
            "Findings Left For Future Quests",
            future,
        ),
    )
    for title, carryover in carryover_sets:
        if carryover.count <= 0:
            continue
        sections.append(f"## {title}")
        sections.append("")
        sections.append(f"- Count: **{carryover.count}**")
        for summary in carryover.summaries[:3]:
            sections.append(f"- {summary}")
        sections.append("")

    return "\n".join(sections)


def _carryover_lines_standard(quest_data: Optional[QuestData]) -> List[str]:
    """Render artifact-backed carry-over findings for standard text output."""
    if quest_data is None:
        return []

    inherited = quest_data.inherited_findings_used
    future = quest_data.findings_left_for_future_quests
    if inherited.count <= 0 and future.count <= 0:
        return [
            "    Carry-Over Findings",
            "    No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.",
            "",
        ]

    lines: List[str] = []
    carryover_sets = (
        ("Inherited Findings Used", inherited),
        (
            "Findings Left For Future Quests",
            future,
        ),
    )
    for title, carryover in carryover_sets:
        if carryover.count <= 0:
            continue
        lines.append(f"    {title}")
        lines.append(f"    Count: {carryover.count}")
        for summary in carryover.summaries[:3]:
            lines.append(f"    - {summary}")
        lines.append("")

    return lines


def render_minimal(stats: QuestStats, config: CelebrationConfig) -> str:
    """Render minimal one-line celebration."""
    emoji_check = "" if config.is_safe else ""
    emoji_pkg = "" if config.is_safe else ""
    emoji_test = "" if config.is_safe else ""

    tools = f"| {emoji_pkg}{stats.tools_count} tools" if stats.tools_count else ""
    tests = f"| {emoji_test}{stats.tests_count} tests" if stats.tests_count else ""

    return f"{emoji_check}Quest Complete: {stats.name} {tools} {tests}".strip()


def render_standard(
    stats: QuestStats,
    config: CelebrationConfig,
    output: Optional[TextIO] = None,
    quest_data: Optional[QuestData] = None,
) -> str:
    """Render standard celebration and optionally write to output.

    Returns a string for backwards compatibility with existing tests/callers.
    If output is provided, also writes the rendered text to that stream.
    """
    if quest_data is not None:
        title_name = quest_data.name
        quest_id = quest_data.quest_id
    else:
        title_name = stats.name
        quest_id = stats.quest_id

    lines: List[str] = []
    lines.append("")
    if config.is_safe:
        lines.append("+------------------------------------------------------------+")
        lines.append("|                       QUEST COMPLETE                       |")
        lines.append("+------------------------------------------------------------+")
    else:
        lines.append("╔══════════════════════════════════════════════════════════════╗")
        lines.append("║          ✨ QUEST COMPLETE ✨                                ║")
        lines.append("╚══════════════════════════════════════════════════════════════╝")
    lines.append("")

    lines.append(f"    {title_name}")
    if quest_id:
        lines.append(f"    {quest_id}")
    lines.append("")

    if quest_data is not None and quest_data.achievements:
        lines.append("    ACHIEVEMENTS" if config.is_safe else "    🏆 ACHIEVEMENTS")
        lines.append("")
        for ach in quest_data.achievements:
            prefix = "*" if config.is_safe else "⭐️"
            model = f" ({ach.attribution})" if ach.attribution else ""
            lines.append(f"    {prefix} {ach.title}{model}")
        lines.append("")

    reliability_lines = _build_reliability_lines(quest_data)
    if reliability_lines:
        lines.append("    HANDOFF & RELIABILITY")
        lines.append("")
        for line in reliability_lines:
            lines.append(f"    - {line}")
        lines.append("")

    carryover_lines = _carryover_lines_standard(quest_data)
    if carryover_lines:
        lines.extend(carryover_lines)

    lines.append("    QUEST STATS" if config.is_safe else "    📊 QUEST STATS")
    lines.append("")
    if quest_data:
        lines.append(f"    Plan iterations: {quest_data.plan_iterations}")
        lines.append(f"    Fix iterations: {quest_data.fix_iterations}")
        lines.append(f"    Review findings: {len(quest_data.review_findings)}")
    else:
        lines.append(f"    Plan iterations: {stats.plan_iterations}")
        lines.append(f"    Fix iterations: {stats.fix_iterations}")

    if stats.tools_count:
        lines.append(f"    Tools: {stats.tools_count}")
    if stats.tests_count:
        lines.append(f"    Tests: {stats.tests_count}")
    if stats.bugs_fixed:
        lines.append(f"    Bugs fixed: {stats.bugs_fixed}")
    if stats.pr_number is not None:
        lines.append(f"    PR: #{stats.pr_number}")

    lines.append("")

    if config.ascii_art:
        lines.append(
            trophy_art(title_name, stats.tools_count, safe_mode=config.is_safe)
        )
        lines.append("")

    lines.append(
        "    Quest workflow complete!"
        if config.is_safe
        else "    🎉 Quest workflow complete! 🚀"
    )
    lines.append("")

    rendered = "\n".join(lines)
    if output is not None:
        output.write(rendered)
    return rendered


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
    # Get quest info
    if quest_data is not None:
        title_name = quest_data.name
        quest_id = quest_data.quest_id
    else:
        title_name = stats.name
        quest_id = stats.quest_id

    def quest_quote() -> Optional[str]:
        if quest_data is None:
            return None

        priority = ("arbiter", "code-reviewer", "fixer", "builder", "planner")
        for role in priority:
            for agent in quest_data.agents:
                if role in agent.name.lower() and agent.summary.strip():
                    return agent.summary.strip()

        for finding in quest_data.review_findings:
            if finding.strip():
                return finding.strip()

        return None

    # Markdown-first header (closer to celebrate skill output intent)
    output.write("\n")
    output.write(f"# 🎉 QUEST COMPLETE — {title_name}\n\n")
    if quest_id:
        output.write(f"**Quest ID:** `{quest_id}`  \n")
    output.write("**Status:** `approved` -> `archived`\n\n")

    # Extract short name from slug for block letters
    if quest_data and quest_data.slug:
        slug_words = quest_data.slug.replace("-", " ").upper().split()
    elif stats.slug:
        slug_words = stats.slug.replace("-", " ").upper().split()
    else:
        slug_words = title_name.upper().split()

    word1 = slug_words[0][:5] if len(slug_words) > 0 else "QUEST"
    word2 = slug_words[1][:6] if len(slug_words) > 1 else ""

    output.write("```text\n")
    title_block1 = block_letter_title(word1, safe_mode=config.is_safe, max_width=70)
    output.write(title_block1 + "\n")

    if word2:
        title_block2 = block_letter_title(word2, safe_mode=config.is_safe, max_width=70)
        output.write(title_block2 + "\n")
    output.write("```\n\n")
    output.write("---\n\n")

    # Brief summary
    if quest_data and quest_data.brief_summary:
        output.write(f"{quest_data.brief_summary}\n\n")

    # Phase progress bars
    if config.show_progress and stats.phases:
        output.write("## ⚙️ Phase Progress\n\n")
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

    # Impact metrics (markdown-first)
    if quest_data is not None:
        output.write("## 🎯 IMPACT METRICS\n\n")
        output.write(
            f"- Review findings addressed: **{len(quest_data.review_findings)}**\n"
        )
        output.write(f"- Review rounds completed: **{quest_data.review_count}**\n")
        output.write(
            f"- Plan stabilized in **{quest_data.plan_iterations}** iteration(s)\n"
        )
        output.write(
            f"- Fix loop completed in **{quest_data.fix_iterations}** pass(es)\n"
        )
        if quest_data.pr_number is not None:
            output.write(f"- Shipping artifact: **PR #{quest_data.pr_number}**\n")
        output.write("\n")

    # Achievements (rich data only)
    if quest_data is not None and quest_data.achievements:
        output.write("## 🏆 Achievements\n\n")
        for ach in quest_data.achievements:
            marker = "*" if config.is_safe else "⭐️"
            model = f" ({ach.attribution})" if ach.attribution else ""
            output.write(f"- {marker} **{ach.title}{model}** — {ach.description}\n")
        output.write("\n")

    reliability_lines = _build_reliability_lines(quest_data)
    if reliability_lines:
        output.write("## 🛡️ Handoff & Reliability\n\n")
        for line in reliability_lines:
            output.write(f"- {line}\n")
        output.write("\n")

    carryover_sections = _carryover_sections_markdown(quest_data)
    if carryover_sections:
        output.write(carryover_sections)

    # Quality score (rich data only)
    if quest_data is not None:
        tier = quest_data.quality_tier or "Unknown"
        tier_icon = QUALITY_TIERS.get(tier, ("⭐️", "", ""))[0]
        output.write(f"## {tier_icon} Quality Tier: **{tier}**\n\n")
        output.write(
            render_quality_score(quest_data.quality_score, safe_mode=config.is_safe)
        )
        output.write("\n")

    quote = quest_quote()
    if quote:
        output.write('> "' + quote.replace("\n", " ").strip() + '"\n\n')

    # Gremlin Battle (if there were review findings)
    if config.ascii_art and quest_data and len(quest_data.review_findings) > 0:
        output.write("\n")
        output.write(
            gremlin_battle_art(
                len(quest_data.review_findings), safe_mode=config.is_safe
            )
        )
        output.write("\n")

    # Trophy art
    if config.ascii_art:
        output.write(
            trophy_art(title_name, stats.tools_count, safe_mode=config.is_safe)
        )
        output.write("\n")

    # Rocket Launch
    if config.ascii_art:
        output.write(rocket_launch_art(safe_mode=config.is_safe))
        output.write("\n")

    output.write("## 🚀 Victory Narrative\n\n")
    output.write(
        "**Victory Unlocked!** 🎮\n\n"
        if not config.is_safe
        else "Victory Unlocked!\n\n"
    )
    output.write(
        "This quest proved that disciplined orchestration ships clean results under review pressure. "
    )
    if stats.plan_iterations > 1:
        output.write(f"Planning adapted across **{stats.plan_iterations}** passes, ")
    else:
        output.write("Planning held steady on the first pass, ")
    output.write(
        f"fixes converged in **{stats.fix_iterations}** loop(s), and the final handoff landed with confidence.\n\n"
    )

    # End credits with scrolling
    if config.show_credits:
        output.write("## 🎬 Credits\n\n")
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

    # Gremlin Retirement (the happy ending)
    if config.ascii_art:
        output.write("\n")
        output.write(gremlin_retirement_art(safe_mode=config.is_safe))
        output.write("\n")


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
        output.write(
            render_achievements(quest_data.achievements, safe_mode=config.is_safe)
            + "\n"
        )

    reliability_lines = _build_reliability_lines(quest_data)
    if reliability_lines:
        output.write("Handoff and reliability gossip:\n")
        for line in reliability_lines:
            output.write(f"- {line}\n")
        output.write("\n")

    carryover_sections = _carryover_sections_markdown(quest_data)
    if carryover_sections:
        output.write(carryover_sections)

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
    quest_data = load_quest_data(quest_dir)

    # Check if animations are disabled
    if not config.enabled:
        output.write(render_minimal(stats, config) + "\n")
        return 0

    # Dispatch to appropriate renderer
    if config.style == "minimal":
        output.write(render_minimal(stats, config))
        reliability_lines = _build_reliability_lines(quest_data)
        if reliability_lines:
            output.write(
                f" | handoffs {len(quest_data.agents)} | reviews {quest_data.review_count}"
            )
        output.write("\n")
    elif config.style == "standard":
        standard_text = render_standard(
            stats, config, output=None, quest_data=quest_data
        )
        scroll_credits(standard_text.split("\n"), speed=config.speed, output=output)
    elif config.style == "epic":
        render_epic(stats, config, output, quest_data=quest_data)
    elif config.style == "silly":
        render_silly(stats, config, output, quest_data=quest_data)
    else:
        # Fallback to standard
        standard_text = render_standard(
            stats, config, output=None, quest_data=quest_data
        )
        scroll_credits(standard_text.split("\n"), speed=config.speed, output=output)

    if config.style != "minimal":
        output.write("\n")

    return 0
