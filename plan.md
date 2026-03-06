# Plan: Document Solo Quest Mode and Complexity Routing

## Overview

Update two user-facing documentation files to cover complexity routing and solo quest mode. No code changes — documentation only.

**Key framing decision:** "Manual" and "cancel" both mean "exit the quest system." No quest folder, no artifacts, not a quest. The router identifies tasks that don't need a pipeline and lets the user skip it. The two real quest modes are **solo** and **full workflow**. Documentation should mention that trivial/low-risk tasks get routed out, but should NOT document what manual steps look like — we don't know, and we don't track them.

## File 1: `docs/guides/quest_input_routing.md`

### Change 1.1: Update the flow diagram (lines 7-19)

**Current:** Shows three paths (resume, straight-to-planning, questioning).
**New:** Show the full routing flow: resume check → substance evaluation → questioner gate → complexity routing → two quest modes (solo/workflow) or exit.

```
/quest "your input"
       │
       ├── Quest ID provided?  ──yes──>  Resume existing quest
       │
       └── New quest  ──>  Evaluate input substance
                                │
                                ├── Gaps detected (confidence < 0.70)
                                │       └── Ask questions first ──> Re-evaluate
                                │
                                └── Enough detail  ──>  Complexity × Risk routing
                                        │
                                        ├── trivial + low risk  ──>  Exit (no quest needed)
                                        ├── moderate complexity  ──>  Solo quest (lightweight)
                                        └── substantial / high risk  ──>  Full quest (dual reviews)
```

Update the path descriptions below:
- **Path 1 (Resume):** Keep as-is
- **Path 2:** Rename to "Detailed Input — Complexity Routing" — once substance is confirmed, the complexity × risk matrix determines the route
- **Path 3:** Rename to "Thin Input — Questioning First, Then Routing" — questioning is a gate, after which complexity routing runs

After the paths, add a short note: "When the router determines a task is trivial and low-risk, it recommends exiting the quest system entirely — no folder, no artifacts, no pipeline. You just do it directly. This isn't a quest mode; it's Quest recognizing the task doesn't need one."

### Change 1.2: Add "Complexity Routing" section after "How Quest Evaluates Your Input"

New section between current lines 49 and 51. Content:

1. **Three complexity levels** with examples:
   - **Trivial:** Single file, config change, documentation, small bug fix
   - **Moderate:** Multi-file change within one module, new function/endpoint
   - **Substantial:** Cross-cutting changes, new module, architecture, security-sensitive

2. **The complexity × risk matrix** (table):

   | Risk \ Complexity | Trivial | Moderate | Substantial |
   |---|---|---|---|
   | Low | Exit | Solo | Full quest |
   | Medium | Solo | Solo | Full quest |
   | High | Full quest | Full quest | Full quest |

   Brief explanation: "Exit" means Quest suggests you skip the pipeline. "Solo" is the lightweight quest. "Full quest" is the full dual-review workflow.

3. **What the two quest modes mean:**
   - **Solo quest:** Single plan reviewer, no arbiter, single code reviewer, fix iterations capped at 2, quality ceiling at Gold. Same pipeline, fewer stages.
   - **Full quest (workflow):** Dual reviewers (Claude + Codex), arbiter synthesis, full fix loop (default max 3), no tier ceiling.

### Change 1.3: Add "Solo Mode" section after Complexity Routing

Keep concise — solo is a lighter version of the same pipeline, not a separate system. Content:

- Single plan reviewer (Reviewer A only — no Reviewer B)
- No arbiter — Reviewer A's verdict routes directly
- Single code reviewer (Reviewer A only)
- Fix iterations capped at `min(2, allowlist max)` — lighter process, faster turnaround
- Quality tier ceiling at Gold — Diamond and Platinum require dual independent reviews

One paragraph of rationale: lighter process = lower ceiling, because the rigor that justifies higher tiers (dual independent reviews, arbiter synthesis) isn't present.

Don't over-document. This section should be ~10-15 lines, not a deep dive.

### Change 1.4: Add "Override: You Always Choose" section after Solo Mode

New section explaining:

- The router **recommends**, the human **chooses**
- Show the two quest-route override formats from SKILL.md:
  - Solo recommended → options: solo / full quest / cancel
  - Workflow recommended → options: full quest / solo / cancel
  - Manual recommended → options: just do it / solo / full quest / cancel
- Note: when the router recommends exiting (trivial/low), you can still override into solo or full if you want the pipeline
- Brief: "Quest always presents its recommendation first, but you can override."

### Change 1.5: Update Examples section (lines 145-180)

Keep existing examples, add two new ones:

