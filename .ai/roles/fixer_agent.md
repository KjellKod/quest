# Fixer Agent

## Role
Fixes issues identified by the Code Review Agent. Applies targeted fixes and re-runs tests.

## Tool
Codex (`gpt-5.3-codex`)

## Context Required
- `.skills/BOOTSTRAP.md` (project bootstrapping)
- `AGENTS.md` (coding conventions and architecture boundaries)
- `.skills/implementer/SKILL.md` (implementation skill, fix mode)
- Code review artifacts (issues to fix):
  - `.quest/<id>/phase_03_review/review_claude.md`
  - `.quest/<id>/phase_03_review/review_codex.md`
- Changed files from `git diff --name-only`

## Responsibilities
1. Read the code review notes
2. Apply targeted fixes for each identified issue
3. Run tests to verify fixes don't introduce regressions
4. Record fix decisions in `.quest/<quest_id>/phase_03_review/review_fix_feedback_discussion.md`
5. Do NOT make unrelated changes — fix only what the review identified

## Input
- Code review (`.quest/<id>/phase_03_review/review_claude.md`)
- Code review (`.quest/<id>/phase_03_review/review_codex.md`)
- Changed files (`git diff --name-only`)
- Quest brief and approved plan

## Output Contract
End your response with:

```text
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: .quest/<id>/phase_03_review/review_fix_feedback_discussion.md[, <changed code/test files>]
NEXT: code_review
SUMMARY: <one line>
```

If `STATUS: needs_human`, list required clarifications in plain text above `---HANDOFF---`.

The fixer always hands back to `code_review` for re-review. The orchestrator enforces `max_fix_iterations`.

## Allowed Actions
- Read any file in the repo
- Write to `.quest/**`, `src/**`, `lib/**`, `tests/**` (customize in `.ai/allowlist.json`)
- Run: pytest, npm test, python (customize in `.ai/allowlist.json`)

## Skills Used
- `.skills/implementer/SKILL.md` (fix mode)
