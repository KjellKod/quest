# Implementation Plan: Quest Council Mode

## Revision Notes

**Iteration 2 -- Addressing Arbiter Verdict (2 items):**

1. **Removed "auto" from both enums.** `planning.mode` is now `["quest", "council"]`. `planning.ask` is now `["always", "never"]`. Defaults updated to `mode: "quest"`, `ask: "always"`. Schema descriptions, allowlist defaults, SKILL.md logic (Change 4), and the "Rationale for auto mode" paragraph (Change 1) updated accordingly. The backward-compatibility fallback (missing planning block) remains `mode: "quest"`, `ask: "never"`.

2. **Closed both open questions as decisions.** Open Question 1: both Plan A and Plan B are regenerated on each iteration (full Council loop runs again with arbiter feedback). Open Question 2: follow `planning_track` in state.json (if Council was chosen, re-planning uses Council). Both are now stated as decisions in the "Decisions (Resolved)" section, no longer marked as open questions.

## Overview

**Problem:** Complex quests (migrations, refactors, architecture changes) benefit from exploring multiple planning approaches before committing to one. The current Quest flow produces a single plan, iterates on it, and proceeds. There is no mechanism to generate competing approaches and merge the best parts.

**Impact:** Users get better plans for complex work. The system becomes more discoverable (users see they can configure planning rigor). Both candidate plans and the comparison become permanent audit artifacts.

**Scope:**
- **In:** Changes to SKILL.md (main procedural document), allowlist schema/defaults, state.json extension, new plan_comparison template, arbiter_agent.md updates for comparison duties
- **Out:** Build/review/fix phases, new agent roles, UI changes beyond the single planning-track prompt, roster configuration (options menu), keyword heuristic auto-recommendation (deferred to a follow-up)

**Key constraint:** Quest Council adds a BRANCH in Step 3 (Plan Phase), not a new workflow. Once `plan.md` exists, everything downstream is unchanged.

## Quest Brief Reference

Acceptance criteria from `.quest/quest-council-mode_2026-02-05__1636/quest_brief.md`:

1. `/quest` prompts user to choose Quest Council or Quest at the start
2. Choosing "Quest" runs the existing flow unchanged
3. Choosing "Council" produces plan_a.md, plan_b.md, plan_comparison.md, and merged plan.md
4. `state.json` records `planning_track` and resume skips re-asking
5. Allowlist supports `planning.mode` and `planning.ask` configuration
6. Existing quest behavior is preserved when Council is not selected

## Approach

This plan is organized into 7 changes. Changes 1-3 are the structural foundation (schema, config, state). Changes 4-5 are the procedural core (SKILL.md modifications). Change 6 is the arbiter role update. Change 7 is the new template.

---

### Change 1: Extend allowlist schema with `planning` block

**File:** `/Users/kjell/ws/extra/quest/.ai/schemas/allowlist.schema.json`
**Action:** Modify

Add a new `planning` property to the root schema object. This block controls planning-track behavior without touching any existing fields.

**Schema addition:**
```json
"planning": {
  "type": "object",
  "properties": {
    "mode": {
      "type": "string",
      "enum": ["quest", "council"],
      "description": "Which planning track to use. 'quest' = single plan with review loop, 'council' = dual plan + compare + merge. Used directly when ask is 'never'; used as the default selection when ask is 'always'."
    },
    "ask": {
      "type": "string",
      "enum": ["always", "never"],
      "description": "Whether to prompt the user for track selection. 'always' = prompt every new quest (default to planning.mode if user presses Enter), 'never' = use planning.mode silently without prompting."
    }
  },
  "additionalProperties": false
}
```

**Rationale for removing `auto`:** The original proposal included `auto_recommend` with keyword heuristics and an `auto` mode meaning "ask the user." Since `ask: "always"` already means "ask the user," having `mode: "auto"` duplicates that intent and creates undefined combinations (e.g., `ask: "never"` + `mode: "auto"` has no answer). Removing `auto` from both fields produces a clean 2x2 matrix with no ambiguous states. The keyword heuristic is deferred to a follow-up quest.

**Rationale for naming:** The proposal used `"standard"` for the fast track. We use `"quest"` to match the user-facing label ("Quest" vs "Quest Council"). This avoids a confusing mapping between internal config names and what users see.

