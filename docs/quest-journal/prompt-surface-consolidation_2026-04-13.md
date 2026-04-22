# Quest Journal: Prompt Surface / Instruction Architecture Consolidation

- Quest ID: `prompt-surface-consolidation_2026-04-13__1701`
- Completed: 2026-04-13
- Mode: solo
- Quality: Platinum
- Outcome: Consolidated overlapping Quest prompt-surface proposals into one canonical instruction architecture document.

## What Shipped

**Problem:** Two overlapping proposal docs exist in `ideas/` that address related aspects of Quest prompt-surface improvement: one focused on selective rule-pack loading (`2026-04-13-focused-rule-packs.md`) and one on workflow-first skill structure (`2026-04-13-orchestration-improvement-workflow....

## Files Changed

- `.quest/prompt-surface-consolidation_2026-04-13__1701/phase_01_plan/plan.md`
- `.quest/prompt-surface-consolidation_2026-04-13__1701/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/prompt-surface-consolidation_2026-04-13__1701/phase_02_implementation/pr_description.md`
- `ideas/2026-04-13-instruction-architecture.md`
- `.ws/2026-04-13-focused-rule-packs.md`
- `.ws/2026-04-13-orchestration-improvement-workflow.md`
- `ideas/README.md`
- `ideas/archive/2026-04-13-review-intelligence-canonical.md`
- `.quest/prompt-surface-consolidation_2026-04-13__1701/phase_03_review/review_code-reviewer-a.md`

## Iterations

- Plan iterations: 1
- Fix iterations: 0

## Quest Brief

> 3. Prompt Surface / Instruction Architecture
>
> Consolidate Quest prompt-surface improvement docs into one canonical instruction architecture proposal. Merge `ideas/2026-04-13-focused-rule-packs.md` and `ideas/2026-04-13-orchestration-improvement-workflow.md` into a single successor doc, keeping the scope strictly at the proposal/documentation level. The merged doc must clearly separate:
>
> 1. selective rule-pack loading
> 2. canonical ownership of policy families
> 3. workflow-first skill structure
> 4. prompt assembly/debugging model
> 5. migration plan
>
> It must explicitly preserve these rules:
> - this only matters if runtime prompt loading actually changes
> - avoid pack explosion
> - keep role wiring separate from policy packs
> - use workflows as short executable recipes with entry/exit conditions
> - prefer one medium-value coherent proposal over two overlapping documentation-shape ideas
>
> This quest should only produce cleaned-up proposal docs, not implementation changes. Create a new successor document in `ideas/`, retire superseded working docs to `.ws/`, and update `ideas/README.md` plus cross-references so nothing goes stale.
>
> Note: Other agents are working with other docs. Don't trip them up. If any document is missing then check the `.ws/` folder as it might have been moved there.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/prompt-surface-consolidation_2026-04-13.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "solo",
  "agents": [],
  "achievements": [
    {
      "icon": "[BUG]",
      "title": "Gremlin Slayer",
      "desc": "Tackled 4 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 2 reviews"
    },
    {
      "icon": "[SOLO]",
      "title": "Solo Adventurer",
      "desc": "Completed quest with a single companion"
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
      "label": "Plan iterations: 1"
    },
    {
      "icon": "🔧",
      "label": "Fix iterations: 0"
    },
    {
      "icon": "📝",
      "label": "Review findings: 2"
    }
  ],
  "quality": {
    "tier": "Platinum",
    "grade": "P"
  },
  "test_count": null,
  "tests_added": null,
  "files_changed": 9
}
```
<!-- celebration-data-end -->
