#!/usr/bin/env python3
"""Update quest state.json consistently from the command line.

Supports two modes:

  Raw setter (original):
    python3 scripts/quest_state.py --quest-dir .quest/<id> --phase building --status in_progress

  Atomic validated transition (preferred):
    python3 scripts/quest_state.py --quest-dir .quest/<id> --transition building --status in_progress

  With optimistic locking (recommended for multi-agent):
    python3 scripts/quest_state.py --quest-dir .quest/<id> --transition building --status in_progress --expect-phase plan_reviewed

The --transition flag calls quest_validate-quest-state.sh before writing.
If validation fails, state.json is not modified.

The --expect-phase flag adds optimistic locking: the transition is
rejected immediately if the current phase in state.json does not match
the expected value, narrowing (not eliminating — the check precedes the
validator and the final write) TOCTOU races when multiple
agents may be updating state concurrently.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from quest_runtime.state import load_state, update_state, write_state


def find_validator() -> Path:
    """Locate quest_validate-quest-state.sh relative to this script."""
    script_dir = Path(__file__).resolve().parent
    validator = script_dir / "quest_validate-quest-state.sh"
    if validator.is_file():
        return validator
    raise FileNotFoundError(
        f"quest_validate-quest-state.sh not found at {validator}"
    )


def run_validator(quest_dir: str, target_phase: str) -> tuple[int, str]:
    """Run the bash validator and return (exit_code, output)."""
    validator = find_validator()
    result = subprocess.run(
        ["bash", str(validator), quest_dir, target_phase],
        capture_output=True,
        text=True,
        cwd=os.environ.get("QUEST_REPO_ROOT", str(validator.parent.parent)),
    )
    combined = result.stdout + result.stderr
    return result.returncode, combined


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update .quest/<id>/state.json",
        epilog=(
            "Use --transition instead of --phase for atomic validated "
            "transitions. The validator runs first; state is only written "
            "if validation passes."
        ),
    )
    parser.add_argument("--quest-dir", required=True)

    phase_group = parser.add_mutually_exclusive_group()
    phase_group.add_argument(
        "--phase",
        help="Set phase directly (no validation). Use --transition instead.",
    )
    phase_group.add_argument(
        "--transition",
        metavar="PHASE",
        help="Validate then transition to PHASE atomically.",
    )

    parser.add_argument("--status")
    parser.add_argument(
        "--expect-phase",
        metavar="PHASE",
        help=(
            "Optimistic lock: reject immediately if current phase in "
            "state.json does not match PHASE. Narrows (not eliminates) TOCTOU races "
            "when multiple agents update state concurrently."
        ),
    )
    parser.add_argument("--last-role")
    parser.add_argument("--last-verdict")
    parser.add_argument("--quest-mode")
    parser.add_argument("--plan-iteration", type=int)
    parser.add_argument("--fix-iteration", type=int)
    parked_group = parser.add_mutually_exclusive_group()
    parked_group.add_argument(
        "--parked-bg-session",
        metavar="JSON",
        help=(
            "Persist parked background-session metadata as state.json "
            'parked_bg_session. Must be a JSON object with a "session_id" '
            'field, e.g. \'{"agent": "planner", "phase": "plan", '
            '"iteration": 1, "session_id": "<uuid>", "short_id": "<id>"}\'.'
        ),
    )
    parked_group.add_argument(
        "--clear-parked-bg-session",
        action="store_true",
        help=(
            "Remove parked_bg_session from state.json (after the relay "
            "resumed the session or it was swept)."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Resolve to absolute path once so validator subprocess and Python
    # process both target the same state.json regardless of cwd.
    quest_dir = str(Path(args.quest_dir).resolve())

    target_phase = args.transition or args.phase

    # Fail closed on an empty lock value: a shell caller expanding an unset
    # variable (--expect-phase "$PHASE") must not silently bypass the lock.
    if args.expect_phase is not None and not args.expect_phase.strip():
        print(
            "--expect-phase requires a non-empty phase name.",
            file=sys.stderr,
        )
        return 1

    if args.expect_phase and not args.transition:
        print(
            "--expect-phase requires --transition (ignored with --phase).",
            file=sys.stderr,
        )
        return 1

    if args.transition:
        # Read current phase BEFORE validation for accurate error reporting
        current_phase = "unknown"
        try:
            current_phase = load_state(quest_dir).get("phase", "unknown")
        except Exception:
            pass

        # Optimistic lock: reject if current phase doesn't match expectation
        if args.expect_phase and current_phase != args.expect_phase:
            print(
                f"Optimistic lock failed: expected phase '{args.expect_phase}' "
                f"but state.json has '{current_phase}'. Another agent may have "
                f"modified state concurrently.",
                file=sys.stderr,
            )
            return 1

        # Validate before mutating
        rc, output = run_validator(quest_dir, args.transition)
        if rc != 0:
            print(
                f"Transition {current_phase} -> {args.transition} rejected by validator.",
                file=sys.stderr,
            )
            print(output, file=sys.stderr)
            return 1

        # Re-check the lock AFTER the (slow) validator subprocess: a
        # concurrent update landing during validation would otherwise be
        # clobbered. This narrows the remaining check-to-write window from
        # validator-duration to microseconds.
        if args.expect_phase:
            try:
                current_phase = load_state(quest_dir).get("phase", "unknown")
            except Exception:
                current_phase = "unknown"
            if current_phase != args.expect_phase:
                print(
                    f"Optimistic lock failed after validation: expected phase "
                    f"'{args.expect_phase}' but state.json has '{current_phase}'. "
                    "Another agent modified state concurrently.",
                    file=sys.stderr,
                )
                return 1

    parked_bg_session = None
    if args.parked_bg_session is not None:
        try:
            parked_bg_session = json.loads(args.parked_bg_session)
        except json.JSONDecodeError as exc:
            print(f"--parked-bg-session must be valid JSON: {exc}", file=sys.stderr)
            return 1
        if not isinstance(parked_bg_session, dict) or not parked_bg_session.get(
            "session_id"
        ):
            print(
                '--parked-bg-session must be a JSON object with a "session_id" field.',
                file=sys.stderr,
            )
            return 1

    state = update_state(
        quest_dir,
        phase=target_phase,
        status=args.status,
        last_role=args.last_role,
        last_verdict=args.last_verdict,
        quest_mode=args.quest_mode,
        plan_iteration=args.plan_iteration,
        fix_iteration=args.fix_iteration,
        parked_bg_session=parked_bg_session,
    )
    if args.clear_parked_bg_session and "parked_bg_session" in state:
        state.pop("parked_bg_session", None)
        write_state(quest_dir, state)
    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