---

### Change 2: Update allowlist defaults

**File:** `/Users/kjell/ws/extra/quest/.ai/allowlist.json`
**Action:** Modify

Add the `planning` block with sensible defaults. Bump version from 2 to 3.

```json
"planning": {
  "mode": "quest",
  "ask": "always"
}
```

Also bump `"version": 2` to `"version": 3`.

**Default behavior:** With `mode: "quest"` and `ask: "always"`, the orchestrator always prompts the user to choose a track. If the user presses Enter without selecting, the default is "quest" (the familiar fast flow). This is the least surprising default -- no silent behavior changes for existing users.

**Backward compatibility:** If the `planning` block is absent (old allowlist), SKILL.md treats it as `mode: "quest"`, `ask: "never"` -- equivalent to today's behavior. This is documented explicitly in the SKILL.md procedure.

---

### Change 3: Extend state.json schema

**File:** `/Users/kjell/ws/extra/quest/.skills/quest/SKILL.md` (documented in the State File Format section)
**Action:** Modify the state.json documentation

Add `planning_track` to the state file format:

```json
{
  "quest_id": "feature-x_2026-02-02__1430",
  "slug": "feature-x",
  "phase": "plan | plan_reviewed | presenting | presentation_complete | building | reviewing | fixing | complete",
  "status": "pending | in_progress | complete | blocked",
  "planning_track": "quest | council",
  "plan_iteration": 2,
  "fix_iteration": 0,
  "last_role": "arbiter_agent",
  "last_verdict": "approve | iterate",
  "created_at": "2026-02-02T14:30:00Z",
  "updated_at": "2026-02-02T14:45:00Z"
}
```

**Resume behavior:** When resuming a quest (Step 0), the orchestrator reads `planning_track` from state.json. If present, it skips the track selection prompt. If absent (legacy quest), it defaults to `"quest"`.

---

### Change 4: Modify SKILL.md Step 1 (Intake) -- add track selection prompt

**File:** `/Users/kjell/ws/extra/quest/.skills/quest/SKILL.md`
**Action:** Modify Step 1, add a new sub-step after step 8 (copy allowlist) and before step 9 (initialize state.json)

Insert a new step 9 (renumber old 9 to 10):

> **9. Planning track selection:**
>
> Read `planning.mode` and `planning.ask` from the allowlist snapshot. If the `planning` block is absent, treat as `mode: "quest"`, `ask: "never"`.
>
> - If `ask` is `"never"`: use `mode` directly (skip prompt).
> - If `ask` is `"always"`: prompt the user, with `mode` as the default selection:
>   ```
>   Which planning track?
>   1. Quest Council: generates two competing plans, compares, and merges into one best plan (recommended for complex work)
>   2. Quest: single plan with review loop (faster, good for focused changes)
>   Choose [1/2] (default: 2):
>   ```
>   If the user presses Enter with no input, use the value of `mode` (default: `"quest"`).
> - Record the selection in `planning_track` field of state.json.

Update the state.json initialization (now step 10) to include `"planning_track": "<selected>"`.

**Design note:** The default is Quest (fast), not Council. The original proposal defaulted to Council, but that would slow down every quest for existing users who expect the current behavior. Users who want Council will select it explicitly. The prompt text mentions "recommended for complex work" to nudge users toward Council when appropriate, without imposing it.

---

### Change 5: Modify SKILL.md Step 3 (Plan Phase) -- add Council branch

**File:** `/Users/kjell/ws/extra/quest/.skills/quest/SKILL.md`
**Action:** Modify Step 3 to branch based on `planning_track`

This is the PRIMARY change. The existing Step 3 loop becomes the "Quest track" path. A new "Council track" path is added as a conditional branch.

**Structure of the modified Step 3:**

