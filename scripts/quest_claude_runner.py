#!/usr/bin/env python3
"""Run a Claude-designated Quest role through the local bridge with handoff polling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from quest_runtime.artifacts import expected_artifacts_for_role
from quest_runtime.claude_runner import run_claude_role


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Quest Claude role via bridge")
    parser.add_argument("--quest-dir", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--iter", required=True, type=int)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--handoff-file", required=True)
    parser.add_argument("--model", default="opus")
    # NOTE: This default is duplicated in scripts/claude_cli_bridge.py.
    # If you change it here, update it there too.
    parser.add_argument("--timeout", type=float, default=1800.0,
                        help="Command timeout seconds (default: 1800)")
    parser.add_argument("--permission-mode", default="bypassPermissions")
    parser.add_argument("--bridge-script", default="scripts/claude_cli_bridge.py")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--add-dir", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        artifact_paths = expected_artifacts_for_role(
            quest_dir=args.quest_dir,
            phase=args.phase,
            agent=args.agent,
        )
    except ValueError as exc:
        payload = {
            "exit_code": 1,
            "handoff_state": "missing",
            "result_kind": "invocation_error",
            "source": None,
            "stderr": str(exc),
            "stdout": "",
        }
        print(json.dumps(payload, ensure_ascii=True))
        return 1
    result = run_claude_role(
        cwd=args.cwd,
        quest_dir=args.quest_dir,
        phase=args.phase,
        agent=args.agent,
        iteration=args.iter,
        prompt_file=args.prompt_file,
        handoff_file=args.handoff_file,
        bridge_script=Path(args.cwd) / args.bridge_script,
        model=args.model,
        timeout=args.timeout,
        permission_mode=args.permission_mode,
        artifact_paths=artifact_paths,
        allow_text_fallback=True,
        add_dirs=args.add_dir,
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
