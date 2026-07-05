#!/usr/bin/env python3
"""Probe a Quest Claude transport by requiring a real artifact and handoff write.

--transport bridge (default): scripts/quest_claude_bridge.py (claude --print).
--transport background-agent: scripts/claude_bg_run.py (claude --bg).
"""

from __future__ import annotations

import argparse
import json

from quest_runtime.claude_runner import (
    DEFAULT_BG_RUNNER_SCRIPT,
    DEFAULT_BRIDGE_SCRIPT,
    resolve_path,
    run_bg_probe,
    run_bridge_probe,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe a Quest Claude transport via artifact write"
    )
    parser.add_argument("--quest-dir", required=True)
    parser.add_argument(
        "--model",
        required=True,
        help="Claude model value to probe; exact `claude` omits the CLI --model flag.",
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--permission-mode", default="bypassPermissions")
    parser.add_argument(
        "--transport",
        default="bridge",
        choices=["bridge", "background-agent"],
        help="which transport to probe (default: bridge, backward compatible)",
    )
    parser.add_argument("--bridge-script", default=DEFAULT_BRIDGE_SCRIPT)
    parser.add_argument("--bg-runner-script", default=DEFAULT_BG_RUNNER_SCRIPT)
    parser.add_argument("--cwd", default=".")
    args = parser.parse_args()
    if not args.model.strip():
        parser.error(
            "--model must be a model name (e.g. `sonnet`, `claude-opus-4-8`) "
            "or the literal `claude` for the account-default model"
        )
    return args


def main() -> int:
    args = parse_args()
    if args.transport == "background-agent":
        result = run_bg_probe(
            cwd=args.cwd,
            quest_dir=args.quest_dir,
            bg_runner_script=resolve_path(args.cwd, args.bg_runner_script),
            model=args.model,
            timeout=args.timeout,
            permission_mode=args.permission_mode,
        )
    else:
        result = run_bridge_probe(
            cwd=args.cwd,
            quest_dir=args.quest_dir,
            bridge_script=resolve_path(args.cwd, args.bridge_script),
            model=args.model,
            timeout=args.timeout,
            permission_mode=args.permission_mode,
        )
    payload = {
        "transport": args.transport,
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
