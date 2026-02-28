# Code Review Agent

## Overview
There are **two** Code Review Agent invocations on each review pass. They run **in parallel** using different model families for independent perspectives, writing to `review_reviewer_a.md` and `review_reviewer_b.md`.

## Instances

### Code Review Slot A (Reviewer A)
- **Tool:** Claude (`Task(subagent_type="code-reviewer")`), Codex (`mcp__codex__codex`), or OpenCode (`task(agent="code-reviewer")`)
- **Artifact path:** `.quest/<id>/phase_03_review/review_reviewer_a.md`
- **Perspective:** Independent first pass on the implementation diff.

### Code Review Slot B (Reviewer B)
- **Tool:** Codex (`mcp__codex__codex`), or OpenCode (`task(agent="code-reviewer")` with different model)
- **Artifact path:** `.quest/<id>/phase_03_review/review_reviewer_b.md`
- **Perspective:** Independent second pass on the same implementation diff (different model family).

## Context Required
- `.skills/BOOTSTRAP.md` (project bootstrapping)
- `AGENTS.md` (coding conventions and architecture boundaries)
- `.skills/code-reviewer/SKILL.md` (review skill)
- Changed files from `git diff --name-only`
- Optional diff summary from `git diff --stat`
- Quest brief (for acceptance criteria reference)

## Responsibilities
1. Read all changed files provided by the orchestrator (from git diff)
2. Check code quality, security, and patterns against `AGENTS.md`
3. Verify test coverage for new/changed code
4. Identify bugs, logic errors, or architectural violations
5. Write review to the assigned artifact path for the current slot

## Input
- Changed files (`git diff --name-only`)
- Diff summary (`git diff --stat`, optional)
- Quest brief and plan

## Output Contract

**Step 1 — Write handoff.json** to your slot's path:
- Slot A (Reviewer A): `.quest/<id>/phase_03_review/handoff_reviewer_a.json`
- Slot B (Reviewer B): `.quest/<id>/phase_03_review/handoff_reviewer_b.json`

```json
{
  "status": "complete | needs_human | blocked",
  "artifacts": [".quest/<id>/phase_03_review/review_reviewer_a.md or review_reviewer_b.md"],
  "next": "fixer | null",
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
NEXT: fixer | null
SUMMARY: <one line>
```

Both steps are required. The JSON file lets the orchestrator read your result without ingesting your full response. The text block is the backward-compatible fallback.

If `STATUS: needs_human`, list required clarifications in plain text above `---HANDOFF---`.

If `NEXT: null`, the review passed with no blocking issues.
If `NEXT: fixer`, there are issues to fix.

## Allowed Actions
- Read any file in the repo
- Write to `.quest/**` only
- Run: git diff, git log, git status

## Skills Used
- `.skills/code-reviewer/SKILL.md`
