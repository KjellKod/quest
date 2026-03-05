"""ASCII art templates for quest celebrations."""

from typing import List


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

    return """\n      .-\"\"\"-.\n     /  ^ ^  \\\n    |   o o   |   👾💤\n    |   \\_/   |  \n     \\  ===  /   Now with pension\n      '-...-'    and healthcare!\n    """


def rocket_launch_art(safe_mode: bool = False) -> str:
    """Return rocket launch ASCII art."""
    if safe_mode:
        return """\n          |\n         / \\\n        /___\\\n        |   |\n        |   |\n       /| | |\\\n      / | | | \\\n     |  | | |  |\n     |  | | |  |\n      \\ | | | /\n       \\|_|_/\n        /   \\\n       /     \\\n    """

    return """\n          |\n         / \\\n        /🚀 \\\n        |   |\n        |   |\n       /| | |\\\n      / | | | \\\n     |  | | |  |\n     |  | | |  |\n      \\ | | | /\n       \\|_|_/\n        /   \\\n       /     \\\n    """


def banner_border(width: int = 78, safe_mode: bool = False) -> str:
    """Return a banner border line."""
    if safe_mode:
        return "=" * width
    return "═" * width


def box_banner(text: str, width: int = 78, safe_mode: bool = False) -> str:
    """Return text wrapped in a box banner."""
    if safe_mode:
        top = "+" + "-" * (width - 2) + "+"
        bottom = "+" + "-" * (width - 2) + "+"
        middle = f"| {text:<{width - 4}} |"
    else:
        top = "╔" + "═" * (width - 2) + "╗"
        bottom = "╚" + "═" * (width - 2) + "╝"
        middle = f"║ {text:<{width - 4}} ║"

    return f"{top}\n{middle}\n{bottom}"


def get_credits_lines(quest_stats: dict, safe_mode: bool = False) -> List[str]:
    """Generate end credits lines."""
    lines = []

    if safe_mode:
        header = "END CREDITS"
    else:
        header = "🎬 END CREDITS 🎬"

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
        lines.append("✨ Thank you for using Quest! ✨")

    return lines
