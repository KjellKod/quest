---
name: review-decisions
description: Canonical decision policy for turning review findings into `review_backlog.json` decisions (`fix_now`, `verify_first`, `defer`, `drop`, `needs_human_decision`) with deterministic metadata and loop-cap behavior.
---

# Review Decisions

Shared policy for Arbiter and PR shepherd style decision-making after review findings are normalized.

## When To Use

Use this skill when:
- Converting canonical review findings into backlog decisions
- Enforcing allowed decision taxonomy
- Applying loop-cap policy (governed by `gates.max_fix_iterations` in allowlist)
- Appending deferred findings to `.quest/backlog/deferred_findings.jsonl`

## Canonical Decision Set

Allowed `decision` values:
- `fix_now`
- `verify_first`
- `defer`
- `drop`
- `needs_human_decision`

Each backlog item must include:
- `decision_confidence`
- `reason`
- `needs_validation`
- `owner`
- `batch`

## Baseline Rules

1. Use `fix_now` for high-severity, high-confidence findings with clear evidence.
2. Use `verify_first` when confidence/evidence is weaker or reproduction is needed.
3. Use `defer` when scope/priority does not justify immediate work.
4. Use `drop` for low-value/noise findings after explicit evaluation.
5. Use `needs_human_decision` when risk/tradeoff needs explicit human call.

## Loop-Cap Rules

- Max fix iterations are governed by `gates.max_fix_iterations` in the allowlist (default 3).
- Solo mode uses `min(solo.max_fix_iterations, gates.max_fix_iterations)`.
- At cap, unresolved findings must be converted to:
  - `defer` (with accepted-debt rationale), or
  - `needs_human_decision`
- Do not silently continue looping after cap.

## Deferred Backlog Requirements

When a finding is deferred, append one JSON object per line to:
- `.quest/backlog/deferred_findings.jsonl`

Required lineage fields per deferred record:
- `deferred_by_quest`
- `deferred_at` (ISO8601 UTC)
- `defer_reason`
- `proposed_followup`

## Batching And Ownership

- `owner` should identify who can resolve the finding (usually by touched area).
- `batch` should group related files/findings to keep implementation slices focused.
- Prefer deterministic grouping by canonical write scope path.
