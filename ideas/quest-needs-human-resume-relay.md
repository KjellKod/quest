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
  `needs_human` before building. **Caveat (2026-06-12):** context_health.log
  does NOT show this today — its line format records handoff presence
  (`handoff_json=found|missing|unparsable`), not handoff *status*, so a
  `needs_human` handoff logs identically to `complete`. See sketch step 0.

## Q&A (2026-06-12, maintainer review of the Step-2 deferral)

**Q1. Should Quest have a resume loop?**
Not yet — the deferral stands. Framing point: for Quest's artifact-driven
philosophy, fresh re-dispatch is not a degraded mode; agents are *supposed* to
rebuild from artifacts, not conversation. Session-resume is a
context-preservation optimization, not a correctness fix. Gate it on measured
`needs_human` frequency in `context_health.log`.

**Q2. CLI abort / laptop shutdown, then `/quest <slug>` — handled?**
Yes, but resume means *re-dispatch*, never *reattach*. Continuity lives in
`.quest/<id>/state.json` + artifacts on disk. Session IDs are deliberately not
persisted to a quest file: deterministic names
(`quest-<quest_id>-<agent>-i<iter>`) are the recovery key, and the start/resume
orphan sweep (`claude_bg_run.py --sweep quest-<id>-`) stops anything live under
that prefix. After a reboot the daemon's sessions are dead anyway — the durable
record is the artifacts. Known gap (audit-only, not recovery): the migration
spec's T2 `bg_sessions.jsonl` was dropped in favor of name-based sweep, so
there is no quest-local log of which session IDs ran.

**Q3. How will we actually know `needs_human` is rare after X quests?**
Today, we won't — context_health.log records handoff presence/parseability,
not status, so `needs_human` is invisible in it. The good news (verified
2026-06-12): persistence is NOT a gap — `quest_complete.py` moves the whole
quest folder to `.quest/archive/<id>/`, logs included (56 archived quests on
the reference machine, 41 with intact context_health.log). So the only
essential fix is the producer: once the line carries `status=`, the question
is answerable per-machine with
`grep -h "status=needs_human" .quest/archive/*/logs/context_health.log`.
See sketch step 0. The pattern is exactly what Step 2 did for `transport=`.

**Q2b. Does `needs_human` bubble up through Codex to the human and back to
Claude (the interactivity litmus test)?**
Yes, functionally, today — the workflow Q&A loop covers runner-invoked Claude:
question surfaces to the human via the orchestrator, the answer goes back by
re-invoking the same agent with answers appended against the same artifact
paths. What the litmus test reveals is not a missing loop but that the loop has
**amnesia**: a fresh Claude answers, not the session that asked. Closing that
amnesia is exactly this idea; the relay mechanism itself already shipped in
Step 1 (`claude_bg_run.py --resume/--answer`).

## Sketch (when measured demand exists)

0. **Measurement prerequisite (shipped with the Step-2 wiring PR, 2026-06-12):** add
   `status=complete|needs_human|blocked` to the context_health.log line
   (the runner already parses the handoff to classify, so it knows; workflow
   prose logs the same field for native `Task(...)` roles). That alone makes
   the frequency answerable from `.quest/archive/*/logs/` (quest folders are
   archived whole, logs included). Optional surfacing, in order of value:
   (a) quest-end historical rollup — a few lines in `quest_complete.py`
   scanning the archive ("across N archived quests: M needs_human");
   (b) a `needs_human` count in the journal `celebration_data` only if the
   stat should reach the committed/published record (dashboard reads the
   journal, not the local archive).
1. Runner gains `--handoff-file` passthrough + a `parked_session` field in its
   JSON envelope (session_id surfaced to the orchestrator).
2. Workflow prose: on `needs_human` from a runner-invoked Claude role, ask the
   human (existing Q&A path), then re-invoke the runner with
   `--resume <session_id> --answer "<reply>"`; on resume failure the runner
   already falls back to a fresh dispatch carrying the answer.
3. Teardown rule: parked sessions are swept at quest archive/abandon time.
