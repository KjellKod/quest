"""ASCII art templates for quest celebrations."""

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from quest_celebrate.quest_data import Achievement, AgentInfo, QuestData

from quest_celebrate.quest_data import friendly_model_name

# Minimal 5-line tall block letter font for A-Z, 0-9, space, and hyphen.
# Each character is 6 columns wide (5 + 1 space separator).
_BLOCK_FONT = {
    "A": [
        " ### ",
        "#   #",
        "#####",
        "#   #",
        "#   #",
    ],
    "B": [
        "#### ",
        "#   #",
        "#### ",
        "#   #",
        "#### ",
    ],
    "C": [
        " ####",
        "#    ",
        "#    ",
        "#    ",
        " ####",
    ],
    "D": [
        "#### ",
        "#   #",
        "#   #",
        "#   #",
        "#### ",
    ],
    "E": [
        "#####",
        "#    ",
        "###  ",
        "#    ",
        "#####",
    ],
    "F": [
        "#####",
        "#    ",
        "###  ",
        "#    ",
        "#    ",
    ],
    "G": [
        " ####",
        "#    ",
        "# ###",
        "#   #",
        " ####",
    ],
    "H": [
        "#   #",
        "#   #",
        "#####",
        "#   #",
        "#   #",
    ],
    "I": [
        "#####",
        "  #  ",
        "  #  ",
        "  #  ",
        "#####",
    ],
    "J": [
        "#####",
        "    #",
        "    #",
        "#   #",
        " ### ",
    ],
    "K": [
        "#   #",
        "#  # ",
        "###  ",
        "#  # ",
        "#   #",
    ],
    "L": [
        "#    ",
        "#    ",
        "#    ",
        "#    ",
        "#####",
    ],
    "M": [
        "#   #",
        "## ##",
        "# # #",
        "#   #",
        "#   #",
    ],
    "N": [
        "#   #",
        "##  #",
        "# # #",
        "#  ##",
        "#   #",
    ],
    "O": [
        " ### ",
        "#   #",
        "#   #",
        "#   #",
        " ### ",
    ],
    "P": [
        "#### ",
        "#   #",
        "#### ",
        "#    ",
        "#    ",
    ],
    "Q": [
        " ### ",
        "#   #",
        "# # #",
        "#  # ",
        " ## #",
    ],
    "R": [
        "#### ",
        "#   #",
        "#### ",
        "#  # ",
        "#   #",
    ],
    "S": [
        " ####",
        "#    ",
        " ### ",
        "    #",
        "#### ",
    ],
    "T": [
        "#####",
        "  #  ",
        "  #  ",
        "  #  ",
        "  #  ",
    ],
    "U": [
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        " ### ",
    ],
    "V": [
        "#   #",
        "#   #",
        "#   #",
        " # # ",
        "  #  ",
    ],
    "W": [
        "#   #",
        "#   #",
        "# # #",
        "## ##",
        "#   #",
    ],
    "X": [
        "#   #",
        " # # ",
        "  #  ",
        " # # ",
        "#   #",
    ],
    "Y": [
        "#   #",
        " # # ",
        "  #  ",
        "  #  ",
        "  #  ",
    ],
    "Z": [
        "#####",
        "   # ",
        "  #  ",
        " #   ",
        "#####",
    ],
    "0": [
        " ### ",
        "#   #",
        "#   #",
        "#   #",
        " ### ",
    ],
    "1": [
        "  #  ",
        " ##  ",
        "  #  ",
        "  #  ",
        "#####",
    ],
    "2": [
        " ### ",
        "#   #",
        "  ## ",
        " #   ",
        "#####",
    ],
    "3": [
        " ### ",
        "#   #",
        "  ## ",
        "#   #",
        " ### ",
    ],
    "4": [
        "#   #",
        "#   #",
        "#####",
        "    #",
        "    #",
    ],
    "5": [
        "#####",
        "#    ",
        "#### ",
        "    #",
        "#### ",
    ],
    "6": [
        " ### ",
        "#    ",
        "#### ",
        "#   #",
        " ### ",
    ],
    "7": [
        "#####",
        "    #",
        "   # ",
        "  #  ",
        "  #  ",
    ],
    "8": [
        " ### ",
        "#   #",
        " ### ",
        "#   #",
        " ### ",
    ],
    "9": [
        " ### ",
        "#   #",
        " ####",
        "    #",
        " ### ",
    ],
    " ": [
        "     ",
        "     ",
        "     ",
        "     ",
        "     ",
    ],
    "-": [
        "     ",
        "     ",
        "#####",
        "     ",
        "     ",
    ],
}

