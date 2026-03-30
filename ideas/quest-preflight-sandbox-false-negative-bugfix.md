# Bugfix Idea: Quest Preflight Should Distinguish Sandbox Timeout From True Claude Unavailability

Date: 2026-03-23
Area: Quest orchestration preflight

## Problem

The current quest preflight can incorrectly report:

> Claude bridge not available -- quest will run Codex-only (all roles).

when Claude is actually installed, authenticated, and usable.

## Confirmed behavior

What was verified:

- `claude` exists on the machine
- `claude auth status` is healthy
- sandboxed `claude --print ...` hangs / times out in this Codex environment
- sandboxed `python3 scripts/quest_claude_probe.py ...` times out
- escalated/outside-sandbox `claude --print ...` succeeds immediately
- escalated/outside-sandbox `python3 scripts/quest_claude_probe.py ...` succeeds and writes the expected handoff artifact

So the current failure mode is not:
- missing Claude installation
- bad Claude authentication
- true bridge unavailability

It is:
- sandbox-induced false negative during Codex-led Claude bridge probing

## Root cause

`./scripts/quest_preflight.sh --orchestrator codex` currently treats a failed sandboxed probe as `available: false` without distinguishing why it failed.

That collapses multiple different cases into the same outcome:
- Claude CLI missing
- Claude auth missing
- real bridge failure
- sandbox/network/process restrictions causing timeout

Because of that, a quest can incorrectly route to Codex-only fallback even when the intended balanced model setup is available.

## Why this matters

This affects quest quality and role balancing.

A quest that should use:
- Claude planner/reviewer roles
- Codex planner/reviewer roles

can instead run all roles on Codex because preflight misclassified Claude as unavailable.

That is a real orchestration bug, not just a cosmetic warning issue.

## Desired behavior

Quest preflight should distinguish at least these outcomes:

1. `claude_cli_missing`
2. `claude_auth_missing`
3. `claude_bridge_timeout_in_sandbox`
4. `claude_bridge_unreachable`
5. `claude_bridge_available`

At minimum, sandbox timeout must not be silently translated into “Claude unavailable”.

## Recommended fix

### 1. Make probe results more explicit

Update the Codex-side Claude probe/preflight path so it captures and surfaces the actual failure mode.

Instead of only:
- `available: true|false`

return something like:
- `available`
- `failure_kind`
- `stderr`
- `probe_runtime`

Example failure kinds:
- `cli_missing`
- `auth_missing`
- `timeout`
- `sandbox_timeout`
- `bridge_error`

### 2. Improve warning text

Current warning text blames install/auth too aggressively.

If the failure is a timeout in sandbox, the warning should say that directly.

Example:

> Claude bridge probe timed out in the current sandboxed Codex session. Claude may still be available outside the sandbox. Retry with escalated probe or use verified availability before falling back to Codex-only mode.

### 3. Use a better fallback policy

If Claude CLI is present and authenticated but the probe times out in sandbox, the system should not immediately downgrade to Codex-only without marking the result as uncertain.

Safer alternatives:
- mark status as `unknown` instead of `unavailable`
- ask for an escalated probe
- allow the orchestrator to use the last known successful bridge status if recent and trustworthy

### 4. Preserve operational clarity in quest logs

Quest logs and quest briefs should record the real reason for fallback.

Bad:
- `Claude bridge not available`

Better:
- `Claude bridge probe timed out in sandbox; fallback chosen due to uncertain reachability`

## Acceptance criteria for a fix

- A sandbox timeout no longer produces the same classification as true Claude unavailability.
- Warning text does not incorrectly instruct the user to authenticate when auth is already healthy.
- Quest routing can distinguish `unavailable` from `uncertain due to sandbox timeout`.
- A verified outside-sandbox Claude probe is treated as evidence of availability.
- Quest logs reflect the actual fallback reason.

## Follow-up

After this bugfix, restart blocked quests that were downgraded to Codex-only based on sandbox false negatives when Claude availability has been confirmed outside the sandbox.
