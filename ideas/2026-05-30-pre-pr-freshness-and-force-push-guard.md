---
title: Pre-PR sync with the default branch (in pr-assistant)
purpose: Before pr-assistant opens a PR, bring the branch up to date with the remote default branch so we never open a PR that is already stale against main. Sync runs automatically; the only thing surfaced to a human is a merge/rebase conflict.
audience: Quest maintainers
scope: .skills/pr-assistant (standalone skill) and its reuse by .skills/pr-shepherd and the quest PR handoff
status: proposed
owner: kjell
---

# Pre-PR sync with the default branch

> Direction agreed; concrete wiring proposed. Implement in its own PR.

## The problem (kept simple)

We can open a PR whose branch is already **behind the remote default branch**.
No sane human would deliberately push a PR that is stale against `main` — they'd
sync first. The tool should do the same thing, automatically, as part of opening
the PR. The stale-base case showed up in a real run (a dependency/state miss that
only surfaced after the PR was open).

That's the whole feature: **sync the branch with the default branch as part of PR
creation. If the sync is clean, carry on. If it conflicts, stop and ask the
human.** Nothing more.

## Where it lives

This is a behavior of **`pr-assistant`**, the standalone PR-creation skill — *not*
a quest concept. `pr-assistant` runs on its own (any branch, any repo, quest or
not), and quest simply calls it at PR-handoff time. So the sync must live where
PR creation lives, and every PR benefits — not just quest-closed ones.

- **`pr-assistant`**: sync before creating the PR.
- **`pr-shepherd`**: reuse the same helper before it pushes review-fix commits
  (same staleness risk on a long-lived PR).
- A single shared helper script (`scripts/`) so both call one implementation.

This is the same conclusion two independent reviews reached: it is PR-lifecycle
behavior, so it does **not** belong in the quest state machine and needs **no**
new quest phase.

## How it works

As the first step of PR creation (before push / before `gh pr create`):

1. `git fetch origin`.
2. Detect the default branch: `git symbolic-ref refs/remotes/origin/HEAD`,
   falling back to `gh repo view --json defaultBranchRef` (do not hard-depend on
   `gh` being present/authed — the symbolic-ref path is primary).
3. If the branch is already up to date with the default branch → do nothing,
   continue.
4. Otherwise sync the branch onto it (rebase by default; see Open Questions).
   - **Clean sync** → continue to push + open the PR. No prompts.
   - **Conflict** → stop and surface the conflicting files to the human. This is
     the *only* human-interaction point.

### No permissions to grant — it just works

The sync uses ordinary git operations on the author's own not-yet-merged PR
branch. It should run without any permission prompt or pre-granted allowlist
entry. A rebased-then-already-pushed branch is updated with
`git push --force-with-lease` — `--lease` makes this safe (it refuses to clobber
work that appeared on the remote since the last fetch), and it is the author's
own PR branch, so it is not the "rewrite shared history" case the general
force-push caution is about. The only thing that ever interrupts the flow is a
conflict.

> Reconcile with `feedback_force_push_authorization.md` ("full permissions does
> not authorize force-push; surface and ask"): that rule guards *arbitrary*
> force-pushes. Syncing your own open-PR branch onto the default branch with
> `--force-with-lease` is a narrow, lease-protected, expected case. The doc/skill
> should state this exception explicitly rather than prompt every time.

## Deliberately NOT in scope

- **No new quest state-machine phase / `pr_ready` transition.** PR readiness is a
  pr-assistant concern; quest calls the skill, it does not model this itself.
- **No permission grants or allowlist gymnastics as a precondition.** It just
  works; only conflicts stop it.
- **No re-running the project's test/build suite locally.** CI already validates
  the PR; re-running it here would just duplicate CI and add latency. The feature
  is about *not being stale*, not about re-validating. (If a repo ever wants a
  fast local pre-check, that's a separate, optional, opt-in idea — likely YAGNI.)
- **No auto-resolving conflicts.** Conflicts always stop and ask.
- **Not a CI change.** This runs locally, before the PR exists.

## Open questions

- **Rebase vs merge default.** Rebase keeps history linear (needs the
  `--force-with-lease` update described above); merge avoids the force-push but
  adds a merge commit. Lean rebase; make it overridable if a repo prefers merge.
- **Worktree mode.** When the branch lives in a separate worktree
  (`branch_mode: worktree`), the sync must operate on that worktree, not the
  `.quest/` artifact root — the same source-vs-artifact split `workflow.md` already
  handles for build/fix.

## References
- PR creation: `.skills/pr-assistant/SKILL.md` (pushes first if the remote branch
  is behind — the natural home for the sync).
- PR shepherding: `.skills/pr-shepherd/SKILL.md` (pushes review-fix commits).
- Force-push policy memory: `feedback_force_push_authorization.md`.
- Sibling closing-phase concern (different phase, same retro):
  `ideas/archive/2026-05-30-code-review-adjudication.md`.