# Character width including separator
_CHAR_WIDTH = 6


def block_letter_title(text: str, safe_mode: bool = False, max_width: int = 80) -> str:
    """Render quest name in big ASCII block letters.

    Falls back to a simple centered banner if the rendered title exceeds
    max_width or if any character is not in the font.

    Args:
        text: The text to render.
        safe_mode: If True, use ASCII-only characters (block font is always ASCII).
        max_width: Maximum terminal width. Titles wider than this get fallback.

    Returns:
        Multi-line string with the block letter rendering.
    """
    upper = text.upper()

    # Check if all characters are in the font
    if not all(ch in _BLOCK_FONT for ch in upper):
        return _fallback_banner(text, max_width)

    # Check if rendered width fits
    rendered_width = len(upper) * _CHAR_WIDTH - 1  # subtract trailing separator
    if rendered_width > max_width:
        return _fallback_banner(text, max_width)

    # Build the 5 lines
    rows = []
    for row_idx in range(5):
        parts = []
        for ch in upper:
            parts.append(_BLOCK_FONT[ch][row_idx])
        rows.append(" ".join(parts))

    # Font source is ASCII '#'. In Unicode mode, render with solid blocks.
    if not safe_mode:
        rows = [row.replace("#", "█") for row in rows]

    return "\n".join(rows)


def _fallback_banner(text: str, max_width: int) -> str:
    """Simple centered banner for names that don't fit block letters."""
    border = "=" * min(max_width, max(len(text) + 8, 40))
    centered = text.center(len(border))
    return f"{border}\n{centered}\n{border}"


def render_achievements(
    achievements: "List[Achievement]", safe_mode: bool = False
) -> str:
    """Render achievements as a formatted section."""
    if not achievements:
        return ""

    lines = []
    if safe_mode:
        lines.append("    ACHIEVEMENTS UNLOCKED\n")
        for ach in achievements:
            model = f" ({ach.attribution})" if getattr(ach, "attribution", "") else ""
            lines.append(f"    * {ach.title}{model} - {ach.description}")
    else:
        lines.append("    🏆 ACHIEVEMENTS UNLOCKED 🏆\n")
        for ach in achievements:
            model = f" ({ach.attribution})" if getattr(ach, "attribution", "") else ""
            lines.append(f"    ⭐️ {ach.title}{model} - {ach.description}")

    lines.append("")
    return "\n".join(lines)


def render_impact_metrics(quest_data: "QuestData", safe_mode: bool = False) -> str:
    """Render impact metrics in a formatted grid."""
    lines = []
    if safe_mode:
        lines.append("IMPACT METRICS")
    else:
        lines.append("\U0001f4ca IMPACT METRICS")

    lines.append("-" * 40)

    lines.append(f"  Agents Involved:    {len(quest_data.agents)}")
    lines.append(f"  Files Changed:      {len(quest_data.files_changed)}")
    lines.append(f"  Plan Iterations:    {quest_data.plan_iterations}")
    lines.append(f"  Fix Iterations:     {quest_data.fix_iterations}")
    lines.append(f"  Review Findings:    {len(quest_data.review_findings)}")
    lines.append(f"  Reviews Conducted:  {quest_data.review_count}")

    if quest_data.pr_number is not None:
        lines.append(f"  PR Number:          #{quest_data.pr_number}")

    lines.append("")
    return "\n".join(lines)


def render_quality_score(score: int, safe_mode: bool = False) -> str:
    """Render quality score as a visual bar with letter grade."""
    # Map score to letter grade
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"

    bar_width = 20
    filled = int(bar_width * score / 100)
    empty = bar_width - filled

    if safe_mode:
        bar = "=" * filled + "-" * empty
    else:
        bar = "\u2588" * filled + "\u2591" * empty

    lines = [
        "QUALITY SCORE",
        "-" * 40,
        f"  [{bar}] {score}% (Grade: {grade})",
        "",
    ]
    return "\n".join(lines)


