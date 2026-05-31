# Quest Journal: shared-quest-symlink

- Quest ID: `shared-quest-symlink_2026-05-31__1239`
- Slug: shared-quest-symlink
- Completed: 2026-05-31
- Mode: solo
- Quality: Gold
- Celebration: [`celebrations/shared-quest-symlink_2026-05-31.md`](celebrations/shared-quest-symlink_2026-05-31.md)
- Outcome: - **Agent:** Planner - **Model:** claude-opus-4-8 - **Date:** 2026-05-31 - **Quest ID:** shared-quest-symlink_2026-05-31__1239

## What Shipped

- **Agent:** Planner
- **Model:** claude-opus-4-8
- **Date:** 2026-05-31
- **Quest ID:** shared-quest-symlink_2026-05-31__1239

## Files Changed

- `.quest/shared-quest-symlink_2026-05-31__1239/phase_01_plan/plan.md`
- `.quest/shared-quest-symlink_2026-05-31__1239/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/shared-quest-symlink_2026-05-31__1239/phase_02_implementation/pr_description.md`
- `.quest/shared-quest-symlink_2026-05-31__1239/phase_02_implementation/builder_feedback_discussion.md`
- `.quest/shared-quest-symlink_2026-05-31__1239/phase_03_review/review_code-reviewer-a.md`
- `.quest/shared-quest-symlink_2026-05-31__1239/phase_03_review/review_findings_code-reviewer-a.json`

## Iterations

- Plan iterations: 2
- Fix iterations: 0

## Agents

- **The Implementer** (builder): 

## Quest Brief

$quest in a new worktree branch, run this quest in solo mode. 
"Generalize Quest's worktree .quest symlink so it's guaranteed on every quest start.

  GOAL
  Make every quest start guarantee that, when running inside a linked git worktree, the worktree's `.quest/` is a symlink to the MAIN repo's shared `.quest/` —
  for ALL branch modes and whether Quest or a human created the worktree.

  WHY / BUG (verified)
  `.quest/` is intentionally gitignored — a single shared, per-repo run store. `scripts/quest_startup_branch.py` ALREADY symlinks `.quest/` into a worktree
  (~lines 361–374), but ONLY in the worktree-creation path (branch_mode: worktree). When a human pre-creates a worktree and Quest runs with branch_mode: none (or
  the 'already on branch → skipped' path), that code is never reached, so the worktree keeps its OWN real `.quest/`. Those artifacts are orphaned — not in the
  shared store, and destroyed when the worktree is removed — which silently breaks quest_complete.py journaling, quest_backfill_journal.py, and the dashboard.
  This caused a real incident (a completed quest left no journal entry / dashboard record).

  SCOPE (targeted, thin — do not refactor unrelated parts)
  - scripts/quest_startup_branch.py: extract the symlink-ensure into a reusable helper (e.g. ensure_shared_quest_symlink(repo_root, workdir)) and call it on
  EVERY startup path (none, branch, worktree, and the skipped/already-on-branch path), not just worktree creation.
  - Detect a linked worktree via `git rev-parse --git-common-dir` (≠ local .git ⇒ linked; shared store = dirname(common-dir)/.quest). In the main worktree,
  no-op.
  - SAFE migration (critical — NEVER lose data):
      * `.quest` absent → create the symlink.
      * `.quest` already a symlink → leave it.
      * `.quest` is a REAL dir with content → MOVE/merge its quest subdirs into the shared `.quest/` first, THEN replace with the symlink. Never rmtree-and-drop.
  If the same quest id exists in both and differs, preserve both (keep shared, move the worktree copy aside) and flag a conflict.
  - Add a `quest_symlink` field to the JSON result: created | present | migrated | conflict | n/a.
  - .skills/quest/SKILL.md startup (Quest Folder Creation, where it runs quest_startup_branch.py): surface the quest_symlink outcome to the human after the fact
  — especially migrated/conflict.

  CONSTRAINTS
  - Never destroy or drop existing `.quest/` content — migrate, don't delete.
  - Keep it targeted; add/extend tests.

  ACCEPTANCE CRITERIA
  1. ensure_shared_quest_symlink runs at quest start in ALL branch modes (incl. none and skipped/already-on-branch).
  2. In a linked worktree, <worktree>/.quest ends as a symlink to <main-repo>/.quest: created when absent, left when already a symlink, and content-migrated with
  NO data loss when a real dir pre-exists.
  3. JSON result includes quest_symlink; SKILL.md surfaces it to the human.
  4. Main (non-linked) worktree → quest_symlink: n/a, no symlink created.
  5. Tests cover: absent→created; real-dir-with-quests→migrated (assert no quest lost); already-symlink→present/no-op; main-repo→n/a; conflicting-same-id→both
  preserved + flagged.
  6. SELF-VALIDATION (live, partial): this quest runs in a worktree IT creates (branch_mode: worktree). Confirm its own <worktree>/.quest is a symlink to the
  main repo's .quest and this quest's artifacts are visible in the shared store. NOTE: this only exercises the pre-existing worktree-creation happy path — the
  running quest used the PRE-EDIT script, so your edits take effect on FUTURE starts, not this one. The NEW generalized path (branch_mode none /
  human-pre-created worktree) MUST be proven by the AC#5 tests, not by self-dogfooding.

  OUT OF SCOPE (separate follow-ups — do NOT bundle)
  - Making quest completion/journaling a fail-closed terminal gate (quest_complete.py as the only path to `complete`).
  - Backfilling the missing journal entry for the already-merged code-review-adjudication quest.

  WORKSPACE: create and run in a new quest/<slug> worktree branch (worktree mode)."

  Two notes:
  - I deliberately scoped this to the symlink fix only and listed the completion-gate + the journal backfill as explicit out-of-scope, so the new agent doesn't
  sprawl (and per your own value-over-theatre rule). Those two are worth their own quest/just-do-it later.
  - If you'd rather skip the pipeline entirely, the same text works as a "just do it" prompt — drop the /quest wrapper and the workspace line and hand it over.
  But I'd keep it a solo quest: the migration logic is exactly where a review pass earns its keep.

## Carry-Over Findings

- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- Full celebration: [`celebrations/shared-quest-symlink_2026-05-31.md`](celebrations/shared-quest-symlink_2026-05-31.md)
- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/shared-quest-symlink_2026-05-31.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "solo",
  "agents": [
    {
      "name": "builder",
      "model": "",
      "role": "The Implementer"
    }
  ],
  "achievements": [
    {
      "icon": "[BUG]",
      "title": "Gremlin Slayer",
      "desc": "Tackled 5 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 2 reviews"
    },
    {
      "icon": "[PLAN]",
      "title": "Plan Perfectionist",
      "desc": "Iterated plan 2 times"
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
      "label": "Plan iterations: 2"
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
  "files_changed": 6
}
```
<!-- celebration-data-end -->
