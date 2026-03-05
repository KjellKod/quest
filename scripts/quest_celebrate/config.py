"""Configuration loading for quest celebrations.

Configuration precedence (highest to lowest):
  1. CLI flags (--style, --speed, --no-credits)
  2. Environment variables (QUEST_ANIMATIONS, QUEST_STYLE, QUEST_SPEED)
  3. .ai/allowlist.json quest_completion section
  4. Auto-detection (CI, TERM, pipe detection)
  5. Defaults (style=epic, speed=default, credits=true)

Note: .quest/config.json support is deferred to a future enhancement (YAGNI).
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from quest_celebrate.terminal import detect_terminal_capabilities, is_safe_mode


@dataclass
class CelebrationConfig:
    """Configuration for quest celebration."""

    style: str = "epic"  # minimal, standard, epic, silly
    speed: str = "default"  # fast, default, slow
    show_credits: bool = True
    show_progress: bool = True
    ascii_art: bool = True
    enabled: bool = True
    safe_mode: str = "auto"  # auto, always, never

    # Computed fields (not from config, but from terminal detection)
    is_safe: bool = field(default=False, repr=False)
    columns: int = field(default=80, repr=False)


def _load_allowlist_config(repo_root: Optional[Path] = None) -> Dict[str, Any]:
    """Load quest_completion config from .ai/allowlist.json."""
    if repo_root is None:
        # Try to find repo root from script location
        # scripts/quest_celebrate/config.py -> scripts/quest_celebrate/ -> scripts/ -> repo_root
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parents[1]

    allowlist_path = repo_root / ".ai" / "allowlist.json"

    if not allowlist_path.exists():
        return {}

    try:
        with open(allowlist_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("quest_completion", {})
    except (json.JSONDecodeError, IOError):
        return {}


def _apply_env_overrides(config: CelebrationConfig) -> CelebrationConfig:
    """Apply environment variable overrides to config."""
    # QUEST_ANIMATIONS=0 disables all
    quest_animations = os.environ.get("QUEST_ANIMATIONS")
    if quest_animations is not None:
        if quest_animations == "0":
            config.enabled = False
        elif quest_animations == "1":
            config.enabled = True

    # QUEST_STYLE overrides style
    quest_style = os.environ.get("QUEST_STYLE")
    if quest_style in ("minimal", "standard", "epic", "silly"):
        config.style = quest_style

    # QUEST_SPEED overrides speed
    quest_speed = os.environ.get("QUEST_SPEED")
    if quest_speed in ("fast", "default", "slow"):
        config.speed = quest_speed

    # QUEST_CREDITS=0 hides credits
    quest_credits = os.environ.get("QUEST_CREDITS")
    if quest_credits is not None:
        config.show_credits = quest_credits != "0"

    return config


def _apply_cli_overrides(
    config: CelebrationConfig,
    style: Optional[str] = None,
    speed: Optional[str] = None,
    no_credits: bool = False,
    safe_mode: Optional[str] = None,
) -> CelebrationConfig:
    """Apply CLI flag overrides to config (highest precedence)."""
    if style in ("minimal", "standard", "epic", "silly"):
        config.style = style

    if speed in ("fast", "default", "slow"):
        config.speed = speed

    if no_credits:
        config.show_credits = False

    if safe_mode in ("auto", "always", "never"):
        config.safe_mode = safe_mode

    return config


def _apply_auto_detection(config: CelebrationConfig) -> CelebrationConfig:
    """Apply auto-detected terminal capabilities."""
    caps = detect_terminal_capabilities()
    config.columns = caps.columns

    # Determine safe mode
    if config.safe_mode == "auto":
        config.is_safe = caps.is_ci or not caps.supports_unicode
    elif config.safe_mode == "always":
        config.is_safe = True
    else:  # never
        config.is_safe = False

    # Auto-adjust for CI or non-interactive
    if caps.is_ci or not caps.is_interactive:
        if config.speed == "default":
            config.speed = "fast"

    return config


def load_config(
    repo_root: Optional[Path] = None,
    cli_style: Optional[str] = None,
    cli_speed: Optional[str] = None,
    cli_no_credits: bool = False,
    cli_safe_mode: Optional[str] = None,
) -> CelebrationConfig:
    """Load celebration configuration with full precedence chain.

    Precedence (highest to lowest):
      1. CLI flags
      2. Environment variables
      3. .ai/allowlist.json
      4. Auto-detection (CI, TERM, pipe detection)
      5. Defaults
    """
    # Start with defaults
    config = CelebrationConfig()

    # Layer 4: Auto-detection (applied early so other layers can override)
    caps = detect_terminal_capabilities()
    config.columns = caps.columns

    # Determine safe mode from auto-detection
    # Only use safe mode in CI or if terminal doesn't support Unicode
    # Being piped or non-interactive shouldn't mean boring output
    if cli_safe_mode is None:
        config.is_safe = caps.is_ci or not caps.supports_unicode

    # Layer 3: allowlist.json
    allowlist_config = _load_allowlist_config(repo_root)
    if allowlist_config:
        config.style = allowlist_config.get("animation_style", config.style)
        config.show_credits = allowlist_config.get(
            "show_end_credits", config.show_credits
        )
        config.show_progress = allowlist_config.get(
            "show_progress_bars", config.show_progress
        )
        config.ascii_art = allowlist_config.get("ascii_art", config.ascii_art)
        config.enabled = allowlist_config.get("enabled", config.enabled)
        config.safe_mode = allowlist_config.get("safe_mode", config.safe_mode)
        # Only apply allowlist speed if not in CI/non-interactive mode
        # (CI should always be fast regardless of allowlist default)
        if not (caps.is_ci or not caps.is_interactive):
            config.speed = allowlist_config.get("animation_speed", config.speed)
        elif "animation_speed" in allowlist_config:
            # In CI, allow explicit speed override from allowlist
            config.speed = allowlist_config["animation_speed"]

    # Re-apply auto-detection speed for CI/non-interactive if not explicitly set
    if caps.is_ci or not caps.is_interactive:
        if config.speed not in ("fast", "slow"):
            config.speed = "fast"

    # Layer 2: Environment variables
    config = _apply_env_overrides(config)

    # Layer 1: CLI flags
    config = _apply_cli_overrides(
        config,
        style=cli_style,
        speed=cli_speed,
        no_credits=cli_no_credits,
        safe_mode=cli_safe_mode,
    )

    # Final safe mode determination
    if config.safe_mode == "auto":
        config.is_safe = caps.is_ci or not caps.supports_unicode
    elif config.safe_mode == "always":
        config.is_safe = True
    elif config.safe_mode == "never":
        config.is_safe = False

    return config
