---
title: Research Fan-Out Skill
purpose: Define a reusable research skill that can be invoked directly by users or by Quest planners when planning depends on parallel investigation.
audience:
  - quest-maintainers
  - skill-authors
  - quest-users
status: proposed
date: 2026-04-29
related:
  - .skills/quest/agents/planner.md
  - .skills/quest/delegation/workflow.md
  - docs/quest-journal/thin-orchestrator_2026-02-09.md
  - ideas/2026-04-15-subagent-path-constraints-hardening.md
---

# Summary

Quest planning sometimes depends on research that is naturally parallel:
reviewing external docs, reading local markdown, comparing sibling repos,
mapping dependency surfaces, surveying migration costs, or pressure-testing a
proposal from multiple perspectives.

Today the planner is effectively one research/planning agent. That keeps the
pipeline simple, but it underuses parallelism on research-heavy quests. The
better direction is a reusable research skill: humans can invoke it directly,
and the Quest planner can request it when research lanes are independent enough
to justify fan-out.

# Proposal

Create a standalone `research` or `quest-research` skill that:

1. Accepts a topic, source list, and optional lenses.
2. Dispatches bounded read-only research agents in parallel.
3. Requires each agent to write a concise memo with explicit claims and
   evidence.
4. Runs a reconciler after all memos finish.
5. Writes a recommendation artifact that the user or Quest planner can consume.

The planner should not freely spawn unbounded subagents. It should either:

- invoke the research skill with a bounded set of lenses, or
- ask the orchestrator to run the research skill before final plan synthesis.

This keeps the planner focused on producing a plan while the skill owns
fan-out discipline, artifact paths, reconciliation, and reporting.

# Example Invocation

```text
I want to evaluate [TOPIC]. Spawn 6 parallel research subagents with these
distinct lenses: (1) security/threat-model auditor, (2)
performance/scalability skeptic, (3) developer ergonomics advocate, (4)
competitive landscape analyst, (5) migration-cost estimator, (6)
maintenance-burden forecaster. Each writes a 500-word memo to
.research/<lens>.md with explicit claims and evidence. Then run a 7th
'reconciler' agent that reads all six, identifies points of agreement,
surfaces contradictions as numbered DECISIONS_NEEDED, and produces
RECOMMENDATION.md with a confidence score. Don't ask me anything until the
reconciler has run.
```

# Artifact Layout

Standalone use:

```text
.research/<topic-slug>/
  manifest.json
  security.md
  performance.md
  ergonomics.md
  competitive-landscape.md
  migration-cost.md
  maintenance-burden.md
  RECOMMENDATION.md
```

Quest use:

```text
.quest/<id>/phase_01_plan/research/
  manifest.json
  <lens>.md
  RECOMMENDATION.md
```

# Manifest Contract

```json
{
  "topic": "short topic",
  "mode": "standalone | quest",
  "requested_lenses": ["security", "performance"],
  "agents_spawned": 2,
  "reconciler_ran": true,
  "artifacts": [
    ".quest/<id>/phase_01_plan/research/security.md",
    ".quest/<id>/phase_01_plan/research/performance.md",
    ".quest/<id>/phase_01_plan/research/RECOMMENDATION.md"
  ],
  "decisions_needed": 1,
  "confidence": "low | medium | high"
}
```

# Research Memo Contract

Each lens memo should be short and structured:

```markdown
# <Lens> Memo

## Claims
- [claim with evidence source/path]

## Evidence
- [file path, URL, repo path, command output summary, or explicit observation]

## Risks
- [risk or uncertainty]

## Recommendation
[one paragraph]
```

Default target length: 300-700 words. Long raw notes should be avoided; link to
source files or URLs instead.

# Reconciler Contract

`RECOMMENDATION.md` should include:

- `## Executive Recommendation`
- `## Points of Agreement`
- `## Contradictions`
- `## DECISIONS_NEEDED`
- `## Confidence`
- `## Sources`

Contradictions that require human judgment should be numbered:

```markdown
## DECISIONS_NEEDED
1. [decision] — why it matters, which memos disagree
```

# Planner Integration

The Quest planner may request research fan-out when all are true:

- the quest has meaningful research uncertainty,
- the research lanes are independent,
- the result will materially change the plan,
- the added latency is justified by risk or scope.

The planner should avoid research fan-out for:

- simple bug fixes,
- narrow refactors with obvious local context,
- tasks where one repo search is enough,
- questions that require immediate human clarification instead of research.

When used inside Quest, the final `plan.md` should include:

```markdown
## Research Inputs
- .quest/<id>/phase_01_plan/research/RECOMMENDATION.md
- .quest/<id>/phase_01_plan/research/security.md
- .quest/<id>/phase_01_plan/research/performance.md

Summary: [how the research changed the plan]
```

Step 7 completion should mention:

- number of research agents spawned,
- whether a reconciler ran,
- path to `RECOMMENDATION.md`,
- count of `DECISIONS_NEEDED`.

# Defaults And Limits

- Default lenses: choose 3 based on the topic.
- Common lenses: security, performance, developer ergonomics, migration cost,
  maintenance burden, dependency mapping, competitive landscape, test strategy.
- Default max agents: 3.
- Soft cap: 6 agents when the user or planner provides clear lenses.
- Hard cap: 8 agents unless the user explicitly overrides.
- Research agents are read-only except for their assigned memo path.
- Reconciler is the only writer for `RECOMMENDATION.md`.
- The orchestrator should retain paths and one-line summaries, not full memo
  content, preserving the thin-orchestrator rule.

# Risks

| Risk | Mitigation |
|---|---|
| Research sprawl | Require a bounded lens list and concise memo contract. |
| Duplicated work | Planner/orchestrator assigns non-overlapping lenses. |
| Context bloat | Store memos on disk; pass paths, not full content. |
| Wrong artifact paths | Use fixed output paths and post-run path validation. |
| Weak synthesis | Always run a reconciler; planner consumes `RECOMMENDATION.md`, not six raw memos alone. |
| Slower planning | Use only when research uncertainty materially affects the plan. |

# Implementation Sketch

1. Add `.skills/research/SKILL.md` with the workflow above.
2. Register it in `.skills/SKILLS.md`.
3. Add lightweight wrappers for `.agents/skills/research/SKILL.md` and
   `.claude/skills/research/SKILL.md` if this should be installed across
   runtimes.
4. Update `.quest-manifest` and `.quest-checksums` for installed skill files.
5. Update `.skills/quest/agents/planner.md` to say the planner may request the
   research skill for research-heavy planning, but should not run unbounded
   ad hoc fan-out.
6. Update `.skills/quest/delegation/workflow.md` to report research fan-out
   artifacts in completion summaries when present.
7. Add path-compliance checks for `.quest/<id>/phase_01_plan/research/**`
   before the planner consumes the research output.

# Open Questions

- Should the first implementation be standalone-only before Quest planner
  integration?
- Should web browsing be an explicit per-invocation permission, or simply a
  source type the skill can use when the runtime supports it?
- Should `DECISIONS_NEEDED` block plan creation, or should the planner make
  explicit assumptions and continue?
- Should research outputs be archived into `docs/quest-journal/` or remain only
  in the quest archive?
