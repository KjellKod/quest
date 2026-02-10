# Quest Journal: quest-council-mode

**Quest ID:** quest-council-mode_2026-02-05__1636
**Date:** 2026-02-05
**Status:** Abandoned (plan approved, never built)

## Summary

Planned a dual-planning-track feature for `/quest` where users could choose between "Quest" (fast, single plan) and "Quest Council" (rigorous, two competing plans merged by arbiter). Plan was approved after 2 iterations but was never built.

## What was planned

- Planning track prompt at quest start: Quest vs Quest Council
- Council flow: generate `plan_a.md` and `plan_b.md`, review both, arbiter merges best parts into final `plan.md`
- `planning_track` field in state.json for resume support
- `planning.mode` and `planning.ask` fields in allowlist.json

## Why abandoned

The idea was captured in `ideas/quest-council_v1.md` and `ideas/quest-council_v1_alternative.md` for future consideration. The thin-orchestrator work (Phase 2) was prioritized instead. Council mode may return as a future phase.

## This is where it all began... an idea

> Complex work (migrations, refactors) benefits from exploring multiple approaches early. Quest Council generates two competing plan candidates, compares them, and merges into one best final plan before execution.
