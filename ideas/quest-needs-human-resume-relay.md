# Quest needs_human → Resume Relay

Date: 2026-06-11
Status: `proposed`
Related: `scripts/claude_bg_run.py`,
`docs/implementation/claude-bg-transport-step2-wiring.md` (declared this out of
scope), `docs/implementation/history` (Step-1/Step-2 docs once archived)

## Idea

`scripts/claude_bg_run.py` already supports an interactive relay: a role that
writes a `needs_human` handoff (when invoked with `--handoff-file`) exits 10 and
**leaves the background session alive**, and `--resume <session_id|short_id|name>
--answer "<reply>"` continues the same conversation (fork, with fresh-dispatch
fallback). Quest deliberately does NOT use this today: the Step-2 wiring passes
the handoff path via `--wait-for` only, so a `needs_human` handoff tears the
session down and the orchestrator re-dispatches fresh — identical semantics to
the bridge, zero session-leak risk.

The upgrade: when a Codex-led Claude role returns `needs_human`, keep the parked
session, ask the human, and resume it with the answer — preserving the role's
full working context instead of rebuilding it from prompt + artifacts.

## Why not yet (scope notes from Step 2)

- Quest's orchestrator has no per-role conversation state; tracking parked
  sessions adds a leak hazard (sessions burning subscription if never resumed).
- Needs an explicit lifecycle: who tears down a parked session when the human
  abandons the quest? (`--sweep quest-<id>-` covers crashes, not parked-on-purpose.)
- Value is real but unproven: measure how often quest roles actually return
  `needs_human` before building (the context_health.log already shows it).

## Sketch (when measured demand exists)

1. Runner gains `--handoff-file` passthrough + a `parked_session` field in its
   JSON envelope (session_id surfaced to the orchestrator).
2. Workflow prose: on `needs_human` from a runner-invoked Claude role, ask the
   human (existing Q&A path), then re-invoke the runner with
   `--resume <session_id> --answer "<reply>"`; on resume failure the runner
   already falls back to a fresh dispatch carrying the answer.
3. Teardown rule: parked sessions are swept at quest archive/abandon time.
