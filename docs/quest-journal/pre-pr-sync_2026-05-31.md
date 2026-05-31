# Quest Journal: Pre-PR sync with default branch

- Quest ID: `pre-pr-sync_2026-05-31__1211`
- Slug: pre-pr-sync
- Completed: 2026-05-31
- Mode: workflow
- Quality: Platinum
- Celebration: [`celebrations/pre-pr-sync_2026-05-31.md`](celebrations/pre-pr-sync_2026-05-31.md)
- Outcome: implement using $quest ideas/2026-05-30-pre-pr-freshness-and-force-push-guard.md

## What Shipped

**Problem:** `pr-assistant` can open a PR whose branch is already **behind the remote
default branch**, so the PR is born stale against `main`. A human would sync first;
the tool should too — automatically, as part of opening the PR. The same staleness
risk exists in `pr-shepherd` when it pushes ...

## Files Changed

- `.quest/pre-pr-sync_2026-05-31__1211/phase_01_plan/plan.md`
- `.quest/pre-pr-sync_2026-05-31__1211/phase_01_plan/arbiter_verdict.md.next`
- `.quest/pre-pr-sync_2026-05-31__1211/phase_01_plan/review_findings.json.next`
- `.quest/pre-pr-sync_2026-05-31__1211/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/pre-pr-sync_2026-05-31__1211/phase_01_plan/review_plan-reviewer-b.md`
- `.quest/pre-pr-sync_2026-05-31__1211/phase_02_implementation/pr_description.md`
- `.quest/pre-pr-sync_2026-05-31__1211/phase_02_implementation/builder_feedback_discussion.md`
- `.quest/pre-pr-sync_2026-05-31__1211/phase_03_review/review_fix_feedback_discussion.md`

## Iterations

- Plan iterations: 1
- Fix iterations: 1

## Agents

- **The A Code Critic** (code-reviewer-a): 
- **The B Code Critic** (code-reviewer-b): 

## Quest Brief

implement using $quest ideas/2026-05-30-pre-pr-freshness-and-force-push-guard.md

## This is where it all began...

Original idea: `ideas/2026-05-30-pre-pr-freshness-and-force-push-guard.md`

> Pre-PR sync with the default branch: before `pr-assistant` opens a PR, bring the
> branch up to date with the remote default branch so we never open a PR that is
> already stale against `main`. Sync runs automatically; the only thing surfaced
> to a human is a merge/rebase conflict.
>
> The behavior belongs in `pr-assistant`, with `pr-shepherd` reusing the same
> shared helper before review-fix pushes. It should not become a new Quest state
> machine phase.
>
> The sync uses ordinary git operations: fetch origin, detect the default branch
> from `origin/HEAD` with a `gh repo view` fallback, no-op when already current,
> and sync cleanly by default. If conflicts are clearly safe and non-destructive,
> resolve and continue; otherwise pause and ask the human. Never use blanket
> `-X theirs` or `-X ours`.
>
> A rebased branch may be updated with `git push --force-with-lease`; this is the
> narrow lease-protected exception for the author's own PR branch, not a general
> force-push permission.
>
> Out of scope: no new Quest phase, no allowlist permission grants, no duplicated
> local test/build suite before PR creation, no CI change, and no blind conflict
> resolution.

## Carry-Over Findings

- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- Full celebration: [`celebrations/pre-pr-sync_2026-05-31.md`](celebrations/pre-pr-sync_2026-05-31.md)
- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/pre-pr-sync_2026-05-31.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "workflow",
  "agents": [
    {
      "name": "code-reviewer-a",
      "model": "",
      "role": "The A Code Critic"
    },
    {
      "name": "code-reviewer-b",
      "model": "",
      "role": "The B Code Critic"
    }
  ],
  "achievements": [
    {
      "icon": "[BUG]",
      "title": "Gremlin Slayer",
      "desc": "Tackled 33 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 7 reviews"
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
      "label": "Fix iterations: 1"
    },
    {
      "icon": "📝",
      "label": "Review findings: 7"
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
  "files_changed": 8
}
```
<!-- celebration-data-end -->
