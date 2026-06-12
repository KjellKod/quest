---
title: claude-bg-run — Standalone Background-Agent Runner (Step 1)
purpose: Specify a quest-agnostic CLI that runs a single Claude background-agent task to completion and returns a structured result, communicating purely through files. It is the proving ground for the background-agent transport before any quest wiring.
audience: Implementing agent and reviewers.
scope: One standalone script (dispatch → confirm → wait-on-files → collect → teardown). No quest coupling.
status: implemented — PoC validated end-to-end on a real machine (see PoC status)
owner: maintainers
last_updated: 2026-06-11
related:
  - docs/implementation/claude-bg-transport-migration.md
  - scripts/quest_claude_bridge.py
  - scripts/quest_runtime/claude_runner.py
  - ideas/archive/2026-05-31-codex-driven-interactive-claude-relay.md
---

# claude-bg-run — Standalone Background-Agent Runner (Step 1)

## Purpose

A single, dependency-free CLI — proposed `scripts/claude_bg_run.py` — that runs
**one** Claude task through the official background-agent surface
(`claude --bg` + the per-user supervisor) and blocks until the task has produced
its expected output **files**, then returns a structured result and tears the
session down.

It is deliberately **quest-agnostic** (exactly like `scripts/quest_claude_bridge.py`
is today): it knows nothing about quest phases, `handoff.json` schemas,
`orchestration.json`, or roles. It knows only: *dispatch a prompt, wait for these
files to appear, return what happened.* That makes it independently runnable and
testable — `claude_bg_run.py --prompt "…write result to out.json" --wait-for out.json` —
so we can prove and iterate on the transport **before** touching quest. Quest
later calls it with its own artifact paths as `--wait-for`; that wiring is Step 2
and out of scope here.

### Non-goals (Step 1)

- No quest integration, no transport switch, no preflight changes (Step 2).
- No multi-turn conversation, no replying to a running session.
- No log scraping for results (see finding F1 — impossible reliably).
- Not a replacement for the bridge yet; it is a peer we validate alongside it.

## Validated behavior (live, Claude Code 2.1.159→2.1.173)

These findings are empirical (run against the real CLI) and drive every design
choice below. Where a behavior could not be fully validated here, it is marked
and pushed to the machine-validation checklist.

