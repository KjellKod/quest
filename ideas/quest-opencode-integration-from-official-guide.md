# Idea: Quest OpenCode Integration from Official Guide

## Execution Prompt (Read First)

Use this with **Claude Opus 4.6** as the orchestrator (delegating implementation roles to Codex where configured):

```txt
Implement Quest OpenCode integration using the official OpenCode orchestration model.

Execution mode:
- You are the orchestrator.
- Keep orchestration decisions in Claude.
- Configure and validate Codex-backed subagent roles (implementer/fixer/reviewer-b) through config+markdown wiring.

Constraints:
- Do not use any v2/v3 branch logic.
- Do not introduce a custom TypeScript driver.
- Do not duplicate workflow text into large inline prompt files.
- Keep changes minimal, explicit, and maintainable.

Follow source docs listed under "Source Documents to Follow".
Respect repo rules listed under "Repo Execution Constraints (Quest AGENTS.md)".

Tasks:
1) Implement all items in "Scope (In)" and none from "Scope (Out)".
2) Enforce "Non-Interactive Subagent Contract":
   - Codex path: no questions, never `needs_human`; use explicit assumptions or `blocked`.
   - Claude fallback path: may return `needs_human` only when creator input is truly required.
3) Implement "Runtime Observability Contract" as specified:
   - JSONL in `.quest/<id>/logs/subagent_runtime.log`
   - `event=start` before invoke and `event=finish` after handoff parse/fallback
   - keep existing `context_health.log` behavior unchanged for handoff compliance
4) Verify model IDs and report unresolved availability risks.
5) Satisfy all "Acceptance Criteria".

Deliverables:
- Exact files changed
- Why each change is needed
- Any runtime caveats
- A short smoke-test checklist
```

## Goal

Implement Quest OpenCode integration using OpenCode's official model:
- config + markdown orchestration
- no custom runtime driver unless needed later
- no branch archaeology or legacy duplication

## Target Orchestration Model (Cross-Runtime)

This is the **canonical model policy for implementing this idea with Quest now**.
It is implementation-specific and does **not** change Quest's long-term default model policy in this repository.

Use the same model philosophy across both planning and build/fix loops:
- strongest reasoning model as orchestrator + reviewer A
- strongest implementation model as implementer + reviewer B

| Quest role | Model |
|---|---|
| Orchestrator | Claude Opus 4.6 |
| Implementer | Codex 5.3 |
| Reviewer A | Claude Opus 4.6 |
| Reviewer B | Codex 5.3 |

Application rule:
- Planning loop: orchestrator -> planner worker -> review A + review B
- Build/fix loop: orchestrator -> implementer/fixer worker -> review A + review B

## Why This Exists

We now have a clean orchestration guide in the OpenCode clone:
- `packages/web/src/content/docs/orchestration.mdx`

This idea document turns that guidance into a practical execution brief for Quest work.

## Guiding Truths

1. Subagents are session-based child runs, not plain function calls.
2. Wiring and content are separate:
   - wiring = agent mode, task permissions, command routing
   - content = orchestration instructions and role prompts
3. Start with minimal config/markdown orchestration.
4. Add code-driver logic only if real runtime limits appear.
5. If your runtime path does not expose OpenCode question reply flow, subagents must run non-interactively.

## Non-Interactive Subagent Contract

For this integration, subagents should not block on human Q&A.

- Primary agent dispatch: `permission.task` must allow all required Quest subagents without approval prompts.
- Worker behavior: no "ask user" flow inside subagents during plan/build/review/fix loops.
- Worker fallback: when inputs are incomplete, make explicit assumptions and continue; write assumptions/risk notes into artifacts.
- Safety valve:
  - Codex path: return structured `blocked` (not `needs_human`), then retry/fallback policy applies.
  - Claude fallback path: may return structured `needs_human` when creator input is truly required.

## Runtime Observability Contract

Timeout policy should be data-driven, not guessed.

- Orchestrator writes JSONL to `.quest/<id>/logs/subagent_runtime.log`.
- Keep `.quest/<id>/logs/context_health.log` as the handoff compliance log (source/handoff integrity).
- Do not merge timing fields into `context_health.log` by default.
- Separation rationale:
  - `context_health.log` remains stable and easy to parse for routing/compliance diagnostics.
  - `subagent_runtime.log` can evolve for performance analysis without breaking existing compliance tooling.
  - Failure in one log stream should not corrupt or block the other.
- Log two events per invocation attempt:
  - `event=start` immediately before subagent invocation.
  - `event=finish` immediately after handoff parse/fallback decision.
- Required fields on every event:
  - `timestamp` (ISO-8601 UTC)
  - `event` (`start` or `finish`)
  - `invocation_id`
  - `phase`
  - `agent`
  - `runtime` (`claude` or `codex`)
  - `plan_iteration` (integer, `0` when not in plan loop)
  - `fix_iteration` (integer, `0` when not in fix loop)
  - `attempt` (integer, per role+phase retry counter)
- Required fields on `event=finish`:
  - `started_at` (ISO-8601 UTC)
  - `finished_at` (ISO-8601 UTC)
  - `duration_ms`
  - `outcome` (`complete`, `blocked`, `needs_human`, `error`)
  - `fallback_used` (boolean)
  - `fallback_target` (`claude`, `codex`, or `null`)
- Policy note: `outcome=needs_human` is allowed only for Claude-path invocations.
- Retries and fallbacks are separate invocation attempts (`invocation_id` per attempt).
- Logging is observability-only. Routing must not depend on telemetry file availability.
- Use these logs to compute per-role/runtime p50/p95/p99 before introducing hard timeouts.
- Optional reporting view: generate a merged report at completion, but keep underlying logs separate.

Minimal permission shape to target:

```json
{
  "agent": {
    "quest": {
      "mode": "primary",
      "permission": {
        "task": "allow"
      }
    },
    "planner": {
      "mode": "subagent",
      "permission": {
        "question": "deny"
      }
    },
    "implementer": {
      "mode": "subagent",
      "permission": {
        "question": "deny"
      }
    },
    "reviewer-a": {
      "mode": "subagent",
      "permission": {
        "question": "deny"
      }
    },
    "reviewer-b": {
      "mode": "subagent",
      "permission": {
        "question": "deny"
      }
    }
  }
}
```

If your OpenCode build does not expose `question` in documented permission keys, keep the same non-interactive behavior as a prompt contract and treat any subagent question as a workflow defect.

## Source Documents to Follow

- `/Users/kjell/ws/extra/quest/.ws/opencode/packages/web/src/content/docs/orchestration.mdx`
- `/Users/kjell/ws/extra/quest/.ws/opencode/packages/web/src/content/docs/agents.mdx`
- `/Users/kjell/ws/extra/quest/.ws/opencode/packages/web/src/content/docs/commands.mdx`
- `/Users/kjell/ws/extra/quest/.ws/opencode/packages/web/src/content/docs/permissions.mdx`

## Repo Execution Constraints (Quest AGENTS.md)

- Follow Quest gate sequence exactly:
  - routing -> plan -> dual plan review -> arbiter -> walkthrough -> explicit approval -> build -> dual code review -> fixes
- Do not edit project/source files before Build gate approval.
- Run this work on a feature branch with a draft PR.
- Before merge, add an explicit review comment to the PR.
- Keep changes readability-first and simple (KISS/YAGNI/SRP/DRY).
- Ensure `.ai/allowlist.json` covers:
  - source directories writable by builder/fixer
  - test commands needed by builder/fixer
  - approval gates expected by orchestration

## Model Guidance

Primary implementation runtime pattern:
- Claude Opus 4.6 as orchestrator
- Codex 5.3 as implementation/review subagent runtime where configured

Final architecture review:
- Claude Opus 4.6

OpenCode runtime validation candidates:
- Big Pickle (orchestrator)
- KiMi K2.5 or Minimax M2.5 (independent reviewer)

Precedence for this document:
1. `Target Orchestration Model (Cross-Runtime)` is the canonical policy for this implementation quest.
2. `Model Guidance` is supporting guidance for execution and validation.
3. `Quest Default Runtime (Post-Integration)` is future-looking runtime guidance, not the implementation target for this quest.

## Scope (In)

- Add/verify `quest` primary agent wiring
- Ensure subagents are declared as `mode: subagent`
- Ensure `quest` primary uses full subagent dispatch permission (`permission.task: allow` or equivalent wildcard allow)
- Ensure `/quest` command routes to `agent: "quest"`
- Keep markdown agent files authoritative
- Enforce non-interactive subagent behavior (no subagent question prompts during orchestration loops)
- Add orchestrator runtime telemetry (`start`/`finish` events, `started_at`, `finished_at`, `duration_ms`) for every subagent invocation attempt
- Ensure orchestration prompt includes:
  - linear flow
  - fan-out/fan-in hint for dual review
  - iteration loop guardrails (`max_iterations`)

## Scope (Out)

- No TypeScript orchestration driver
- No 701-line inline SKILL duplication
- No `.ai/roles/` reconstruction

## Acceptance Criteria

1. `/quest` command executes through `quest` primary agent.
2. `quest` can dispatch required subagents without permission prompts (`permission.task` fully allowed for orchestration).
3. Codex subagents do not ask interactive questions and do not return `needs_human`; they proceed with explicit assumptions or return `blocked`. Only Claude fallback may return `needs_human`.
4. Orchestration flow supports dual-review pattern (fan-out/fan-in) at prompt level.
5. Orchestration flow supports refinement/fix loop with max-iteration guard.
6. Orchestrator emits JSONL runtime telemetry for every invocation attempt with `event=start` and `event=finish`, including `started_at`, `finished_at`, and `duration_ms`.
7. Config and markdown definitions are minimal and maintainable.
8. Model IDs are validated with `/models` or `opencode models`.
9. Execution follows repo gate discipline (no build-before-approval violations).
10. Allowlist coverage is sufficient to avoid subagent permission deadlocks.

## Review Prompt (Copy/Paste)

Use this with **Claude Opus 4.6**:

```txt
Review this Quest OpenCode integration change set for architectural correctness.

Review focus:
1) Does wiring follow official OpenCode orchestration semantics?
2) Are task permissions correct for reliable orchestration dispatch (no task approval bottlenecks)?
3) Is command routing to the orchestrator explicit and correct?
4) Are subagents non-interactive by contract (no subagent question deadlocks)?
5) Are fan-out/fan-in and iteration loops represented cleanly without framework lock-in?
6) Did we avoid unnecessary complexity (custom driver, duplication, legacy artifacts)?

Return:
- Critical issues first
- Then medium/low risks
- Final verdict: APPROVE or ITERATE
```

## Notes

If orchestration later needs strict parallel execution control, external retries, or external state transitions, create a follow-up idea for a small code-based driver.
If timeout/kill policy is added later, derive defaults from observed p95/p99 runtime telemetry instead of static guesses.

## Quest Default Runtime (Post-Integration)

- Orchestrator: Trinity Large Preview (free, agentic trained, 200K context)
- Planner: Trinity Large Preview (strong reasoning for planning)
- Reviewer A: Big Pickle (primary reviewer, needs depth)
- Reviewer B: KiMi K2.5 (different model family, genuine diversity)
- Arbiter: Big Pickle or Trinity (decision-making, weighing reviews)
- Builder: Big Pickle (full tool access, code competence)
- Fixer: Big Pickle (same as builder)
