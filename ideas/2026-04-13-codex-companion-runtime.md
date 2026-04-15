---
title: Codex Companion Runtime -- Minimum Prove-It Roadmap
purpose: Phased proposal for a shared Codex runtime that serves both the human `/gpt` command surface and Quest orchestration, with explicit proof gates before expansion
audience: Quest maintainers
status: proposed
date: 2026-04-13
related:
  - .ws/codex-plugin-cc-vs-quest-2026-04-13.md
  - .skills/gpt/SKILL.md
  - .skills/quest/SKILL.md
  - scripts/quest_preflight.sh
  - scripts/quest_runtime/claude_runner.py
  - docs/guides/quest_setup.md
---

# Codex Companion Runtime

## Short Version

Quest should not replace its orchestration architecture with the OpenAI Claude plugin model.

Quest should borrow the best runtime ideas:
- app-server-backed Codex sessions
- background jobs
- stored job state
- status/result/cancel
- resumable threads
- better setup diagnostics
- first-class adversarial review

But Quest should do this in the smallest possible way first.

The first goal is not "build a full Codex subsystem."
The first goal is:

> prove that a shared Codex runtime materially improves speed, usability, and Quest integration for one narrow flow used by both humans and Quest.

If that proof fails, stop.
If that proof is weak, keep MCP as the default and do not expand.
If that proof is strong, continue in phases.

## Problem

Today, Quest uses Codex mainly through MCP.

Current state:

- the shipped human-facing interface is the `/gpt` skill
- Quest does not currently route through `/gpt`
- references to `gpt:*` in this note are shorthand for a possible future expansion of the `/gpt` user surface into named operations, not a second live command interface that already exists

That is good at:
- simple transport
- low complexity
- thin integration

It is weaker at:
- background work
- status/result/cancel
- resumable Codex sessions
- setup diagnostics
- operator UX
- repeated Codex work in one session

There is also a practical operator complaint:
- MCP sometimes feels slow

That complaint may be one of three things:

1. Codex model latency
2. MCP transport/runtime overhead
3. lack of background/runtime controls, which makes waiting feel worse

We should not guess which one is dominant.
We should measure it.

## Non-Goals

This proposal does **not** mean:
- replacing Quest routing, gates, or artifact contracts
- removing MCP immediately
- moving all Codex roles to app-server on day one
- making Quest orchestration call user-facing slash commands directly
- building a large runtime before proving value

## Core Design Rule

Build **one shared Codex runtime adapter**.

Two consumers use it:
- human-facing `/gpt` command surface
- Quest orchestration internals

Do **not** make Quest orchestration shell out to the current user-facing `/gpt` skill.
If the `/gpt` surface later expands into named operations, that human UX layer should still remain separate from Quest orchestration.

Correct layering:

```text
human /gpt UX ----------+
                         +--> codex_runtime adapter --> backend
Quest orchestration -----+
```

Backends:
- `mcp`
- `app_server`

This keeps the user UX layer and the workflow layer separate while sharing the same engine.

## Success Criteria For The Whole Idea

This idea is only worth continuing if the minimum slice shows clear gains in at least two of these:

1. Lower time-to-useful-result
2. Better human operator UX
3. Better Quest integration with less glue code
4. Better support for background work and inspection
5. Better reliability or debuggability

If the minimum slice only adds complexity without showing clear gains, stop and keep MCP as the default.

## Phase 0 -- Baseline Before Any Build

### Goal

Measure current MCP behavior before changing anything.

### Work

1. Pick a small benchmark set:
   - 3 small reviews
   - 3 medium reviews
   - 2 long-running task-style prompts

2. For each benchmark, record current MCP behavior:
   - start timestamp
   - finish timestamp
   - wall-clock duration
   - prompt type
   - whether the operator had to wait inline
   - whether the result was easy to inspect later
   - any obvious failure/debug friction

