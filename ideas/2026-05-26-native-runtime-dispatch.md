---
title: Native Runtime Dispatch Before Cross-Family Bridges
purpose: Make Quest role dispatch prefer the orchestrator's native same-family sub-agent runtime before falling back to CLI, MCP, or bridge adapters.
audience:
  - quest-maintainers
  - quest-users
  - runtime-adapter-authors
status: proposed
date: 2026-05-26
related:
  - .skills/quest/SKILL.md
  - .skills/quest/delegation/workflow.md
  - .skills/quest/agents/planner.md
  - ideas/2026-05-18-per-quest-orchestration-override.md
  - ideas/2026-04-29-research-fanout-skill.md
  - scripts/quest_claude_runner.py
  - scripts/quest_claude_bridge.py
origin:
  - Development Time Jira metrics Quest startup exposed confusion between configured Codex roles and automatic Claude fallback after a Codex CLI timeout.
---

# Native Runtime Dispatch Before Cross-Family Bridges

## Summary

Quest should choose role execution by the configured role runtime and by the
orchestrator's native same-family capabilities before using cross-family
bridges.

If the orchestrator is Codex and a role is configured as Codex, Quest should
spawn a native Codex sub-agent when that runtime is available. It should not
route the role through Codex CLI MCP as the first choice, and it should not
fall back to Claude just because one Codex adapter timed out.

The symmetric rule should apply to Claude-led sessions: if the orchestrator is
Claude and a role is configured as Claude, use Claude's native task/sub-agent
runtime first.

Cross-family execution still matters, but it is a bridge case:

| Orchestrator | Role runtime | Preferred dispatch | Bridge needed? |
|---|---|---|---|
| Codex | Codex | Native Codex sub-agent (`spawn_agent` when available) | No |
| Codex | Claude | `scripts/quest_claude_runner.py` / `quest_claude_bridge.py` | Yes |
| Claude | Claude | Native Claude task/sub-agent runtime | No |
| Claude | Codex | Codex MCP / companion runtime | Yes |

This is a dispatch policy proposal, not a model-quality claim.

## Motivation

Per-quest orchestration now records the user's model choices in
`.quest/<id>/orchestration.json`. Those choices should be binding in normal
execution.

The current workflow text still has older wording that can make Codex roles
look synonymous with `mcp__codex__codex` / Codex CLI. In a Codex-led
environment that exposes native sub-agent tools, that is less efficient and
less faithful to the selected runtime:

- It introduces an extra CLI/MCP transport boundary.
- It forces mapping abstract model names such as `gpt-5.5` to CLI-specific
  names when no mapping is needed for native sub-agents.
- A tool timeout can be mistaken for model failure.
- The fallback path may silently switch model families even though the user
  intentionally configured the role as Codex.

The practical rule should be simpler: same-family roles use same-family native
sub-agents first; cross-family roles use bridges.

## Proposed Policy

### Runtime selection

Every role dispatch should classify the selected role model from
`.quest/<id>/orchestration.json` into a runtime family:

- Claude-family: `claude`, `claude-*`
- Codex-family: `gpt-*`, `codex`, `gpt-*-codex`, and other OpenAI/Codex-backed
  model names supported by the local orchestrator

Then dispatch using this precedence:

1. Native same-family sub-agent runtime.
2. Same-family adapter fallback, if the native runtime is unavailable.
3. Cross-family fallback only when explicitly allowed by the configured role,
   the workflow section, or the user.

### Codex-led sessions

When the orchestrator is Codex:

1. Codex-family role:
   - Prefer native `spawn_agent`.
   - Pass the role instructions and prepared artifact paths in the prompt.
   - Use `fork_context=false` by default. Quest role agents should receive the
     brief, role instructions, relevant artifact paths, and explicit
     assumptions in the prompt, not the full orchestrator transcript.
   - Set `model` from `orchestration.json` only when an explicit override is
     needed; otherwise let the child inherit the parent model.
   - Use `worker` for builder/fixer roles; use `default` for planner,
     reviewer, and arbiter artifact roles unless a more specific local agent
     type exists.
   - Read `handoff.json` from disk after completion.
   - Require the final sub-agent response to be a compact handoff only:
     status, artifact paths, next role, and one-line summary. Full plans,
     reviews, code diffs, and analysis belong in artifacts.
