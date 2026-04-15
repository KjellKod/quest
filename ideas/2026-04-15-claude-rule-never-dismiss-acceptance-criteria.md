---
title: CLAUDE Rule - Never Dismiss Acceptance Criteria
purpose: Codify strict acceptance-criteria adherence to prevent avoidable rework and reviewer pushback.
audience:
  - quest-developers
  - quest-users
scope: Completion-policy guardrail for acceptance criteria.
status: proposed
owner: kjell
---

## Problem
The evaluation cites a concrete failure where Claude dismissed a missing `--help` timeout requirement as "not worth fixing" even though it was explicit acceptance criteria. The same section also flags PR text that treated pytest commands as "manual validation," which caused reviewer pushback and rework.

## Proposal
Adopt the evaluation rule text as a hard policy:

> "Never dismiss acceptance criteria as 'not worth fixing.' If the user specifies acceptance criteria, every item must be satisfied before considering the task complete."

Quest-specific adaptation: echo this rule in role prompts (`builder.md`, `plan-reviewer.md`) so completion criteria are checked during execution and review, not only in global policy text.

## Dual-Mode Sanity Check
### Inside-repo use (Quest developed here)
This aligns with existing Quest quality discipline. Plan and review phases already structure criteria; this rule clarifies that criteria are completion gates, not suggestions.

### Outside-in use (Quest invoked from another repo)
Outside-in workflows often encode acceptance criteria in issue text or PR comments. The same rule applies verbatim and prevents "partial done" outcomes.

### Conflicts and Required Adaptations
No direct conflict with existing hooks or skills. This is policy-only, but it should be tracked in `quest-policy-canonicalization-and-enforcement-roadmap.md` as a candidate for enforceable checks in prompts and review gates.

## Actionable Steps
1. Add the exact rule text to the canonical execution-discipline policy surface.
2. Add matching reminder language to `.skills/quest/agents/builder.md`.
3. Add matching reviewer checklist language to `.skills/quest/agents/plan-reviewer.md` and code-review roles.
4. In PR-generation workflows, require that validation steps map directly to each listed acceptance criterion.

## Cross-References
- `ideas/quest-policy-canonicalization-and-enforcement-roadmap.md`
- `ideas/2026-04-15-pr-create-checklist-via-pr-assistant.md`
- `ideas/2026-04-13-instruction-architecture.md`

## Risks / Non-Goals
- Non-goal: expanding scope beyond user-requested criteria.
- Risk: rigid interpretation can block progress if criteria are ambiguous; prompts should require explicit assumptions instead of silent dismissal.
- Risk: without enforcement hooks/checklists, the rule can still be skipped under pressure.

## Success Signal
No Quest completion is marked done while any explicit acceptance criterion remains unmet, and PR review feedback no longer flags criteria as ignored or reclassified as optional.
