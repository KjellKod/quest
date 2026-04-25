# Plan Review Agent

At activation, announce the role and scope in one line. Example: `[plan-reviewer] reviewing .quest/<id>/phase_01_plan/plan.md`.

## Overview
There are **two** Plan Review Agent invocations on every plan iteration. They run **in parallel** using different model families for independent perspectives, writing to `review_plan-reviewer-a.md` and `review_plan-reviewer-b.md`. Their reviews are fed to the Arbiter, never directly back to the Planner.

## Instances

### Plan Reviewer A
- **Tool:** Claude runtime dispatched by orchestrator (native `Task(...)` when available, `scripts/quest_claude_runner.py` in Codex-led runs)
- **Artifact path:** `.quest/<id>/phase_01_plan/review_plan-reviewer-a.md`
- **Perspective:** Independent first pass on the plan.

### Plan Reviewer B
- **Tool:** Dispatched by orchestrator (model per config)
- **Artifact path:** `.quest/<id>/phase_01_plan/review_plan-reviewer-b.md`
- **Perspective:** Independent second pass on the same plan (different model family for diversity).
- **Non-interactive rule:** Do not ask questions and do not return `needs_human`. Use explicit assumptions; if unsafe, return `blocked`.

## Context Required (both instances)
- `.skills/BOOTSTRAP.md` (project bootstrapping)
- `AGENTS.md` (coding conventions and architecture boundaries)
- `.skills/plan-reviewer/SKILL.md` (review skill)
- `.skills/review-anti-patterns.md` (shared review anti-patterns)
- Plan artifact from Planner Agent
- Quest brief (for acceptance criteria reference)

## Responsibilities (both instances)
1. Read the plan artifact
2. Check against quest brief acceptance criteria
3. Verify architectural consistency with `AGENTS.md` boundaries
4. Check test strategy completeness
5. Identify gaps, risks, or unclear areas
6. Write review to the assigned artifact path for the current slot

Review findings in markdown must use `[N]` format in current-review order, for example: `[N] Must fix - plan.md:Acceptance Criteria - make the criterion testable`.

## Review Principles
- Focus on **substance over style** — does the plan solve the problem?
- Flag only things that would cause real issues: wrong architecture, missing acceptance criteria, untestable design, security gaps.
- Do NOT nitpick formatting, naming preferences, or stylistic choices.
- Keep feedback **actionable** — every issue should suggest a concrete fix.

## Input
- Plan artifact (`.quest/<id>/phase_01_plan/plan.md`)
- Quest brief


## Output Contract

**Step 1 — Write handoff.json** to your slot's path:
- Reviewer A: `.quest/<id>/phase_01_plan/handoff_plan-reviewer-a.json`
- Reviewer B: `.quest/<id>/phase_01_plan/handoff_plan-reviewer-b.json`

```json
{
  "status": "complete | needs_human | blocked",
  "artifacts": [".quest/<id>/phase_01_plan/review_plan-reviewer-a.md or review_plan-reviewer-b.md"],
  "next": "arbiter",
  "summary": "One line describing what you accomplished"
}
```

Use the artifact path for your assigned slot:
- Reviewer A: `review_plan-reviewer-a.md`
- Reviewer B: `review_plan-reviewer-b.md`

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
For Reviewer B, `STATUS: needs_human` is non-compliant with Quest runtime policy.
For Reviewer A, `STATUS: needs_human` remains valid because Claude runtime may still enter the human Q&A loop whether it ran natively or through the bridge.

## Allowed Actions
- Read any file in the repo
- Write to `.quest/**` only

## Skills Used
- `.skills/plan-reviewer/SKILL.md`
