#!/usr/bin/env python3
"""Render persisted celebration title art."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from quest_celebrate.ascii_art import ansi_shadow_title
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from quest_celebrate.ascii_art import ansi_shadow_title


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render Quest celebration title art in the persisted GitHub style.",
    )
    parser.add_argument("title", help="Title text to render.")
    parser.add_argument(
        "--max-width",
        type=int,
        default=70,
        help="Maximum rendered row width before word splitting.",
    )
    args = parser.parse_args()

    print(ansi_shadow_title(args.title, max_width=args.max_width))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
