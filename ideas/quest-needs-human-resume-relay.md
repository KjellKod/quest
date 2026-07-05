# Quest needs_human → Resume Relay

Date: 2026-06-11 (updated 2026-06-16)
Status: `shipped` — stopgap in PR #137; full same-session relay implemented in PR #142 (park, persist id in state.json, resume with the human's answer, cold-restart re-presentation, quest-end sweep)
Related: `scripts/claude_bg_run.py`, `scripts/quest_runtime/claude_runner.py`
(`build_bg_cmd`), `docs/implementation/claude-bg-transport-step2-wiring.md`
(declared this out of scope), `docs/implementation/history` (Step-1/Step-2 docs
once archived)

## Stopgap shipped (PR #137, 2026-06-16)

The Step-2 lifecycle fix (the outer runner now waits for `claude_bg_run.py`
instead of poll-and-killing it) exposed a latent hang: with the handoff path in
`--wait-for` only, a `needs_human` handoff was invisible to the bg runner, so it
waited for the (never-written) primary artifacts until its full `--timeout`
(~30 min) before failing. The role blocked instead of surfacing the question.

Stopgap (not the full relay): `build_bg_cmd` now passes **`--handoff-file`** (so
`needs_human` is recognized the instant the handoff is written) **plus
`--teardown-on-needs-human`** (a new bg-runner flag that tears the session down
on `needs_human` instead of leaving it alive for `--resume`). Net effect —
`needs_human` behaves exactly like the bridge: surfaced promptly, session torn
down, orchestrator reads the handoff status. No session leak, no 30-min hang,
and **still no resume loop** — a fresh dispatch rebuilds from artifacts as
before. This is the deliberate "fresh re-dispatch is not a degraded mode"
stance from Q1 below, now also true on the bg transport.

The full interactive relay (keep the session alive, forward the human's answer
to the *same* session) remains the upgrade described in the sketch.

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

Status legend: ✅ shipped · 🟡 partially shipped · ⬜ not started.

0. ✅ **Measurement prerequisite (shipped with the Step-2 wiring PR, 2026-06-12):**
   `status=complete|needs_human|blocked` is in the context_health.log line, and
   `quest_complete.py` prints a quest-end rollup across `.quest/archive/*/logs/`.
   The frequency question is now answerable per-machine. **This is the gate:**
   read the rollup before building the full relay below.
1. 🟡 **Runner support.** `claude_bg_run.py` already supports the relay
   (`--handoff-file` recognizes `needs_human`; `--resume <id> --answer` continues
   the same conversation with fresh-dispatch fallback). PR #137 wired
   `--handoff-file` into `build_bg_cmd` but pairs it with
   `--teardown-on-needs-human` (stopgap: surface + teardown, no keep-alive).
   **Still ⬜:** surface the live `session_id` in the runner's JSON envelope up
   through `run_claude_role` → the orchestrator (today the bg envelope carries
   it on stdout, but `RunResult` does not propagate it).

### What the *true interactive behavior* needs (the follow-up PR)

2. ⬜ **Flip the stopgap for roles that should park.** Stop passing
   `--teardown-on-needs-human` (or gate it on a config/role flag) so the bg
   session is *kept alive* on `needs_human`. The success path is unchanged;
   only `needs_human` changes from teardown to park. Add a question cap so a
   role cannot park-resume-park indefinitely.
3. ⬜ **Propagate `session_id` + `questions`.** Add fields to `RunResult` (and
   the bg classification in `claude_runner.py`) so a `needs_human` result hands
   the orchestrator the parked `session_id` and the question list, not just a
   `handoff_missing`-ish result_kind.
4. ⬜ **Workflow resume loop.** On `needs_human` from a bg Claude role:
   surface the questions to the human (existing orchestrator Q&A path), capture
   the answer, then re-dispatch `claude_bg_run.py --resume <session_id>
   --answer "<reply>"` and continue — looping until the role returns without a
   question. On resume failure the runner already falls back to a fresh
   dispatch carrying the answer (graceful degradation to today's behavior).
5. ⬜ **Persist + chain the session id.** Store the live `session_id` in
   `.quest/<id>/state.json` so a quest paused for a human (minutes/hours, or
   resumed in a new orchestrator session) can still forward the answer. Resume
   works even if the supervisor idle-reaped the process — the transcript
   persists on disk — but the id must be remembered. **Chain it:** each
   `--resume` forks a *new* session id (returned as `resumed_from` + new
   `session_id`), so state must update every round.
6. ⬜ **Lifecycle / sweep guard.** A parked session is legitimately alive
   between question and answer, so the orphan sweep
   (`--sweep quest-<id>-`) must run only at quest start/abandon, never while a
   session is parked awaiting a human. Define who tears down a parked session
   when the human abandons the quest (quest archive/abandon time).
7. ⬜ **Ask-policy relaxation.** Quest roles are currently told "don't ask,
   make assumptions." The relay means *allowing* a bg Claude role to ask when
   genuinely blocked (write the `needs_human` handoff) — a deliberate, scoped
   relaxation for the bg-Claude path only; Codex roles stay non-interactive.

Conveyance is the easy part: Codex is the orchestrator and the human is present
in the Codex session, so "convey + get reply" is just the orchestrator printing
the questions and waiting — no new transport. The historically-hard bit (no
`claude reply` CLI) is already solved by resume-by-session-id.