def trophy_art(quest_name: str, tool_count: int = 0, safe_mode: bool = False) -> str:
    """Return trophy ASCII art."""
    if safe_mode:
        return """\n    ___________\n   '._==_==_=_.'\n   .-\\:      /-.\n  | (|:.     |) |\n   '-|:.     |-'\n     \\::.    /\n      '::. .'\n        ) (\n      _.' '._\n     """

    return """\n    🏆___________🏆\n   '._==_==_=_.'\n   .-\\:      /-.\n  | (|:.     |) |\n   '-|:.     |-'\n     \\::.    /\n      '::. .'\n        ) (\n      _.' '._\n     """


def gremlin_battle_art(bugs_fixed: int = 0, safe_mode: bool = False) -> str:
    """Return gremlin battle ASCII art."""
    if safe_mode:
        return """\n      .-\"\"\"-.\n     /       \\\n    |  O   O  |\n    |   ___   |\n     \\  '-`  /\n      '-...-'\n    DEFEATED!\n    """

    return """\n      .-\"\"\"-.\n     /       \\\n    |  O   O  |   👾\n    |   ___   |  Code Gremlin\n     \\  '-`  /   VANQUISHED!\n      '-...-'\n    """


def gremlin_retirement_art(safe_mode: bool = False) -> str:
    """Return gremlin retirement ASCII art (silly style)."""
    if safe_mode:
        return """\n      .-\"\"\"-.\n     /  ^ ^  \\\n    |   o o   |\n    |   \\_/   |\n     \\  ===  /\n      '-...-'\n    ~ Now with pension ~\n    """

    return """\n      .-\"\"\"-.\n     /  ^ ^  \\\n    |   o o   |   👾💤\n    |   \\_/   |  \n     \\  ===  /   Now with pension\n      '-...-'    and zero on-call!\n    """


def rocket_launch_art(safe_mode: bool = False) -> str:
    """Return rocket launch ASCII art."""
    if safe_mode:
        return """\n          |\n         / \\\n        /___\\\n        |   |\n        |   |\n       /| | |\\\n      / | | | \\\n     |  | | |  |\n     |  | | |  |\n      \\ | | | /\n       \\|_|_/\n        /   \\\n       /     \\\n    """

    return """\n          |\n         / \\\n        /🚀 \\\n        |   |\n        |   |\n       /| | |\\\n      / | | | \\\n     |  | | |  |\n     |  | | |  |\n      \\ | | | /\n       \\|_|_/\n        /   \\\n       /     \\\n    """


def banner_border(width: int = 78, safe_mode: bool = False) -> str:
    """Return a banner border line."""
    if safe_mode:
        return "=" * width
    return "\u2550" * width


def box_banner(text: str, width: int = 78, safe_mode: bool = False) -> str:
    """Return text wrapped in a box banner."""
    if safe_mode:
        top = "+" + "-" * (width - 2) + "+"
        bottom = "+" + "-" * (width - 2) + "+"
        middle = f"| {text:<{width - 4}} |"
    else:
        top = "+" + "=" * (width - 2) + "+"
        bottom = "+" + "=" * (width - 2) + "+"
        middle = f"| {text:<{width - 4}} |"

    return f"{top}\n{middle}\n{bottom}"


def get_credits_lines(quest_stats: dict, safe_mode: bool = False) -> List[str]:
    """Generate end credits lines (legacy dict-based API).

    For rich credits from QuestData, use get_movie_credits_lines() instead.
    """
    lines = []

    if safe_mode:
        header = "END CREDITS"
    else:
        header = "\U0001f3ac END CREDITS \U0001f3ac"

    lines.append("")
    lines.append(header)
    lines.append("")

    # Add stats if available
    name = quest_stats.get("name", "Unknown Quest")
    lines.append(f"Quest: {name}")

    if quest_stats.get("tools_count"):
        lines.append(f"Tools Created: {quest_stats['tools_count']}")
    if quest_stats.get("tests_count"):
        lines.append(f"Tests Added: {quest_stats['tests_count']}")
    if quest_stats.get("bugs_fixed"):
        lines.append(f"Bugs Vanquished: {quest_stats['bugs_fixed']}")
    if quest_stats.get("pr_number"):
        lines.append(f"PR: #{quest_stats['pr_number']}")
    if quest_stats.get("duration_hours"):
        lines.append(f"Duration: {quest_stats['duration_hours']:.1f} hours")

    lines.append("")

    if safe_mode:
        lines.append("Thank you for using Quest!")
    else:
        lines.append("\u2728 Thank you for using Quest! \u2728")

    return lines


