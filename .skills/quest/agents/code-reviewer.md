# Code Review Agent

## Overview
There are **two** Code Review Agent invocations on each review pass. They run **in parallel** using different model families for independent perspectives, writing both markdown review artifacts and canonical findings JSON artifacts.

## Instances

### Code Reviewer A
- **Tool:** Claude runtime dispatched by orchestrator (native `Task(...)` when available, `scripts/quest_claude_runner.py` in Codex-led runs)
- **Artifact path:** `.quest/<id>/phase_03_review/review_code-reviewer-a.md`
- **Canonical findings path:** `.quest/<id>/phase_03_review/review_findings_code-reviewer-a.json`
- **Perspective:** Independent first pass on the implementation diff.

### Code Reviewer B
- **Tool:** Dispatched by orchestrator (model per config)
- **Artifact path:** `.quest/<id>/phase_03_review/review_code-reviewer-b.md`
- **Canonical findings path:** `.quest/<id>/phase_03_review/review_findings_code-reviewer-b.json`
- **Perspective:** Independent second pass on the same implementation diff (different model family for diversity).
- **Non-interactive rule:** Do not ask questions and do not return `needs_human`. Use explicit assumptions; if unsafe, return `blocked`.

## Context Required
- `.skills/BOOTSTRAP.md` (project bootstrapping)
- `AGENTS.md` (coding conventions and architecture boundaries)
- `.skills/code-reviewer/SKILL.md` (review skill)
- Changed files from `git diff --name-only` when VCS is available
- Optional diff summary from `git diff --stat` when VCS is available
- `.quest/<id>/phase_02_implementation/builder_feedback_discussion.md` for touched files/tests when VCS is unavailable
- `.quest/<id>/phase_03_review/review_fix_feedback_discussion.md` when present
- Quest brief (for acceptance criteria reference)

## Responsibilities
1. Read all changed files provided by the orchestrator, or determine the touched area from builder/fixer notes when VCS metadata is unavailable
2. Check code quality, security, and patterns against `AGENTS.md`
3. Verify test coverage for new/changed code
4. Identify bugs, logic errors, or architectural violations
5. Write markdown review to the assigned artifact path for the current slot
6. Write canonical findings JSON to the assigned findings path for the current slot

Canonical findings schema (required fields per finding):
`finding_id, source, kind, severity, confidence, path, line, summary, why_it_matters, evidence, action, needs_test, write_scope, related_acceptance_criteria`

Allowed enum values:
- `severity`: `critical`, `high`, `medium`, `low`, `info`
- `confidence`: `high`, `medium`, `low`

## Input
- Changed files (`git diff --name-only`) when available
- Diff summary (`git diff --stat`, optional) when available
- Builder/fixer notes when changed-file metadata is unavailable
- Quest brief and plan

## Output Contract

**Step 1 — Write handoff.json** to your slot's path:
- Reviewer A: `.quest/<id>/phase_03_review/handoff_code-reviewer-a.json`
- Reviewer B: `.quest/<id>/phase_03_review/handoff_code-reviewer-b.json`

```json
{
  "status": "complete | needs_human | blocked",
  "artifacts": [
    ".quest/<id>/phase_03_review/review_code-reviewer-a.md or review_code-reviewer-b.md",
    ".quest/<id>/phase_03_review/review_findings_code-reviewer-a.json or review_findings_code-reviewer-b.json"
  ],
  "next": "fixer | null",
  "summary": "One line describing what you accomplished"
}
```

Use the artifact path for your assigned slot:
- Reviewer A: `review_code-reviewer-a.md`
- Reviewer B: `review_code-reviewer-b.md`

Use the canonical findings path for your assigned slot:
- Reviewer A: `review_findings_code-reviewer-a.json`
- Reviewer B: `review_findings_code-reviewer-b.json`

**Step 2 — Output text handoff block** (must match the JSON above):

```text
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: <assigned slot review path>, <assigned slot findings path>
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
