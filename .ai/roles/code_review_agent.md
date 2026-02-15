# Code Review Agent

## Overview
There are **two** Code Review Agent invocations on each review pass. They run **in parallel** using different model families for independent perspectives, writing to `review_claude.md` and `review_codex.md`.

## Instances

### Code Review Slot A (Claude)
- **Tool:** Claude (`Task(subagent_type="code-reviewer")`)
- **Artifact path:** `.quest/<id>/phase_03_review/review_claude.md`
- **Perspective:** Independent first pass on the implementation diff (Claude model family).

### Code Review Slot B (Codex)
- **Tool:** Codex (`mcp__codex__codex`, model: `gpt-5.3-codex`)
- **Artifact path:** `.quest/<id>/phase_03_review/review_codex.md`
- **Perspective:** Independent second pass on the same implementation diff (GPT model family).

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

**Timestamp front matter:** Your review file MUST begin with YAML front matter containing timing metadata:

```yaml
---
reviewer: Claude (Slot A) | Codex (Slot B)
started: <ISO 8601 timestamp when you began reviewing>
completed: <ISO 8601 timestamp when you finished reviewing>
---
```

Record `started` before you begin analysis and `completed` after writing the review body. These timestamps are used by the orchestrator to verify parallel execution.

**Step 1 — Write handoff.json** to your slot's path:
- Slot A (Claude): `.quest/<id>/phase_03_review/handoff_claude.json`
- Slot B (Codex): `.quest/<id>/phase_03_review/handoff_codex.json`

```json
{
  "status": "complete | needs_human | blocked",
  "artifacts": [".quest/<id>/phase_03_review/review_claude.md or review_codex.md"],
  "next": "fixer | null",
  "summary": "One line describing what you accomplished"
}
```

Use the artifact path for your assigned slot:
- Slot A (Claude): `review_claude.md`
- Slot B (Codex): `review_codex.md`

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
