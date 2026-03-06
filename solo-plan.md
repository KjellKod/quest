---
title: Quest Complexity Routing — Solo & Manual Routes
status: approved
revision: 1
revision_notes: |
  Fixes from plan review:
  - Added full 9-cell complexity × risk routing matrix (was only 3 explicit cases)
  - Added plan->plan solo transition in validation script (reviewer A replaces arbiter for re-iteration)
  - Resolved reviewer A next-value mismatch: workflow remaps "arbiter" → "builder" in solo mode
  - Questioner logic unchanged (keeps existing confidence >= 0.70 gate)
---

# Implementation Plan: Quest Complexity Routing

## Overview

**Problem:** Every task routed through quest gets the full pipeline (dual plan review, arbiter, dual code review). Trivial and moderate tasks get the same ceremony as cross-cutting refactors, wasting tokens and time.

**Solution:** Add a `complexity` dimension to the router and two new route types (`solo`, `manual`). The router recommends; the human always chooses.

**Impact:** 6 files modified, 1 idea file consumed. No new files created. No new agents — solo reuses existing agents with fewer invocations.

## Phase 1: Router — Add Complexity Dimension and New Routes

**File:** `.skills/quest/delegation/router.md`

**Changes:**
1. Add **Complexity Assessment** section after the existing 7 substance evaluation dimensions:
   - Define three complexity levels: `trivial`, `moderate`, `substantial`
   - Provide signal descriptions (same as idea doc):
     - **Trivial:** Single file, documentation, config change, idea doc, small bug fix, adding a test
     - **Moderate:** Multi-file change within one module, new function/endpoint, focused refactor
     - **Substantial:** Cross-cutting changes, new module, architecture change, security-sensitive, multi-system integration

2. Update **Decision Logic** section:
   - Keep existing `questioner` logic unchanged (confidence < 0.70, missing info)
   - Add routing rules for `solo` and `manual`:
     ```
     IF risk_level == "high" OR complexity == "substantial":
       → workflow (full quest)
     IF risk_level == "medium" AND complexity == "moderate":
       → solo (lightweight quest)
     IF risk_level == "low" AND complexity == "trivial":
       → manual (just do it)
     ```
   - Default to `workflow` for any ambiguous combination (safe fallback)
   - Full complexity × risk routing matrix:
     ```
     | Risk \ Complexity | trivial  | moderate | substantial |
     |-------------------|----------|----------|-------------|
     | low               | manual   | solo     | workflow    |
     | medium            | solo     | solo     | workflow    |
     | high              | workflow | workflow | workflow    |
     ```

3. Update **Output Contract** JSON:
   - Add `"complexity": "trivial | moderate | substantial"` field
   - Expand `"route"` to: `"questioner | workflow | solo | manual"`

**Acceptance Criteria:**
- [ ] Router output JSON includes `complexity` field
- [ ] Router output JSON supports four route values: `questioner`, `workflow`, `solo`, `manual`
- [ ] Routing logic documented for all complexity × risk combinations
- [ ] Existing questioner/workflow logic unchanged (backward compatible)

## Phase 2: SKILL.md — Route Presentation with Human Override

**File:** `.skills/quest/SKILL.md`

**Changes:**
1. Update **Step 3: Route** to handle all four routes:

   **If route = "solo":**
   - Present the routing classification with complexity assessment
   - Show override options:
     ```
     Quest Assessment:
       Risk: <risk_level>
       Complexity: <complexity>
       Recommended route: solo (lightweight quest)

     Options:
       1. Run as solo quest (recommended) — single plan review, single code review
       2. Run as full quest — dual reviews, arbiter, the works
       3. Just do it manually — no pipeline
       4. Cancel
     ```
   - On selection: create quest folder with `quest_mode` in brief, proceed to workflow with mode

   **If route = "manual":**
   - Present recommendation:
     ```
     Quest Assessment:
       Risk: low
       Complexity: trivial
       Recommended: manual (no pipeline)

     Options:
       1. Just do it (recommended)
       2. Run as solo quest
       3. Run as full quest
       4. Cancel
     ```
   - On "just do it": exit quest system, let user work directly

   **If route = "workflow":**
   - Add override options (in addition to existing flow):
     ```
     Options:
       1. Run as full quest (recommended)
       2. Run as solo quest (lighter)
       3. Cancel
     ```

