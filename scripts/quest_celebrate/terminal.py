"""Terminal capability detection for quest celebrations."""

import os
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class TerminalCaps:
    """Terminal capabilities for celebration rendering."""

    supports_unicode: bool
    supports_emoji: bool
    is_interactive: bool
    is_ci: bool
    columns: int


def _get_columns() -> int:
    """Get terminal width, defaulting to 80."""
    try:
        import shutil

        cols, _ = shutil.get_terminal_size()
        return max(40, min(cols, 200))
    except Exception:
        return 80


def _check_ci() -> bool:
    """Check if running in a CI environment."""
    ci_envs = [
        "CI",
        "GITHUB_ACTIONS",
        "JENKINS",
        "JENKINS_URL",
        "GITLAB_CI",
        "CIRCLECI",
        "TRAVIS",
        "DRONE",
        "BUILDKITE",
        "TF_BUILD",  # Azure Pipelines
    ]
    return any(os.environ.get(env) for env in ci_envs)


def _check_unicode_support() -> bool:
    """Check if terminal supports Unicode block characters."""
    term = os.environ.get("TERM", "").lower()

    # TERM=dumb is a clear no-unicode signal
    if term == "dumb":
        return False

    # Known good terminals
    good_terms = ["xterm", "screen", "tmux", "rxvt", "eterm", "st", "alacritty"]
    if any(t in term for t in good_terms):
        return True

    # VS Code terminal (may have issues with some Unicode)
    if "vscode" in term or os.environ.get("TERM_PROGRAM") == "vscode":
        return True  # Modern VS Code handles Unicode well

    # Default to True on Unix-like systems, False on Windows without modern terminal
    if sys.platform == "win32":
        # Windows Terminal and modern consoles support Unicode
        wt_session = os.environ.get("WT_SESSION")
        windows_terminal = os.environ.get("TERM_PROGRAM") == "Windows Terminal"
        return bool(wt_session or windows_terminal)

    return True


def _check_emoji_support() -> bool:
    """Check if terminal supports emoji rendering."""
    # CI environments typically don't render emoji well in logs
    if _check_ci():
        return False

    term = os.environ.get("TERM", "").lower()
    if term == "dumb":
        return False

    # macOS Terminal.app has limited emoji support
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    if term_program == "apple_terminal":
        return True  # Modern versions support emoji

    return _check_unicode_support()


def detect_terminal_capabilities() -> TerminalCaps:
    """Detect terminal capabilities for celebration rendering."""
    is_ci = _check_ci()
    is_interactive = sys.stdout.isatty() and sys.stderr.isatty()

    # CI logs often mangle Unicode rendering, so force ASCII-safe there.
    # Outside CI, detect Unicode support even when output is piped.
    supports_unicode = False if is_ci else _check_unicode_support()

    # Emoji support: disable in CI (logs don't render emoji well)
    supports_emoji = not is_ci and _check_emoji_support()

    return TerminalCaps(
        supports_unicode=supports_unicode,
        supports_emoji=supports_emoji,
        is_interactive=is_interactive,
        is_ci=is_ci,
        columns=_get_columns(),
    )


def is_safe_mode() -> bool:
    """Convenience function to check if safe mode should be used."""
    caps = detect_terminal_capabilities()
    return caps.is_ci or not caps.supports_unicode
