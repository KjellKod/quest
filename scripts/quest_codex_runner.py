#!/usr/bin/env python3
"""Execute a standalone task or saved Quest role using the installed Codex CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from quest_runtime.codex_runner import (
    CodexResult,
    probe_codex,
    run_codex,
    run_codex_role,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    for operation in ("probe", "task", "role"):
        command = commands.add_parser(operation)
        command.add_argument("--cwd", default=".")
        if operation != "role":
            command.add_argument(
                "--auth", choices=("cached", "api-key"), default="cached"
            )
        if operation == "probe":
            continue
        command.add_argument(
            "--prompt-file", help="UTF-8 prompt file; omitted or '-' reads stdin"
        )
        command.add_argument("--output-dir", required=operation == "task")
        command.add_argument(
            "--sandbox",
            choices=("read-only", "workspace-write", "danger-full-access"),
            default="workspace-write",
        )
        command.add_argument("--timeout", type=float, default=1800)
        command.add_argument("--allow-non-git", action="store_true")
        if operation == "task":
            command.add_argument("--model")
            command.add_argument("--effort")
        else:
            command.add_argument("--quest-dir", required=True)
            command.add_argument("--phase", required=True)
            command.add_argument("--agent", required=True)
            command.add_argument("--iter", required=True, type=int)
            command.add_argument("--artifact-subset", choices=("findings-only",))
    args = parser.parse_args()
    if args.operation == "probe":
        payload = probe_codex(args.cwd, args.auth)
        print(json.dumps(payload))
        return 0
    result = CodexResult(
        "precondition_failed",
        auth_mode=args.auth if args.operation == "task" else "unknown",
        requested_model=args.model if args.operation == "task" else None,
        requested_effort=args.effort if args.operation == "task" else None,
    )
    try:
        prompt = (
            sys.stdin.read()
            if args.prompt_file in (None, "-")
            else Path(args.prompt_file).read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError):
        result.message = "Cannot read UTF-8 prompt input."
    else:
        shared = dict(
            cwd=args.cwd,
            output_dir=args.output_dir,
            prompt=prompt,
            sandbox=args.sandbox,
            timeout=args.timeout,
            allow_non_git=args.allow_non_git,
        )
        try:
            if args.operation == "role":
                result = run_codex_role(
                    **shared,
                    quest_dir=args.quest_dir,
                    phase=args.phase,
                    agent=args.agent,
                    iteration=args.iter,
                    artifact_subset=args.artifact_subset,
                )
            else:
                result = run_codex(
                    **shared, auth=args.auth, model=args.model, effort=args.effort
                )
        except (OSError, UnicodeError):
            result.result_kind = "invocation_error"
            result.message = (
                "Codex runtime/output error; execution may already have occurred."
            )
    print(json.dumps(result.payload()))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
