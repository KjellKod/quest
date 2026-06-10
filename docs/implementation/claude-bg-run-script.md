---
title: claude-bg-run — Standalone Background-Agent Runner (Step 1)
purpose: Specify a quest-agnostic CLI that runs a single Claude background-agent task to completion and returns a structured result, communicating purely through files. It is the proving ground for the background-agent transport before any quest wiring.
audience: Implementing agent and reviewers.
scope: One standalone script (dispatch → confirm → wait-on-files → collect → teardown). No quest coupling.
status: draft — for review before implementation
owner: maintainers
last_updated: 2026-06-09
related:
  - docs/implementation/claude-bg-transport-migration.md
  - scripts/quest_claude_bridge.py
  - scripts/quest_runtime/claude_runner.py
  - ideas/2026-05-31-codex-driven-interactive-claude-relay.md
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

## Validated behavior (live, this environment, Claude Code 2.1.159→2.1.170)

These findings are empirical (run against the real CLI) and drive every design
choice below. Where a behavior could not be fully validated here, it is marked
and pushed to the machine-validation checklist.

| # | Finding | Consequence for the script |
|---|---|---|
| F1 | `claude logs <id>` returns the **raw TUI screen buffer** (ANSI/cursor escapes); the model's text answer is not cleanly extractable. | Results MUST travel via files. `logs` is used only as an opaque diagnostic blob on failure. |
| F2 | `claude agents --json` reports per-session `state` and `status`. Observed transitions: `working`/`busy` → `done`/`idle`; a session that needs a permission decision ends `blocked`/`idle`. | Completion + failure are detectable structurally: success via files (primary) + `state==done`; **`state==blocked` → fail fast** (don't wait for timeout). |
| F3 | The supervisor starts **on-demand** ("origin: transient — started on-demand by `claude --bg`"). There is a cold-start window; once, a dispatch printed success while `daemon status` was `not running` and the session never registered. | A **confirmation step** is mandatory: after dispatch, poll `agents --json` until the session appears (bounded). No appearance → `dispatch_failed`. The success line alone is not proof. |
| F4 | A `--bg` dispatch blocked by the bypass disclaimer printed an error **and still exited 0**. | Do not trust the process exit code. Success = parsing `backgrounded · <shortID>` from stdout **and** F3 confirmation. |
| F5 | `--permission-mode bypassPermissions` (and `auto`) are refused until `claude --dangerously-skip-permissions` is accepted once interactively, per machine. | bypass is the intended unattended mode; the script must detect the refusal error and surface remediation. This one-time acceptance is a hard prerequisite. |
| F6 | A `--permission-mode acceptEdits` session asked to create new files ended `blocked` without writing. | For unattended file-writing, `acceptEdits` is insufficient; bypass (F5) is required. The script defaults to bypass and treats `blocked` as a permission failure with a clear message. |
| F7 | Dispatch stdout format: `backgrounded · <shortID>[ · <name>]`, plus a 4-line management hint. An idle no-prompt dispatch appended `(idle — send a prompt to start)`. | shortID regex: `backgrounded\s*·\s*([0-9a-f]+)`; name is optional; tolerate the idle suffix. |
| F8 | `agents --json` background entries carry `id`, `name`, `status`, `state`, `sessionId`, `pid`, `cwd`; interactive sessions lack `id/name/status/state`. | Match dispatched sessions by `name` (preferred) or `id`; ignore `kind==interactive` rows. |
| F9 | `claude stop <id>` then `claude rm <id>` cleanly remove a session (verified: list returns to interactive-only). Background sessions auto-isolate edits into `.claude/worktrees/` unless disabled. | Teardown = stop → rm, only **after** results are collected. Pass `--settings '{"worktree":{"bgIsolation":"none"}}'` so writes land in the real workspace, not a worktree `rm` would delete. |
| F10 | **Not validated here:** an end-to-end write by a *bypass-accepted* session reaching `state==done` with the expected files present. Blocked by F5 (no interactive acceptance available in this sandbox). | Must be confirmed on a real logged-in machine — see Machine-validation checklist. The script is designed for it; the proof is operational. |

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
```

### Output envelope (`--json`)

```json
{
  "status": "ok | timeout | dispatch_failed | blocked | session_failed | incomplete | precondition_failed",
  "short_id": "d868c9d3",
  "session_id": "d868c9d3-…",
  "name": "bgrun-1a2b3c4d",
  "wait_for": ["…"],
  "artifacts_found": ["…"],
  "missing": ["…"],
  "final_state": "done | blocked | absent | working",
  "duration_s": 41.2,
  "logs_tail": "…",          // present only on non-ok status, raw/opaque
  "message": "human-readable summary / remediation"
}
```

Exit codes: `0` ok; `2` precondition_failed (CLI/auth/bypass-acceptance — F4/F5);
`3` dispatch_failed (F3); `4` blocked (F6); `5` timeout; `6` session_failed/incomplete.
(Distinct codes so a shell harness — and later quest's `classify_failure_kind`
— can route without parsing stdout.)

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
     name==<name> (or id==shortID); capture id + sessionId
   - never appears → dispatch_failed(3) with daemon-status snapshot in message
3. WAIT  (loop until deadline)
   - every poll-interval: check all --wait-for paths exist & non-empty
       → all satisfied: capture, go COLLECT (ok)
   - every status-interval: read this session's state from `agents --json`
       working  → keep waiting
       blocked  → COLLECT then blocked(4) + logs_tail + permission remediation (F6)
       done but wait-for unsatisfied → short grace (e.g. 2 poll-intervals), then incomplete(6)
       absent (unexpected) → session_failed(6)
   - deadline reached → `claude stop <id>` → timeout(5)
4. COLLECT
   - record artifacts_found / missing; on any non-ok, capture `claude logs <id>` tail (opaque)
5. TEARDOWN  (unless --keep)
   - only AFTER collect: `claude stop <id>` (if alive) → `claude rm <id>`  (F9 order)
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

## PoC status (2026-06-10)

Proof of concept landed and validated:

- `scripts/claude_bg_run.py` — stdlib-only runner implementing the lifecycle
  below, plus `pty_capture()` (the headless-PTY noise firewall) and a
  `--self-test` that demonstrates strip-to-signal with no `claude` needed.
- `tests/unit/test_claude_bg_run.py` — 12 tests, **all passing** (`uv run pytest`),
  driving a fake-`claude` shim through every branch: ok+teardown-order,
  needs_human bubble-back, blocked+distilled-logs, dispatch_failed (never
  registers), bypass-refusal→precondition, timeout→stop, incomplete, the
  shortID/idle-suffix regex, and the real-PTY firewall.
- **Real-CLI smoke** (live `claude --bg`, this environment): dispatch +
  `agents --json` confirmation (captured the real `sessionId`) + state polling +
  teardown (no orphans) all worked. `claude logs` was distilled to clean,
  escape-free text — the noise firewall verified against real output.
- **Not yet provable in-sandbox:** the happy "ok via artifact file" path with a
  real session — writes need the one-time bypass acceptance, and this env's own
  `Stop` hook (`stop-hook-reply-gate.py`) forces sessions to `blocked`. Both are
  environment constraints, not runner behavior; the fake-shim tests cover the
  path deterministically. Closing it is machine-validation item 1.

## Decisions made (changeable at review)

1. Name `scripts/claude_bg_run.py`; single **blocking** `run` behavior (no
   subcommands) — smallest surface that proves the transport. Passthrough helpers
   (status/logs/stop) are just the native `claude` commands; no need to wrap.
2. Default `--permission-mode bypassPermissions` (F6 shows lesser modes block).
3. Runner **injects** the completion-protocol unless `--no-protocol`, so the tool
   is useful with a naive prompt yet yields full control to quest later.
4. Distinct exit codes per failure class (for shell + future quest routing).

## One open item for you

F10: the end-to-end write under a *bypass-accepted* session could not be proven
in this sandbox (no interactive acceptance available). The design assumes it
works (it is the documented, billed-as-subscription path); item 1 of the
machine-validation checklist is the gate. If you can run that one command on your
machine after `claude --dangerously-skip-permissions`, we'll have the green light
before writing code — or we write the code and that command becomes its first
real-run test. Your call which order.