3. Write the benchmark method down in one repo-local note or fixture file so future comparisons are honest.

### Evaluation Criterion

Phase 0 passes only if we have a repeatable baseline.

If we skip baseline measurement, we will not know whether the new runtime is genuinely better or just more exciting.

## Phase 1 -- Minimum Useful Slice

### Goal

Build the smallest real feature that is:
- directly callable by a human
- directly usable by Quest
- measurable

### Scope

Implement only:
- `/gpt setup`
- `/gpt review`
- `/gpt status`
- `/gpt result`

Backed by:
- a minimal `codex_runtime` adapter
- an `app_server` backend
- a small local job store

Quest integration:
- use the same runtime for **one** Codex review role only
- recommended first target: one non-destructive Codex review path

Do **not** add:
- task/rescue
- cancel
- resume
- adversarial review
- builder/fixer integration

### Why This Is The Right Minimum

It gives us:
- one human command path
- one Quest path
- one shared engine
- one real measurement point

It avoids:
- write-path complexity
- cancellation complexity
- multi-role orchestration churn
- broad migration risk

### Proposed Human UX

Commands:
- `/gpt setup`
- `/gpt review [--base <ref>] [--background]`
- `/gpt status [job-id]`
- `/gpt result [job-id]`

These are proposed future operations under the existing `/gpt` surface.
They are not live commands today.

### Proposed Quest Use

Quest should call the shared runtime directly for one Codex review slot:
- likely a code-review role first
- not builder
- not fixer
- not arbiter yet

The Quest layer should receive structured data:
- `job_id`
- `thread_id`
- `status`
- `summary`
- `result payload`
- timestamps

### Required Data To Persist

Minimum persisted fields:
- `job_id`
- `kind`
- `target`
- `backend`
- `status`
- `created_at`
- `started_at`
- `completed_at`
- `thread_id`
- `summary`
- `result_path` or inline stored result
- `stderr` or failure summary

### Evaluation Criterion

Phase 1 is successful only if all of the following are true:

1. A human can run `/gpt review`, then later inspect it with `/gpt status` and `/gpt result`.
2. Quest can use the same runtime for one Codex review slot without special-case shell glue.
3. The app-server path is at least not worse than MCP on reliability for the chosen benchmark.
4. Measured UX is clearly better in at least one of:
   - easier follow-up
   - easier inspection
   - easier debugging
   - better background workflow
5. Latency is:
   - either materially better, or
   - roughly similar but with meaningfully better operator UX

### Stop Condition

Stop after Phase 1 if:
- latency is not meaningfully better
- UX is only marginally better
- Quest integration becomes more complex than the gain justifies
- job-state handling feels brittle

If Phase 1 fails, keep MCP as the main path and do not continue the roadmap.

## Phase 2 -- Add The Strongest Missing Human/Quest Feature

### Goal

Add the next feature only if Phase 1 proved meaningful.

### Scope

Add:
- `gpt:adversarial-review`

And allow Quest to use the same review mode for one review slot.

### Why Phase 2 Next

The adversarial-review pattern is one of the clearest wins from the plugin:
- no write-path complexity
- high review value
- useful to humans and Quest
- good disagreement generator in dual-review flows

### Evaluation Criterion

Phase 2 succeeds if:
- human users prefer it for "challenge this design" tasks
- Quest reviewers produce meaningfully different findings vs standard review
- findings stay grounded and actionable

### Stop Condition

Stop expansion if adversarial review becomes:
- noisy
- repetitive
- mostly stylistic
- not materially different from normal review

## Phase 3 -- Task Path For Humans And Limited Quest Use

### Goal

Add a write-capable or investigation-capable Codex task path.

### Scope

Add:
- `gpt:task` as canonical name
- optional alias: `gpt:rescue`

Support:
- fresh run
- background run
- read-only vs write-capable mode
- stored thread IDs

Quest use:
- start with fallback or fixer-like bounded tasks
- do not move builder broadly yet