2. Update **Quest Folder Creation** (Step after route selection):
   - Add `quest_mode` field to `state.json` initialization: `"quest_mode": "workflow" | "solo" | "manual"`
   - Record the selected mode (which may differ from the recommended route if user overrode)

**Acceptance Criteria:**
- [ ] All four routes present override options to user
- [ ] User can always escalate (solo → workflow) or de-escalate (workflow → solo)
- [ ] `quest_mode` recorded in state.json reflects actual selection, not just recommendation
- [ ] Manual route exits quest system cleanly

## Phase 3: Workflow — Solo Pipeline (Conditional Skips)

**File:** `.skills/quest/delegation/workflow.md`

**Changes:**
1. Add a **Quest Mode Check** section near the top (after Defaults, before Step 0):
   - On entry, read `quest_mode` from `state.json`
   - Define mode-specific behavior table:
     ```
     | Aspect              | workflow      | solo          |
     |---------------------|--------------|---------------|
     | Plan reviewers      | Dual (A + B) | Single (A)    |
     | Arbiter             | Yes          | No            |
     | Code reviewers      | Dual (A + B) | Single (A)    |
     | Max fix iterations  | From allowlist (default 3) | min(2, allowlist) |
     | Quality tier ceiling | None         | Gold          |
     ```

2. **Step 3 (Plan Phase)** — Solo modifications:
   - Step 3.4 (Invoke BOTH Plan Reviewers): If `quest_mode == "solo"`, invoke ONLY Reviewer A (Claude Task). Skip Reviewer B (Codex).
   - Step 3.5 (Invoke Arbiter): If `quest_mode == "solo"`, skip entirely. Remap Reviewer A's verdict:
     - If Reviewer A handoff `next: "planner"` → iterate (plan needs revision)
     - If Reviewer A handoff `next: "arbiter"` → remap to `next: "builder"` (approved in solo; the reviewer contract always says "arbiter" but solo treats this as approval)
     - Write remapped verdict to state so downstream consumers (validation script) always see `next: "builder"` for approved plans
   - Parallelism log: When solo, log `Plan review: dispatched=single (solo mode)`

3. **Step 5 (Review Phase)** — Solo modifications:
   - Step 5.4 (Invoke BOTH Code Reviewers): If `quest_mode == "solo"`, invoke ONLY Reviewer A. Skip Reviewer B.
   - Step 5.5 (Check verdicts): When solo, only check Reviewer A's verdict:
     - `next: "fixer"` → proceed to fix
     - `next: null` → review passed, proceed to complete
   - Parallelism log: When solo, log `Code review: dispatched=single (solo mode)`

4. **Step 6 (Fix Phase)** — Solo modifications:
   - Cap `max_fix_iterations` at `min(2, gates.max_fix_iterations)` when solo
   - Re-invoke only Reviewer A (not both) after fix

5. **Step 7 (Complete)** — Solo modifications:
   - Record `quest_mode: "solo"` in celebration_data JSON
   - Quality tier: apply ceiling of Gold (if computed tier > Gold, cap to Gold)
   - Context health report: Solo quests will show fewer agents (expected), note this in report

**Acceptance Criteria:**
- [ ] Solo quest skips Reviewer B and Arbiter in plan phase
- [ ] Solo quest skips Reviewer B in code review phase
- [ ] Solo quest caps fix iterations at min(2, allowlist max)
- [ ] Solo quest celebration_data includes `quest_mode: "solo"`
- [ ] Workflow mode behavior completely unchanged (no regressions)

