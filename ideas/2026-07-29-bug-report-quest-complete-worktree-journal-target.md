# Bug report: Quest completion writes journals to the primary checkout from a worktree

## Summary

When a Quest uses `branch_mode: worktree` and the worktree `.quest/` entry is
a symlink to the shared Quest store in the primary checkout,
`scripts/quest_complete.py --quest-dir .quest/<id>` writes the journal and
celebration files under the primary checkout instead of the Quest source
worktree.

## Reproduction

- Consumer repo:
  `/Users/kjell/ws/extra/candid_talent_edge`
- Source worktree:
  `/Users/kjell/ws/extra/candid_talent_edge/.worktrees/quest/filter-semantics-fix`
- Branch:
  `quest/filter-semantics-fix`
- Quest:
  `filter-semantics-fix_2026-07-28__2103`
- State:
  `branch_mode: worktree`
- Command, run from the source worktree:

  ```bash
  python3 scripts/quest_complete.py \
    --quest-dir .quest/filter-semantics-fix_2026-07-28__2103
  ```

## Observed

The script reported and created:

- `/Users/kjell/ws/extra/candid_talent_edge/docs/quest-journal/filter-semantics-fix_2026-07-29.md`
- `/Users/kjell/ws/extra/candid_talent_edge/docs/quest-journal/celebrations/filter-semantics-fix_2026-07-29.md`

Those paths belong to the primary checkout. The worktree initially had no
generated journal files.

## Expected

Source-bearing completion artifacts should be written under the Quest's saved
`worktree_path` when it exists, matching the workflow rule that Steps 4–7 use
`source_workspace_root`.

The shared Quest archive may remain in the primary repository's shared
`.quest/` store.

## Impact

- Pollutes an unrelated or dirty primary checkout.
- Omits journal files from the feature branch that implemented the Quest.
- Requires manual copying and provenance-sensitive cleanup.
- Risks losing the journal from the eventual PR.

## Recovery used

The two generated files were copied byte-identically into the feature
worktree, checksums were verified, and only the generated primary-checkout
copies were moved to Trash. Unrelated primary-checkout changes were untouched.

## Suggested fix

Have `quest_complete.py` derive two roots explicitly:

1. `quest_store_root` for archive operations, based on the resolved Quest
   directory.
2. `source_workspace_root` for journal and celebration writes, based on
   `state.json.worktree_path` when present and valid, otherwise the invoking
   repository root.

Add an integration test with a linked worktree whose `.quest/` path is a
symlink to the primary checkout.
