---
title: Quest Install Posture — In-Repo vs Outside-In
purpose: Describe the two ways to install/run Quest against a project, their trade-offs, and how to choose.
audience: Maintainers, contributors, and anyone setting up Quest in a project
scope: Distribution and install topology only — not the runtime contract
status: active
owner: maintainers
last_updated: 2026-07-11
related:
  - docs/architecture/orchestration-runtime-v1.md
---

# Quest Install Posture — In-Repo vs Outside-In

Quest is a **generic orchestrator**: its value is consistency across
repos. There are two ways to make Quest available to a project, and
they trade off differently. This document describes both honestly so
you can choose, and records where the shipped tooling currently sits.

Whichever mode you pick, **per-project state always lives in the
project** — only the skill's *location* differs.

---

## Mode 1 — In-Repo (vendored)

The Quest skill set and helper scripts are copied **into the project
repo**. The repo then carries its own copy and the orchestrator
discovers the skill through normal host skill discovery
(`.claude/skills/`, `.agents/skills/`, `.opencode/`, `.skills/`,
`scripts/quest_*`).

This is the **tooling-supported, primary path today**. `scripts/quest_installer.sh`,
run from the root of a target repo, installs and updates Quest:

```bash
cd /path/to/your/repo
/path/to/quest_installer.sh            # interactive install/update
/path/to/quest_installer.sh --check    # dry-run preview
/path/to/quest_installer.sh --force    # CI/non-interactive
```

It honours `.quest-manifest` categories (`copy-as-is`,
`user-customized`, `merge-carefully`), self-updates, and can target a
branch. Updating means re-running it.

The manifest is an inventory of files managed by the Quest installer, not an
allowlist for the project's tooling namespaces. Unlisted files under shared
locations such as `.ai/`, `.skills/`, `.agents/`, and `.claude/` remain
host-owned. Their location alone never transfers ownership to Quest.

**Strengths**
- Self-contained: works offline after install; CI can run Quest with no
  external dependency.
- Pinned/version-controlled alongside the project; reproducible.
- Per-repo customization is possible (and can be re-synced via the
  manifest's merge handling).

**Costs**
- N copies across N repos can drift; updates must be re-pulled per repo.
- Quest internals show up in the project's diffs/PRs.

## Mode 2 — Outside-In (referenced)

One canonical Quest install (e.g. `~/ws/extra/quest/`) holds the skill
and scripts. Projects carry **only `.quest/` state**; the orchestrator
reads the skill from the canonical install.

There is **no dedicated installer flag** for this mode today. You set it
up by host-specific means:

- **Claude Code:** run the agent from the canonical Quest checkout, or
  install Quest's skill at the user level (`~/.claude/skills/`) so it is
  discoverable in every repo. The in-repo installer does *not* do this
  for you.
- **Codex:** install Quest as a global Codex skill — still a *copy* into
  `~/.codex/skills/`, not a live reference. The in-repo installer does not
  do this for you.

> Caveat: a user-level/global skill install is still a copy that you
> update in one place — it is "outside-in" relative to each *project*,
> not a single live source the orchestrator reads in place. A true
> read-from-canonical setup means literally running the agent inside the
> canonical checkout.

**Strengths**
- Single place to update; the change reaches every project the next time
  its orchestrator runs.
- Tiny per-project footprint; clean project diffs (no Quest internals
  churning in project PRs).

**Costs**
- No one-command setup; the mechanism is host-specific.
- Harder for offline/air-gapped projects and for forks that need
  customization the canonical install shouldn't carry.

Outside-in operation does not make the target repository part of Quest's
source distribution. Generic commit and review work runs against the target's
own code and conventions; it does not apply canonical Quest source-completeness
checks to target files.

## Manifest validation by topology

`scripts/quest_validate-manifest.sh` defaults to installed/consumer mode. It
validates the inventory already declared in `.quest-manifest`, including stale
or forbidden entries, while leaving unlisted host files alone. `--installed`
selects the same behavior explicitly.

`--strict` is for maintainers validating the canonical Quest source checkout
and for Quest's own CI. It scans the source distribution patterns for omitted
Quest-owned files. Do not run strict distribution validation as a generic
commit or review gate in a vendored consumer repo or against an outside-in
target, and do not add host-owned files to `.quest-manifest` to satisfy it.

---

## Choosing a mode

**Pick in-repo when:**
- The repo must be self-contained (CI, air-gapped, regulated/forked
  setups with extra phases that don't belong upstream).
- You want Quest pinned and version-controlled with the project.
- It's a one-off project and propagation across repos is a non-issue.

**Pick outside-in when:**
- You maintain several repos with Quest and want updates to land in one
  place.
- You want project diffs to stay free of Quest internals.
- You're comfortable wiring up host-specific skill discovery instead of a
  one-command installer.

A fork that customizes Quest (e.g. mandatory extra review phases for a
regulated codebase) is an in-repo case by nature — mark the deviations
so re-syncing with canonical stays feasible.

## State always lives in the project

Regardless of mode, the project owns its state:

- **`.quest/`** — quest folders, `archive/`, `audit.log`, and the
  cross-worktree registry. A symlink `<worktree>/.quest →
  <main-repo>/.quest` (created by `scripts/quest_startup_branch.py`)
  lets every worktree of the same project share one state directory.
  This symlink shares **state**, not the **skill** — it is independent
  of which install mode you use.
- **Project-local scripts** that bridge Quest to project conventions.
- **Project-specific quest briefs** kept in scratch.

## Referring to Quest from a project

- In project READMEs/docs: link to the canonical install path or the
  public Quest repository.
- In CI: in-repo installs invoke the vendored `scripts/quest_*` directly;
  outside-in installs invoke the canonical install's scripts. Do not
  hand-vendor stray copies of individual `quest_*.py` files outside the
  installer's manifest.

---

*Origin: the outside-in posture was first articulated in a 2026-05-20
conversation about whether to install Quest into a project (diffly) or
operate it from a canonical install. This document was later broadened
to present both modes after noting the shipped installer makes in-repo a
first-class path, not a rare exception.*
