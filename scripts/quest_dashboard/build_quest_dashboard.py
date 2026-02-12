#!/usr/bin/env python3
"""Build a static Quest Dashboard HTML page from repo quest data.

Usage:
    python3 scripts/quest_dashboard/build_quest_dashboard.py
    python3 scripts/quest_dashboard/build_quest_dashboard.py --output custom/path.html
    python3 scripts/quest_dashboard/build_quest_dashboard.py --github-url https://github.com/owner/repo
"""

import argparse
import sys
from pathlib import Path

# Add scripts/ to path so quest_dashboard package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quest_dashboard.loaders import load_dashboard_data
from quest_dashboard.render import render_dashboard


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build Quest Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/quest_dashboard/build_quest_dashboard.py
  python3 scripts/quest_dashboard/build_quest_dashboard.py --output docs/custom.html
  python3 scripts/quest_dashboard/build_quest_dashboard.py --github-url https://github.com/owner/repo
        """,
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root. Default: auto-detect from script location.",
    )
    parser.add_argument(
        "--output",
        default="docs/dashboard/index.html",
        help="Output HTML path relative to repo root. Default: docs/dashboard/index.html",
    )
    parser.add_argument(
        "--github-url",
        default=None,
        help="GitHub repo URL. Auto-detected from git remote if omitted.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    """Main entry point."""
    args = parse_args(argv)

    # Determine repo root
    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
    else:
        # Auto-detect: script is in scripts/quest_dashboard/, repo root is 2 levels up
        repo_root = Path(__file__).resolve().parents[2]

    # Determine output path
    if Path(args.output).is_absolute():
        output_path = Path(args.output).resolve()
    else:
        output_path = (repo_root / args.output).resolve()

    # Load dashboard data (github_url wired per Arbiter Note 4)
    data = load_dashboard_data(repo_root, github_url=args.github_url)

    # Render HTML
    html = render_dashboard(data, output_path, repo_root)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    # Print summary
    print(f"Dashboard built: {output_path}")
    print(f"  Finished: {len(data.finished_quests)}")
    print(f"  In Progress: {len(data.active_quests)}")
    print(f"  Abandoned: {len(data.abandoned_quests)}")

    # Print warnings to stderr
    for warning in data.warnings:
        print(f"  Warning: {warning}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