```
### Step 3: Plan Phase

Read `planning_track` from state.json.

If `planning_track` is `"council"` -> follow **Step 3C: Council Planning Track**
Otherwise -> follow **Step 3Q: Quest Planning Track** (existing behavior)

#### Step 3Q: Quest Planning Track

[EXISTING Step 3 content, unchanged -- move it here verbatim]

#### Step 3C: Council Planning Track

Read allowlist gates (same as 3Q):
  auto_approve_phases.plan_creation
  auto_approve_phases.plan_review
  auto_approve_phases.plan_refinement
  gates.max_plan_iterations (default: 4)

**Phase 1 of Council: Generate two candidate plans**

1. Update state: plan_iteration += 1, status: in_progress, last_role: planner_agent

2. Create plan_candidates directory:
   .quest/<id>/phase_01_plan/plan_candidates/

3. Invoke Planner TWICE IN PARALLEL (two Task tool calls in the same message):

   **Plan A** (Task tool with `planner` agent):
   - Prompt: Include quest brief + instruction:
     "Generate Plan A: a CONSERVATIVE approach. Favor minimal changes,
      lowest risk, reuse of existing patterns, and smallest blast radius.
      Write the plan to: .quest/<id>/phase_01_plan/plan_candidates/plan_a.md"
   - If iteration > 1, include arbiter verdict

   **Plan B** (Task tool with `planner` agent):
   - Prompt: Include quest brief + instruction:
     "Generate Plan B: an AMBITIOUS approach. Favor thoroughness,
      better long-term architecture, and stronger abstractions, even if
      it means more files changed or more complexity upfront.
      Write the plan to: .quest/<id>/phase_01_plan/plan_candidates/plan_b.md"
   - If iteration > 1, include arbiter verdict

   Wait for BOTH responses.
   Verify both plan files exist. If not written, extract from responses and write them.

   If .quest/<id>/phase_01_plan/user_feedback.md exists, include it in BOTH
   planner prompts as additional context for the revision.

**Phase 2 of Council: Review both candidates**

4. Invoke BOTH Plan Reviewers IN PARALLEL (same as standard flow, but reviewing BOTH candidates):

   **Claude reviewer** (Task tool with `plan-reviewer` agent):
   - Prompt: Include quest brief + BOTH plan paths:
     "Review both plan candidates:
      Plan A: .quest/<id>/phase_01_plan/plan_candidates/plan_a.md
      Plan B: .quest/<id>/phase_01_plan/plan_candidates/plan_b.md
      Compare their strengths and weaknesses. Write a single review
      covering both plans to: .quest/<id>/phase_01_plan/review_claude.md"

   **Codex reviewer** (mcp__codex__codex):
   - Same structure, pointing to both plan files
   - Write to: .quest/<id>/phase_01_plan/review_codex.md

   Wait for BOTH responses, verify both review files written.

**Phase 3 of Council: Arbiter comparison and merge**

5. Invoke Arbiter with EXTENDED prompt:

   If arbiter.tool is "codex":
     mcp__codex__codex(
       model: "gpt-5.2",
       prompt: "You are the Arbiter Agent in COUNCIL MODE.

       Read your instructions: .ai/roles/arbiter_agent.md
       Read the council comparison instructions in that file.

       Quest brief: .quest/<id>/quest_brief.md
       Plan A: .quest/<id>/phase_01_plan/plan_candidates/plan_a.md
       Plan B: .quest/<id>/phase_01_plan/plan_candidates/plan_b.md
       Claude review: .quest/<id>/phase_01_plan/review_claude.md
       Codex review: .quest/<id>/phase_01_plan/review_codex.md

       You must write THREE files:
       1. .quest/<id>/phase_01_plan/plan_comparison.md (use template: .ai/templates/plan_comparison.md)
       2. .quest/<id>/phase_01_plan/plan.md (the final merged plan)
       3. .quest/<id>/phase_01_plan/arbiter_verdict.md

       NEXT must be: builder (approve) or planner (iterate)"
     )

   If arbiter.tool is "claude": use Task tool with `arbiter` agent, same content.

   Parse verdict for NEXT field.

6. Check verdict (same logic as standard track):
   - If NEXT: builder -> Plan approved. Update state: phase: plan_reviewed. Proceed to Step 3.5.
   - If NEXT: planner -> Check iteration count, loop back to Phase 1 of Council.
```

**Key design decisions:**

