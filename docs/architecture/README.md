---
title: Architecture Index
purpose: Source-of-truth index for Quest platform architecture and runtime contracts.
audience: Maintainers, contributors, AI agents
scope: High-level platform direction and concrete runtime specifications
status: active
owner: maintainers
last_updated: 2026-03-04
related:
  - docs/architecture/quest-platform-constellations.md
  - docs/architecture/orchestration-runtime-v1.md
  - docs/architecture/quest-install-posture.md
---

# Architecture

This directory is the canonical source for "what the platform is" and
"how it must behave."

If a document here conflicts with notes in `ideas/` or `.ws/`, this
directory wins.

## Documents

| File | Purpose |
|---|---|
| `quest-platform-constellations.md` | Product and system direction beyond single `/quest` workflow. Defines named approaches, host portability, and visual composition direction. |
| `orchestration-runtime-v1.md` | Concrete runtime contract: execution model, events, heartbeat, failure policy, and adapter interface. |
| `quest-install-posture.md` | The two install modes (in-repo vs outside-in), their trade-offs, and how to choose. Distribution topology, not runtime contract. |

## Scope Boundary

- `docs/architecture/` defines system design and runtime contracts.
- `docs/guides/` explains how to use it.
- `ideas/` holds proposals and drafts until stabilized.
- `.ws/` remains scratchpad/workbench only.

## Update Rule

Update architecture docs when any of these change:
- control-plane semantics (state machine, retries, fallbacks, gates),
- orchestration model (single approach vs multi-approach/constellations),
- runtime contracts (events, heartbeat, adapter IO),
- authoring model (CLI-first, visual composer behavior).
