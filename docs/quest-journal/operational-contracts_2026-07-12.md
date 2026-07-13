# Quest Journal: Quest Brief — operational-contracts

- Quest ID: `operational-contracts_2026-07-11__1435`
- Slug: operational-contracts
- Completed: 2026-07-12
- Mode: workflow
- Quality: Gold
- Celebration: [`celebrations/operational-contracts_2026-07-12.md`](celebrations/operational-contracts_2026-07-12.md)
- Outcome: ### Problem Three operational contracts currently trust the wrong boundary: 1. `pr_sync_default_branch.py` lets an advisory `git merge-tree` probe prevent an explicitly requested rebase or merge. 2. `quest_claude_bridge.py` and `claude_bg_run.py` strip caller-owned prompt/answer content instead...

## What Shipped

### Problem

Three operational contracts currently trust the wrong boundary:

1. `pr_sync_default_branch.py` lets an advisory `git merge-tree` probe prevent an explicitly requested rebase or merge.
2. `quest_claude_bridge.py` and `claude_bg_run.py` strip caller-owned prompt/answer content instead...

## Files Changed

- `.quest/operational-contracts_2026-07-11__1435/phase_01_plan/plan.md`
- `.quest/operational-contracts_2026-07-11__1435/phase_01_plan/arbiter_verdict.md.next`
- `.quest/operational-contracts_2026-07-11__1435/phase_01_plan/review_findings.json.next`
- `.quest/operational-contracts_2026-07-11__1435/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/operational-contracts_2026-07-11__1435/phase_01_plan/review_plan-reviewer-b.md`
- `.quest/operational-contracts_2026-07-11__1435/phase_02_implementation/pr_description.md`
- `.quest/operational-contracts_2026-07-11__1435/phase_02_implementation/builder_feedback_discussion.md`
- `.quest/operational-contracts_2026-07-11__1435/phase_03_review/review_code-reviewer-a.md`
- `.quest/operational-contracts_2026-07-11__1435/phase_03_review/review_findings_code-reviewer-a.json`
- `.quest/operational-contracts_2026-07-11__1435/phase_03_review/review_code-reviewer-b.md`
- `.quest/operational-contracts_2026-07-11__1435/phase_03_review/review_findings_code-reviewer-b.json`
- `.quest/operational-contracts_2026-07-11__1435/phase_03_review/review_arbiter_verdict.md.next`
- `.quest/operational-contracts_2026-07-11__1435/phase_03_review/review_findings.json.next`

## Iterations

- Plan iterations: 2
- Fix iterations: 0

## Agents

- **The Judge** (arbiter): 
- **The Implementer** (builder): 

## Quest Brief

Implement Workstream B — Operational helper and transport correctness from ideas/2026-07-11-quest-hardening.md.

Precondition:
- Workstream A (#1, #4, #18, #22) must already have a merged PR.
- Start from the updated main branch after that merge.
- If Workstream A is not merged, stop and report the dependency.
- Use an isolated worktree.
- Do not modify Candid Talent Edge.

Scope is strictly original findings #3, #9, and #20:

- #3 Applied PR synchronization authority: inspect mode remains non-mutating and may use git merge-tree as an advisory estimate. When --apply is requested, run the existing safety guards and let the actual rebase or merge determine whether a conflict exists. Preserve abort behavior, conflict-file reporting, push-required reporting, and force-with-lease semantics.
- #9 Transport fidelity: quest_claude_bridge.py and claude_bg_run.py must reject whitespace-only prompts or answers but otherwise preserve caller content exactly, including leading indentation and trailing newlines. Cover direct prompts, prompt files, stdin, and background resume answer files.
- #20 PR-summary ownership: update a marker comment only when its author login exactly matches the current authenticated actor. Foreign humans, foreign bots, unknown authors, and missing-current-login cases must not be selected for PATCH; create a new summary instead.

Follow the complete Quest workflow and approval gates.

Plan lifecycle:
- Before implementation begins, change only Workstream B in ideas/2026-07-11-quest-hardening.md from [todo] to [ongoing].
- Do not change Workstream C.
- Workstream A should already be [done] with its PR link.
- After the complete Workstream B PR has been created, change Workstream B to [done], record its PR number/link, commit that status update, and push it to the same PR.
- Do not archive the hardening plan because Workstream C will remain.

Testing requirements:

#3:
- Preserve non-mutating inspect behavior.
- Prove that --apply invokes the requested rebase/merge even when the advisory probe predicts a conflict.
- Prove that actual rebase and merge conflicts are aborted and reported without leaving the worktree conflicted.
- Preserve clean rebase/merge behavior.
- Deliberately revise the existing test that pins probe-authoritative apply behavior; document that the old test encoded the defective contract.

#9:
- Cover leading indentation and trailing newlines.
- Cover direct bridge prompt, prompt file, stdin, background prompt, and resume answer file.
- Preserve whitespace-only rejection.
- Assert the exact content passed to the Claude subprocess boundary.

#20:
- Same authenticated user + marker updates the existing summary.
- Foreign human, foreign bot, unknown author, and failed current-login lookup create rather than update.
- Deliberately revise the test that currently trusts any bot marker; document that it encoded the defective contract.

Run at minimum:
- pytest -q tests/unit/test_pr_sync_default_branch.py
- pytest -q tests/unit/test_claude_bg_run.py
- the focused quest_claude_bridge test module
- pytest -q tests/unit/test_pr_shepherd.py
- relevant integration/runtime tests
- repository formatting and lint gates
- strict Quest-source manifest/checksum validation

Manually validate #3 in a disposable Git repository with clean and conflicting rebase and merge cases. Do not perform the manual sync test in the real Quest checkout.

Keep the implementation minimal and readable under KISS, YAGNI, SRP, DRY, and strong-typing principles. Avoid unrelated refactors.

Carry the work through planning, dual plan review, arbiter, presentation and explicit approval, implementation, dual code review, fixes, validation, commit, push, and creation of a draft PR.

## Carry-Over Findings

- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- Full celebration: [`celebrations/operational-contracts_2026-07-12.md`](celebrations/operational-contracts_2026-07-12.md)
- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/operational-contracts_2026-07-12.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "workflow",
  "agents": [
    {
      "name": "arbiter",
      "model": "",
      "role": "The Judge"
    },
    {
      "name": "builder",
      "model": "",
      "role": "The Implementer"
    }
  ],
  "claude_transport_counts": {},
  "achievements": [
    {
      "icon": "[BUG]",
      "title": "Gremlin Slayer",
      "desc": "Tackled 19 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 5 reviews"
    },
    {
      "icon": "[PLAN]",
      "title": "Plan Perfectionist",
      "desc": "Iterated plan 2 times"
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
      "label": "Plan iterations: 2"
    },
    {
      "icon": "🔧",
      "label": "Fix iterations: 0"
    },
    {
      "icon": "📝",
      "label": "Review rounds: 5"
    }
  ],
  "quality": {
    "tier": "Gold",
    "grade": "G"
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
  "files_changed": 13
}
```
<!-- celebration-data-end -->
