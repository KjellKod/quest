#!/usr/bin/env python3
"""Run a Claude-designated Quest role with handoff polling.

Transport (Codex-led Claude roles):
  --transport auto (default)   background-agent; startup preflight must prove
                               it or stop for a user decision.
  --transport background-agent forced `claude --bg` via scripts/claude_bg_run.py.
  --transport bridge           explicit `claude --print` via the bridge script.
The resolved transport is echoed in the output JSON envelope and recorded on
each context_health.log line.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from quest_runtime.artifacts import expected_artifacts_for_role
from quest_runtime.claude_runner import (
    DEFAULT_BG_RUNNER_SCRIPT,
    DEFAULT_BRIDGE_SCRIPT,
    resolve_claude_transport,
    resolve_path,
    run_claude_role,
)


_TELEMETRY_ENV = "QUEST_RUNNER_TELEMETRY_LOG"


def _append_telemetry(event: dict) -> None:
    """Append a single JSON line to the runner telemetry log if env var is set.

    This is an opt-in seam used by tests to observe the actual runner-produced
    sequence of attempts (plus external events like ``publish`` when the caller
    chooses to append them). Production runs are unaffected unless
    ``QUEST_RUNNER_TELEMETRY_LOG`` is exported, in which case the file simply
    accumulates invocation records. Failures to write telemetry must never
    affect the runner outcome.
    """

    log_path = os.environ.get(_TELEMETRY_ENV)
    if not log_path:
        return
    try:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = dict(event)
        record.setdefault("ts", time.time())
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    except Exception:
        # Telemetry is best-effort; never fail the runner because of it.
        # Broad except is intentional — the docstring contract is that
        # telemetry must never affect runner outcome, which includes
        # TypeError from json.dumps on unexpected payloads.
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Quest Claude role")
    parser.add_argument("--quest-dir", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--iter", required=True, type=int)
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--handoff-file", required=True)
    parser.add_argument(
        "--model",
        required=True,
        help="Claude model value from orchestration.json; exact `claude` omits the CLI --model flag.",
    )
    parser.add_argument("--timeout", type=float, default=1800.0,
                        help="Command timeout seconds (default: 1800)")
    parser.add_argument("--permission-mode", default="bypassPermissions")
    parser.add_argument(
        "--transport",
        default="auto",
        choices=["auto", "background-agent", "bridge"],
        help="Claude transport (default auto: background-agent; bridge is explicit)",
    )
    parser.add_argument("--bridge-script", default=DEFAULT_BRIDGE_SCRIPT)
    parser.add_argument("--bg-runner-script", default=DEFAULT_BG_RUNNER_SCRIPT)
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--add-dir", action="append", default=[])
    parser.add_argument("--resume", help="background-agent session id/short id/name to resume")
    parser.add_argument("--answer-file", help="file containing the human answer for --resume")
    parser.add_argument(
        "--teardown-on-needs-human",
        action="store_true",
        help="tear down bg needs_human sessions instead of parking them for resume",
    )
    args = parser.parse_args()
    if not args.model.strip():
        parser.error(
            "--model must be a model name (e.g. `sonnet`, `claude-opus-4-8`) "
            "or the literal `claude` for the account-default model"
        )
    if args.answer_file and not args.resume:
        parser.error("--answer-file requires --resume (the parked session to continue)")
    if args.resume and not args.answer_file:
        parser.error(
            "--resume requires --answer-file (the human's reply to deliver); "
            "without it the bg runner would fall back to reading stdin"
        )
    if (args.resume or args.answer_file) and args.transport == "bridge":
        parser.error(
            "--resume/--answer-file require the background-agent transport; "
            "the bridge cannot continue a parked session"
        )
    return args


def main() -> int:
    args = parse_args()
    transport = resolve_claude_transport(args.transport)
    # Kept in the JSON envelope for compatibility with existing consumers.
    # New auto runs never downgrade; bridge is explicit.
    transport_downgraded = False
    _append_telemetry(
        {
            "event": "attempt_start",
            "agent": args.agent,
            "phase": args.phase,
            "iter": args.iter,
            "transport": transport,
        }
    )
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
            "transport": transport,
            "transport_downgraded": transport_downgraded,
            "stderr": str(exc),
            "stdout": "",
        }
        _append_telemetry(
            {
                "event": "attempt_end",
                "agent": args.agent,
                "phase": args.phase,
                "iter": args.iter,
                "result_kind": "invocation_error",
                "handoff_state": "missing",
                "exit_code": 1,
                "transport": transport,
            }
        )
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
        bridge_script=resolve_path(args.cwd, args.bridge_script),
        model=args.model,
        timeout=args.timeout,
        permission_mode=args.permission_mode,
        artifact_paths=artifact_paths,
        allow_text_fallback=True,
        add_dirs=args.add_dir,
        transport=transport,
        bg_runner_script=resolve_path(args.cwd, args.bg_runner_script),
        teardown_on_needs_human=getattr(args, "teardown_on_needs_human", False),
        resume=getattr(args, "resume", None),
        answer_file=getattr(args, "answer_file", None),
    )
    payload = {
        "exit_code": result.exit_code,
        "handoff_state": result.handoff_state,
        "result_kind": result.result_kind,
        "source": result.source,
        "transport": transport,
        "transport_downgraded": transport_downgraded,
        "stderr": result.stderr.strip(),
        "stdout": result.stdout.strip(),
    }
    for key in (
        "status",
        "session_id",
        "short_id",
        "questions",
        "resumed_from",
        "teardown_failed",
        "teardown_survivor_id",
        "teardown_survivor_name",
        "teardown_survivor_session_id",
        "reset_at",
        "rejected_model",
    ):
        value = getattr(result, key)
        if value not in (None, [], False):
            payload[key] = value
    _append_telemetry(
        {
            "event": "attempt_end",
            "agent": args.agent,
            "phase": args.phase,
            "iter": args.iter,
            "result_kind": result.result_kind,
            "handoff_state": result.handoff_state,
            "exit_code": result.exit_code,
            "transport": transport,
        }
    )
    print(json.dumps(payload, ensure_ascii=True))
    return 0 if result.exit_code == 0 else result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
