# Minimal Fix Plan: Consistent `---HANDOFF---` Contracts (Transitional, Phase-4-Compatible)

## Goal
Make the existing role files + orchestrator workflow agree on a single handoff contract:
- **Subagents end responses with `---HANDOFF---` + `STATUS/ARTIFACTS/NEXT/SUMMARY`**
- **No role file claims a JSON-only contract**
- **No “Context Is In Your Prompt” text that contradicts the thin orchestrator (paths, not pasted content)**
- **Claude Task tool prompts explicitly ask for the handoff**

## Non-goals (to stay Phase 4 compatible)
- Do **not** restructure the quest pipeline.
- Do **not** add new roles or new orchestration layers.
- Do **not** rewrite roles to duplicate skill instructions (Phase 4 removes most of these role files anyway).

## Files that need changes

### Role files (handoff contract + remove conflicting context section)
- `.ai/roles/planner_agent.md`
- `.ai/roles/plan_review_agent.md`
- `.ai/roles/arbiter_agent.md`
- `.ai/roles/builder_agent.md`
- `.ai/roles/code_review_agent.md`
- `.ai/roles/fixer_agent.md`

### Orchestrator workflow (Claude Task tool prompts must request handoff)
- `.skills/quest/delegation/workflow.md`

---

## Standard handoff format (to use everywhere)

Agents may include human-readable text *before* the handoff (including questions when `needs_human`), but must always end with:

```text
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: <comma-separated file paths written>
NEXT: <next role or null>
SUMMARY: <one line>
```

Notes:
- If `STATUS: needs_human`, put the questions in plain text **above** `---HANDOFF---` so the orchestrator can extract them from “text before handoff”.
- `ARTIFACTS` should list only files actually written/updated by the agent.

---

## Exact before/after changes

### 1) `.ai/roles/planner_agent.md`

**Before**
````markdown
## Output Contract
```json
{
  "role": "planner_agent",
  "status": "complete | needs_human | blocked",
  "artifacts_written": [{"path": ".quest/<id>/phase_01_plan/plan.md", "kind": "plan"}],
  "questions": [],
  "next_role": "plan_review_claude",
  "summary": "..."
}
```
````

**After**
````markdown
## Output Contract
End your response with:
```text
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: .quest/<id>/phase_01_plan/plan.md
NEXT: plan_review
SUMMARY: <one line>
```
````

Rationale: matches the orchestrator’s Context Retention Rule (paths + one-line summary), removes JSON-only claim.

---

### 2) `.ai/roles/plan_review_agent.md`

**Before**
````markdown
## Input
- Plan artifact (`.quest/<id>/phase_01_plan/plan.md`)
- Quest brief
- Planner handoff JSON

## Output Contract
```json
{
  "role": "plan_review_claude | plan_review_codex",
  "status": "complete | needs_human | blocked",
  "artifacts_written": [{"path": ".quest/<id>/phase_01_plan/review_claude.md", "kind": "review"}],
  "questions": [],
  "next_role": "arbiter_agent",
  "summary": "..."
}
```

## Important: Context Is In Your Prompt
The plan to review, quest brief, and all other context are provided directly in your prompt below. Do NOT ask the Creator to paste them — they are already included. Work with what you have.
````

**After**
````markdown
## Input
- Plan artifact (`.quest/<id>/phase_01_plan/plan.md`)
- Quest brief

## Output Contract
End your response with:
```text
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: .quest/<id>/phase_01_plan/review_<claude|codex>.md
NEXT: arbiter
SUMMARY: <one line>
```
````

And **remove** the entire “## Important: Context Is In Your Prompt” section.

Rationale: thin orchestrator passes **paths**, not pasted content; this removes a misleading instruction and aligns the output with `---HANDOFF---`.

---

### 3) `.ai/roles/arbiter_agent.md`

**Before**
````markdown
## Output Contract
```json
{
  "role": "arbiter_agent",
  "status": "complete",
  "artifacts_written": [{"path": ".quest/<id>/phase_01_plan/arbiter_verdict.md", "kind": "verdict"}],
  "questions": [],
  "next_role": "planner_agent | builder_agent",
  "summary": "Iteration N: [approve|iterate] — [reason]"
}
```

