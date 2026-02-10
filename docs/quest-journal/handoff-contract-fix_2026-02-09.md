# Quest Journal: handoff-contract-fix

**Quest ID:** handoff-contract-fix_2026-02-09__2228
**Completed:** 2026-02-09
**Type:** Architecture consistency fix

## Summary

Fixed handoff contract inconsistencies across Quest role files and workflow. Standardized all 6 role files on `---HANDOFF---` text format with STATUS/ARTIFACTS/NEXT/SUMMARY fields, removed "Context Is In Your Prompt" contradictions, and made workflow prompts explicitly request handoff format.

This quest addressed inconsistencies discovered during the thin-orchestrator quest where agents sometimes produced handoff formats and sometimes didn't, causing orchestration failures.

## Key Changes

**Role files updated (all 6):**
- Replaced JSON output contracts with `---HANDOFF---` text format
- Removed "Context Is In Your Prompt" sections that contradicted thin orchestrator principle
- Made ARTIFACTS field slot-specific for dual-reviewer roles
- Aligned NEXT tokens with workflow routing expectations

**Workflow updated:**
- Made all Claude Task tool prompts explicitly request handoff format
- Removed Task tool invocations and standardized on Codex-only subagent topology
- Fixed minimal prompt example to include all required handoff fields
- Updated error handling and fallback guidance for Codex-only execution

## Files Changed

```
.ai/roles/planner_agent.md
.ai/roles/plan_review_agent.md
.ai/roles/arbiter_agent.md
.ai/roles/builder_agent.md
.ai/roles/code_review_agent.md
.ai/roles/fixer_agent.md
.skills/quest/delegation/workflow.md
```

## Impact

- Consistent handoff contract across all agents (no more JSON vs text confusion)
- Orchestrator can reliably parse STATUS, ARTIFACTS, NEXT, and SUMMARY from all agents
- Thin orchestrator principle fully implemented (no "Context Is In Your Prompt" claims)
- Codex-only subagent topology established (gpt-5.3-codex for all non-orchestrator agents)
- Prepares for Phase 4 (role file elimination)

## This is where it all began...

From the investigation that triggered this quest:

> The handoff format is inconsistent. Looking at the actual review files from thin-orchestrator quest:
> - Plan review: Claude ✅ has HANDOFF, Codex ❌ missing HANDOFF
> - Code review: Claude ❌ missing HANDOFF, Codex ✅ has HANDOFF
>
> Root cause: Role files specify JSON contracts, workflow expects text format, skills don't mention handoffs, and Claude prompts don't explicitly request the format.

From `ideas/handoff-fix-plan.md`:

> ## Goal
> Make the existing role files + orchestrator workflow agree on a single handoff contract:
> - Subagents end responses with `---HANDOFF---` + `STATUS/ARTIFACTS/NEXT/SUMMARY`
> - No role file claims a JSON-only contract
> - No "Context Is In Your Prompt" text that contradicts the thin orchestrator
> - Claude Task tool prompts explicitly ask for the handoff

## Iterations

- Plan iterations: 3
  - Iteration 1: Initial plan with basic handoff fixes
  - Iteration 2: Added Codex-only constraint enforcement
  - Iteration 3: Made reviewer topology deterministic with stable artifact names
- Fix iterations: 1
  - Fixed slot-specific ARTIFACTS in reviewer roles
  - Added missing ARTIFACTS to minimal prompt example
- Review verdict: Approved (both reviewers clean)

## Constraints Applied

Per quest brief: "Use only gpt-5.3-codex agents in all locations except the orchestrator"
- All subagents invoked via mcp__codex__codex with model: gpt-5.3-codex
- Planner: Codex ✓
- Plan reviewers (both): Codex ✓
- Arbiter: Codex ✓
- Builder: Codex ✓
- Code reviewers (both): Codex ✓
- Fixer: Codex ✓

## Next Steps

This quest is transitional and Phase-4-compatible. Phase 4 will:
- Eliminate 1:1 role files (planner, reviewers, builder, fixer)
- Move handoff contract wiring into orchestrator prompts
- Keep only arbiter and quest-agent roles

The handoff contract established here will be preserved when Phase 4 eliminates the role files.