2. Claude-family role:
   - Use `scripts/quest_claude_runner.py`, backed by
     `scripts/quest_claude_bridge.py`, with the same artifact contract and
     context-health logging.
3. If native Codex sub-agent spawning is unavailable:
   - Fall back to Codex CLI MCP for Codex-family roles.
   - Record the adapter used in `context_health.log`.

### Claude-led sessions

When the orchestrator is Claude:

1. Claude-family role:
   - Prefer native Claude task/sub-agent dispatch.
   - Preserve the same artifact preparation, handoff polling, and
     context-health logging contract.
   - Use the Claude equivalent of `fork_context=false` when available: do not
     pass the full orchestrator transcript to role agents unless the workflow
     explicitly needs it. If Claude's native task API does not expose this
     control, document the actual behavior before changing dispatch.
   - Require compact final handoffs for the same reason as Codex: artifacts
     are the durable source of truth; the orchestrator should retain only
     paths, status, next, and a one-line summary.
2. Codex-family role:
   - Use the Codex MCP / companion runtime.
3. If native Claude task dispatch is unavailable:
   - Fall back to the best same-family Claude adapter before considering
     Codex-family fallback.

### Context containment

Native sub-agents are compatible with Quest's thin-orchestrator design only if
their response contract stays artifact-first.

The intended context flow is:

```text
orchestrator -> child: brief + role instructions + artifact paths
child -> artifacts: full plan/review/build notes/findings
child -> orchestrator: status + artifact paths + next + one-line summary
```

The orchestrator must not route from the sub-agent's long-form response body.
It must read the role's `handoff.json` and then discard the child response for
routing purposes. This preserves the current anti-poisoning property: role
analysis can be detailed without dragging the whole transcript into the
orchestrator context.

For Codex native sub-agents, `fork_context=false` should be the default for all
Quest role dispatch. Use `fork_context=true` only for exceptional cases where
the child must inherit the exact parent context, and record that exception in
the prompt or context-health log.

For Claude native task/sub-agent dispatch, the implementation needs a targeted
API check:

- Does the native task call always inherit the parent context?
- Is there an option equivalent to `fork_context=false`?
- If not, can Quest emulate containment by using the existing artifact-first
  bridge/runner for Claude roles, or by issuing a minimal prompt through a
  fresh session?

This should be researched before claiming Claude native dispatch has the same
context-isolation semantics as Codex `spawn_agent`.

### Cross-family fallback

Do not silently switch a role from one family to the other after a timeout or
adapter failure.

Examples:

- If `planner=gpt-5.5` and native Codex dispatch fails, retry or fall back
  within Codex runtimes first. Switching to Claude requires explicit user
  approval or an explicit workflow rule for that role.
- If `plan-reviewer-a=claude` and the Claude bridge is unavailable in a
  Codex-led session, block or ask for an approved Codex override instead of
  silently treating the role as Codex.

This keeps `orchestration.json` meaningful.

## Workflow Text Changes

Add a section to `.skills/quest/delegation/workflow.md` near runtime-selection:

```md
### Native Runtime Dispatch

Role execution is chosen by the selected model/runtime in
`.quest/<id>/orchestration.json`, not by role label alone.

If the selected role runtime matches the orchestrator family and native
sub-agent tools are available, use the native sub-agent runtime first:

- Codex orchestrator + Codex role: `spawn_agent`
- Claude orchestrator + Claude role: native `Task(...)`

Use CLI/MCP adapters as same-family fallbacks only when native sub-agent
dispatch is unavailable. Use cross-family bridges only for cross-family roles
or when the user explicitly approves a fallback that changes runtime family.
```

Then update Codex-specific wording:

