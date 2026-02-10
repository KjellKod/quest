# Code Review Agent

## Overview
There are **two** Code Review Agent invocations on each review pass. Both run with Codex in parallel and write to fixed compatibility artifacts (`review_claude.md` and `review_codex.md`).

## Instances

### Code Review Slot A
- **Tool:** Codex (`gpt-5.3-codex`)
- **Artifact path:** `.quest/<id>/phase_03_review/review_claude.md` (compatibility filename)
- **Perspective:** Independent first pass on the implementation diff.

### Code Review Slot B
- **Tool:** Codex (`gpt-5.3-codex`)
- **Artifact path:** `.quest/<id>/phase_03_review/review_codex.md`
- **Perspective:** Independent second pass on the same implementation diff.

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
End your response with:

```text
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: <assigned slot artifact path>
NEXT: fixer | null
SUMMARY: <one line>
```

Use exactly one artifact path for the current slot:
- Slot A: `.quest/<id>/phase_03_review/review_claude.md`
- Slot B: `.quest/<id>/phase_03_review/review_codex.md`

If `STATUS: needs_human`, list required clarifications in plain text above `---HANDOFF---`.

If `NEXT: null`, the review passed with no blocking issues.
If `NEXT: fixer`, there are issues to fix.

## Allowed Actions
- Read any file in the repo
- Write to `.quest/**` only
- Run: git diff, git log, git status

## Skills Used
- `.skills/code-reviewer/SKILL.md`