- **Two parallel planner invocations** rather than one planner producing both plans. This ensures genuinely different approaches (different context windows, different reasoning paths). It also reuses the existing planner agent without modification.
- **Conservative vs Ambitious framing** answers the open question from the proposal. Giving explicit framing constraints produces materially different plans without requiring a new "plan strategy" config knob.
- **Reviewers see both plans.** This is more useful than reviewing them independently because the reviewer can comment on relative strengths ("Plan A handles X better, Plan B handles Y better").
- **Arbiter writes plan_comparison.md AND plan.md.** The arbiter picks a base, merges the best parts of the other, and writes the final merged plan. The comparison is the audit trail. The merged plan.md is what downstream phases consume.
- **Iteration loop reuses the same structure.** If the arbiter says "iterate," the council runs again with both new candidates informed by the arbiter's feedback. This keeps the max_plan_iterations gate working identically.

---

### Change 6: Update arbiter_agent.md with Council comparison duties

**File:** `/Users/kjell/ws/extra/quest/.ai/roles/arbiter_agent.md`
**Action:** Modify -- add a new section for Council Mode responsibilities

Add the following section after the existing "Responsibilities" section:

> ## Council Mode Responsibilities
>
> When invoked in Council mode (two candidate plans), the Arbiter has additional duties:
>
> 1. Read both candidate plans (plan_a.md and plan_b.md)
> 2. Read both reviews (which cover both candidates)
> 3. **Choose a base plan:** Pick the candidate that better addresses the acceptance criteria, has fewer architectural issues, and is more implementable.
> 4. **Merge selectively:** From the non-base plan, incorporate ONLY elements that:
>    - Reduce risk
>    - Increase testability
>    - Improve clarity
>    - Address acceptance criteria gaps in the base
>    Do NOT merge for novelty, elegance, or completeness beyond the acceptance criteria.
> 5. **Write plan_comparison.md** using the template at `.ai/templates/plan_comparison.md`. This is the audit trail explaining the decision.
> 6. **Write plan.md** -- the final merged plan that downstream phases consume. This must be a complete, self-contained plan (not a diff or delta).
> 7. **Write arbiter_verdict.md** -- same format as standard mode.
>
> ### Council Merge Rules
> - The merged plan must not be longer than the longer candidate plan. Merging means choosing the better approach, not concatenating both.
> - If both plans are roughly equivalent, pick Plan A (conservative). Bias toward simplicity.
> - The comparison must explicitly state what was taken from each plan and why.

---

### Change 7: Create plan_comparison.md template

**File:** `/Users/kjell/ws/extra/quest/.ai/templates/plan_comparison.md`
**Action:** Create (new file)

```markdown
# Plan Comparison: <QUEST_SLUG>

## Candidates

### Plan A: <approach label>
- **Summary:** <1-2 sentence summary of approach>
- **Strengths:** <bulleted list>
- **Weaknesses:** <bulleted list>

### Plan B: <approach label>
- **Summary:** <1-2 sentence summary of approach>
- **Strengths:** <bulleted list>
- **Weaknesses:** <bulleted list>

## Head-to-Head

| Dimension | Plan A | Plan B | Winner |
|-----------|--------|--------|--------|
| Risk | ... | ... | A/B |
| Simplicity | ... | ... | A/B |
| Testability | ... | ... | A/B |
| Completeness (AC coverage) | ... | ... | A/B |
| Implementation effort | ... | ... | A/B |

## Decision

**Base plan:** A / B
**Reason:** <1-2 sentences>

## Merged Elements

<!-- List specific elements taken from the non-base plan -->
- From Plan <X>: <element> -- Reason: <why it improves the base>

## Discarded Elements

<!-- List specific elements from the non-base plan that were NOT merged -->
- From Plan <X>: <element> -- Reason: <why it was not worth including>
```

---

## File Changes Summary

| File | Action | Description |
|------|--------|-------------|
| `.ai/schemas/allowlist.schema.json` | modify | Add `planning` object with `mode` and `ask` enum properties |
| `.ai/allowlist.json` | modify | Add `planning` block with defaults, bump version to 3 |
| `.skills/quest/SKILL.md` | modify | Add track selection in Step 1, add Council branch in Step 3, update state.json format |
| `.claude/skills/quest/SKILL.md` | no change | Already delegates to `.skills/quest/SKILL.md` -- no update needed |
| `.ai/roles/arbiter_agent.md` | modify | Add Council Mode Responsibilities section and merge rules |
| `.ai/templates/plan_comparison.md` | create | New template for the plan comparison artifact |