1. **Moderate/low task → routes to solo:**
   ```bash
   /quest "Add input validation to the settings form"
   # Quest Assessment: moderate complexity, low risk → solo recommended
   # Options: 1. Solo (recommended) 2. Full quest 3. Cancel
   ```

2. **User overrides solo → full workflow:**
   ```bash
   /quest "Refactor the notification service"
   # Quest Assessment: moderate complexity, low risk → solo recommended
   # User selects: "Run as full quest"
   # Quest creates full workflow with dual reviews
   ```

### Change 1.6: Update File Structure section (lines 182-196)

Add a note that `router.md` now includes complexity assessment and the complexity × risk matrix in addition to the 7 substance dimensions.

## File 2: `README.md`

### Change 2.1: "What Quest delivers today" section (~line 47)

Add bullet after the "Structured handoff contract" bullet:
- `Smart complexity routing — Quest evaluates task size and risk, then routes to solo (lightweight, single reviewer) or full workflow (dual reviews + arbiter). Trivial tasks exit the pipeline entirely. You always choose.`

### Change 2.2: "What is Quest?" paragraph (~line 87)

Current text says: "Two different models (Claude + GPT) review independently, an arbiter filters nitpicks, and you approve before anything gets built."

Add after this sentence: "For lighter tasks, solo mode uses a single reviewer — same pipeline, fewer stages, faster turnaround."

### Change 2.3: ASCII diagram (~lines 91-104)

Label existing diagram: "Full workflow (complex/high-risk tasks):"

Add a second, simpler diagram below:

```
Solo mode (lighter tasks):
┌──────── PLAN PHASE ────────┐    ┌──────── BUILD PHASE ────────┐
│                             │    │                              │
│  You → Planner → Reviewer ──┼────→  Builder → Reviewer ──────→ Done
│            ▲         │      │  ▲ │              │               │ ▲
│            └── iterate ┘    │  │ │              ▼               │ │
│                             │  │ │           Fixer ─────────────┘ │
│                             │  │ │         (max 2 iterations)     │
└─────────────────────────────┘  │ └──────────────────────────────┘ │
                                 │                                   │
                       GATE: human approval                GATE: human approval
```

### Change 2.4: "Key Features" section (~lines 425-433)

Add bullet:
- `**Smart routing** — evaluates complexity and risk, routes to solo or full workflow. Trivial tasks skip the pipeline. Override anytime.`

### Change 2.5: "The Quest Party: Agent Roles" section (~lines 519-549)

After the existing role descriptions, add a table:

```
### Solo vs Full Workflow

| Role | Full Workflow | Solo Mode |
|------|:---:|:---:|
| Planner | ✓ | ✓ |
| Reviewer A | ✓ | ✓ |
| Reviewer B | ✓ | — |
| Arbiter | ✓ | — |
| Builder | ✓ | ✓ |
| Fixer | ✓ (max 3) | ✓ (max 2) |
```

### Change 2.6: "How the Orchestrator Works" section (~lines 435-478)

After the existing parallel dispatch diagram, add:

> **Solo mode dispatch:** In solo quests, the orchestrator dispatches a single reviewer (Reviewer A only). There's no Reviewer B and no arbiter — Reviewer A's verdict routes directly to the next phase. Review phases complete faster with a single tool call instead of parallel dispatch + synthesis.

### Change 2.7: "Quest scales from simple to complex" examples (~lines 244-261)

Add one example:

```bash
# Solo quest — lighter process for focused tasks
/quest "Add input validation to the settings form"
# Quest recommends: solo (moderate complexity, low risk)
# Single reviewer, faster turnaround
```

## Acceptance Criteria

1. A user reading either file understands when Quest uses solo vs full workflow vs exiting the pipeline
2. The complexity × risk matrix is clearly presented in the routing guide
3. Solo mode constraints are documented concisely with rationale
4. Override mechanism is clear — users see how to escalate or de-escalate
5. README accurately describes both full and solo workflows
6. "Exit" / "manual" / "cancel" are framed as leaving the quest system, not as a quest mode
7. Existing content about questioning phase and 7 dimensions is preserved
8. Existing README tone and structure is preserved

## Files Modified

| File | Type | Sections Affected |
|------|------|-------------------|
| `docs/guides/quest_input_routing.md` | Edit | Flow diagram, paths, new Complexity/Solo/Override sections, examples, file structure |
| `README.md` | Edit | What Quest delivers, What is Quest, ASCII diagram, Key Features, Agent Roles, Orchestrator, examples |

## Files Read-Only (Reference)

- `docs/guides/idea-solo-mode-docs.md`
- `.skills/quest/SKILL.md`
- `.skills/quest/delegation/router.md`
- `.skills/quest/delegation/workflow.md`
- `.ai/allowlist.json`
