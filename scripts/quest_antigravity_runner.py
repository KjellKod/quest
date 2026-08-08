#!/usr/bin/env python3
"""Run a Gemini-designated Quest role on the Antigravity CLI (`agy`).

There is no transport choice here, unlike the Claude runner: `agy --print` is
the only path, so the same runner serves both Claude-led and Codex-led
sessions. The JSON envelope printed on stdout matches the Claude runner's
shape so orchestrators can consume either identically.
"""

from __future__ import annotations

import argparse
import json

from quest_runtime.antigravity_runner import (
    DEFAULT_AGY_BINARY,
    run_antigravity_role,
)
from quest_runtime.artifacts import expected_artifacts_for_role


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Quest Antigravity role")
    parser.add_argument("--quest-dir", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--iter", required=True, type=int)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--handoff-file", required=True)
    parser.add_argument(
        "--model",
        required=True,
        help=(
            "Gemini model slug from orchestration.json (for example "
            "gemini-3.6-flash-high); the exact `gemini` sentinel omits the "
            "CLI --model flag and lets agy pick its default."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=1800.0,
        help="Command timeout seconds (default: 1800)",
    )
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--add-dir", action="append", default=[])
    parser.add_argument(
        "--json-schema",
        help="Optional JSON schema path enforced on agy's structured output",
    )
    parser.add_argument("--agy-binary", default=DEFAULT_AGY_BINARY)
    args = parser.parse_args()
    if not args.model.strip():
        parser.error(
            "--model must be a Gemini slug (e.g. `gemini-3.6-flash-high`) "
            "or the literal `gemini` for the agy default model"
        )
    return args


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
            "runtime": "antigravity",
            "stderr": str(exc),
            "stdout": "",
        }
        print(json.dumps(payload, ensure_ascii=True))
        return 1

    result = run_antigravity_role(
        cwd=args.cwd,
        quest_dir=args.quest_dir,
        phase=args.phase,
        agent=args.agent,
        iteration=args.iter,
        prompt_file=args.prompt_file,
        handoff_file=args.handoff_file,
        model=args.model,
        timeout=args.timeout,
        artifact_paths=artifact_paths,
        add_dirs=args.add_dir,
        json_schema=args.json_schema,
        agy_binary=args.agy_binary,
    )
    payload = {
        "exit_code": result.exit_code,
        "handoff_state": result.handoff_state,
        "result_kind": result.result_kind,
        "source": result.source,
        "runtime": "antigravity",
        "stderr": result.stderr.strip(),
        "stdout": result.stdout.strip(),
    }
    for key in ("status", "rejected_model"):
        value = getattr(result, key)
        if value not in (None, [], False):
            payload[key] = value
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if result.exit_code == 0 else result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
