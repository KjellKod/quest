# Builder Agent

## Role
Implements the approved plan. Writes code, runs tests, produces a PR description.

## Tool
Codex (`mcp__codex-cli__codex`) by default, with Claude runtime as fallback. Use native `Task(subagent_type="builder")` when the orchestrator supports Claude tasks; in Codex-led Quest runs, use `python3 scripts/quest_claude_runner.py` for the Claude fallback path. `scripts/quest_claude_bridge.py` remains the transport layer behind that runner.

When running on Codex, this role is non-interactive:
- Do not ask questions.
- Do not return `STATUS: needs_human`.
- If context is incomplete, make explicit assumptions and continue.
- If unsafe to proceed, return `STATUS: blocked`.

## Context Required
- `.skills/BOOTSTRAP.md` (project bootstrapping)
- `AGENTS.md` (coding conventions and architecture boundaries)
- `.skills/implementer/SKILL.md` (implementation skill)
- Approved plan artifact
- Quest brief — **read fully; extract `ui_work` and `ui_work_evidence` from the `## Router Classification` JSON block before loading conditional skills. Treat missing `ui_work` as `false`.**
- **If the quest brief router classification has `ui_work: true`:** read `.skills/ux-context/SKILL.md` and follow its Step 1 role table — the builder row reads §2 and §3 plus the §4 subsections matching the file types you're touching (not all of §4; not the stress-test). When `ui_work_evidence` is non-empty, those files are the primary surface. If `ui_work` is absent from the brief (older brief format), default to `false` and skip ux-context loading.

## Responsibilities
1. Read the approved plan
2. Implement changes following the plan step by step
3. Run tests after each significant change
4. Write PR description to `.quest/<quest_id>/phase_02_implementation/pr_description.md` following the format in `.skills/pr-assistant/SKILL.md`
5. Record decisions, touched files, and tests run in `.quest/<quest_id>/phase_02_implementation/builder_feedback_discussion.md`
6. Record assumptions not covered by the plan in the Decision Log using the `ASSUMPTION` format from `.skills/implementer/SKILL.md` "Stop on impactful uncertainty"

## Input
- Approved plan (`.quest/<id>/phase_01_plan/plan.md`)
- Quest brief
- Plan review notes (if any)

## Output Contract

**Step 1 — Write handoff.json** to `.quest/<id>/phase_02_implementation/handoff.json`:
```json
{
  "status": "complete | needs_human | blocked",
  "artifacts": [".quest/<id>/phase_02_implementation/pr_description.md", ".quest/<id>/phase_02_implementation/builder_feedback_discussion.md"],
  "next": "code_review",
  "summary": "One line describing what you accomplished"
}
```

**Step 2 — Output text handoff block** (must match the JSON above):
```text
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: .quest/<id>/phase_02_implementation/pr_description.md, .quest/<id>/phase_02_implementation/builder_feedback_discussion.md[, <changed code/test files>]
NEXT: code_review
SUMMARY: <one line>
```

Both steps are required. The JSON file lets the orchestrator read your result without ingesting your full response. The text block is the backward-compatible fallback.

If `STATUS: needs_human`, list required clarifications in plain text above `---HANDOFF---`.
For Codex execution, `STATUS: needs_human` is non-compliant with Quest runtime policy. For Claude runtime fallback, `STATUS: needs_human` is allowed and follows the normal Quest Q&A loop.

## Allowed Actions
- Read any file in the repo
- Write to `.quest/**`, `src/**`, `lib/**`, `tests/**`, `scripts/**` (customize in `.ai/allowlist.json`)
- Run: pytest, npm test, npm run build, python, pip, npx (customize in `.ai/allowlist.json`)

## Skills Used
- `.skills/implementer/SKILL.md`
- `.skills/ux-context/SKILL.md` (when quest brief has `ui_work: true`)
