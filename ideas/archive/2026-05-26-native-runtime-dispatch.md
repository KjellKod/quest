---
title: Native Runtime Dispatch Before Cross-Family Bridges
purpose: Make Quest role dispatch prefer the orchestrator's native same-family sub-agent runtime before falling back to CLI, MCP, or bridge adapters.
audience:
  - quest-maintainers
  - quest-users
  - runtime-adapter-authors
status: done — encoded in the canonical dispatch matrix (.skills/quest/delegation/workflow.md) and select_role_runtime() (scripts/quest_runtime/claude_runner.py); archived 2026-06-11
date: 2026-05-26
related:
  - .skills/quest/SKILL.md
  - .skills/quest/delegation/workflow.md
  - .skills/quest/agents/planner.md
  - docs/quest-journal/orchestration-override_2026-05-18.md
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

This is not primarily a speed argument. The reason to prefer the built-in
native sub-agent mechanism over CLI/MCP/bridge transports is robustness and
direction of travel: native sub-agent spawning is first-party to each model
host and is under active development by the model vendors, so it is the path
they are optimizing and hardening. Bridges and MCP transports are useful glue
for cross-family work, but they add a moving part we maintain rather than one
the vendor maintains. Prefer the first-party mechanism for same-family roles and
keep bridges scoped to the cross-family case they exist for.

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

### Slots, role types, and runtimes are independent

A single review position carries different names in different subsystems, and
they are not 1:1. Keeping them distinct is what makes mixed configurations work.

- **Slot** (`orchestration.json` key): `plan-reviewer-a`, `plan-reviewer-b`,
  `code-reviewer-a`, etc. This is the *position*, and each slot is assigned its
  own model.
- **Runtime/family**: resolved from that slot's model — `claude` or `codex`.
  Resolved **per slot, independently** of the orchestrator's own model and of
  the other slot.
- **Role type / agent definition** (`subagent_type`): one shared definition per
  role — `plan-reviewer`, not `plan-reviewer-a`. Both slots share
  `.claude/agents/plan-reviewer.md` and `.skills/quest/agents/plan-reviewer.md`.
  The `-a`/`-b` distinction lives only in the prompt ("You are Reviewer A/B")
  and the artifact filenames. **Never create per-slot agent definitions.**

Consequences the dispatcher must respect:

- A+B may be any family mix — `claude`+`claude`, `codex`+`codex`, or
  `claude`+`codex` — regardless of the orchestrator. The default config is
  already mixed (`plan-reviewer-a=claude`, `plan-reviewer-b=codex`), so this is
  the normal case, not an edge case.
- The orchestrator model does not constrain slot runtimes; a Claude
  orchestrator routinely drives a Codex reviewer slot and vice-versa.
- Dispatch keys off the slot: resolve its runtime, strip the `-a/-b` suffix to
  get the Claude `subagent_type`, and carry slot identity via the prompt +
  artifact paths.

Worked example — Claude orchestrator, default config:

| Slot | Model | Runtime | Dispatch | Role instructions | Artifacts |
|---|---|---|---|---|---|
| `plan-reviewer-a` | `claude` | Claude | `Task(subagent_type: "plan-reviewer")` | `.skills/quest/agents/plan-reviewer.md` | `review_plan-reviewer-a.md`, `handoff_plan-reviewer-a.json` |
| `plan-reviewer-b` | `gpt-5.5` | Codex | `mcp__codex__codex` | same file | `review_plan-reviewer-b.md`, `handoff_plan-reviewer-b.json` |

Both calls are issued in one message, so they run in parallel.

A fourth naming scheme — the allowlist `role_permissions` keys (`plan_review_a`,
`code_review_agent`, …) — is **not** 1:1 with slots (plan review splits a/b,
code review does not). Reconciling slot ↔ `subagent_type` ↔ permission key is an
enforcement concern, not a dispatch concern; see the permission-posture note
below and the enforcement roadmap. This dispatch policy does not depend on it.

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

**Current state:** native Claude `Task(subagent_type: ...)` dispatch is already
how Claude-family roles run today — e.g. `Task(subagent_type: "plan-reviewer")`
backed by `.claude/agents/plan-reviewer.md`. This section codifies and
guard-rails the existing path; it does not introduce a new capability.

