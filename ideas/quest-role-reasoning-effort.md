---
title: Quest Role Reasoning Effort — Per-Role Thinking Defaults
purpose: Add a simple per-role reasoning effort configuration so Quest can tune planner/reviewer/builder/fixer depth explicitly
audience: Quest orchestrator, workflow, allowlist maintainers
status: draft
---

# Quest Role Reasoning Effort — Per-Role Thinking Defaults

## The Problem

Quest already lets us choose **which model** plays each role via `.ai/allowlist.json`, and it already lets reviews run in `fast`, `auto`, or `full` modes. But it does **not** let us say how much reasoning effort each role should use.

That means:
- planners and arbiters have no explicit "think harder" default
- builders and fixers can't be intentionally cheaper for routine work
- CI review has an `effort: high` knob, but Quest roles do not
- the current behavior is implicit rather than controlled

If we move to GPT-5.4-style reasoning controls, Quest should expose them cleanly.

## The Proposal

Add a single allowlist section:

```json
"reasoning_effort": {
  "planner": "high",
  "plan-reviewer-a": "high",
  "plan-reviewer-b": "high",
  "builder": "medium",
  "code-reviewer-a": "high",
  "code-reviewer-b": "high",
  "arbiter": "high",
  "fixer": "medium"
}
```

Allowed values:
- `low`
- `medium`
- `high`

No more than that for v1. Keep it boring.

## Recommended Defaults

### Default policy

- **Thinking roles** default to `high`
- **Execution roles** default to `medium`
- `low` is reserved for tightly bounded, mechanical work

### Per-role defaults

| Role | Default | Why |
|------|---------|-----|
| `planner` | `high` | Sets structure for the whole quest |
| `plan-reviewer-a` | `high` | Should catch missing acceptance criteria, edge cases, and scope gaps |
| `plan-reviewer-b` | `high` | Same as above; diversity is not useful if both reviewers think shallowly |
| `arbiter` | `high` | Makes final planning judgment and should resolve disagreement carefully |
| `builder` | `medium` | Mostly execution against an approved plan |
| `code-reviewer-a` | `high` | Review quality matters more than speed |
| `code-reviewer-b` | `high` | Same rationale as reviewer A |
| `fixer` | `medium` | Usually bounded by explicit review feedback |

## What Should Default to `low`?

Usually **nothing** in the full quest workflow.

`low` is acceptable only when the work is narrow and mostly mechanical:
- builder for tiny doc/config/test-only edits
- fixer for a single explicit review comment with obvious scope

Roles that should **not** default to `low`:
- planner
- plan reviewers
- code reviewers
- arbiter

If these go shallow by default, Quest loses the rigor people are using it for.

## How It Fits with Existing Controls

This does **not** replace:
- `model_overrides`
- `review_mode`
- `fast_review_thresholds`

Those control different things:

| Control | What it changes |
|---------|-----------------|
| `model_overrides` | which model plays the role |
| `review_mode` | prompt breadth / review verbosity |
| `reasoning_effort` | how hard the model thinks before responding |

All three can coexist.

## Where to Wire It

### 1. Allowlist

Add `reasoning_effort` to `.ai/allowlist.json`.

### 2. Workflow

Update `.skills/quest/delegation/workflow.md` so every Codex role:
- reads `reasoning_effort.<role>` from allowlist
- defaults if missing
- passes that value to `mcp__codex__codex(...)`

Primary Codex-backed roles today:
- `plan-reviewer-b`
- `builder`
- `code-reviewer-b`
- `fixer`

If other Codex-backed slots are introduced later, they should use the same pattern.

### 3. Docs

Add a short note to `.skills/quest/SKILL.md` or the workflow docs explaining:
- supported values: `low|medium|high`
- opinionated defaults
- when `low` is appropriate

## Minimal V1 Behavior

For v1:
- do not add dynamic heuristics
- do not infer effort from diff size
- do not create separate "review reasoning mode" or "build reasoning mode"

Just:
1. read per-role config
2. fall back to sensible defaults
3. pass it through

That is enough to make behavior explicit and tunable.

## Suggested Defaults for GPT-5.4-Level Models

If Quest adopts GPT-5.4-class reasoning controls, the opinionated defaults should be:

```json
{
  "planner": "high",
  "plan-reviewer-a": "high",
  "plan-reviewer-b": "high",
  "builder": "medium",
  "code-reviewer-a": "high",
  "code-reviewer-b": "high",
  "arbiter": "high",
  "fixer": "medium"
}
```

This is the "safe default" profile: serious thinking where judgment matters, moderate effort where execution dominates.

## Future Extension (Not V1)

Only after living with the static defaults should Quest consider:
- route-based overrides (`workflow` vs `solo`)
- task-size overrides (`tiny builder diff -> low`)
- emergency speed profile (`builder: low`, `fixer: low`)

But the first version should stay explicit and simple.

## Recommendation

Implement this as a small configuration enhancement now.

It gives Quest a clear "thinking budget" per role without changing the pipeline shape, and it matches how people already think about the roles:
- planner / arbiter / reviewers are judgment-heavy
- builder / fixer are execution-heavy

That makes the system easier to tune, easier to explain, and more predictable.
