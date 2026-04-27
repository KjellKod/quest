---
title: Agent Skill Development Guardrails
purpose: Define the minimum quality bar for new agent skills that read repo context, write local artifacts, or influence tool behavior.
audience:
  - quest-maintainers
  - skill-authors
scope: Agent skills, hook adapters, generated memory, local indexes, and validation helpers maintained in this repo.
status: proposed
date: 2026-04-27
related:
  - 2026-04-13-quest-memory-architecture.md
  - 2026-04-22-review-ergonomics-and-team-preference-memory.md
  - 2026-04-24-quest-hooks-vs-instructions-boundary.md
---

# Summary

New agent skills should be small, auditable, and easy to remove.

The default shape is:

1. one clear skill purpose,
2. explicit local commands,
3. generated artifacts that can be inspected in a text editor,
4. tests for any code that mutates state,
5. measured outcomes before broadening scope.

# Development Rules

Before adding a skill or hook-backed helper:

- Define the user-visible workflow it improves.
- Keep generated state in a predictable repo-local path.
- Pin any runtime assumptions to a documented version or capability.
- Treat prompt templates as executable behavior and review them like code.
- Separate warnings from enforcement in logs and docs.
- Add tests for generated memory, hook state, or repo-artifact mutation.
- Prefer one-shot commands until repeated manual use proves automation is worth it.
- Keep the first version narrow enough to delete without disrupting unrelated workflows.

# Measurement Rules

Do not claim token, time, or review-quality improvements without a reproducible check.

Minimum evidence:

- benchmark tasks or sample workflows are checked in,
- baseline and changed behavior are both recorded,
- warning counts are measured separately from behavior changes,
- estimator formulas are documented,
- the result reports a range and caveats, not just a headline percentage.

For the current memory and context proposals, useful first metrics are modest:

- fewer irrelevant file reads,
- fewer repeated reads of unchanged files,
- fewer repeated user corrections,
- fewer repeated low-value review findings.

# Good First Patterns

These fit the current Quest architecture:

- per-quest file anatomy index for agent orientation,
- confidence-scored team-preference memory,
- deterministic hook adapters over shared policy scripts,
- explicit scan and validation commands.

These should remain outside the first version unless a concrete workflow proves the need:

- broad heuristic bug detectors that create noisy findings,
- runtime-specific behavior without validator backstops,
- generated reflections that are not tied to a user action or review artifact,
- expanded UI or reporting surfaces before the artifact files prove useful.

# Acceptance Criteria

This idea is useful when future skill proposals answer these questions before implementation:

1. What exact workflow gets better?
2. What local files or state does the skill read or write?
3. What runtime capability does it rely on?
4. What test proves artifact mutation is correct?
5. What benchmark or sample workflow proves the claimed benefit?
6. What is intentionally out of scope for the first version?

If those answers are missing, the proposal is not ready to build.