## Phase 4: Validation Script — Solo-Aware Artifact Checks

**File:** `scripts/validate-quest-state.sh`

**Changes:**
1. Read `quest_mode` from `state.json` early (alongside `CURRENT_PHASE`)
2. In `validate_artifacts()`:
   - For `plan->plan` transition (plan re-iteration) when `quest_mode == "solo"`:
     - Require: `review_plan-reviewer-a.md` (reviewer A triggers re-plan)
     - Do NOT require: `arbiter_verdict.md` (no arbiter in solo)
   - For `plan->plan_reviewed` transition when `quest_mode == "solo"`:
     - Require: `plan.md`, `review_plan-reviewer-a.md`
     - Do NOT require: `review_plan-reviewer-b.md`, `arbiter_verdict.md`
   - For `reviewing->fixing` and `reviewing->complete` when `quest_mode == "solo"`:
     - Require only: `review_code-reviewer-a.md`
     - Do NOT require: `review_code-reviewer-b.md`
3. In `validate_semantic_content()`:
   - For `plan_reviewed->building` when `quest_mode == "solo"`:
     - Check Reviewer A's handoff instead of arbiter's handoff
     - Accept `next: "builder"` from `handoff_plan-reviewer-a.json`
   - For `reviewing->complete` when `quest_mode == "solo"`:
     - Check only Reviewer A's `next: null`

**Acceptance Criteria:**
- [ ] Solo quests pass validation without reviewer B / arbiter artifacts
- [ ] Workflow quests unchanged (still require all artifacts)
- [ ] Semantic checks adapted for solo (reviewer A verdict is sufficient)

## Phase 5: Allowlist & Quest Data — Solo Configuration

### File: `.ai/allowlist.json`

**Changes:**
1. Add `solo` section:
   ```json
   "solo": {
     "max_fix_iterations": 2,
     "quality_tier_ceiling": "Gold"
   }
   ```

### File: `scripts/quest_celebrate/quest_data.py`

**Changes:**
1. Add `quest_mode: str = ""` field to `QuestData` dataclass (after `status`)
2. In `load_quest_data()`: read `quest_mode` from `state.json`
3. In `compute_quality_tier()`: add optional `quest_mode` parameter
   - If `quest_mode == "solo"` and computed tier is above Gold → return "Gold"
   - Tier ordering for ceiling check: Diamond > Platinum > Gold (anything above Gold gets capped)
4. In `load_quest_data_from_journal()`: read `quest_mode` from celebration_data JSON if present
5. In `_compute_achievements()`: add a solo-specific achievement:
   - If `quest_mode == "solo"`: add "Solo Adventurer" achievement ("Completed quest with a single companion")

**Acceptance Criteria:**
- [ ] `QuestData.quest_mode` populated from state.json
- [ ] Solo quests capped at Gold tier
- [ ] Solo achievement badge generated
- [ ] Existing workflow tier computation unchanged

## Phase 6: Idea File Cleanup

After implementation is verified:
- The idea file `ideas/quest-complexity-routing.md` should be referenced in the journal entry
- Mark as done in `ideas/README.md` when quest completes

## Summary of All Changes

| File | Change Type | Size |
|------|------------|------|
| `.skills/quest/delegation/router.md` | Add complexity dimension + routes | Small |
| `.skills/quest/SKILL.md` | Route presentation + override UX | Small |
| `.skills/quest/delegation/workflow.md` | Solo conditional skips | Medium |
| `scripts/validate-quest-state.sh` | Solo-aware validation | Small |
| `.ai/allowlist.json` | Solo config section | Trivial |
| `scripts/quest_celebrate/quest_data.py` | quest_mode + tier cap | Small |

**Total estimated scope:** ~200 lines changed across 6 files. No new files. No new agents. No architectural changes — this is additive conditional logic on existing pipeline.
