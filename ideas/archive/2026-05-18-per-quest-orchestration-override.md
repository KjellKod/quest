---
title: Per-Quest Orchestration Override
purpose: Historical record for the shipped per-quest model assignment contract.
audience:
  - quest-users
  - quest-maintainers
scope: Quest startup and per-quest model dispatch.
status: done
date: 2026-05-18
completed: 2026-07-11
related:
  - ../../.skills/quest/SKILL.md
  - ../../.skills/quest/delegation/workflow.md
  - ../../.ai/allowlist.json
---

# Per-Quest Orchestration Override

## Outcome

The core proposal shipped in PR
[#119](https://github.com/KjellKod/quest/pull/119): each Quest persists an
authoritative `.quest/<id>/orchestration.json`, startup presents the role model
matrix, optional overrides remain quest-local, and dispatch reads the persisted
per-quest assignments rather than mutable repository defaults.

PR [#142](https://github.com/KjellKod/quest/pull/142) hardened transport and
concrete model pass-through. PR
[#144](https://github.com/KjellKod/quest/pull/144) added deterministic JSON
override parsing and established the current explicit role defaults.

## Shipped Contract

- Repository `models.*` values provide startup defaults only.
- `.quest/<id>/orchestration.json` is authoritative after Quest creation.
- The user may accept the complete matrix or submit quest-local overrides.
- Resume preserves the original orchestration selection.
- Active role assignments are validated against runtime availability.
- Concrete Claude model IDs pass through; the exact `claude` sentinel uses the
  account default without being forwarded as a model ID.

## Historical Motivation

Before PR #119, trying a different model mix for one Quest required editing
shared `.ai/allowlist.json` state and later reverting it. That created needless
working-tree noise and risked shipping an experiment as the team default. The
per-quest artifact confines the decision to the run and records it for later
review.

## Optional Concepts Not Carried Forward

The original proposal mentioned presets and per-user last-choice memory as a
possible second phase. Those concepts were not part of the shipped acceptance
surface and are not active backlog work. If maintainers want either behavior,
it requires a new evidence-backed proposal and normal Quest approval gates.

## Validation Evidence

Current orchestration unit and shell tests cover default selection, overrides,
JSON parsing, unavailable models, resume behavior, dispatch source-of-truth,
transport resolution, and concrete model pass-through. The canonical behavior
is documented in the files linked in the frontmatter.
