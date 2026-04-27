---
title: Agent Commit Guard For Pre-Commit Review
purpose: Define an opt-in agent-level commit guard that offers pre-commit-review before local commits without installing a raw Git hook.
audience:
  - quest-maintainers
  - skill-authors
  - agent-runtime-authors
status: proposed
date: 2026-04-27
related:
  - .skills/pre-commit-review/SKILL.md
  - .agents/skills/pre-commit-review/SKILL.md
  - .claude/skills/pre-commit-review/SKILL.md
  - .skills/quest/SKILL.md
  - ideas/2026-04-24-quest-hooks-vs-instructions-boundary.md
---

# Summary

`pre-commit-review` is currently a manually invoked skill. That is the right
default: it is interactive, reviews a working-tree diff, presents numbered
findings, and ends with a user decision flow.

The next useful step is not a raw `.git/hooks/pre-commit` integration. Instead,
add an agent-level commit guard in Codex and Claude instruction surfaces:
before an agent creates a local commit for user-requested work, it should offer
or run `pre-commit-review` when meaningful tracked changes are present.

This keeps the behavior portable for repos installed via `quest_installer`
without surprising developers or duplicating Quest's formal code-review phase.

# Proposed Behavior

When an agent is about to create a commit outside Quest's build/review loop:

1. Check whether there are staged or unstaged tracked changes.
2. If there are meaningful tracked changes and the user has not already
   requested a review, offer or run `pre-commit-review`.
3. Present numbered findings using the skill's existing terminal choices:
   - `fix all Must`
   - `fix selected [N...]`
   - `skip`
   - `commit`
4. Never push as part of this guard.
5. Do not silently block commits. The user remains in control.

# Non-Goals

- Do not install a raw Git pre-commit hook.
- Do not invoke an AI model from `.git/hooks/pre-commit`.
- Do not run inside Quest code-reviewer or fixer phases by default.
- Do not write Quest review backlog artifacts from this path.
- Do not make the guard mandatory for human-authored commits.

# Why Agent-Level Beats Git-Hook-Level

`pre-commit-review` is written for an interactive AI agent. A normal Git hook
does not naturally know:

- which agent runtime to invoke,
- how to pass context,
- how to map findings back to the user,
- whether findings should block the commit,
- how to avoid duplicate review inside Quest.

An agent-level guard fits the actual workflow. The agent already has the user
context, can apply the skill text, and can respect the terminal decision flow.

# Installer Portability

Any implementation should live in installed Quest surfaces, not Quest-repo-only
files. Candidate locations:

- `.agents/skills/git-commit-assistant/SKILL.md`
- `.claude/skills/git-commit-assistant/SKILL.md`, if present
- `.skills/BOOTSTRAP.md`
- a shared installed commit-discipline file referenced by Codex and Claude

Every changed installed file must be represented in `.quest-manifest`.

# Quest Pipeline Boundary

Quest already has a formal review/fix loop:

- planner and plan reviewers,
- builder,
- dual code reviewers,
- fixer,
- final review pass.

The commit guard should not run automatically inside that loop. It is meant for
manual or agent-assisted work outside the Quest pipeline, where no PR exists yet
and the user is about to create a local commit.

# Candidate Instruction Text

Add wording similar to:

> Before creating a local commit outside the Quest build/review pipeline, check
> for staged or unstaged tracked changes. If meaningful tracked changes are
> present and the user has not already requested a review, offer or run
> `pre-commit-review`. Do not run this automatically during Quest
> code-reviewer/fixer phases. Never push from this guard.

# Open Questions

- Should the guard offer `pre-commit-review` or run it automatically before a
  commit assistant creates the commit?
- Should the default differ between Codex and Claude?
- Should there be a user preference to always skip the guard in a repo?
- Should `skip` be remembered only for the current commit attempt, or for the
  whole session?
