# Install Posture — Outside-In By Default

Quest is a **generic orchestrator** whose value is consistency across
repos. The recommended install posture is **outside-in**: the
canonical skill install lives once, at `~/ws/extra/quest/` (or
wherever the user keeps their Quest install), and every project
using Quest only carries **per-repo state** — never copies of the
skill itself.

This document records the decision and explains when (rarely) to
deviate.

---

## What "outside-in" looks like

```
~/ws/extra/quest/                      ← canonical install
├── .skills/quest/                      ← the orchestration skill
├── scripts/                            ← quest_state.py, quest_startup_branch.py, …
├── docs/                               ← this file lives here
├── ideas/                              ← canonical proposals
└── tests/

~/ws/extra/<project>/                  ← any project using Quest
├── .quest/                             ← per-project state
│   ├── <quest-slug>_YYYY-MM-DD__HHMM/  ← in-flight quest folder
│   ├── archive/                        ← completed quests
│   ├── audit.log                       ← shared append-only log
│   └── active_quests.json              ← cross-worktree registry
├── scripts/                            ← optional project-local helpers
│   └── quest-active.py                 ← reference impl pending canonical adoption
└── …                                   ← regular project files
```

The skill is read by the orchestrator from the canonical install. The
project working directory provides only the **state and the context**.
A symlink `<worktree>/.quest → <main-repo>/.quest` (created by
`quest_startup_branch.py`) means every worktree of the same project
sees the same state directory.

## Why outside-in

1. **Updates propagate once.** When a canonical change lands (e.g.
   the cross-worktree `active_quests.json` registry hooks proposed
   in `ideas/active-quests-registry.md`), every project using Quest
   benefits the next time its orchestrator runs. With per-repo
   install, the same change would require N edits across N project
   copies — and would inevitably drift.
2. **Single source of truth.** Bug reports, feature requests, and
   ideas all flow into one canonical location. Per-repo install
   creates a maintenance burden where each project owner needs to
   re-pull updates manually.
3. **Smaller per-project footprint.** Projects only carry the state
   and any project-specific overrides. The skill itself (which is
   substantial — workflow.md alone is ~1300 lines) lives once.
4. **Cleaner repo diffs.** PRs to a project repo don't show Quest
   internals churning. Quest's evolution is visible only in the
   canonical install.

## When per-repo install would be appropriate (rare)

- **Forked customisation that can't be merged upstream.** If a
  regulated codebase requires mandatory extra review phases that
  don't belong in the generic skill, a per-repo Quest fork can hold
  them. Mark the fork's deviations clearly so re-syncing with
  canonical is feasible later.
- **Product-embedded Quest.** If a project ships a binary that
  itself embeds Quest at runtime for its own users, bundling makes
  sense — the project effectively becomes a Quest *redistributor*.
  This is not the same as a project *using* Quest for development.
- **Air-gapped environments.** A project that develops without
  network access to the canonical install needs a local copy.
  Document the sync cadence.

In all three cases, the per-repo install is an exceptional state
that needs explicit ownership and a re-sync plan, not the default.

## State that lives in the project, not the canonical install

- **`.quest/`** — quest folders, archive, audit log, registry. State.
- **Project-local scripts** that bridge the canonical install to the
  project's conventions. Example: `scripts/quest-active.py` in
  diffly is a reference implementation living in the project while
  the canonical install catches up.
- **Project-specific quest briefs** stored in scratch
  (`.ws/quest-prompts.md` in diffly).

## How to refer to Quest from a project

- In project READMEs / docs: link to the canonical install path or
  to the public Quest repository if open-sourced.
- In CI: invoke the canonical install's entrypoint scripts directly.
  Do not vendor copies of `quest_*.py` into the project.

## References

- Reference implementation of `quest-active` in any project's
  `scripts/quest-active.py` — canonical adoption tracked in
  `ideas/active-quests-registry.md`.
- This posture was confirmed in conversation 2026-05-20 when a user
  asked: "should we just use the quest installer and install quest
  orchestration in diffly like we can do, or should we operate with
  quest from Outside -> in. like we currently are doing?" The answer
  is outside-in unless one of the exceptions above applies.
