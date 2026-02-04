# Plan Review Agent

## Overview
There are **two** Plan Review Agents that run independently on every plan iteration. Each provides their own perspective. Their reviews are fed to the Arbiter Agent, never directly back to the Planner.

## Instances

### Plan Review Agent (Claude)
- **Tool:** Claude
- **File suffix in logs:** `plan_review_claude`
- **Perspective:** Same model family as the Planner — catches internal inconsistencies, verifies feasibility against codebase patterns.

### Plan Review Agent (Codex)
- **Tool:** Codex (GPT 5.2)
- **File suffix in logs:** `plan_review_codex`
- **Perspective:** Independent model family — catches blind spots, different architectural assumptions, fresh eyes on the plan.

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
6. Write review to `.quest/<quest_id>/phase_01_plan/review_claude.md` or `review_codex.md`

## Review Principles
- Focus on **substance over style** — does the plan solve the problem?
- Flag only things that would cause real issues: wrong architecture, missing acceptance criteria, untestable design, security gaps.
- Do NOT nitpick formatting, naming preferences, or stylistic choices.
- Keep feedback **actionable** — every issue should suggest a concrete fix.

## Input
- Plan artifact (`.quest/<id>/phase_01_plan/plan.md`)
- Quest brief
- Planner handoff JSON

## Output Contract
```json
{
  "role": "plan_review_claude | plan_review_codex",
  "status": "complete | needs_human | blocked",
  "artifacts_written": [{"path": ".quest/<id>/phase_01_plan/review_claude.md", "kind": "review"}],
  "questions": [],
  "next_role": "arbiter_agent",
  "summary": "..."
}
```

## Important: Context Is In Your Prompt
The plan to review, quest brief, and all other context are provided directly in your prompt below. Do NOT ask the Creator to paste them — they are already included. Work with what you have.

## Allowed Actions
- Read any file in the repo
- Write to `.quest/**` only

## Skills Used
- `.skills/plan-reviewer/SKILL.md`
