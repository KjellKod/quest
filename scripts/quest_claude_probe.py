#!/usr/bin/env python3
"""Probe the Claude bridge by requiring a real artifact and handoff write."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from quest_runtime.claude_runner import run_bridge_probe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe Quest Claude bridge via artifact write"
    )
    parser.add_argument("--quest-dir", required=True)
    parser.add_argument("--model", default="opus")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--permission-mode", default="bypassPermissions")
    parser.add_argument("--bridge-script", default="scripts/quest_claude_bridge.py")
    parser.add_argument("--cwd", default=".")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_bridge_probe(
        cwd=args.cwd,
        quest_dir=args.quest_dir,
        bridge_script=Path(args.cwd) / args.bridge_script,
        model=args.model,
        timeout=args.timeout,
        permission_mode=args.permission_mode,
    )
    payload = {
        "exit_code": result.exit_code,
        "handoff_state": result.handoff_state,
        "result_kind": result.result_kind,
        "source": result.source,
        "stderr": result.stderr.strip(),
        "stdout": result.stdout.strip(),
    }
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if result.exit_code == 0 else result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
