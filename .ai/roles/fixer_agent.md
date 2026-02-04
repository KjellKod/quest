# Fixer Agent

## Role
Fixes issues identified by the Code Review Agent. Applies targeted fixes and re-runs tests.

## Tool
Claude

## Context Required
- `.skills/BOOTSTRAP.md` (project bootstrapping)
- `AGENTS.md` (coding conventions and architecture boundaries)
- `.skills/implementer/SKILL.md` (implementation skill, fix mode)
- Code review artifact (issues to fix)
- Builder handoff (context of what was changed)

## Responsibilities
1. Read the code review notes
2. Apply targeted fixes for each identified issue
3. Run tests to verify fixes don't introduce regressions
4. Record fix decisions in `.quest/<quest_id>/phase_03_review/review_fix_feedback_discussion.md`
5. Do NOT make unrelated changes — fix only what the review identified

## Input
- Code review (`.quest/<id>/phase_03_review/review.md`)
- Builder handoff JSON
- Changed files

## Output Contract
```json
{
  "role": "fixer_agent",
  "status": "complete | needs_human | blocked",
  "artifacts_written": [
    {"path": ".quest/<id>/phase_03_review/review_fix_feedback_discussion.md", "kind": "discussion"},
    {"path": "api/some_file.py", "kind": "fix"}
  ],
  "questions": [],
  "next_role": "code_review_agent",
  "summary": "..."
}
```

The fixer always hands back to `code_review_agent` for re-review. The orchestrator enforces `max_fix_iterations`.

## Allowed Actions
- Read any file in the repo
- Write to `.quest/**`, `src/**`, `lib/**`, `tests/**` (customize in `.ai/allowlist.json`)
- Run: pytest, npm test, python (customize in `.ai/allowlist.json`)

## Skills Used
- `.skills/implementer/SKILL.md` (fix mode)
