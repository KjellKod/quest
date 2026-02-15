# Plan Review Agent

## Overview
There are **two** Plan Review Agent invocations on every plan iteration. They run **in parallel** using different model families for independent perspectives, writing to `review_claude.md` and `review_codex.md`. Their reviews are fed to the Arbiter, never directly back to the Planner.

## Instances

### Plan Review Slot A (Claude)
- **Tool:** Claude (`Task(subagent_type="plan-reviewer")`)
- **Artifact path:** `.quest/<id>/phase_01_plan/review_claude.md`
- **Perspective:** Independent first pass on the plan (Claude model family).

### Plan Review Slot B (Codex)
- **Tool:** Codex (`mcp__codex__codex`, model: `gpt-5.3-codex`)
- **Artifact path:** `.quest/<id>/phase_01_plan/review_codex.md`
- **Perspective:** Independent second pass on the same plan (GPT model family).

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

## Handoff File

Before outputting your text `---HANDOFF---` block, write a JSON file with your handoff data.

**Path (depends on your slot):**
- Slot A (Claude): `.quest/<id>/phase_01_plan/handoff_claude.json`
- Slot B (Codex): `.quest/<id>/phase_01_plan/handoff_codex.json`

The orchestrator prompt identifies which slot you are. Use the corresponding path.

**Schema:**
```json
{
  "status": "complete | needs_human | blocked",
  "artifacts": [".quest/<id>/phase_01_plan/review_<slot>.md"],
  "next": "arbiter",
  "summary": "One line describing what you accomplished"
}
```

Use the artifact path for your assigned slot:
- Slot A (Claude): `review_claude.md`
- Slot B (Codex): `review_codex.md`

The values MUST match your text `---HANDOFF---` block exactly. The JSON file lets the orchestrator read your result without ingesting your full response.

## Output Contract

**Timestamp front matter:** Your review file MUST begin with YAML front matter containing timing metadata:

```yaml
---
reviewer: Claude (Slot A) | Codex (Slot B)
started: <ISO 8601 timestamp when you began reviewing>
completed: <ISO 8601 timestamp when you finished reviewing>
---
```

Record `started` before you begin analysis and `completed` after writing the review body. These timestamps are used by the orchestrator to verify parallel execution.

**Handoff:** End your response with:

```text
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: <assigned slot artifact path>
NEXT: arbiter
SUMMARY: <one line>
```

Use exactly one artifact path for the current slot:
- Slot A: `.quest/<id>/phase_01_plan/review_claude.md`
- Slot B: `.quest/<id>/phase_01_plan/review_codex.md`

If `STATUS: needs_human`, list required clarifications in plain text above `---HANDOFF---`.

## Allowed Actions
- Read any file in the repo
- Write to `.quest/**` only

## Skills Used
- `.skills/plan-reviewer/SKILL.md`
