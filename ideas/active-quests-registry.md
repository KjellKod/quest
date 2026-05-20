# Cross-worktree active-quests registry (`.quest/active_quests.json`)

**Status:** proposal. Should become the canonical default for handling
concurrent quests across multiple Git worktrees of the same repo.

**Reference implementation:** lands today in
`/Users/kjell/ws/extra/difflyx/scripts/quest-active.py` against the
local `.quest/active_quests.json` of that repo. The canonical version
should live alongside the other `quest_*.py` helpers in `scripts/` and
be exposed as `quest active <subcommand>` via the existing skill
router. The diffly copy can be deleted once the canonical version
lands.

---

## Problem

When a developer runs Quest in two worktrees of the same repo at the
same time (one in `repo/` on `quest/feature-a`, another in
`repo/.worktrees/quest/feature-b`), there is no mechanical signal that
the second quest is starting against a repo that already has one in
flight. The two orchestrators do not see each other; the human has to
remember which terminal is doing what.

Concretely observed in `difflyx/.quest/archive/`:

- `vc-view-completeness` ran 47 hours wall time, dominated by
  human-gate waits between phases. Had a second independent quest
  been launched in parallel, the human could have walked between two
  plans during the same gate window — doubling throughput without
  changing any single quest's quality bar.
- No visible "I'm pretty sure I started a quest somewhere else but I
  closed that terminal" recovery story.
- Operator confusion when phases of two quests interleaved without a
  visible registry.

This is the single biggest throughput lever identified in
`/Users/kjell/ws/extra/difflyx/.ws/quest-speed-analysis.md` §6 R4: it
unlocks parallel quests without changing the quality bar of any
single quest.

## Why a shared file works

`.quest/` is **gitignored** and **shared across worktrees** by Quest's
own convention: `quest_startup_branch.py` (around lines 330-374)
symlinks `<worktree>/.quest -> <main-repo>/.quest`. The symlink
resolution means every worktree sees the same physical directory. A
file at `.quest/active_quests.json` is therefore a natural shared
rendezvous:

- Visible from any worktree without configuration.
- Not under version control, so no merge conflicts ever.
- Per-repo scoped (a quest in one repo cannot see a quest in
  another).
- Already in the convention the install ships — no new directory or
  new layer to teach the operator about.

The shared-inode-via-symlink property is the load-bearing assumption.
If a future project ever switches to per-worktree `.quest/`
directories, the registry either moves to a non-worktree location
(e.g. `~/.cache/quest/<repo-hash>/`) or falls back to per-worktree
files. Today's convention makes the shared file the right choice.

## Schema

```json
{
  "version": 1,
  "active": [
    {
      "quest_id": "vc-view-completeness_2026-05-16__1641",
      "slug": "vc-view-completeness",
      "worktree": "/Users/kjell/ws/extra/difflyx/.worktrees/quest/vc-view-completeness",
      "main_repo": "/Users/kjell/ws/extra/difflyx",
      "branch": "quest/vc-view-completeness",
      "phase": "phase_03_review",
      "phase_started_at": "2026-05-18T10:00:00-06:00",
      "orchestrator_pid": 12345,
      "orchestrator_hostname": "mbp.local",
      "started_at": "2026-05-16T16:41:00-06:00",
      "updated_at": "2026-05-19T15:00:00-06:00"
    }
  ]
}
```

- `quest_id` is the unique key. Re-registration replaces the existing
  row (idempotent).
- `orchestrator_pid` + `orchestrator_hostname` enable a `kill -0 pid`
  liveness probe on the same host. On a different host the entry is
  surfaced as `other-host:<name>` rather than considered alive or
  dead — the operator decides what to do.
- `phase` is updated on phase transitions. `updated_at` always
  advances on every write so a stuck-but-running orchestrator stays
  visible as "fresh."
- `version: 1` lets the schema extend later. A reader that sees an
  unknown version errors loudly rather than silently dropping data.

## Concurrency

Concurrent writers (two orchestrators in two worktrees, or an
orchestrator and a manual `quest active register` call) serialise on
a sibling lock file `.quest/.active_quests.json.lock` via
`fcntl.flock`:

```python
with lock_file.open("w") as lock_f:
    fcntl.flock(lock_f, fcntl.LOCK_EX)
    data = json.loads(registry.read_text()) if registry.exists() else default
    mutator(data)
    atomic_write(registry, data)
```

Atomic write = `tmp.write` + `rename(tmp, real)`. The separate lock
file guards against the rename-window race where two writers could
otherwise interleave reads on the old inode and overwrite each
other after the rename.

Why a separate lock file rather than flock-on-the-registry:
`atomic_write` replaces the inode, so a flock taken on the old inode
becomes invisible to a process that opens the registry after the
rename. A persistent lock file that is never replaced sidesteps the
race entirely. The lock file is created on demand and survives across
calls; it carries no payload.

## Stale-entry policy

