# Quest Step Numbering Cleanup

## Status
Proposed

## Problem

After the SKILL.md refactoring into `SKILL.md` + `delegation/workflow.md`, there is a step numbering overlap where **Resume Check** appears in both files under different step numbers.

**SKILL.md** has:
- Step 1: Resume Check
- Step 2: Classify Input (New Quest)
- Step 3: Route

**workflow.md** has:
- Step 0: Resume Check
- Step 1: Precondition Check
- Step 2: Route Intent
- Step 3: Plan Phase
- Step 3.5: Interactive Plan Presentation
- Step 4-7: Build, Review, Fix, Complete

## How It Looks Today

An agent reading both files sequentially sees:

```
SKILL.md Step 1: Resume Check  ->  "delegate to workflow.md"
workflow.md Step 0: Resume Check  ->  [detailed auto-resume table]
workflow.md Step 1: Precondition Check
workflow.md Step 2: Route Intent
```

The agent encounters "Resume Check" twice under two different step numbers. SKILL.md's version is a thin routing decision ("read state and delegate here"), while workflow.md's version is the full auto-resume logic with the state-to-phase mapping table.

The potential confusion: does the agent execute workflow.md starting at Step 0 (re-doing the resume check it already did), or skip to Step 1 (precondition check)? SKILL.md says "delegate to `delegation/workflow.md`" without specifying which step to start at, and workflow.md's Step 0 repeats the same concern SKILL.md already handled.

In practice this is not a bug — running the resume check twice is idempotent (it just reads state.json). But it is a clarity issue for agent interpretation.

## Why It Works Today

The two steps serve slightly different purposes:
- **SKILL.md Step 1**: "Is this a resume? If yes, skip classification/routing and go straight to workflow"
- **workflow.md Step 0**: "I'm resuming — which specific phase do I jump to?"

Because reading state.json is idempotent, the double-read causes no harm. But the naming overlap ("Resume Check" in both) obscures the fact that they do different things.

## Proposed Solution

**Remove workflow.md Step 0 entirely** and fold its missing state mappings into the Step 2 Route Intent table.

The reason: workflow.md Step 0 and Step 2 are almost the same table with Step 0 having three extra rows:

| Step 0 (auto-resume, no instruction) | Step 2 (Route Intent, no instruction) |
|---|---|
| plan + no arbiter -> plan phase | pending plan -> Plan Phase |
| plan + arbiter approved -> Step 3.5 | plan approved -> Step 3.5 |
| plan_reviewed -> Step 3.5 | plan_reviewed -> Step 3.5 |
| presenting -> Step 3.5 | presenting -> Step 3.5 |
| presentation_complete -> Step 4 | presentation_complete -> Step 4 |
| building -> check builder, route to review | *missing from Step 2* |
| reviewing -> check if fixes needed | *missing from Step 2* |
| complete -> show summary | *missing from Step 2* |

The concrete changes:

1. **workflow.md**: Delete Step 0. Add the three missing rows (`building`, `reviewing`, `complete`) to the Step 2 Route Intent table. Renumber remaining steps (Step 1 becomes Step 0, Step 2 becomes Step 1, etc.).
2. **SKILL.md**: Change "Delegate to `delegation/workflow.md`" to point at the specific entry step (e.g., "Delegate to `delegation/workflow.md` Step 1 (Route Intent)").

Result: one resume/routing table instead of two, no duplicate logic, SKILL.md points to the exact workflow entry point.

## Why This Is Better

- Single source of truth for state-to-action mapping
- No ambiguity about which step the agent enters workflow.md at
- The Route Intent table already handles the "what do I do given this state?" question — it just needs three more rows
- Eliminates the "Resume Check" naming collision between files

## Risk Assessment Needed

Before implementing, a risk assessment should be done to evaluate what happens if things go wrong:

- **Agent misrouting**: If the renumbered steps cause existing quest state references (in state.json, in agent prompts, or in user muscle memory like `/quest <id> "resume from step 3"`) to point at the wrong step, quests could resume into the wrong phase. Need to verify no external references depend on step numbers.
- **Missing state mapping**: If the three rows are merged incorrectly into the Route Intent table, resumed quests in `building`, `reviewing`, or `complete` states could hit the wrong branch. Need to verify the merged table covers all state transitions the original Step 0 handled.
- **Codex/Claude agent interpretation**: Different models may parse the renumbered steps differently. Test with both Claude and Codex to confirm correct routing after the change.
- **In-flight quests**: Any quests started before this change should still resume correctly after it. Verify state.json format compatibility is unaffected (it should be, since state.json stores phase names not step numbers).