1. Claude-family role:
   - Use native Claude `Task` dispatch.
   - Preserve the same artifact preparation, handoff polling, and
     context-health logging contract.
   - Context isolation is automatic and needs no `fork_context` equivalent: a
     `Task` sub-agent starts in its own fresh context window and does not
     inherit the orchestrator transcript — it only sees the prompt it is given.
     The real containment vector is the *return* path: the sub-agent's final
     message comes back as the `Task` tool result and cannot be suppressed.
     Therefore the durable contract is a compact handoff OUT — the child writes
     full plan/review/build output to artifacts and limits its final message to
     STATUS/ARTIFACTS/NEXT/SUMMARY; the orchestrator routes from `handoff.json`
     on disk and discards the response body.
   - Honor the per-role model from `orchestration.json`. The agent definitions
     are `model: inherit`, which uses the *orchestrator's* model. If a slot's
     `orchestration.json` value names a specific Claude variant (e.g.
     `claude-haiku`, `claude-opus-4.7`), pass it explicitly to the `Task` model
     parameter; inherit only when the value is the bare family token `claude`.
     Otherwise a deliberate per-role model choice is silently voided — the same
     failure mode this proposal forbids for cross-family switches.
   - Issue parallel roles (e.g. both plan reviewers) as multiple `Task`
     tool-uses in a single message; the harness runs them concurrently.
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

For Claude native `Task` dispatch the isolation model is the inverse of Codex's
and needs no research hedge:

- A `Task` sub-agent does not inherit the orchestrator transcript. It starts in
  a fresh context window seeded only by its prompt, so there is nothing to
  "fork" and no `fork_context` knob — isolation-in is automatic and stronger
  than `fork_context=false`.
- The exposure is the return path: the sub-agent's final message is delivered
  to the orchestrator as the `Task` tool result and lands in orchestrator
  context. This cannot be turned off.

So for Claude, containment is enforced entirely by the compact-handoff-OUT
contract: full output to artifacts, final message limited to
STATUS/ARTIFACTS/NEXT/SUMMARY, orchestrator routes from `handoff.json` on disk
and ignores the response body. This is documented Claude Code behavior, not an
open question.

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

### Permission posture (state it plainly)

Native dispatch is permission-neutral. Per-role file/bash boundaries in
`.ai/allowlist.json` `role_permissions` are **not enforced at runtime today**:
the `PreToolUse` hook `.claude/hooks/enforce-allowlist.sh` is not wired in
`.claude/settings.json`, and even if it were, it cannot yet identify which role
is calling (it reads a positional role argument, but `PreToolUse` provides
stdin only). This is tracked in the enforcement-activation work
(`ideas/2026-05-04-ci-review-allowlist-quality-roadmap.md`, plus the archived
`ideas/archive/2026-04-20-allowlist-enforcement-activation.md`).

So role boundaries — planner/reviewers not editing source, the hard pre-build
phase gate — currently hold by **agent instruction and orchestrator
discipline**, not by a sandbox. Native same-family dispatch does not change
this in either direction; it neither adds nor removes enforcement. Any docs or
PR description for this work must say so plainly: this proposal does not make
per-role permissions robust. It is orthogonal to that effort, and routing more
real work through native sub-agents raises the value of landing that roadmap.

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

## Documentation Updates Required

Implementing this policy MUST update the user-facing Quest documentation, not
just the workflow internals. Whoever lands the quest is responsible for:

- Explaining the slot / role-type / runtime / permission-key distinction in
  plain language, with the worked mixed-runtime example above.
- Documenting that A/B slots can be any family mix and that the orchestrator
  model does not constrain slot runtimes.
- Documenting the native-first dispatch rule and the no-silent-cross-family
  fallback rule where users actually look — the Quest setup/usage guides and the
  orchestration-override docs — cross-linked from `orchestration.json`.
- Stating the permission posture honestly (instruction-level today).

The bar: a new user can read one place and understand exactly how their
per-quest model choices map to real dispatch. Treat the docs as part of the
definition of done, not a follow-up.

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
- A text-contract test confirms the Claude dispatch section documents
  fresh-context-in (automatic, no `fork_context`) plus compact-handoff-out
  (enforced), and requires compact final responses.
- A text-contract test confirms a specific same-family model variant in
  `orchestration.json` is dispatched explicitly rather than left to
  `model: inherit`.

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
- Wiring or fixing per-role permission enforcement (the `PreToolUse` hook and
  role-identification gap). This proposal is permission-neutral; enforcement is
  tracked separately.

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
- Claude native context behavior is documented as fresh-context-in (automatic,
  no `fork_context`) plus compact-handoff-out (enforced), routing from
  `handoff.json` on disk.
- Slot runtime is resolved independently per slot; A/B family mixes (including
  the default claude+codex) are documented as normal, and the orchestrator model
  does not constrain slot runtimes.
- A specific same-family model variant named in `orchestration.json` is passed
  explicitly to native dispatch rather than silently replaced by
  `model: inherit`.
- The permission posture is stated honestly: instruction-level today, native
  dispatch enforcement-neutral.
- Implementing the policy updates user-facing Quest documentation, not just
  workflow internals.

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
