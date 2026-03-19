#!/usr/bin/env python3
"""Update quest state.json consistently from the command line."""

from __future__ import annotations

import argparse
import json
import sys

from quest_runtime.state import update_state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update .quest/<id>/state.json")
    parser.add_argument("--quest-dir", required=True)
    parser.add_argument("--phase")
    parser.add_argument("--status")
    parser.add_argument("--last-role")
    parser.add_argument("--last-verdict")
    parser.add_argument("--quest-mode")
    parser.add_argument("--plan-iteration", type=int)
    parser.add_argument("--fix-iteration", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = update_state(
        args.quest_dir,
        phase=args.phase,
        status=args.status,
        last_role=args.last_role,
        last_verdict=args.last_verdict,
        quest_mode=args.quest_mode,
        plan_iteration=args.plan_iteration,
        fix_iteration=args.fix_iteration,
    )
    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
