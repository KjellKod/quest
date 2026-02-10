# Contracts & Verification (Concrete Proposal)

This doc specifies **minimal contracts** (artifacts + checks) that make Quest more “pipeline-validatable” without changing its overall flow.

The emphasis is on:
- explicit artifacts,
- machine-checkable handoffs,
- and evidence capture for verification.

## 1) Handoff Contract: make it real, not just aspirational

Quest already ships `.ai/schemas/handoff.schema.json`. The smallest “principled” move is to require each role to **write a JSON handoff file** (in addition to any markdown summary).

### Proposed convention

For each role run, write:

- `.quest/<id>/<phase_dir>/handoff_<role>.json`

Examples:
- `.quest/<id>/phase_01_plan/handoff_planner_agent.json`
- `.quest/<id>/phase_01_plan/handoff_arbiter_agent.json`
- `.quest/<id>/phase_02_implementation/handoff_builder_agent.json`
- `.quest/<id>/phase_03_review/handoff_code_review_agent.json`

If multiple iterations occur, preserve history:

- `.quest/<id>/<phase_dir>/handoff_<role>_iter<N>.json`

### Validation

Add a validator that checks:
- file exists,
- parses as JSON,
- validates against `.ai/schemas/handoff.schema.json`,
- and all `artifacts_written[].path` exist on disk.

This turns the workflow into a **deterministic artifact router**:
the orchestrator can follow `next_role` without interpreting freeform text.

## 2) Evidence Bundle: what to capture (minimal)

The philosophy demands auditability. We want the smallest artifact that answers:

- What verification ran?
- What passed/failed?
- Can someone reproduce it?

### Proposed artifacts (build/fix)

Write under `.quest/<id>/logs/`:

- `verification_manifest.json` (machine-readable index)
- `verification_<timestamp>.log` (stdout/stderr capture of the “verify” command)

Optionally (nice-to-have, not required):
- `git_diff_stat.txt`
- `git_diff_name_only.txt`
- `environment.txt` (runtime versions: node/python, etc.)

### Minimal `verification_manifest.json` shape

```json
{
  "quest_id": "feature-x_2026-02-02__1430",
  "phase": "building|fixing",
  "timestamp": "2026-02-02T15:03:22Z",
  "checks": [
    {
      "name": "unit-tests",
      "command": "pytest -q",
      "exit_code": 0,
      "log_path": ".quest/<id>/logs/verification_20260202T150322Z.log"
    }
  ]
}
```

This is intentionally tiny: it’s enough to make verification *traceable*.

## 3) Validators: boring checks that block bad output early

### A) Plan lint (fast, heuristic, works on markdown)

Add a script that fails if `plan.md` is missing:
- `## Overview`
- `## Approach`
- `## File Changes Summary` (or equivalent)
- `## Test Strategy`
- acceptance criteria reference (explicit section or a link to the brief)

And warns (non-fatal) if:
- “Out of Scope” is missing,
- risks/open-questions missing,
- file summary lists broad globs (`src/**`) instead of concrete paths.

This keeps planning disciplined without enforcing a rigid markdown schema.

### B) Diff ↔ plan sanity check

Before marking a quest “review-ready”, validate:
- `git diff --name-only` is non-empty (if implementation happened),
- every changed file appears in the plan’s file summary table *or* is in a small “allowed drift” list (e.g., lockfiles),
- plan’s test strategy references at least one command that exists in allowlist for the builder/fixer.

This is how you prevent “plan says A, code did B” drift.

### C) Handoff schema checks

Validate `handoff.json` for every role. Do not proceed if it fails schema.

This is the smallest possible “pipeline decides what is acceptable” enforcement point.

## 4) Risk-based gates (still small)

The current allowlist has static `auto_approve_phases`. The small improvement is to add an *optional* risk rubric that can override auto-approve when certain conditions are met.

### Example “risk rules” concept (optional)

- If changed paths match `**/auth/**` or `**/payments/**` => require human approval before implementation and fix loop.
- If diff exceeds thresholds (files/LOC) => force full review mode (Codex) + require human approval for fix loop.

Keep it simple: path patterns + size thresholds + phase gating.

## 5) How this stays portable across Claude + OpenAI

The contract lives in `.ai/` + `.skills/`:
- `.ai/schemas/handoff.schema.json` is tool-agnostic.
- evidence manifests are tool-agnostic.
- validators are plain scripts.

That means:
- Claude `/quest` can adopt these additions with small SKILL.md adjustments.
- A Codex-only runner (see `ideas/codex-quest-skill.md`) can reuse the same contracts and validators.

## 6) Minimal migration plan (safe, incremental)

1. Start writing `handoff.json` files (don’t change anything else).
2. Add schema validation for those handoffs (block if invalid).
3. Add plan lint (warn-only at first, then block).
4. Add evidence manifest for build/fix.
5. Add diff ↔ plan check for drift.
6. Add optional risk rules once the above is stable.

The punchline: **increase autonomy only after validators are stable**, not after prompts are clever.

