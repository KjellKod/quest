"""Progress bar rendering for quest celebrations."""

import sys
import time
from typing import List, TextIO, Tuple


def render_progress_bar(
    percent: int,
    detail: str,
    width: int = 30,
    safe_mode: bool = False,
) -> str:
    """Render a single progress bar.

    Args:
        percent: Percentage complete (0-100)
        detail: Description text to show after bar
        width: Width of the bar itself (not including brackets/padding)
        safe_mode: If True, use ASCII characters only

    Returns:
        Formatted progress bar string
    """
    filled = int(width * percent / 100)
    empty = width - filled

    # Always use ASCII for progress bars — Unicode blocks render
    # poorly in many terminals. Emojis work much better as indicators.
    bar = "=" * filled + "-" * empty

    # Add emoji indicator based on progress
    if safe_mode:
        return f"[{bar}] {percent:3}% - {detail}"

    if percent >= 100:
        emoji = "✅"
    elif percent >= 75:
        emoji = "🔄"
    elif percent >= 25:
        emoji = "⚡"
    else:
        emoji = "🚀"

    return f"{emoji} [{bar}] {percent:3}% - {detail}"


def animate_progress_bars(
    phases: List[Tuple[str, int]],
    speed: str = "default",
    safe_mode: bool = False,
    output: TextIO = sys.stdout,
) -> None:
    """Animate progress bars through a sequence of phases.

    Args:
        phases: List of (detail_text, target_percent) tuples
        speed: Animation speed ("fast", "default", "slow")
        safe_mode: Use ASCII-only characters
        output: Output stream (default sys.stdout)
    """
    # Determine delay based on speed
    # These are TOTAL delays for the full animation (divided by 5 steps)
    # Timing per phase: fast=~0.4s, default=~2.4s, slow=~6.4s
    if speed == "fast":
        delay = 0.4
    elif speed == "slow":
        delay = 6.4
    else:  # default
        delay = 2.4

    # Clear any previous output and start fresh
    for phase_idx, (detail, target_percent) in enumerate(phases):
        # Animate from 0 to target
        steps = 5
        for step in range(1, steps + 1):
            percent = int(target_percent * step / steps)
            bar = render_progress_bar(percent, detail, width=30, safe_mode=safe_mode)
            # Clear line and write new bar
            output.write(f"\r{bar}")
            output.flush()
            if step < steps:  # Don't delay on final step
                time.sleep(delay / steps)

        # Move to next line after completing this phase
        output.write("\n")
        output.flush()

        # Small pause between phases
        if phase_idx < len(phases) - 1:
            time.sleep(delay / steps * 0.5)


def render_phase_progress(
    phases: List[Tuple[str, str]],
    safe_mode: bool = False,
    output: TextIO = sys.stdout,
) -> None:
    """Render progress for quest phases with status indicators.

    Args:
        phases: List of (phase_name, status) tuples where status is
                "complete", "in_progress", or "pending"
        safe_mode: Use ASCII-only characters
        output: Output stream (default sys.stdout)
    """
    for name, status in phases:
        if safe_mode:
            if status == "complete":
                indicator = "[OK]"
            elif status == "in_progress":
                indicator = "[..]"
            else:
                indicator = "[  ]"
        else:
            if status == "complete":
                indicator = "[OK]"
            elif status == "in_progress":
                indicator = "[..]"
            else:
                indicator = "[  ]"

        line = f"{indicator} {name}"
        output.write(line + "\n")

    output.flush()


def scroll_credits(
    lines: List[str],
    speed: str = "default",
    output: TextIO = sys.stdout,
) -> None:
    """Print lines with per-line delay for cinematic credit scrolling.

    Args:
        lines: Credit lines to scroll.
        speed: Scroll speed ("fast", "default", "slow").
            fast: 0.02s/line, default: 0.15s/line, slow: 0.3s/line.
        output: Output stream.
    """
    if speed == "fast":
        delay = 0.02
    elif speed == "slow":
        delay = 0.3
    else:  # default
        delay = 0.15

    for line in lines:
        output.write(line + "\n")
        output.flush()
        time.sleep(delay)