**Total files changed:** 5 (4 modified, 1 created)

## Acceptance Criteria Validation

| AC | How it is met | Validation |
|----|--------------|------------|
| 1. `/quest` prompts user to choose track | Change 4: new step 9 in Step 1 prompts with `[1/2]` | Manual: start a new quest, verify prompt appears |
| 2. "Quest" runs existing flow unchanged | Change 5: Step 3Q is the existing Step 3, verbatim | Manual: select Quest, verify identical behavior to current |
| 3. "Council" produces plan_a, plan_b, comparison, merged plan | Change 5: Step 3C phases 1-3 produce all four artifacts | Manual: select Council, verify all four files exist in phase_01_plan/ |
| 4. state.json records planning_track, resume skips re-asking | Change 3+4: planning_track in state.json; Step 0 reads it | Manual: start Council quest, interrupt, resume with quest ID, verify no re-prompt |
| 5. Allowlist supports planning.mode and planning.ask | Changes 1+2: schema and defaults | Inspect allowlist.json and schema, verify fields parse |
| 6. Existing behavior preserved when Council not selected | Change 5: Step 3Q is unchanged; Change 2 defaults to ask:always so user can always pick Quest | Manual: with default config, select Quest, verify no behavioral change |

## Test Strategy

All tests are manual since the Quest system is a procedural document interpreted by AI agents, not executable code.

**MANUAL TEST 1: Track selection prompt appears**
- **Why manual:** Orchestration procedure, no code to unit-test
- **Preconditions:** Clean repo with updated SKILL.md and allowlist
- **Steps:**
  1. Run `/quest "Add a loading skeleton"`
  2. Observe the track selection prompt
  3. Press Enter (default)
- **Expected:** Default selects "Quest" track. State.json contains `"planning_track": "quest"`.
- **Observability:** Read `.quest/<id>/state.json`

**MANUAL TEST 2: Quest track is unchanged**
- **Why manual:** Behavioral regression test
- **Preconditions:** Same as Test 1
- **Steps:**
  1. Run `/quest "Add a loading skeleton"`, select Quest
  2. Observe plan phase proceeds as before (single plan, dual review, arbiter)
- **Expected:** No plan_candidates/ directory created. plan.md written directly. Identical to pre-change behavior.
- **Observability:** `ls .quest/<id>/phase_01_plan/` -- should show plan.md, reviews, verdict. No plan_candidates/.

**MANUAL TEST 3: Council track produces all artifacts**
- **Why manual:** End-to-end orchestration test
- **Preconditions:** Same as Test 1
- **Steps:**
  1. Run `/quest "Refactor the authentication module"`, select Council
  2. Wait for plan phase to complete
- **Expected:**
  - `.quest/<id>/phase_01_plan/plan_candidates/plan_a.md` exists
  - `.quest/<id>/phase_01_plan/plan_candidates/plan_b.md` exists
  - `.quest/<id>/phase_01_plan/plan_comparison.md` exists
  - `.quest/<id>/phase_01_plan/plan.md` exists (merged final plan)
  - `.quest/<id>/phase_01_plan/arbiter_verdict.md` exists
- **Observability:** File listing + read plan_comparison.md to verify it follows template structure

**MANUAL TEST 4: Resume skips track selection**
- **Why manual:** State persistence test
- **Preconditions:** Quest started with Council track
- **Steps:**
  1. Start a Council quest, let it reach plan phase
  2. Interrupt (close session)
  3. Run `/quest <id>` to resume
- **Expected:** No track selection prompt. Quest resumes in Council track based on state.json.
- **Observability:** Verify no prompt shown; verify plan phase continues in council mode

**MANUAL TEST 5: ask:never skips prompt**
- **Why manual:** Configuration test
- **Preconditions:** Set `planning.ask: "never"` and `planning.mode: "council"` in allowlist
- **Steps:**
  1. Run `/quest "some task"`
