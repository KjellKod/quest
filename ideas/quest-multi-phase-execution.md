# Quest Multi-Phase Execution

Status: proposed

Related program roadmap:
[Quest Diamond efficiency](../docs/implementation/backlog/quest-diamond-efficiency-roadmap.md). Diamond follows
this topology: the umbrella roadmap remains a planning artifact, while each
executable WP starts from current `main` and receives its own bounded Quest and
independently reviewable PR. Benchmark comparison uses pinned commits rather
than a persistent integration branch.

## Question

How should Quest handle work that has multiple real phases, where later phases depend on artifacts produced and validated in earlier phases?

Examples:
- research -> verification -> synthesis
- phase 0 foundation -> phase 1 implementation -> phase 2 polish
- migration tranche A -> tranche B -> tranche C

## Position

Do not stretch one quest across a long multi-phase program by default.

Preferred pattern:
- use **one umbrella quest** to produce or refine the big plan, phase map, and acceptance criteria
- then run **one quest per executable phase** when the phase has its own implementation/review/fix loop

In short:
- **one quest for planning the program**
- **one quest per buildable phase**

## Why

Quest is strongest when a quest has:
- one clear brief
- one bounded implementation target
- one review/fix loop
- one completion point

Long-running umbrella quests become awkward because:
- state gets muddy when multiple phases are partially complete
- model/runtime changes midstream make resume behavior messy
- review findings from one phase bleed into later phases
- approval gates lose clarity
- token/session continuity gets harder even with good handoff files

Fresh quests per phase keep:
- scope honest
- approval points clear
- review artifacts phase-local
- failures easier to isolate
- model/allowlist changes easier to apply intentionally

## Recommended Operating Model

### 1. Program Quest

Run a full quest to produce:
- master brief
- phase map
- sequencing
- dependencies
- exit criteria per phase
- risk register
- open questions

Artifacts should make later phase quests easy to start.

### 2. Phase Quests

For each implementation-ready phase:
- start a new quest using the approved phase artifact as primary input
- carry forward only the necessary context and evidence
- treat the phase quest as a normal bounded Quest with its own plan/review/build/fix lifecycle

### 3. Shared Dossier

Keep a shared dossier outside `.quest/` for cross-phase continuity.

Examples:
- `.ws/<initiative>/`
- `docs/implementation/<initiative>/`

Use it for:
- canonical brief
- claim inventory
- verification tables
- cross-phase handoff file
- cumulative roadmap

Use `.quest/<id>/` only for the ephemeral run state of a specific quest.

## Exception: When One Quest Can Span Multiple Passes

A single quest can legitimately include multiple passes when those passes are part of one bounded deliverable rather than separate implementation phases.

Good examples:
- Pass A: reading and claim capture
- Pass Bn: vendor/repo pattern extraction and verification
- Pass Cn: synthesis from the verified pattern set

This works when:
- all passes serve one primary output
- the build phase is still fundamentally one dossier-producing effort
- review/fix loops are about improving the same artifact set, not shipping separate increments

Example:
- one quest can own the research/verification/synthesis passes because they all produce one coherent dossier package
- but actual product implementation phases derived from that dossier should become separate quests later

## Decision Rule

Use a new quest when any of these become true:
- the next phase has a different acceptance surface
- it needs a different model mix or allowlist
- it needs a fresh approval gate
- it produces a separately shippable increment
- its review/fix loop should be judged independently

Keep the same quest only when:
- the passes are all in service of one bounded deliverable set
- the brief remains stable
- the same quest-level success criteria still apply

## Practical Recommendation

For big initiatives:
1. Run one quest to create the executable program plan.
2. If the current work is still one bounded dossier/output package, keep it in one quest with explicit passes.
3. When a pass turns into its own shippable or independently reviewable phase, split to a new quest.

## Summary

Quest should treat **multi-phase program planning** and **phase execution** as different things.

- Program-level planning can happen in one quest.
- Real implementation phases should usually become separate quests.
- Research/verification/synthesis passes can stay in one quest when they all feed the same bounded output package.
