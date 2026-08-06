# Quest Journal: Quest Brief

- Quest ID: `prebuild-replanning-contract-r2_2026-08-04__1630`
- Slug: prebuild-replanning-contract-r2
- Completed: 2026-08-05
- Mode: workflow
- Quality: Tin
- Celebration: [`celebrations/prebuild-replanning-contract-r2_2026-08-05.md`](celebrations/prebuild-replanning-contract-r2_2026-08-05.md)
- Outcome: Fix Quest's pre-build replanning contract so every human-requested plan change before Build returns safely to planning through validated state transitions. Use the full Quest workflow in an isolate...

## What Shipped

**Problem:** Quest cannot validate every requested pre-Build return to `plan`. Stale approval artifacts can outrank human intent, completed planning artifacts can be truncated without sealed audit history, and a findings-only Arbiter retry can recreate an already-valid verdict.

**Scope:** Add on...

## Files Changed

- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_01_plan/arbiter_verdict.md.next`
- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_01_plan/review_findings.json.next`
- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_01_plan/review_plan-reviewer-b.md`
- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_01_plan/plan.md`
- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_02_implementation/pr_description.md`
- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_02_implementation/builder_feedback_discussion.md`
- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_03_review/review_code-reviewer-a.md`
- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_03_review/review_findings_code-reviewer-a.json`
- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_03_review/review_code-reviewer-b.md`
- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_03_review/review_findings_code-reviewer-b.json`
- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_03_review/review_fix_feedback_discussion.md`
- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_03_review/review_arbiter_verdict.md.next`
- `.quest/prebuild-replanning-contract-r2_2026-08-04__1630/phase_03_review/review_findings.json.next`

## Iterations

- Plan iterations: 3
- Fix iterations: 3

## Agents

- **The Judge** (arbiter):
- **The Implementer** (builder):

## Quest Brief

Fix Quest's pre-build replanning contract so every human-requested plan change before Build returns safely to planning through validated state transitions.

Use the full Quest workflow in an isolated worktree. Reproduce bugs with failing tests before implementation.

Required behavior:

1. Allow validated human-driven replanning from `plan_reviewed`, `presenting`, and `presentation_complete` to `plan`, preserving automatic `plan -> plan` refinement.
2. Define one user-replan procedure for walkthrough changes, sharpen revisions, Build-gate rejection, and resumed plan-change instructions.
3. Record current non-empty feedback before transition. Missing, empty, malformed, erased, replayed, or stale feedback must fail without changing `state.json`.
4. Use `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition plan --status in_progress --expect-phase <current>`. Never hand-edit state or use `--phase` to bypass validation.
5. Durably invalidate prior approval. Resume must dispatch the Planner despite stale Planner, Reviewer, Arbiter, handoff, verdict, findings, or backlog artifacts.
6. Block Build until the revised plan repeats current-generation review, arbitration where applicable, presentation, and explicit human presentation approval.
7. Support workflow and solo modes without requiring unavailable solo artifacts.
8. Permit human replanning at the automatic plan-iteration cap while retaining the cap for automatic refinement.
9. Do not add backward transitions from `building`, `reviewing`, `fixing`, or `complete`.
10. Update workflow documentation with unambiguous entry points and exact commands.
11. Keep canonical `phase_01_plan/**` paths as the current working set and add immutable, atomic audit snapshots under `.quest/<id>/history/plan/iteration-NNNN/` before completed plan iterations can be truncated.
12. Preserve valid Arbiter verdict scratch output during findings-only retries. Retry only invalid findings and bind the exact verdict to the following Planner dispatch.
13. Publish the delegated bug report to `ideas/2026-08-04-bug-reporting-automatic-plan-refinement-feedback-loss.md`, accurately distinguishing the confirmed truncation trigger from unconfirmed broader loss.

Required regressions cover every supported and forbidden edge, current feedback identity, unchanged state on failure, both modes, stale-artifact resume, renewed Build gates, all four entry points, mandatory presentation, automatic iteration caps, relevant `auto_approve_phases` all-true/all-false behavior, snapshot idempotence and mismatch failure, exact Arbiter verdict continuity, and current-generation handoffs.

Keep the change focused. Do not rename scripts. Update managed checksums and relevant docs. Run focused state tests, Quest runtime tests, unit suite, formatting, configuration validation, manifest validation, handoff-contract validation, checksum drift validation, and git diff checks.

## Findings Left For Future Quests

- Count: **3**
- status value replan_requested is written by the runtime but missing from the documented state enum.
- _read_json maps a missing file (OSError) to the same invalid_json:<name> category as a genuine parse failure, so an absent inventory file is reported as malformed JSON.
- The approval table promises that plan_refinement: false 'Does not block requested human replan', but at that exact gate both human replan entry points fail closed and the workflow docs record no caveat.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- Full celebration: [`celebrations/prebuild-replanning-contract-r2_2026-08-05.md`](celebrations/prebuild-replanning-contract-r2_2026-08-05.md)
- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/prebuild-replanning-contract-r2_2026-08-05.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "workflow",
  "agents": [
    {
      "name": "arbiter",
      "model": "",
      "role": "The Judge",
      "transport": "background-agent"
    },
    {
      "name": "builder",
      "model": "",
      "role": "The Implementer"
    }
  ],
  "claude_transport_counts": {
    "background-agent": 24
  },
  "achievements": [
    {
      "icon": "[BUG]",
      "title": "Gremlin Slayer",
      "desc": "Tackled 51 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 12 reviews"
    },
    {
      "icon": "[PLAN]",
      "title": "Plan Perfectionist",
      "desc": "Iterated plan 3 times"
    },
    {
      "icon": "[WIN]",
      "title": "Quest Complete",
      "desc": "All phases finished successfully"
    }
  ],
  "metrics": [
    {
      "icon": "📊",
      "label": "Plan iterations: 3"
    },
    {
      "icon": "🔧",
      "label": "Fix iterations: 3"
    },
    {
      "icon": "📝",
      "label": "Review rounds: 12"
    },
    {
      "icon": "🚌",
      "label": "Claude transport: background-agent ×24"
    }
  ],
  "quality": {
    "tier": "Tin",
    "grade": "T"
  },
  "inherited_findings_used": {
    "count": 0,
    "summaries": []
  },
  "findings_left_for_future_quests": {
    "count": 3,
    "summaries": [
      "status value replan_requested is written by the runtime but missing from the documented state enum.",
      "_read_json maps a missing file (OSError) to the same invalid_json:<name> category as a genuine parse failure, so an absent inventory file is reported as malformed JSON.",
      "The approval table promises that plan_refinement: false 'Does not block requested human replan', but at that exact gate both human replan entry points fail closed and the workflow docs record no caveat."
    ]
  },
  "test_count": null,
  "tests_added": null,
  "files_changed": 14
}
```
<!-- celebration-data-end -->
