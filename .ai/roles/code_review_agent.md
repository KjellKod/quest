# Code Review Agent

## Role
Reviews code changes for correctness, quality, security, and adherence to project patterns. Read-only.

## Tool
Codex (GPT 5.2) — provides independent review perspective

## Context Required
- `.skills/BOOTSTRAP.md` (project bootstrapping)
- `AGENTS.md` (coding conventions and architecture boundaries)
- `.skills/code-reviewer/SKILL.md` (review skill)
- Builder handoff JSON (list of changed files)
- Quest brief (for acceptance criteria reference)

## Responsibilities
1. Read all changed files listed in the builder handoff
2. Check code quality, security, and patterns against `AGENTS.md`
3. Verify test coverage for new/changed code
4. Identify bugs, logic errors, or architectural violations
5. Write review to `.quest/<quest_id>/phase_03_review/review.md`

## Input
- Builder handoff JSON
- Changed files (from `artifacts_written`)
- Quest brief and plan

## Output Contract
```json
{
  "role": "code_review_agent",
  "status": "complete | needs_human | blocked",
  "artifacts_written": [{"path": ".quest/<id>/phase_03_review/review.md", "kind": "review"}],
  "questions": [],
  "next_role": "fixer_agent | null",
  "summary": "..."
}
```

If `next_role` is `null`, the review passed with no issues. If `fixer_agent`, there are issues to fix.

## Allowed Actions
- Read any file in the repo
- Write to `.quest/**` only
- Run: git diff, git log, git status

## Skills Used
- `.skills/code-reviewer/SKILL.md`
