#!/usr/bin/env python3
"""CLI entry point for quest celebrations.

Usage:
    python3 scripts/quest_celebrate/celebrate.py --quest-dir .quest/<id>
    python3 scripts/quest_celebrate/celebrate.py --quest-dir .quest/<id> --style epic
    python3 scripts/quest_celebrate/celebrate.py --quest-dir .quest/<id> --style minimal

Copy import pattern from build_quest_dashboard.py lines 14-21.
"""

import argparse
import sys
from pathlib import Path

# Prefer installed package; fall back to sys.path for direct script execution
try:
    from quest_celebrate.animations import celebrate
    from quest_celebrate.config import load_config
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from quest_celebrate.animations import celebrate
    from quest_celebrate.config import load_config


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Celebrate quest completion with style",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Styles:
  minimal   One-line summary, ideal for CI and scripts
  standard  Boxed banner with quest stats
  epic      Full cinematic experience: block-letter title, achievements,
            impact metrics, quality score, movie credits (DEFAULT)
  silly     Over-the-top celebration with gremlin battles and maximum flair

Examples:
  python3 scripts/quest_celebrate/celebrate.py --quest-dir .quest/my-quest
  python3 scripts/quest_celebrate/celebrate.py --quest-dir .quest/my-quest --style epic
  python3 scripts/quest_celebrate/celebrate.py --quest-dir .quest/my-quest --style minimal
  python3 scripts/quest_celebrate/celebrate.py --quest-dir .quest/my-quest --safe-mode always
        """,
    )
    parser.add_argument(
        "--quest-dir",
        required=True,
        help="Path to quest directory (e.g., .quest/my-quest_2026-01-01__1200)",
    )
    parser.add_argument(
        "--style",
        choices=["minimal", "standard", "epic", "silly"],
        default=None,
        help="Animation style (default: epic). See style descriptions below",
    )
    parser.add_argument(
        "--speed",
        choices=["fast", "default", "slow"],
        default=None,
        help="Animation speed (default: from config or auto-detect)",
    )
    parser.add_argument(
        "--no-credits",
        action="store_true",
        help="Hide end credits",
    )
    parser.add_argument(
        "--safe-mode",
        choices=["auto", "always", "never"],
        default=None,
        help="ASCII-safe mode (default: auto-detect)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without displaying celebration",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """Main entry point."""
    args = parse_args(argv)

    # Resolve quest directory
    quest_dir = Path(args.quest_dir).resolve()

    # Load configuration with full precedence chain
    config = load_config(
        cli_style=args.style,
        cli_speed=args.speed,
        cli_no_credits=args.no_credits,
        cli_safe_mode=args.safe_mode,
    )

    # Dry run just shows config
    if args.dry_run:
        print(f"Quest directory: {quest_dir}")
        print(f"Configuration: {config}")
        return 0

    # Run celebration
    return celebrate(quest_dir, config)


if __name__ == "__main__":
    sys.exit(main())
