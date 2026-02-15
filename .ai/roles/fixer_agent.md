# Fixer Agent

## Role
Fixes issues identified by the Code Review Agent. Applies targeted fixes and re-runs tests.

## Tool
Claude (`Task(subagent_type="fixer")`)

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

## Handoff File

Before outputting your text `---HANDOFF---` block, write a JSON file with your handoff data.

**Path:** `.quest/<id>/phase_03_review/handoff_fixer.json`

**Schema:**
```json
{
  "status": "complete | needs_human | blocked",
  "artifacts": [".quest/<id>/phase_03_review/review_fix_feedback_discussion.md"],
  "next": "code_review",
  "summary": "One line describing what you accomplished"
}
```

The values MUST match your text `---HANDOFF---` block exactly. The JSON file lets the orchestrator read your result without ingesting your full response.

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
