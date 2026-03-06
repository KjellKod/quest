---
title: Quest Complexity Routing — Not Everything Needs a Quest
purpose: Add complexity-aware routing so the orchestrator can recommend simpler workflows for simple tasks
audience: Quest orchestrator, router, workflow
status: draft
---

# Quest Complexity Routing — Not Everything Needs a Quest

## The Problem

Today the quest router produces `{route, confidence, risk_level}` and sends tasks to either `questioner` (need more info) or `workflow` (full quest pipeline). There's no middle ground. A 142-line markdown idea doc gets the same plan → dual plan review → arbiter → build → dual code review → fix treatment as a cross-cutting security refactor.

This wastes time, wastes tokens, and produces artificial iteration counts that pollute quality metrics. Worse, it trains users to avoid the quest system for small tasks — exactly the tasks where lightweight orchestration would be most useful.

## The Proposal: Expand the Router's Vocabulary

The router already assesses `risk_level` and `confidence`. Add a `complexity` dimension and a richer set of route options:

```json
{
  "route": "workflow | solo | manual",
  "confidence": 0.85,
  "risk_level": "low | medium | high",
  "complexity": "trivial | moderate | substantial",
  "reason": "...",
  "missing_information": []
}
```

### Route Definitions

| Route | When | Pipeline | Agents |
|-------|------|----------|--------|
| `questioner` | Need more info before routing | Questions → re-route | Questioner only |
| `workflow` | High risk OR substantial complexity | Full pipeline | Plan → dual review → arbiter → build → dual code review → fix |
| `solo` | Medium risk, moderate scope | Lightweight pipeline | Plan → single review → build → single review |
| `manual` | Low risk, trivial scope | No pipeline | "This is a one-person job. Just do it." |

### Routing Logic

```
IF missing_information is non-empty AND confidence < 0.6:
  → questioner

IF risk_level == "high" OR complexity == "substantial":
  → workflow (full quest)

IF risk_level == "medium" AND complexity == "moderate":
  → solo (lightweight quest)

IF risk_level == "low" AND complexity == "trivial":
  → manual (just do it)
```

### Complexity Signals

The router can assess complexity from the user's request:

- **Trivial:** Single file, documentation, config change, idea doc, small bug fix, adding a test
- **Moderate:** Multi-file change within one module, new function/endpoint, focused refactor
- **Substantial:** Cross-cutting changes, new module, architecture change, security-sensitive, multi-system integration

### The Human Always Decides

**Critical: The router advises, the human chooses.** The orchestrator presents the recommendation but the human can override:

```
🔍 Quest Assessment:
  Risk: low
  Complexity: trivial
  Recommended route: manual

  💡 "This looks like a one-person job — single plan, single coder, no
     dual review needed. Want to just do it?"

  Options:
  1. ✅ Go manual (recommended)
  2. 🔄 Run as solo quest (single review pass)
  3. 🏗️ Run as full quest (dual reviews, arbiter, the works)
  4. ❌ Cancel
```

This matters for several reasons:
- **Smoke testing:** User might want to run a trivial task through the full pipeline to test the system
- **Training data:** Running a known-simple task through full quest generates reference data for quality baselines
- **Paranoia is valid:** "I know this looks simple but last time it broke prod, give me the full review"
- **User agency:** The system should never decide for the human what level of rigor their work deserves

### What Changes Per Route

| Aspect | `workflow` | `solo` | `manual` |
|--------|-----------|--------|----------|
| Plan review | Dual (A + B) | Single | None |
| Arbiter | Yes | No | No |
| Code review | Dual (A + B) | Single | None (or optional) |
| Fix iterations | Up to max_fix_iterations | Up to 2 | N/A |
| Journal entry | Full celebration_data | Simplified celebration_data | Minimal or none |
| Quality tier | Full scale (Diamond→Cardboard) | Capped at Gold (no dual review = can't claim Diamond) | N/A |

### Quality Tier Implications

A `solo` quest has less review rigor, so its quality tier ceiling is lower:
- `solo` quest tier caps at **Gold** — can't claim Diamond/Platinum without dual review scrutiny
- `manual` tasks don't get quality tiers — they're not quests
- The celebration data should record `quest_mode: "workflow" | "solo" | "manual"` so the tier is interpreted in context

This is honest: a Diamond means "survived dual review with zero issues." If you only had one reviewer, the best you can claim is Gold — which is still great.

### The `solo` Pipeline

Lighter weight but still structured:

```
1. Plan (single planner, no dual review, no arbiter)
2. Human approval (mandatory, same as workflow)
3. Build
4. Single code review
5. Fix (if needed, max 2 iterations)
6. Journal + celebrate
```

One reviewer, one fix pass, still journaled, still celebrated. Just less ceremony.

### The `manual` Path

No pipeline at all. The agent just does the work:

```
1. Agent does the task directly
2. Optional: human asks for a commit
3. Optional: journal entry (minimal — just task name, date, outcome)
```

This is what we did for the celebration idea doc in this session. No plan review needed. No arbiter. Just write the thing and discuss.

## Relation to Other Ideas

- **celebration-from-journal.md** — Quality tier scoring needs to account for `quest_mode`. A `solo` Gold is different context than a `workflow` Gold. The celebration_data JSON should include `quest_mode`.
- **Fast review mode** — Keep it. It controls review *depth* within a route. A `workflow` quest can still use `fast` review for small diffs. A `solo` quest always uses its single review. Orthogonal concerns.

## Implementation Scope (Future)

This is NOT part of the celebration-from-journal PR. It's a separate, larger change:

1. **`.skills/quest/delegation/router.md`** — Add `complexity` dimension and `solo`/`manual` routes
2. **`.skills/quest/SKILL.md`** — Present route recommendation with human override options
3. **`.skills/quest/delegation/workflow.md`** — Define `solo` pipeline (subset of `workflow`)
4. **`scripts/quest_celebrate/quest_data.py`** — Add `quest_mode` to QuestData, adjust tier ceiling per mode
5. **`.ai/allowlist.json`** — Add `solo` pipeline config (max iterations, review count)
6. **Tests** — Router complexity assessment, solo pipeline flow, tier capping

**Effort: Quest-sized.** This changes the router, adds a new pipeline mode, and touches the scoring system. Worth doing through the full quest pipeline — dogfooding the `workflow` route for a `workflow`-complexity change.