### Why This Is A Later Phase

Task paths are more complex than review:
- edits
- broader prompts
- more follow-up
- higher failure surface

We should not build this until the review runtime is already proven valuable.

### Evaluation Criterion

Phase 3 succeeds if:
- humans can launch and inspect task jobs cleanly
- Quest can use the runtime for one bounded non-review Codex role
- stored results and touched-files data are useful
- operational friction is lower than today's generic `/gpt`

### Stop Condition

Stop if:
- write-path complexity grows too fast
- task results are hard to normalize
- Quest role integration becomes messy or fragile

## Phase 4 -- Cancel And Resume

### Goal

Add lifecycle controls once jobs are already proven useful.

### Scope

Add:
- `gpt:cancel`
- resume-last support
- stored thread reuse

Quest use:
- cancellation for aborted or retried background Codex jobs

### Why This Is Not Earlier

Cancel/resume are useful, but not the first proof point.
They are runtime polish features, not the core value test.

### Evaluation Criterion

Phase 4 succeeds if:
- cancel is reliable enough to trust
- resume actually saves time on repeated work
- the extra lifecycle code remains understandable

## Phase 5 -- Backend Policy And Wider Quest Adoption

### Goal

Decide where Quest should use:
- `mcp`
- `app_server`
- fallback between them

### Scope

Only after earlier proof:
- choose default backend policy by role
- possibly keep MCP for some simple roles
- possibly prefer app-server for background or multi-turn Codex work

### Suggested Policy Direction

Likely shape:
- human `/gpt` flows: prefer `app_server`
- Quest review roles: use whichever benchmarked better, likely `app_server` if background/status/result matter
- Quest builder/fixer roles: only switch after explicit proof
- MCP remains as fallback and maybe as default for some simple single-turn paths

### Evaluation Criterion

Phase 5 succeeds if:
- backend selection logic is simple
- operators can explain why one role uses one path
- fallback behavior is explicit and observable

## Recommended Initial Build Order

If we start this work, do it in this order:

1. benchmark baseline
2. implement `codex_runtime` adapter skeleton
3. implement `app_server` backend only
4. implement `/gpt setup`
5. implement `/gpt review`
6. implement `/gpt status`
7. implement `/gpt result`
8. wire one Quest review slot to the same runtime
9. measure and decide go/no-go

Only after that:

10. `gpt:adversarial-review`
11. `gpt:task`
12. `gpt:cancel`
13. resume
14. wider Quest adoption

## What "Meaningful" Must Mean

This proposal only continues if the minimum slice proves one of these in a real way:

### Meaningful for humans

- less waiting anxiety because background work is visible
- easier follow-up because results are stored
- easier debugging because job state exists
- better setup because failures are diagnosable

### Meaningful for Quest

- one shared runtime used by both human commands and Quest
- less bespoke Codex glue in workflow code
- cleaner background/poll/result flow for one review slot
- better observability than plain one-shot MCP

If neither side gets a strong gain, the idea does not deserve expansion.

## Risks

Main risks:
- app-server is not actually faster enough to matter
- runtime state handling adds too much complexity
- Quest ends up with two partially overlapping Codex paths
- background jobs become hard to reason about in failures
- human UX and orchestration needs get mixed together

Mitigations:
- shared adapter, separate consumers
- prove one narrow slice first
- keep MCP available
- stop after Phase 1 if the gains are weak

## Final Recommendation

Do this as a prove-it experiment, not a platform rewrite.

The minimum meaningful slice is:
- `/gpt setup`
- `/gpt review`
- `/gpt status`
- `/gpt result`
- one shared `app_server` runtime
- one Quest review slot using the same engine

That is the right first move because it tests the real thesis:

> can one Codex runtime improve both human Codex usage and Quest orchestration enough to justify the added machinery?

If yes, continue carefully.
If no, stop and keep MCP simple.