```md
When the orchestrator is Codex and native sub-agent tools are available,
Codex-designated roles MUST use the native sub-agent runtime first:

- Use `spawn_agent` for Codex roles.
- Set `fork_context=false` by default and pass only the brief, role
  instructions, relevant artifact paths, and explicit assumptions.
- Use `worker` for builder and fixer roles.
- Use `default` for planner, reviewer, and arbiter artifact roles unless a
  more specific local agent type exists.
- Spawn parallel review agents before waiting.
- Read the role's `handoff.json` from disk after completion.
- Require the sub-agent final response to contain only compact handoff data;
  full output must be written to artifacts.

Use Codex CLI MCP only as a same-family fallback when native sub-agent tools
are unavailable, or when the user explicitly requests the Codex CLI runtime.
```

Update fallback language:

```md
If a same-family adapter fails or times out, do not automatically switch model
families. Retry or fall back within the same runtime family first. Switching
from Codex to Claude or Claude to Codex requires the role to be configured for
that family or explicit user approval.
```

## Tests And Validation

Add focused tests that do not require live model calls:

- A workflow text contract test confirms Codex-family role guidance prefers
  native sub-agent dispatch before Codex CLI MCP.
- A workflow text contract test confirms Claude-family role guidance prefers
  native Claude task dispatch before bridges.
- A fallback policy test confirms timeout language does not permit silent
  cross-family fallback when `orchestration.json` selects a different family.
- A resume/startup test confirms `orchestration.json` remains the role source
  of truth.
- A context-containment test or prompt-contract check confirms native Codex
  role dispatch uses `fork_context=false` by default and requires compact final
  responses.
- A research task verifies whether Claude native task dispatch has a direct
  equivalent to `fork_context=false`; until verified, docs must label Claude
  context isolation as an implementation question, not an assumption.

If a runtime dispatcher helper exists or is introduced later, add unit coverage
for this matrix:

| orchestrator | role model | expected first adapter |
|---|---|---|
| codex | gpt-5.5 | native_codex_subagent |
| codex | claude | claude_bridge |
| claude | claude | native_claude_task |
| claude | gpt-5.5 | codex_mcp |

## Out Of Scope

- Rewriting all Quest role execution into a new dispatcher in the first PR.
- Changing default model assignments.
- Removing existing bridge scripts.
- Adding per-user model preferences.
- Treating native sub-agent availability as globally guaranteed across every
  host or client.
- Claiming Claude native task context-isolation semantics without verifying
  the current API behavior.

## Acceptance Criteria

- Quest docs distinguish runtime family from adapter/transport.
- Codex-led Codex roles prefer native Codex sub-agents when available.
- Claude-led Claude roles prefer native Claude task/sub-agent dispatch when
  available.
- Cross-family execution is documented as a bridge/MCP case.
- Same-family adapter failures do not silently switch model families.
- The policy is tied to `.quest/<id>/orchestration.json` so user-selected
  per-quest roles stay meaningful.
- Codex native role dispatch uses `fork_context=false` by default and compact
  handoffs so sub-agent work does not poison orchestrator context.
- Claude native context behavior is either documented from a verified API
  check or explicitly left as a research item.

## Recommended Quest Prompt

```text
/quest "Clarify Quest runtime dispatch so same-family roles use native sub-agents before bridge adapters.

Reference: ideas/2026-05-26-native-runtime-dispatch.md

Goal:
Update Quest workflow instructions so per-quest model choices in
.quest/<id>/orchestration.json are dispatched through the most direct runtime:
Codex-led Codex roles use native Codex sub-agents when available, Claude-led
Claude roles use native Claude task/sub-agents when available, and cross-family
roles use bridges/MCP.

Acceptance criteria:
- workflow.md documents native same-family dispatch before CLI/MCP/bridge adapters.
- Codex CLI MCP is described as a Codex same-family fallback, not the default
  when native Codex sub-agents are available.
- Claude bridge is described as the Codex-to-Claude path, not a generic fallback
  for Codex role timeouts.
- Fallback policy says same-family failures must not silently switch model
  families without role configuration or explicit user approval.
- Native Codex sub-agent dispatch uses fork_context=false by default and keeps
  final responses to compact handoffs; full outputs stay in artifacts.
- Research and document whether Claude native task dispatch has an equivalent
  context-isolation control before claiming parity.
- Tests or text-contract checks cover the runtime matrix in the idea doc.
- Keep changes focused to Quest workflow docs/tests unless a tiny helper is
  needed to make the policy testable."
```
