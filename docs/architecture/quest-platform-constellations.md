---
title: Quest Platform Constellations
purpose: Define the next-level platform vision where Quest is one first-class orchestration approach among several.
audience: Maintainers, contributors, AI agents
scope: Product architecture, operating model, and rollout direction
status: active
owner: maintainers
last_updated: 2026-03-04
related:
  - docs/architecture/orchestration-runtime-v1.md
  - docs/guides/opencode-model-observations.md
  - ideas/quest-architecture-evolution.md
---

# Quest Platform Constellations

## One-Line Pitch

Quest evolves from a single workflow into a portable orchestration
platform: one reliability-first runtime, many named approaches.

`quest` is no longer the whole product. It is the flagship approach.

## Why This Exists

Current pain is reliability and visibility:
- hanging or dead tool/model calls,
- missing question propagation,
- weak run-time observability,
- orchestration behavior living in instructions only.

The platform must move reliability-critical behavior into code while
preserving Quest's portability and opinionated governance.

## North Star

People should be able to:
- create and name their own orchestration approaches,
- combine and remix approaches safely,
- run from CLI or host integrations (Claude/Codex/OpenCode/Cursor),
- optionally compose visually (drag/drop),
- get deterministic run visibility and failure behavior.

## Core Principles

1. Governance is the differentiator.
2. Reliability before flexibility.
3. One runtime, multiple shells.
4. CLI is canonical; visual composer is a projection.
5. KISS/YAGNI by default: minimal primitives, explicit non-goals.

## Platform Shape

```text
                   +----------------------+
                   |   Visual Composer    |
                   |   (optional UI)      |
                   +----------+-----------+
                              |
                              v
 +----------------+   +----------------------+   +----------------------+
 | Quest CLI      |-->| Quest Runtime Core   |<--| Host Adapters        |
 | (canonical)    |   | (contracts + state)  |   | Claude/Codex/Open... |
 +----------------+   +----------------------+   +----------------------+
                              |
                              v
                   +----------------------+
                   | Approach Registry    |
                   | named approach specs |
                   +----------------------+
```

## Approaches and Constellations

### Approach

A named orchestration pattern with explicit behavior.

Examples:
- `quest` - full governance workflow (plan/review/arbiter/gates/build).
- `solo-adventurer` - single builder with one reviewer and one gate.
- `legion` - bounded parallel execution with arbiter merge.

### Constellation

A user-selected set of approaches and policies for a repo/team.

Examples:
- `default`: `quest` + `solo-adventurer`.
- `high-throughput`: `quest` + `legion` (strict concurrency caps).
- `hardened`: `quest` only, strongest gates.

## Authoring Model

Users define approaches as files, not hidden runtime state.

Suggested location:
- `.quest/approaches/<name>.yaml`
- `.quest/constellations/<name>.yaml`

The visual composer edits those same files. No separate source of truth.

## UX Surfaces

### CLI First (required)

Core commands (target shape):
- `quest approach list`
- `quest approach validate <name>`
- `quest approach run <name> --task "..."`
- `quest constellation use <name>`

### Visual Composer (optional)

Drag/drop is allowed only as an editor for approach specs.

Minimal visual primitives:
- `task`
- `review`
- `gate`
- `parallel`
- `reduce`

Anything more complex must prove value first.

## Reliability Contract (must-have)

Every run must expose:
- explicit lifecycle states,
- heartbeat every 10-15s while active,
- tool/model call start/end/failure events,
- question-raised events routed to orchestrator,
- deterministic retry/fallback behavior,
- append-only run ledger for replay and debugging.

See `orchestration-runtime-v1.md` for the normative contract.

## Transport Strategy

Default:
- direct adapters for core model calls (best observability/control).

Optional:
- MCP adapters behind strict timeout/retry/circuit-breaker policy.

Policy:
- no adapter can bypass runtime contracts.
- all adapters must produce the same structured events and results.

## Non-Goals (current phase)

- no "infinite recursive swarm" orchestration.
- no general workflow DSL engine.
- no distributed scheduler/control plane.
- no UI-only orchestration path.

If we need those, we add them after measurable pressure.

## Rollout Plan

### Phase 1: Reliability Foundation
- runtime event model and ledger,
- heartbeat/watchdog,
- question propagation contract,
- adapter contract.

Kill criteria:
- runtime overhead >15% median,
- quality regressions >10%,
- operational toil >2h/week.

### Phase 2: Approach Registry
- implement `quest` as an explicit approach spec,
- add `solo-adventurer`,
- add validation and dry-run tooling.

Kill criteria:
- approach specs harder to maintain than current flow,
- frequent spec/runtime drift.

### Phase 3: Constellations + Composer
- named constellation selection,
- basic visual editor for existing spec schema.

Kill criteria:
- composer diverges from file schema,
- users cannot debug approach behavior from files alone.

## Decision

Build a platform where Quest is first among peers, not the only shape.

Do it with a strict runtime core and file-based approach contracts.
Keep CLI canonical. Add drag/drop as a convenience layer, never as a
second orchestration engine.

