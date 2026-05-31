# Quest Journal: Direct CLI Guidance

- Quest ID: `direct-cli-guidance_2026-03-22__1052`
- Slug: direct-cli-guidance
- Completed: 2026-03-22
- Mode: solo
- Quality: Platinum
- Celebration: [`celebrations/direct-cli-guidance_2026-03-22.md`](celebrations/direct-cli-guidance_2026-03-22.md)
- Outcome: Claude Code permission prefixes (e.g. `["gh","api"]`, `["gh","pr"]`) only match when the command is the top-level executable. When agents wrap GitHub CLI calls in `bash -lc 'gh ...'`, the prefix sees `bash` not `gh`, and prompts for permission every time.

## What Shipped

Claude Code permission prefixes (e.g. `["gh","api"]`, `["gh","pr"]`) only match when the command is the top-level executable. When agents wrap GitHub CLI calls in `bash -lc 'gh ...'`, the prefix sees `bash` not `gh`, and prompts for permission every time.

## Files Changed

- `.quest/direct-cli-guidance_2026-03-22__1052/phase_01_plan/plan.md`
- `.quest/direct-cli-guidance_2026-03-22__1052/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/direct-cli-guidance_2026-03-22__1052/phase_03_review/review_code-reviewer-a.md`

## Iterations

- Plan iterations: 1
- Fix iterations: 0

## Quest Brief

Add guidance to skill docs that GitHub CLI commands should be invoked directly (not wrapped in `bash -lc`) so that persistent permission prefixes like `["gh","api"]` and `["gh","pr"]` match correctly. Wrapping defeats prefix matching and causes repeated permission prompts during quest orchestration.

## Carry-Over Findings

- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- Full celebration: [`celebrations/direct-cli-guidance_2026-03-22.md`](celebrations/direct-cli-guidance_2026-03-22.md)
- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/direct-cli-guidance_2026-03-22.md`

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
  "inherited_findings_used": {
    "count": 0,
    "summaries": []
  },
  "findings_left_for_future_quests": {
    "count": 0,
    "summaries": []
  },
  "test_count": null,
  "tests_added": null,
  "files_changed": 3
}
```
<!-- celebration-data-end -->
