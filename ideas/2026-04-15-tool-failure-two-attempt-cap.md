---
title: Tool Failure Two-Attempt Cap
purpose: Limit unproductive tool-internals investigation and prioritize fast limitation reporting.
audience:
  - quest-developers
  - quest-users
scope: Investigation-depth policy for failing tool/API calls.
status: proposed
owner: kjell
---

## Problem
The evaluation identifies rabbit-holing as a major friction source, with repeated sessions spent exploring tool schemas or internals instead of executing requested work. This pattern was the second-largest frustration family after wrong-branch/path errors.

## Proposal
Adopt the rule text from the evaluation:

> "When a tool or API call fails, do NOT spend more than 2 attempts investigating the tool's internals or source code. Instead, report the limitation clearly and ask the user how they'd like to proceed."

Quest-specific adaptation: align this with existing workflow fallback behavior so "attempt cap" covers ad-hoc investigation loops not already bounded by Quest runtime ladders.

## Dual-Mode Sanity Check
### Inside-repo use (Quest developed here)
Inside Quest, this curbs deep dives into tooling internals during user tasks and keeps progress focused on deliverables.

### Outside-in use (Quest invoked from another repo)
Outside-in tasks often hit unfamiliar tools; this rule is more valuable there because unknown integrations can trigger long, low-value investigations.

### Conflicts and Required Adaptations
`.skills/quest/delegation/workflow.md` already has bounded retry/fallback ladders for handoff failures. This proposal is complementary and targets exploratory rabbit-holing outside those explicit fallback paths.

## Actionable Steps
1. Add the two-attempt cap language to canonical execution-discipline policy text.
2. Add role prompt reminder: after second failed investigative attempt, produce a concise limitation report and next options.
3. In long sessions, track attempt count in running notes to avoid silent cap violations.
4. During review, treat "third+ internals attempt without escalation" as a process defect.

## Cross-References
- `ideas/2026-04-15-claude-rule-never-dismiss-acceptance-criteria.md`
- `ideas/quest-policy-canonicalization-and-enforcement-roadmap.md`
- `ideas/2026-04-13-instruction-architecture.md`

## Risks / Non-Goals
- Non-goal: forbidding all debugging after two failures.
- Risk: strict cap may stop too early on near-fixable issues; mitigation is clear escalation options, not unlimited investigation.
- Risk: without instrumentation, cap violations may still happen silently.

## Success Signal
Failed-tool sessions either recover within two attempts or escalate clearly; long investigations into internals without user-visible progress become rare.
