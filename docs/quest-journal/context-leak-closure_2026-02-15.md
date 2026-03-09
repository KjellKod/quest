# Quest Journal: Close Remaining Context Leaks (Phase 2b)

**Quest ID:** `context-leak-closure_2026-02-14__2317`
**Date:** 2026-02-15
**Branch:** `evolution_3`
**Plan iterations:** 3
**Fix iterations:** 2

## Summary

Implemented the handoff.json structured file pattern to close the remaining context leaks in the Quest orchestrator. Every agent now writes a tiny JSON file (~200 bytes) alongside its artifacts, and the orchestrator reads this file for routing decisions instead of processing full agent responses.

## What Changed

| File | Change |
|------|--------|
| `.ai/roles/planner_agent.md` | Added `## Handoff File` section |
| `.ai/roles/plan_review_agent.md` | Added `## Handoff File` section with slot-specific paths |
| `.ai/roles/code_review_agent.md` | Added `## Handoff File` section with slot-specific paths |
| `.ai/roles/builder_agent.md` | Added `## Handoff File` section |
| `.ai/roles/fixer_agent.md` | Added `## Handoff File` section |
| `.ai/roles/arbiter_agent.md` | Added `## Handoff File` section |
| `.skills/quest/delegation/workflow.md` | Handoff File Polling, Context Retention Rule update, background agent discard, context health logging, health report at completion, /clear suggestion, stale cleanup |
| `ideas/README.md` | Marked quest-context-optimization and quest-architecture-evolution as in-progress |

## Key Design Decisions

1. **KISS over infrastructure:** Instructed orchestrator to discard response bodies rather than wrapping every call in background Task agents. Simpler but relies on LLM compliance.
2. **Measure, don't assume:** Added `context_health.log` and a completion report that shows handoff.json compliance rate split by Claude vs Codex agents. Transparent about the tradeoff.
3. **Backward compatible:** handoff.json is additive — text `---HANDOFF---` blocks remain as fallback for agents that don't write the JSON file.
4. **Escalation path:** If compliance is low, upgrade to `run_in_background: true` for Claude Task agents.

## This is where it all began...

> From `ideas/quest-context-optimization.md`:
>
> The Quest orchestrator accumulates ~50-80k tokens of agent output per quest despite the thin-orchestrator design. Three remaining leaks: TaskOutput transcripts, MCP Codex responses, and review file reads. The handoff.json pattern closes these leaks by having agents write a tiny status file that the orchestrator polls instead of reading full responses.

> From `ideas/quest-architecture-evolution.md` (Phase 2b):
>
> Close remaining context leaks. The handoff.json pattern: every agent writes a tiny handoff.json alongside artifacts. Orchestrator polls for this file instead of calling TaskOutput. All agents run in background, orchestrator never sees their output. Target: orchestrator context stays under ~30k tokens for entire quest lifecycle.
