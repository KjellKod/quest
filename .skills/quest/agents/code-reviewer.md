# Code Review Agent

## Overview
There are **two** Code Review Agent invocations on each review pass. They run **in parallel** using different model families for independent perspectives, writing to `review_code-reviewer-a.md` and `review_code-reviewer-b.md`.

## Instances

### Code Reviewer A
- **Tool:** Claude runtime dispatched by orchestrator (native `Task(...)` when available, `scripts/quest_claude_runner.py` in Codex-led runs)
- **Artifact path:** `.quest/<id>/phase_03_review/review_code-reviewer-a.md`
- **Perspective:** Independent first pass on the implementation diff.

### Code Reviewer B
- **Tool:** Dispatched by orchestrator (model per config)
- **Artifact path:** `.quest/<id>/phase_03_review/review_code-reviewer-b.md`
- **Perspective:** Independent second pass on the same implementation diff (different model family for diversity).
- **Non-interactive rule:** Do not ask questions and do not return `needs_human`. Use explicit assumptions; if unsafe, return `blocked`.

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
- Reviewer A: `.quest/<id>/phase_03_review/handoff_code-reviewer-a.json`
- Reviewer B: `.quest/<id>/phase_03_review/handoff_code-reviewer-b.json`

```json
{
  "status": "complete | needs_human | blocked",
  "artifacts": [".quest/<id>/phase_03_review/review_code-reviewer-a.md or review_code-reviewer-b.md"],
  "next": "fixer | null",
  "summary": "One line describing what you accomplished"
}
```

Use the artifact path for your assigned slot:
- Reviewer A: `review_code-reviewer-a.md`
- Reviewer B: `review_code-reviewer-b.md`

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
For Reviewer B, `STATUS: needs_human` is non-compliant with Quest runtime policy.
For Reviewer A, `STATUS: needs_human` remains valid because Claude runtime may still enter the human Q&A loop whether it ran natively or through the bridge.

If `NEXT: null`, the review passed with no blocking issues.
If `NEXT: fixer`, there are issues to fix.

## Allowed Actions
- Read any file in the repo
- Write to `.quest/**` only
- Run: git diff, git log, git status

## Skills Used
- `.skills/code-reviewer/SKILL.md`
