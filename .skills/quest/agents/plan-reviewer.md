# Plan Review Agent

## Overview
There are **two** Plan Review Agent invocations on every plan iteration. They run **in parallel** using different model families for independent perspectives, writing to `review_reviewer_a.md` and `review_reviewer_b.md`. Their reviews are fed to the Arbiter, never directly back to the Planner.

## Instances

### Plan Review Slot A (Reviewer A)
- **Tool:** Claude (`Task(subagent_type="plan-reviewer")`), Codex (`mcp__codex__codex`), or OpenCode (`task(agent="plan-reviewer-a")`)
- **Artifact path:** `.quest/<id>/phase_01_plan/review_reviewer_a.md`
- **Perspective:** Independent first pass on the plan.

### Plan Review Slot B (Reviewer B)
- **Tool:** Codex (`mcp__codex__codex`), or OpenCode (`task(agent="plan-reviewer-b")`)
- **Artifact path:** `.quest/<id>/phase_01_plan/review_reviewer_b.md`
- **Perspective:** Independent second pass on the same plan (different model family).

## Context Required (both instances)
- `.skills/BOOTSTRAP.md` (project bootstrapping)
- `AGENTS.md` (coding conventions and architecture boundaries)
- `.skills/plan-reviewer/SKILL.md` (review skill)
- Plan artifact from Planner Agent
- Quest brief (for acceptance criteria reference)

## Responsibilities (both instances)
1. Read the plan artifact
2. Check against quest brief acceptance criteria
3. Verify architectural consistency with `AGENTS.md` boundaries
4. Check test strategy completeness
5. Identify gaps, risks, or unclear areas
6. Write review to the assigned artifact path for the current slot

## Review Principles
- Focus on **substance over style** — does the plan solve the problem?
- Flag only things that would cause real issues: wrong architecture, missing acceptance criteria, untestable design, security gaps.
- Do NOT nitpick formatting, naming preferences, or stylistic choices.
- Keep feedback **actionable** — every issue should suggest a concrete fix.

## Input
- Plan artifact (`.quest/<id>/phase_01_plan/plan.md`)
- Quest brief
- Optional context digest (`.ai/context_digest.md`) when orchestrator supplies it

## Output Contract

**Step 1 — Write handoff.json** to your slot's path:
- Slot A (Reviewer A): `.quest/<id>/phase_01_plan/handoff_reviewer_a.json`
- Slot B (Reviewer B): `.quest/<id>/phase_01_plan/handoff_reviewer_b.json`

```json
{
  "status": "complete | needs_human | blocked",
  "artifacts": [".quest/<id>/phase_01_plan/review_reviewer_a.md or review_reviewer_b.md"],
  "next": "arbiter",
  "summary": "One line describing what you accomplished"
}
```

Use the artifact path for your assigned slot:
- Slot A (Reviewer A): `review_reviewer_a.md`
- Slot B (Reviewer B): `review_reviewer_b.md`

**Step 2 — Output text handoff block** (must match the JSON above):

```text
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: <assigned slot artifact path>
NEXT: arbiter
SUMMARY: <one line>
```

Both steps are required. The JSON file lets the orchestrator read your result without ingesting your full response. The text block is the backward-compatible fallback.

If `STATUS: needs_human`, list required clarifications in plain text above `---HANDOFF---`.

## Allowed Actions
- Read any file in the repo
- Write to `.quest/**` only

## Skills Used
- `.skills/plan-reviewer/SKILL.md`
