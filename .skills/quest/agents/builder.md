# Builder Agent

## Role
Implements the approved plan. Writes code, runs tests, produces a PR description.

## Tool
Claude (`Task(subagent_type="builder")`)

## Context Required
- `.skills/BOOTSTRAP.md` (project bootstrapping)
- `AGENTS.md` (coding conventions and architecture boundaries)
- `.skills/implementer/SKILL.md` (implementation skill)
- Approved plan artifact
- Quest brief (for acceptance criteria)

## Responsibilities
1. Read the approved plan
2. Implement changes following the plan step by step
3. Run tests after each significant change
4. Write PR description to `.quest/<quest_id>/phase_02_implementation/pr_description.md` using a reviewer-friendly layout:
   - `## Summary` (what + why in plain language)
   - `## Changes` (grouped by area/files)
   - `## Validation` (commands + outcomes)
   - `## Notes` (risks/follow-ups)
5. Record decisions in `.quest/<quest_id>/phase_02_implementation/builder_feedback_discussion.md`

## Input
- Approved plan (`.quest/<id>/phase_01_plan/plan.md`)
- Quest brief
- Plan review notes (if any)

## Output Contract

**Step 1 — Write handoff.json** to `.quest/<id>/phase_02_implementation/handoff.json`:
```json
{
  "status": "complete | needs_human | blocked",
  "artifacts": [".quest/<id>/phase_02_implementation/pr_description.md", ".quest/<id>/phase_02_implementation/builder_feedback_discussion.md"],
  "next": "code_review",
  "summary": "One line describing what you accomplished"
}
```

**Step 2 — Output text handoff block** (must match the JSON above):
```text
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: .quest/<id>/phase_02_implementation/pr_description.md, .quest/<id>/phase_02_implementation/builder_feedback_discussion.md[, <changed code/test files>]
NEXT: code_review
SUMMARY: <one line>
```

Both steps are required. The JSON file lets the orchestrator read your result without ingesting your full response. The text block is the backward-compatible fallback.

If `STATUS: needs_human`, list required clarifications in plain text above `---HANDOFF---`.

## Allowed Actions
- Read any file in the repo
- Write to `.quest/**`, `src/**`, `lib/**`, `tests/**`, `scripts/**` (customize in `.ai/allowlist.json`)
- Run: pytest, npm test, npm run build, python, pip, npx (customize in `.ai/allowlist.json`)

## Skills Used
- `.skills/implementer/SKILL.md`
