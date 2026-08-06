#!/usr/bin/env python3
"""Manage immutable Quest plan-iteration snapshots."""

from __future__ import annotations

import argparse
import json
import sys

from quest_runtime.plan_iterations import (
    PlanIterationError,
    cleanup_current,
    publish_refinement,
    snapshot_plan_iteration,
    verify_refinement,
)
from quest_runtime.state import StateError


def positive_integer(value: str) -> int:
    iteration = int(value)
    if iteration < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return iteration


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in (
        "snapshot",
        "cleanup-current",
        "publish-refinement",
        "verify-refinement",
    ):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--quest-dir", required=True)
        subparser.add_argument("--iteration", required=True, type=positive_integer)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "snapshot":
            result = snapshot_plan_iteration(args.quest_dir, args.iteration)
            print(result)
        elif args.command == "cleanup-current":
            cleanup_current(args.quest_dir, args.iteration)
        elif args.command == "publish-refinement":
            result = publish_refinement(args.quest_dir, args.iteration)
            print(result)
        else:
            result = verify_refinement(args.quest_dir, args.iteration)
            print(json.dumps(result, indent=2))
    except (PlanIterationError, StateError, OSError, ValueError) as exc:
        print(f"plan_iteration_error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