## Important: Context Is In Your Prompt
The plan, both reviews, quest brief, and all other context are provided directly in your prompt below. Do NOT ask the Creator to paste them — they are already included. Work with what you have.
````

**After**
````markdown
## Output Contract
End your response with:
```text
---HANDOFF---
STATUS: complete
ARTIFACTS: .quest/<id>/phase_01_plan/arbiter_verdict.md
NEXT: planner | builder
SUMMARY: Iteration <N>: <approve|iterate> — <reason>
```
````

And **remove** the entire “## Important: Context Is In Your Prompt” section.

Rationale: avoids contradicting “pass paths, not content”; keeps the Arbiter’s routing decision in the `NEXT` line that the orchestrator can parse.

---

### 4) `.ai/roles/builder_agent.md`

**Before**
````markdown
## Output Contract
```json
{
  "role": "builder_agent",
  "status": "complete | needs_human | blocked",
  "artifacts_written": [
    {"path": ".quest/<id>/phase_02_implementation/pr_description.md", "kind": "pr_description"},
    {"path": "api/some_file.py", "kind": "code"}
  ],
  "questions": [],
  "next_role": "code_review_agent",
  "summary": "..."
}
```
````

**After**
````markdown
## Output Contract
End your response with:
```text
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: .quest/<id>/phase_02_implementation/pr_description.md, .quest/<id>/phase_02_implementation/builder_feedback_discussion.md, <any changed code/test files>
NEXT: code_review
SUMMARY: <one line>
```
````

Rationale: orchestrator only needs artifact paths + one-line summary; code reviewer can derive file list from git, but listing artifacts remains helpful and consistent.

---

### 5) `.ai/roles/code_review_agent.md`

**Before**
````markdown
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
````

**After**
````markdown
## Output Contract
End your response with:
```text
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: .quest/<id>/phase_03_review/review_<claude|codex>.md
NEXT: fixer | null
SUMMARY: <one line>
```
````

Rationale: matches the workflow’s actual review artifact names (`review_claude.md` / `review_codex.md`) and the `NEXT: fixer | null` convention already used in workflow Codex prompts.

---

### 6) `.ai/roles/fixer_agent.md`

**Before**
````markdown
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
````

**After**
````markdown
## Input
- Code reviews (`.quest/<id>/phase_03_review/review_claude.md` and `.quest/<id>/phase_03_review/review_codex.md`)
- Changed files (as a list in the prompt, and/or via git diff)

## Output Contract
End your response with:
```text
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: .quest/<id>/phase_03_review/review_fix_feedback_discussion.md, <any changed code/test files>
NEXT: code_review
SUMMARY: <one line>
```
````

Rationale: removes JSON mention, aligns with workflow’s two-review-file setup, and keeps the fixer’s handoff consistent for the re-review loop.

---

## Workflow.md: make Claude Task prompts explicitly request handoff

### 7) `.skills/quest/delegation/workflow.md` — Step 3 (Planner + Claude plan-reviewer)

**Before**
```markdown
2. **Invoke Planner** (Task tool with `planner` agent):
   - Prompt: Reference the quest brief path ...

**Claude reviewer** (Task tool with `plan-reviewer` agent):
   - Prompt: Reference file paths only, do not embed content:
     - Quest brief: `.quest/<id>/quest_brief.md`
     - Plan: `.quest/<id>/phase_01_plan/plan.md`
   - Writes to `.quest/<id>/phase_01_plan/review_claude.md`
```