A registry entry is considered stale if the orchestrator PID is dead
**and** `updated_at` is older than 30 minutes. The `cleanup`
subcommand removes stale entries. Cleanup should also run
automatically on every `register` call (cheap), so a freshly-spawned
quest sweeps the registry before adding itself.

The 30-minute floor exists because:

- Phase transitions in Quest can legitimately take 5-15 minutes (LLM
  call + dual reviewers + arbiter + human walkthrough).
- A wall-clock-aggressive cleanup risks evicting a live quest that
  happens to be in a long human-gate wait.
- The PID-liveness check is the strict signal; the age window is the
  soft signal. Both must fail for an entry to be evicted.

## Where Quest should hook in

Three integration points in `scripts/quest_startup_branch.py` and
`scripts/quest_state.py`:

1. **Quest creation (`quest_startup_branch.py`).** After the quest
   folder is created and the worktree is set up, call:
   ```bash
   quest-active register \
     --quest-id "$QUEST_ID" \
     --worktree "$WORKTREE_PATH" \
     --branch "$BRANCH" \
     --phase "phase_00_intake" \
     --pid $ORCHESTRATOR_PID  # caller must inject its own PID (e.g. os.getpid() in Python, $$ in a real shell invocation — NOT a subprocess wrapper, which would record the throwaway shell's PID and the liveness probe would immediately read it as dead)
   ```

2. **Phase transitions (`quest_state.py`).** Wherever the orchestrator
   updates `state.json` with a new phase, also call:
   ```bash
   quest-active phase --quest-id "$QUEST_ID" --phase "$NEW_PHASE"
   ```

3. **Quest archive / completion.** When the quest moves to
   `.quest/archive/`, call:
   ```bash
   quest-active unregister --quest-id "$QUEST_ID"
   ```

A startup warning surfaces if another quest's entry exists for the
same repo when a new quest is created. The operator chooses to
proceed in parallel, abort, or rejoin the existing quest. Default
action is "proceed in parallel" with a one-line summary of the other
quest.

## What the operator gets

```
$ quest active list
Active quests (registry v1):
  vc-view-completeness_2026-05-16__1641  [ALIVE]  3.2 min since update
    worktree: /Users/kjell/ws/extra/difflyx/.worktrees/quest/vc-view-completeness
    branch:   quest/vc-view-completeness
    phase:    phase_03_review
  bench-history-collection_2026-05-19__0900  [stale]  78.4 min since update
    worktree: /Users/kjell/ws/extra/difflyx
    branch:   quest/bench-history-collection
    phase:    phase_02_implementation
```

That is the feature. The human sees "I have two quests in flight; the
bench one looks stuck, let me check." No more "I'm pretty sure I left
one open somewhere."

## Risks and mitigations

- **Stale entries after orchestrator crash.** Mitigated by liveness
  probe + 30-min floor. `quest active cleanup` is a manual fallback;
  `register` auto-cleans on its own write path.
- **Cross-host registry rows.** A registry on a network filesystem
  (rare; `.quest/` is usually local) might receive rows from multiple
  hosts. The hostname field flags this so the operator does not act
  on stale liveness data.
- **Schema evolution.** `version: 1` lets the schema extend later
  without silently dropping data. Future fields are added with serde
  / dict defaults so older readers keep working.
- **Empty file on first run.** Both `register` and `cleanup` create
  the file with `{"version": 1, "active": []}` if it does not exist
  — no setup step required.
- **Rename / flock race.** Sidestepped by using a separate lock file
  that is never replaced (see Concurrency above).

## Why this should be the default

- Zero cost when only one quest is in flight (the file stays an empty
  array).
- Mechanically enables parallel quests in worktrees, which the
  archive shows is the single biggest throughput lever.
- Operator visibility into multi-quest state with no extra UI.
- Self-cleaning via liveness probe.
- No new dependencies; pure Python stdlib (fcntl, json, datetime,
  pathlib, socket).
- Adds ~250 LOC to `scripts/` plus three one-line hooks in
  `quest_startup_branch.py` / `quest_state.py`.
- Forward-compatible: a future `quest dashboard` or `quest tui`
  command reads from the same file.

## Implementation plan

1. Copy `difflyx/scripts/quest-active.py` to
   `quest/scripts/quest_active.py` (rename to match the
   `quest_<verb>.py` convention used by the other helpers).
2. Wire the three hook points (creation, phase, archive).
3. Add a startup advisory in `quest_startup_branch.py` that lists
   any other active quests for the same repo and asks
   proceed/abort/rejoin (default proceed).
4. Document under `docs/concurrency.md`.
5. Add a regression test in `tests/` that spawns two registrations
   concurrently and verifies both land in the registry without
   corruption.

## Related notes

- `quest-speed-analysis.md` §6 R4 in the diffly workspace is the
  empirical case for this proposal.
- The reference implementation in `difflyx/scripts/quest-active.py`
  is self-contained and usable today, ahead of canonical adoption.