def get_movie_credits_lines(
    quest_data: "QuestData", safe_mode: bool = False
) -> List[str]:
    """Generate full movie-style end credits from QuestData.

    Sections: THE END banner, A QUEST PRODUCTION, quest name, STARRING
    (agents + role titles), CREW, SPECIAL ACHIEVEMENTS, FAMOUS LAST WORDS,
    total stats, and gremlin retirement closing.
    """
    lines: List[str] = []
    sep = "=" * 72

    # THE END banner
    lines.append("")
    lines.append(sep)
    if safe_mode:
        lines.append("              THE END")
    else:
        lines.append("              \U0001f3ac THE END \U0001f3ac")
    lines.append(sep)
    lines.append("")
    lines.append("          A QUEST PRODUCTION")
    lines.append("")
    lines.append(f'          "{quest_data.name}"')
    lines.append("")

    # STARRING section
    if quest_data.agents:
        lines.append("  STARRING")
        lines.append("")
        seen = set()
        for agent in quest_data.agents:
            key = (agent.name, agent.model)
            if key in seen:
                continue
            seen.add(key)

            model_label = friendly_model_name(agent.model)
            if model_label:
                name_part = f"{agent.name} [{model_label}]"
            else:
                name_part = agent.name
            role_part = agent.role_title
            dots = "." * max(4, 50 - len(name_part) - len(role_part))
            lines.append(f"    {name_part} {dots} {role_part}")
        lines.append("")

    # CREW section
    lines.append("  CREW")
    lines.append("")
    lines.append("    GitHub API ............ Comment Threader")
    lines.append("    Quest Orchestrator .... The Director")
    lines.append("    pytest ................ Truth Teller")
    lines.append("")

    # SPECIAL ACHIEVEMENTS
    if quest_data.achievements:
        lines.append("  SPECIAL ACHIEVEMENTS")
        lines.append("")
        for ach in quest_data.achievements:
            model = f" ({ach.attribution})" if getattr(ach, "attribution", "") else ""
            lines.append(f'    {ach.icon} "{ach.title}{model}" - {ach.description}')
        lines.append("")

    # FAMOUS LAST WORDS
    # Pick the last agent summary as the quote, or use a default
    quote = "Shipping should feel like a celebration."
    quote_attribution = "Quest Framework"
    if quest_data.agents:
        last_agent = quest_data.agents[-1]
        if last_agent.summary:
            quote = last_agent.summary
            quote_attribution = last_agent.name

    lines.append("  FAMOUS LAST WORDS")
    lines.append("")
    # Wrap quote to ~55 chars
    if len(quote) > 55:
        quote = quote[:52] + "..."
    lines.append(f'    "{quote}"')
    lines.append(f"    -- {quote_attribution}")
    lines.append("")

    # Stats summary
    lines.append(sep)
    lines.append(f"    AGENTS DEPLOYED:   {len(quest_data.agents)}")
    lines.append(f"    FILES CHANGED:     {len(quest_data.files_changed)}")
    lines.append(f"    REVIEWS CONDUCTED: {quest_data.review_count}")
    lines.append(sep)
    lines.append("")

    # Gremlin retirement closing
    if safe_mode:
        lines.append("  ...and the gremlin lived happily ever after")
        lines.append("     on a farm, chasing butterflies.")
    else:
        lines.append("  ...and the gremlin lived happily ever after \U0001f33b")
        lines.append("     on a farm, chasing butterflies. \U0001f98b")
    lines.append("")
    lines.append("THE END. REALLY. FIN.")
    lines.append("")

    return lines
