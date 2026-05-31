---
title: Pre-PR Freshness Gate + Non-Fast-Forward Force-Push Guard
purpose: Close two linked gaps in the quest closing/PR-handoff phase — a quest can complete and a PR can be opened against a stale base with unvalidated install/build state, and a post-rebase force-push has no explicit, authorized guard. Add a config-driven freshness gate that syncs with the remote default branch and re-runs the repo's own install/validate commands before PR readiness, and a non-fast-forward divergence check that never auto-force-pushes.
audience: Quest maintainers
scope: .skills/quest workflow Step 7 (Complete) and the pr-assistant / pr-shepherd handoff, .ai/allowlist.json config, quest state machine
status: proposed
owner: kjell
---

# Pre-PR Freshness Gate + Force-Push Guard

> **Living draft.** Direction is agreed; concrete wiring is proposed but NOT
> final. Hash out the "Open Questions" before implementation. Do not `/quest`
> this yet.

## Why these two are one feature

These came out of the same real run as the code-review adjudication work
(`archive/2026-05-30-code-review-adjudication.md`, shipped in PR #124) but belong to a **different phase** —
quest closing and PR handoff, not code review. They are bundled here because
they are **causally linked**: the freshness gate's job is to *rebase/merge onto
the remote default branch*, and that rebase is precisely what creates the
non-fast-forward divergence the force-push guard exists to handle. Ship the gate
without the guard and you've built the thing that strands the branch; ship the
guard alone and it rarely triggers. Together they form one clean
"get-this-branch-ready-for-its-PR" step.

Both are kept **codebase-agnostic**: the skill never learns project-specific
commands. The repo *declares* what "validate" means; the gate runs whatever the
repo declares.

## Today's behavior (verified)

- The quest state machine's terminal transition is `reviewing -> complete`
  (`scripts/quest_validate-quest-state.sh:244`; phase list at lines 73–74:
  `plan, plan_reviewed, presenting, presentation_complete, building, reviewing,
  fixing, complete`). There is **no freshness/sync step and no `pr_ready`
  phase.**
- PR creation happens *after* the quest completes, via the `pr-assistant` skill
  in draft mode (`workflow.md:1176`). Nothing between "code review clean" and
  "PR opened" re-checks the branch against its base or re-runs install/build.
- `.ai/allowlist.json` already has a `gates` block with
  `require_approval_before_push: true` (lines 233–239) — so push approval is
  modeled, but **force-push / non-fast-forward divergence is not** distinguished
  from a normal push.
- Neither `pr-assistant` nor `pr-shepherd` has any force-push, `--force-with-lease`,
  or divergence detection (`rev-list` non-ff check) logic — confirmed by grep.

Consequence from the real run: a stale-`node_modules` state (a dependency miss)
surfaced only at push time, *outside* the quest, instead of being caught while
the quest still owned the work. And a clean rebased PR needed
`git push --force-with-lease`, which the harness correctly blocked — but there
was no named, authorized path for it; the human had to improvise.

## Part 1 — Pre-PR freshness gate (config-driven)

Add a freshness gate as a **closing quest step, gated like every other
transition.** "Base" = the **remote default branch, detected, not hardcoded.**

### Steps the gate runs
1. `git fetch origin`
2. Detect the default branch: `git symbolic-ref refs/remotes/origin/HEAD` →
   fall back to `gh repo view --json defaultBranchRef`.
3. Rebase (or merge) the quest branch onto that branch.
4. Run the project's declared **install** command, then its **validate**
   commands.
5. Re-check: clean tree, validate passed.
6. Write a `freshness_check.json` artifact recording base SHA, commands run,
   and pass/fail.

### Codebase-agnostic config — `quest_validation` block in `.ai/allowlist.json`
The commands are **config, not baked into the skill**, mirroring how `models`,
`gates`, and `role_permissions` already live in the allowlist:

```jsonc
"quest_validation": {
  "install_cmd": "npm ci",                       // e.g. "pip install -e ." / "uv sync"
  "validate_cmds": ["npm run lint", "npm run typecheck", "npm test"],
  "heavy_globs": { "apps/macos/**": ["xcodebuild ..."] }  // path-triggered extra checks
}
```

A Python repo declares `pip install -e .` / `pytest`; the skill never knows the
difference. `heavy_globs` lets a repo attach expensive checks (e.g. a native
build) only when matching paths changed.

### Enforcement (fail closed, consistent with existing gates)
Writing a passing `freshness_check.json` becomes a **precondition for the
closing transition** — surfaced through the same validated
`quest_state.py --transition` / `quest_validate-quest-state.sh` mechanism every
other phase already uses. No artifact, no transition. Open question below: gate
the existing `reviewing -> complete`, or introduce a new `complete -> pr_ready`
transition so "done" and "ready to PR" stay distinct.

### Codebase-agnostic by omission
If a repo declares **no** `quest_validation` block, the gate degrades to
fetch + base-detect + sync only (or is skipped with a one-line note) — never
inventing commands it wasn't given. *Fail open on the value, fail closed on the
contract*, the same governing rule the adjudication doc uses.

## Part 2 — Non-fast-forward force-push guard

A clean rebased branch needs `git push --force-with-lease`. The harness blocks
force-push because it rewrites remote history, and a broad "full permissions"
grant should **not** silently authorize that.

### When it triggers
After a rebase (Part 1's step 3), local and remote diverge — a non-fast-forward
push. Detectable deterministically: **both**
`git rev-list --count origin/<branch>..HEAD` **and**
`git rev-list --count HEAD..origin/<branch>` are `> 0`.

### How it's enforced
Add a **"non-fast-forward guard"** to `pr-assistant` / `pr-shepherd`: before any
push, run the divergence check. If non-ff, **stop and present a named choice** —
never auto-force:
1. Authorize `git push --force-with-lease` (explicit, one-time).
2. Open the PR from the already-pushed branch instead (CI tests the merge either
   way).

Document in the skill that **broad permission grants do not imply force-push.**
This is reinforced by an existing project memory
(`feedback_force_push_authorization.md`): *"full permissions does not authorize
force-push; surface it and ask first."*

### Optional convenience (off by default)
A `settings.json` permission rule could allow
`git push --force-with-lease origin <your-branch-glob>` to make it frictionless
for the owner's own branches. Recommendation: **keep the ask.** The guard's value
is that it's a deliberate, visible decision.

## Sequencing
1. **Part 1 first** — the gate is the bigger payback and is independently
   valuable (catches stale-dependency / failing-validate before PR).
2. **Part 2 with or right after it** — the rebase Part 1 performs is what makes
   the guard fire, so they're naturally one PR.

## Non-goals
- Not auto-merging or auto-resolving rebase conflicts — conflicts stop and ask.
- Not baking any project-specific command into the skill; everything runs from
  declared `quest_validation` config.
- Not auto-force-pushing under any grant level.
- Not changing PR creation itself (still `pr-assistant`, still draft mode).
- Not a CI change — this runs inside the quest/local flow, before the PR exists.

## Open questions
- **Q1 — Transition shape.** Gate the existing `reviewing -> complete`, or add a
  distinct `complete -> pr_ready` phase to the state machine
  (`quest_validate-quest-state.sh`)? A separate `pr_ready` keeps "work done" and
  "branch ready to ship" cleanly separable and gives the force-push guard an
  obvious home, at the cost of one more phase to maintain.
- **Q2 — Rebase vs. merge.** Default to rebase (clean linear history, but
  requires the force-push guard) or merge (no force-push, messier history)?
  Make it a `quest_validation.sync_strategy` config with a sensible default.
- **Q3 — Where does the gate run** when the quest used a worktree
  (`branch_mode: worktree`)? It must operate on the source branch/worktree, not
  the `.quest/` artifact root — same split called out in `workflow.md:1009`.
- **Q4 — Auto-approve interaction.** Should a failing freshness check ever
  auto-defer (like `auto_approve_phases`), or always stop for the human? Leaning
  always-stop: a failing build is not debt to silently accept.

## References
- Quest closing flow: `.skills/quest/delegation/workflow.md` Step 7 (~1064–1090);
  PR handoff to pr-assistant at line 1176.
- State machine + transitions: `scripts/quest_validate-quest-state.sh`
  (phases 73–74; `reviewing->complete` at 244) and `scripts/quest_state.py`.
- Existing gate/permission config: `.ai/allowlist.json` `gates` block
  (`require_approval_before_push`, lines 233–239).
- PR skills (no force/divergence logic today): `.skills/pr-assistant/SKILL.md`,
  `.skills/pr-shepherd/SKILL.md`.
- Force-push policy memory: `feedback_force_push_authorization.md`.
- Sibling closing-phase concern (different phase, same retro):
  `ideas/archive/2026-05-30-code-review-adjudication.md`.