- **Expected:** No track selection prompt. Proceeds directly with Council track.
- **Observability:** state.json shows `"planning_track": "council"` without user interaction

**MANUAL TEST 6: Missing planning block defaults to quest**
- **Why manual:** Backward compatibility test
- **Preconditions:** Remove `planning` block from allowlist.json entirely
- **Steps:**
  1. Run `/quest "small fix"`
- **Expected:** No track selection prompt. Proceeds with Quest track (backward compatible).
- **Observability:** state.json shows `"planning_track": "quest"`

## Integration Touchpoints

| System | Could break | Validation |
|--------|------------|------------|
| `.ai/allowlist.json` parsing | Old allowlists without `planning` block could cause errors if code expects it | SKILL.md specifies fallback: treat missing block as `mode: "quest"`, `ask: "never"` |
| state.json resume logic (Step 0) | Resume could fail if `planning_track` is missing from old quests | Step 0 defaults missing field to `"quest"` |
| Arbiter agent | Arbiter may not know it is in Council mode if prompt is unclear | Arbiter prompt explicitly says "COUNCIL MODE" and lists all expected output files |
| Planner agent | Planner receives new instructions (conservative/ambitious framing) but role file is unchanged | No role file change needed -- framing is in the orchestrator prompt, not the role |
| Plan reviewers | Reviewers receive two plans instead of one in Council mode | Reviewer prompt explicitly asks for comparative review of both candidates |
| Step 3.5 (Interactive Presentation) | No change needed -- it reads plan.md, which exists in both tracks | No breakage -- Council produces plan.md just like Quest does |
| Build/Review/Fix phases | No change needed -- they consume plan.md | No breakage -- plan.md is the contract between planning and downstream |

## Risks and Mitigations

| # | Risk | Impact | Likelihood | Mitigation |
|---|------|--------|------------|------------|
| 1 | Two parallel planner invocations may produce very similar plans, defeating the purpose of Council | Medium | Medium | Explicit framing ("conservative" vs "ambitious") in the planner prompts forces differentiation. If plans are too similar, the arbiter can note this in plan_comparison.md and pick one without merging. |
| 2 | Council mode doubles planning time (two plans + comparative reviews + merge) | Medium | High | This is expected and documented. The track selection prompt warns "recommended for complex work." Users who want speed pick Quest. |
| 3 | Arbiter merge produces a plan that is worse than either candidate (Frankenstein plan) | High | Low | Merge rules in arbiter_agent.md are strict: "must not be longer than the longer candidate," bias toward simplicity, merge only when it reduces risk/increases testability. Anti-concatenation rule. |
| 4 | Existing users confused by new prompt on every quest start | Medium | Medium | Default answer is Quest (Enter = fast path). Prompt is 3 lines. Users can set `ask: "never"` to suppress permanently. |
| 5 | Schema version bump (2 to 3) breaks tooling that checks version | Low | Low | No known tooling checks the version field. The bump is informational. |

## Decisions (Resolved)

- [x] **Plan A/B iteration:** DECIDED -- both Plan A and Plan B are regenerated on each iteration. The full Council loop runs again with arbiter feedback included in both planner prompts. This is simpler (reuses the same loop), preserves Council's value (genuinely different approaches each iteration), and keeps the `max_plan_iterations` gate working identically to the Quest track.

- [x] **User feedback re-planning track:** DECIDED -- follow `planning_track` in state.json. If the user chose Council, re-planning after Step 3.5 feedback uses Council. This is consistent (the user's original track choice is respected) and requires no conditional logic or additional prompting.

## Open Questions

None.

## Out of Scope

- **Keyword heuristic auto-recommendation:** The original proposal suggested auto-detecting complex prompts. Deferred to a follow-up quest.
- **Roster configuration (options menu):** The proposal included an interactive "options" menu for changing arbiter/reviewers/gates. Deferred -- orthogonal to Council mode.
- **Council with more than 2 candidates:** Fixed at 2 candidates. Extensibility is not a goal for this quest.
- **Changes to build/review/fix phases:** These phases are unchanged. They consume plan.md regardless of which track produced it.
- **Changes to planner_agent.md or plan_review_agent.md role files:** The orchestrator prompt provides all the context these agents need. No role file changes required.
