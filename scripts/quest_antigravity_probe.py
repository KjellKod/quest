#!/usr/bin/env python3
"""Probe the Quest Antigravity runtime by requiring a real artifact + handoff.

A green probe means `agy` actually wrote the files a Quest role must write —
not merely that the binary answered. Mirrors scripts/quest_claude_probe.py.
"""

from __future__ import annotations

import argparse
import json

from quest_runtime.antigravity_runner import (
    DEFAULT_AGY_BINARY,
    run_antigravity_probe,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe the Quest Antigravity runtime via artifact write"
    )
    parser.add_argument("--quest-dir", required=True)
    parser.add_argument(
        "--model",
        required=True,
        help=(
            "Gemini slug to probe (for example gemini-3.6-flash-low); the "
            "exact `gemini` sentinel omits the CLI --model flag."
        ),
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--agy-binary", default=DEFAULT_AGY_BINARY)
    args = parser.parse_args()
    if not args.model.strip():
        parser.error(
            "--model must be a Gemini slug (e.g. `gemini-3.6-flash-low`) "
            "or the literal `gemini` for the agy default model"
        )
    return args


def main() -> int:
    args = parse_args()
    result = run_antigravity_probe(
        cwd=args.cwd,
        quest_dir=args.quest_dir,
        model=args.model,
        timeout=args.timeout,
        agy_binary=args.agy_binary,
    )
    payload = {
        "runtime": "antigravity",
        "available": result.exit_code == 0,
        "exit_code": result.exit_code,
        "handoff_state": result.handoff_state,
        "result_kind": result.result_kind,
        "source": result.source,
        "probe_model": args.model.strip(),
        "stderr": result.stderr.strip(),
        "stdout": result.stdout.strip(),
    }
    if result.rejected_model:
        payload["rejected_model"] = result.rejected_model
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if result.exit_code == 0 else result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