| # | Finding | Consequence for the script |
|---|---|---|
| F1 | ~~`claude logs <id>` returns the raw TUI screen buffer~~ **Corrected (2.1.173): there IS no `claude logs` subcommand** — unknown verbs parse as a *prompt* and no-op. The session transcript at `~/.claude/projects/<project>/<sessionId>.jsonl` is the log. | Results MUST travel via files. Diagnostics (`logs_tail`) come from the transcript JSONL (last assistant-text lines, distilled), located by globbing `<transcripts-root>/*/<sessionId>.jsonl`. |
| F2 | `claude agents --json` reports per-session `state` and `status`. Observed transitions: `working`/`busy` → `done`/`idle`; a session that needs a permission decision ends `blocked`/`idle`. | Completion + failure are detectable structurally: success via files (primary) + `state==done`; **`state==blocked` → fail fast** (don't wait for timeout). |
| F3 | The supervisor starts **on-demand** ("origin: transient — started on-demand by `claude --bg`"). There is a cold-start window; once, a dispatch printed success while `daemon status` was `not running` and the session never registered. | A **confirmation step** is mandatory: after dispatch, poll `agents --json` until the session appears (bounded). No appearance → `dispatch_failed`. The success line alone is not proof. |
| F4 | A `--bg` dispatch blocked by the bypass disclaimer printed an error **and still exited 0**. | Do not trust the process exit code. Success = parsing `backgrounded · <shortID>` from stdout **and** F3 confirmation. |
| F5 | `--permission-mode bypassPermissions` (and `auto`) are refused until `claude --dangerously-skip-permissions` is accepted once interactively, per machine. | bypass is the intended unattended mode; the script must detect the refusal error and surface remediation. This one-time acceptance is a hard prerequisite. |
| F6 | A `--permission-mode acceptEdits` session asked to create new files ended `blocked` without writing. | For unattended file-writing, `acceptEdits` is insufficient; bypass (F5) is required. The script defaults to bypass and treats `blocked` as a permission failure with a clear message. |
| F7 | Dispatch stdout format: `backgrounded · <shortID>[ · <name>]`, plus a 4-line management hint. An idle no-prompt dispatch appended `(idle — send a prompt to start)`. | shortID regex: `backgrounded\s*·\s*([0-9a-f]+)`; name is optional; tolerate the idle suffix. |
| F8 | `agents --json` background entries carry `id`, `name`, `status`, `state`, `sessionId`, `pid`, `cwd`; interactive sessions lack `id/name/status/state`. | Match dispatched sessions by `name` (preferred) or `id`; ignore `kind==interactive` rows. |
| F9 | ~~`claude stop <id>` then `claude rm <id>` cleanly remove a session~~ **Corrected (2.1.173): `stop`/`rm` are not subcommands either** — they parse as a prompt and silently do nothing (this is why earlier teardowns left orphans). The `agents --json` row carries the session's `pid`; the scriptable stop is signalling that pid. The daemon may **respawn a parked session once** from its spare pool (same row id, fresh pid), and a killed row may linger pid-less ("settled") in the listing. Background sessions auto-isolate edits into `.claude/worktrees/` unless disabled. | Teardown = signal the row's *current* pid (SIGTERM, escalate to SIGKILL) **repeatedly until the row drops its pid or disappears**, only **after** results are collected. Pass `--settings '{"worktree":{"bgIsolation":"none"}}'` so writes land in the real workspace. |
| F11 | A **parked** session (idle, awaiting input — e.g. left alive after `needs_human`) reads `state==blocked` in `agents --json`, identical to a genuinely stuck session. | Resume-mode polling must never match the parked parent's row: session matching uses **strict precedence** (short id → name → sessionId), not first-row-wins OR-matching, or the parent's `blocked` shadows the new agent and misreports the run. |
| F12 | `claude --bg --resume <sid>` **forks**: the new agent continues the conversation under a **new sessionId** (daemon roster: `launch.mode=resume, fork=true`), while the parked parent stays alive and would be orphaned. | The envelope reports the NEW `session_id` (chain further resumes off it) plus `resumed_from`; after the new agent is confirmed, the runner retires the parked parent. |
| F10 | ~~Not validated here~~ **CLOSED (2026-06-11, real logged-in machine):** end-to-end writes by bypass-accepted sessions reached the expected files, including the full needs_human → resume-by-name → answered → artifact loop. | The happy path is proven operational. Remaining manual check: `/usage` billing attribution (machine-validation item 2). |

## The file-based completion contract

The runner's entire model of "done" is files on disk. The caller declares what
to wait for; the runner makes the agent's prompt carry a matching instruction.

- `--wait-for <path>` (repeatable): paths that must exist **and be non-empty**
  for the task to count as complete. This is the success condition.
- The runner appends a small, documented **completion-protocol** block to the
  prompt so a naive standalone prompt still works:

  ```
  When you have finished, you MUST write your output to the file(s):
    <wait-for paths>
  Write files directly with the Write tool. Do not ask questions; if details are
  missing, make explicit assumptions and proceed.
  ```

  `--no-protocol` suppresses this when the caller's prompt already specifies the
  artifact contract (quest will pass its own role prompt and may use this).
- Completion = all `--wait-for` paths satisfied (primary), corroborated by
  `state==done`. The runner never parses model text for the result.

This is the same contract `scripts/quest_runtime/claude_runner.py` already polls
for (`handoff.json` + artifacts); the runner just owns the loop so it is usable
without quest.

## CLI surface

Mirrors `quest_claude_bridge.py` where sensible (drop-in transport sibling):

```
scripts/claude_bg_run.py
  (--prompt TEXT | --prompt-file PATH | -)        # task; '-' or stdin supported
                                                  # in resume mode: the fallback task
  --resume REF               (session id, agent SHORT ID, or agent NAME — names are
                              resolved live via `agents --json`, so a session renamed
                              in the agent view stays resumable)
  --answer TEXT | --answer-file PATH | -          (resume mode: the human's reply)
  --no-fallback              (resume mode: don't re-dispatch fresh if resume fails)
  --wait-for PATH            (repeatable, >=1 unless --no-wait)
  --model NAME               (optional; defaults to CLI/account default)
  --permission-mode MODE     (default: bypassPermissions)
  --effort LEVEL             (optional: low|medium|high|xhigh|max)
  --add-dir PATH             (repeatable; cwd added by default)
  --name NAME                (default: auto "bgrun-<8hex>")
  --no-bg-isolation          (default ON → injects --settings bgIsolation:none)
  --timeout SECONDS          (default 1800; runner-enforced; stop at deadline)
  --confirm-timeout SECONDS  (default 20; F3 registration window)
  --poll-interval SECONDS    (default 2; file checks)
  --status-interval SECONDS  (default 10; agents --json checks)
  --keep                     (skip teardown; for debugging)
  --json                     (emit the result envelope to stdout)
  --no-protocol              (don't append the completion-protocol block)
  --transcripts-root PATH    (default ~/.claude/projects; logs_tail source — F1)
```

### Output envelope (`--json`)

```json
{
  "status": "ok | needs_human | timeout | dispatch_failed | blocked | session_failed | incomplete | precondition_failed | interrupted",
  "short_id": "d868c9d3",
  "session_id": "d868c9d3-…",   // resume mode: the NEW (forked) session id — F12
  "name": "bgrun-1a2b3c4d",
  "resumed": false,
  "resumed_from": null,          // resume mode: the session id that was continued
  "fell_back": false,            // resume failed, re-dispatched fresh with the answer
  "wait_for": ["…"],
  "artifacts_found": ["…"],
  "missing": ["…"],
  "questions": ["…"],            // needs_human: the agent's question(s)
  "final_state": "done | blocked | absent | working",
  "duration_s": 41.2,
  "logs_tail": "…",          // non-ok status only; distilled from the transcript (F1)
  "message": "human-readable summary / remediation"
}
```

Exit codes: `0` ok; `2` precondition_failed (CLI/auth/bypass-acceptance — F4/F5);
`3` dispatch_failed (F3); `4` blocked (F6); `5` timeout; `6` session_failed/incomplete;
`10` needs_human (actionable, not a failure); `130` interrupted (Ctrl-C, session
torn down). (Distinct codes so a shell harness — and later quest's
`classify_failure_kind` — can route without parsing stdout.)

## Lifecycle (the state machine)

```
0. PRECHECK
   - `command -v claude`; `claude auth status` → loggedIn:true (honor CLAUDE_CONFIG_DIR/HOME)
   - if permission-mode is bypass/auto: dispatch will reveal the F5 gate; detect its
     exact error string up front is not possible without dispatching, so treat the
     F5 error in step 1 as precondition_failed with remediation.
1. DISPATCH
   - build argv: claude --bg --name <name> [--model][--effort] --permission-mode <m>
     [--settings bgIsolation:none] --add-dir <each> "<prompt + completion-protocol>"
   - run, capture stdout (DO NOT trust exit code — F4)
   - if stdout matches the bypass-acceptance refusal (F5) → precondition_failed(2)
   - parse shortID (F7); if absent → dispatch_failed(3)
2. CONFIRM (F3)
   - poll `agents --json` every poll-interval up to confirm-timeout for a row whose
     id==shortID (or name==<name>) — strict precedence, never by sessionId, which
     would falsely match the parked parent in resume mode (F11); capture id + sessionId
   - never appears → dispatch_failed(3) with daemon-status snapshot in message
   - resume mode, once confirmed: retire the parked parent agent (F12; respects --keep)
3. WAIT  (loop until deadline)
   - every poll-interval: check all --wait-for paths exist & non-empty
       → all satisfied: capture, go COLLECT (ok)
   - every status-interval: read this session's state from `agents --json`
       working  → keep waiting
       blocked  → COLLECT then blocked(4) + logs_tail + permission remediation (F6)
       done but wait-for unsatisfied → short grace (e.g. 2 poll-intervals), then incomplete(6)
       absent (unexpected) → session_failed(6)
   - deadline reached → timeout(5); the final teardown stops the session
4. COLLECT
   - record artifacts_found / missing; on any non-ok, distill the transcript tail (F1)
5. TEARDOWN  (unless --keep; skipped entirely for needs_human — session stays resumable)
   - only AFTER collect: signal the row's current pid until the row settles (F9)
6. RETURN envelope + exit code
```

## Auth, permissions, worktrees (operator prerequisites)

- **One-time, per machine (human):** `claude login` (subscription), and
  `claude --dangerously-skip-permissions` once, accepting the disclaimer, so
  background sessions may run in `bypassPermissions` (F5). The runner cannot do
  these; it detects their absence and returns `precondition_failed` with the
  exact remediation command.
- **Worktree isolation (F9):** default `--settings '{"worktree":{"bgIsolation":"none"}}'`
  so edits land in the real working directory and are not lost to `claude rm`'s
  worktree cleanup. `--add-dir` defaults to cwd; callers add more.

## Standalone validation plan (no quest)

A `tests/`-style harness and a manual checklist, both runnable without quest:

Unit (no live model — a fake `claude` shim on `PATH`):
- argv construction pins flags incl. bgIsolation + name scheme + completion-protocol.
- shortID parse over real samples incl. the `(idle …)` suffix (F7) and the F5
  refusal string → precondition_failed.
- exit-code-0-on-error is ignored; success requires shortID + confirmation (F4).
- confirm timeout → dispatch_failed (F3); state mapping working/done/blocked/absent (F2/F6).
- teardown never precedes collect; deadline issues stop then timeout.

Manual / machine-validation checklist (real logged-in machine — closes F10):
1. After the one-time bypass acceptance, run:
   `claude_bg_run.py --json --wait-for /tmp/bgrun/out.json
     --prompt "Write {\"ok\":true} to /tmp/bgrun/out.json"` → expect status ok,
   file present, session removed afterward.
2. Confirm `/usage` attributes the run to **subscription**, not API credit
   (validates the billing premise of the whole migration).
3. Force a permission block (omit bypass) → expect status blocked(4), fast, with
   remediation — not a 30-min hang.
4. Kill the daemon mid-run / run in a constrained shell → expect dispatch_failed
   or session_failed, never a silent hang (F3).
5. Verify writes land in the real path, not `.claude/worktrees/` (F9).

## Relationship to the bridge and to Step 2

- Same spirit and a comparable CLI to `scripts/quest_claude_bridge.py`, so Step 2
  can select between them behind the `claude_role_transport` switch
  (see `docs/implementation/claude-bg-transport-migration.md`) with no change to
  prompts or the artifact contract.
- Step 2 (separate, after this proves out): quest's runner calls `claude_bg_run.py`
  with `handoff.json` + role artifacts as `--wait-for` and `--no-protocol`
  (quest supplies its own role prompt), maps the exit codes into
  `classify_failure_kind`, and adds the preflight transport probe.

## PoC status (2026-06-11)

Proof of concept landed and validated:

- `scripts/claude_bg_run.py` — stdlib-only runner implementing the lifecycle
  below, plus `pty_capture()` (the headless-PTY noise firewall) and a
  `--self-test` that demonstrates strip-to-signal with no `claude` needed.
- `tests/unit/test_claude_bg_run.py` — 20 tests, **all passing** (`uv run pytest`),
  driving a fake-`claude` shim (multi-row `agents --json` with pids, parked
  parent, no fake stop/rm/logs verbs) through every branch: ok+pid-signal
  teardown, --keep, needs_human bubble-back, **needs_human keeps the session
  alive (no teardown)**, **resume not shadowed by the parked parent (F11
  regression)**, **resume by renamed agent name / by short id**, resume-unknown
  →precondition, **resume falls back to a fresh dispatch**, resume-without-answer
  →precondition, blocked+transcript-logs, dispatch_failed (never registers),
  bypass-refusal→precondition, timeout→teardown, incomplete, the
  shortID/idle-suffix regex, and the real-PTY firewall.
- Resume relay: `needs_human` leaves the session alive and surfaces `session_id`;
  the orchestrator answers with `--resume <session_id|short_id|name> --answer
  "<reply>"` (fallback to a fresh `--bg` carrying the answer if resume fails).
  Ctrl-C tears the live session down (exit 130) instead of orphaning it.
- **Real-CLI end-to-end (2026-06-11, real logged-in machine, 2.1.173):** the full
  loop validated live — dispatch → `needs_human` (question bubbled, session
  parked) → **resume by agent NAME** → answer delivered into the same
  conversation (fork, F12) → declared artifact written → status ok → parked
  parent retired → new agent torn down. This run also *corrected* three earlier
  findings: no `logs`/`stop`/`rm` subcommands exist (F1/F9 — old teardown was a
  silent no-op that left orphans), a parked session reads `state==blocked`
  (F11 — it used to shadow the resume and misreport `blocked`), and resume forks
  to a new sessionId (F12).
- Machine-validation item 2 (`/usage` attributes runs to subscription, not API
  credit) remains a manual check.

## Examples to try

One-time, per machine (a human, once): `claude login`, then accept bypass mode
once interactively with `claude --dangerously-skip-permissions` (the runner
defaults to `--permission-mode bypassPermissions`).

```bash
# 0. No claude needed — prove the PTY noise firewall (ANSI in → clean text out).
python3 scripts/claude_bg_run.py --self-test

# 1. Happy path: dispatch, wait for the declared file, return ok, tear down.
python3 scripts/claude_bg_run.py --json \
  --wait-for /tmp/bgrun/out.json \
  --prompt 'Write {"ok":true,"note":"hello from a bg agent"} to /tmp/bgrun/out.json'
#   → status ok; /tmp/bgrun/out.json present; session removed.
#   Then check `/usage` shows this against your SUBSCRIPTION, not API credit.

# 2. needs_human bubble-back, then resume the SAME session with the answer.
#    Give the agent a real fork so it asks instead of assuming:
python3 scripts/claude_bg_run.py --json \
  --handoff-file /tmp/bgrun/handoff.json \
  --wait-for /tmp/bgrun/plan.md \
  --prompt 'Draft a 3-line rollout plan in /tmp/bgrun/plan.md. If you must choose
            between a canary rollout and a big-bang rollout and it is not
            specified, do NOT guess: write {"status":"needs_human","questions":
            ["canary or big-bang?"]} to /tmp/bgrun/handoff.json and stop.'
#   → status needs_human, questions:[...], session LEFT ALIVE, prints session_id.

# ...the orchestrator asks the human, gets "canary", then continues that session.
# --resume takes the session_id, the agent's short id, or its NAME — so a session
# renamed in the agent view (`claude agents`) stays resumable:
python3 scripts/claude_bg_run.py --json \
  --resume <session_id-or-short_id-or-name-from-step-2> \
  --answer 'Use a canary rollout.' \
  --wait-for /tmp/bgrun/plan.md \
  --prompt 'Draft a 3-line rollout plan in /tmp/bgrun/plan.md.'   # fallback task
#   → resumes the same conversation as a FORK (new session_id in the envelope,
#     `resumed_from` = the continued session; chain further resumes off the new id);
#     the parked parent agent is retired once the fork is confirmed. On resume
#     failure, re-dispatches fresh with the answer (because --prompt is provided).
#     status ok; plan.md written.

# 3. Quest-style call (what Step 2 will issue): wait on the role's own artifacts.
python3 scripts/claude_bg_run.py --json --no-protocol \
  --name quest-<id>-plan-reviewer-a \
  --handoff-file .quest/<id>/phase_01_plan/handoff_plan-reviewer-a.json \
  --wait-for  .quest/<id>/phase_01_plan/review_plan-reviewer-a.md \
  --wait-for  .quest/<id>/phase_01_plan/handoff_plan-reviewer-a.json \
  --add-dir "$(pwd)" \
  --prompt-file .quest/<id>/phase_01_plan/reviewer_a_prompt.txt

# 4. No-write smoke that does NOT need the bypass accept (plan mode, no files):
python3 scripts/claude_bg_run.py --json --permission-mode plan \
  --prompt 'Reply with exactly: OK'
#   → completion == reaching `done`; useful to confirm dispatch/confirm/teardown.
```

## Decisions made (changeable at review)

1. Name `scripts/claude_bg_run.py`; single **blocking** `run` behavior (no
   subcommands) — smallest surface that proves the transport. Status passthrough
   is the native `claude agents --json`; there are no native logs/stop verbs to
   pass through (F1/F9), so the runner owns transcript-tail and pid-signalling.
2. Default `--permission-mode bypassPermissions` (F6 shows lesser modes block).
3. Runner **injects** the completion-protocol unless `--no-protocol`, so the tool
   is useful with a naive prompt yet yields full control to quest later.
4. Distinct exit codes per failure class (for shell + future quest routing).

## One open item for you

~~F10: the end-to-end write under a bypass-accepted session could not be proven
in this sandbox.~~ **Closed 2026-06-11** — the full loop (dispatch →
`needs_human` → resume by name → artifact written → parent retired) ran green on
a real logged-in machine; see PoC status. The one remaining manual check is
`/usage` billing attribution (machine-validation item 2): confirm a run lands on
your **subscription**, not API credit.