**After**
```markdown
2. **Invoke Planner** (Task tool with `planner` agent):
   - Prompt: Reference file paths only, do not embed content:
     - Quest brief: `.quest/<id>/quest_brief.md`
     - Arbiter verdict (iteration 2+): `.quest/<id>/phase_01_plan/arbiter_verdict.md`
     - (Optional) User feedback: `.quest/<id>/phase_01_plan/user_feedback.md`
   - Prompt MUST end with:
     - `End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY`
     - `ARTIFACTS` must include `.quest/<id>/phase_01_plan/plan.md`

**Claude reviewer** (Task tool with `plan-reviewer` agent):
   - Prompt MUST end with:
     - `End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY`
     - `ARTIFACTS` must include `.quest/<id>/phase_01_plan/review_claude.md`
     - `NEXT: arbiter`
```

### 8) `.skills/quest/delegation/workflow.md` — Step 4/5/6 (Builder + Claude code-reviewer + Fixer)

**Before**
```markdown
2. **Invoke Builder** (Task tool with `builder` agent):
   - Prompt: Reference file paths only, do not embed content:
     - Approved plan: `.quest/<id>/phase_01_plan/plan.md`
     - Quest brief: `.quest/<id>/quest_brief.md`

**Claude reviewer** (Task tool with `code-reviewer` agent):
   - Prompt: Reference file paths only, do not embed content:
     - Quest brief: `.quest/<id>/quest_brief.md`
     - Plan: `.quest/<id>/phase_01_plan/plan.md`
     - Changed files: <file list from step 3>
     - Instruction: Use `git diff` to review actual changes
   - Writes to `.quest/<id>/phase_03_review/review_claude.md`

2. **Invoke Fixer** (Task tool with `fixer` agent):
   - Prompt: Reference file paths only, do not embed content:
     - Code review (Claude): `.quest/<id>/phase_03_review/review_claude.md`
     - Code review (Codex): `.quest/<id>/phase_03_review/review_codex.md`
     - Changed files: <file list from git diff>
     - Quest brief: `.quest/<id>/quest_brief.md`
     - Plan: `.quest/<id>/phase_01_plan/plan.md`
```

**After**
```markdown
2. **Invoke Builder** (Task tool with `builder` agent):
   - Prompt MUST end with:
     - `End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY`
     - `NEXT: code_review`
     - `ARTIFACTS` must include `.quest/<id>/phase_02_implementation/pr_description.md`

**Claude reviewer** (Task tool with `code-reviewer` agent):
   - Prompt MUST end with:
     - `End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY`
     - `ARTIFACTS` must include `.quest/<id>/phase_03_review/review_claude.md`
     - `NEXT: fixer | null`

2. **Invoke Fixer** (Task tool with `fixer` agent):
   - Prompt MUST end with:
     - `End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY`
     - `NEXT: code_review`
```

### 9) `.skills/quest/delegation/workflow.md` — Arbiter (Claude tool path)

**Before**
```markdown
- If "claude": use Task tool with `arbiter` agent:
  - Prompt: Reference file paths only, do not embed content:
    - Instructions: `.ai/roles/arbiter_agent.md`
    - Quest brief: `.quest/<id>/quest_brief.md`
    - Plan: `.quest/<id>/phase_01_plan/plan.md`
    - Claude review: `.quest/<id>/phase_01_plan/review_claude.md`
    - Codex review: `.quest/<id>/phase_01_plan/review_codex.md`
    - Output: `.quest/<id>/phase_01_plan/arbiter_verdict.md`
```

**After**
```markdown
- If "claude": use Task tool with `arbiter` agent:
  - Prompt MUST end with:
    - `End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY`
    - `ARTIFACTS` must include `.quest/<id>/phase_01_plan/arbiter_verdict.md`
    - `NEXT: planner | builder`
```

---

## Why this aligns with Phase 4 (and doesn’t contradict it)

Phase 4’s direction is: **eliminate 1:1 role files** and inject “wiring” directly into orchestrator prompts (including the handoff format). This plan:
- Treats the changes as **transitional wiring cleanup** (output contract + remove misleading context claims), not new architecture.
- Makes today’s system consistent with Phase 2’s **thin orchestrator** rule (paths, not pasted content).
- Reduces rework for Phase 4 because the orchestrator already standardizes on `---HANDOFF---`; Phase 4 can later delete these role files without changing the handoff contract again.
