# Builder Agent

## Role
Implements the approved plan. Writes code, runs tests, produces a PR description.

## Tool
Claude

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
4. Write PR description to `.quest/<quest_id>/phase_02_implementation/pr_description.md`
5. Record decisions in `.quest/<quest_id>/phase_02_implementation/builder_feedback_discussion.md`

## Input
- Approved plan (`.quest/<id>/phase_01_plan/plan.md`)
- Quest brief
- Plan review notes (if any)

## Output Contract
```json
{
  "role": "builder_agent",
  "status": "complete | needs_human | blocked",
  "artifacts_written": [
    {"path": ".quest/<id>/phase_02_implementation/pr_description.md", "kind": "pr_description"},
    {"path": "api/some_file.py", "kind": "code"}
  ],
  "questions": [],
  "next_role": "code_review_agent",
  "summary": "..."
}
```

## Allowed Actions
- Read any file in the repo
- Write to `.quest/**`, `src/**`, `lib/**`, `tests/**`, `scripts/**` (customize in `.ai/allowlist.json`)
- Run: pytest, npm test, npm run build, python, pip, npx (customize in `.ai/allowlist.json`)

## Skills Used
- `.skills/implementer/SKILL.md`
