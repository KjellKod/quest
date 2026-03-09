# Codex-Led Claude Bridge Runtime Hardening

Status: complete

Retired from `ideas/` on 2026-03-09 after the bridge runtime path landed in Quest orchestration (`scripts/quest_claude_runner.py`, `scripts/quest_claude_probe.py`, workflow/runtime docs, and runtime tests) and was exercised by a Codex-led solo smoke test.

## Problem

We already added a working Claude bridge for Codex-led Quest runs, but it still does not "just work."

The current system is too prompt-dependent. To get even a trivial smoke test to pass, the operator has to restate runtime rules that should already be owned by Quest itself:

- run the bridge probe first
- use the correct Claude runner script
- use `bypassPermissions`
- grant explicit repo / quest access
- enforce non-interactive behavior
- prohibit `needs_human`
- use file polling and `handoff.json`
- use `scripts/quest_state.py`
- respect solo-mode dispatch rules

If those details must be repeated in the user prompt, the runtime is not yet native.

## Desired Behavior

In a Codex-led Quest:

- Claude-designated roles should dispatch through the Quest Claude bridge automatically
- the bridge probe should happen automatically before the first Claude role
- permission mode and allowed directory access should be encoded in the runtime adapter
- non-interactive policy should be enforced by Quest, not delegated to the prompt
- state transitions and handoff polling should be script-owned
- solo/full dispatch rules should be mechanical

The user prompt should only need to describe the task, not the runtime plumbing.

## What Must Become Implicit

These should stop being operator instructions and become Quest-owned defaults:

- `scripts/quest_claude_probe.py` runs automatically before first bridge-backed Claude role
- `scripts/quest_claude_runner.py` is the canonical Claude dispatch path for Codex-led runs
- `scripts/claude_cli_bridge.py` is the transport layer, not the orchestration entrypoint
- Claude bridge roles run with:
  - `bypassPermissions`
  - explicit repo access
  - explicit `.quest/<id>/...` artifact access
  - non-interactive policy (`no questions`, `no needs_human`, explicit assumptions)
- `scripts/quest_state.py` owns state transitions
- `handoff.json` polling is the routing source of truth

## Required Repo Changes

1. Add a first-class `claude_bridge` runtime path in Quest orchestration
2. Make role dispatch choose runtime adapter from model/runtime mapping, not prose assumptions
3. Encode bridge preflight in workflow, not in operator prompts
4. Encode bridge permission mode and directory access in the runner
5. Enforce non-interactive Claude bridge policy in runtime code and workflow docs
6. Route state transitions through `scripts/quest_state.py`
7. Route handoff polling / validation through Quest-owned helpers
8. Make solo-mode dispatch explicit and mechanical for Codex-led runs
9. Add a built-in smoke test path or documented minimal acceptance test

## Acceptance Criteria

- A Codex-led solo Quest can run a trivial task without the operator restating bridge mechanics
- Claude-designated roles are automatically dispatched through the correct runner
- The bridge probe runs automatically before first Claude dispatch
- `runtime=claude` appears in `context_health.log` for bridge-backed Claude roles
- `handoff.json` is the authoritative routing source without prompt-level reminders
- Solo-mode role selection is automatic: planner, reviewer A, builder only
- The operator prompt can stay task-focused

## Anti-Goal

Do not solve this by writing longer user prompts or more operator checklists.

That only hides the orchestration gap instead of fixing it.
