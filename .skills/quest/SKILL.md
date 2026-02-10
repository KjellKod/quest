# Quest Orchestration Skill

Multi-agent workflow for planning, reviewing, building, and fixing features through coordinated agent handoffs.

## Usage

```
/quest "Add a loading skeleton to the candidate list"
/quest "Implement the transparency audit plan"
/quest transparency-v2_2026-02-02__1831
/quest transparency-v2_2026-02-02__1831 "now review the code"
/quest status
```

---

## Procedure

When starting, say: "Now I understand the Quest." Then proceed.

### Step 1: Resume Check

If the user provides a quest ID (matches pattern `*_YYYY-MM-DD__HHMM`):
1. Read `.quest/<id>/state.json` and resume from the recorded phase
2. Delegate to `delegation/workflow.md`

If the user says `/quest status`, handle as a utility command (see `delegation/workflow.md` Utility Commands).

### Step 2: Classify Input (New Quest)

If no quest ID is provided:
1. Read `delegation/router.md`
2. Evaluate the user's input against the 7 substance dimensions
3. Produce the routing decision JSON: `{route, confidence (0.0-1.0), risk_level, reason, missing_information}`

### Step 3: Route

Based on the router decision:

**If route = "questioner":**
1. Read `delegation/questioner.md`
2. Follow the questioning procedure (1-3 questions at a time, max 10 total)
3. Collect the structured summary
4. Re-run router (Step 2) with enriched input (original prompt + summary)
5. If route is now "workflow": proceed to "If route = workflow" below
6. If route is still "questioner": allow one more short questioning pass (10-question total cap still applies), then proceed to workflow regardless

**If route = "workflow":**
1. Present the routing classification to the user (see Risk Visibility below)
2. Create quest folder (see Quest Folder Creation below)
3. Read `delegation/workflow.md`
4. Begin at workflow Step 1 (Precondition Check)

### Risk Visibility

Before creating the quest folder, present the routing classification to the user:

1. Display the risk level and confidence:
   - If `risk_level` is "high": **"Risk: HIGH — <reason>"**
   - If `risk_level` is "medium": **"Risk: MEDIUM — <reason>"**
   - If `risk_level` is "low": "Risk: low — <reason>"
2. If the quest went through the questioner path, note this: "Questioning phase completed — gaps addressed before planning."
3. Wait for user acknowledgment before proceeding (for high risk only). For medium and low, display and continue.

### Quest Folder Structure

`.quest/` contains:
- Active quest directories (created per-run)
- `archive/` — completed quests moved here after journaling (see Step 7 in workflow.md)
- `audit.log` — persistent log across all quest runs

### Quest Folder Creation

1. Suggest a slug (lowercase, hyphenated, 2-5 words) and confirm with the user
2. Create `.quest/<slug>_YYYY-MM-DD__HHMM/` with subfolders:
   `phase_01_plan/`, `phase_02_implementation/`, `phase_03_review/`, `logs/`
3. Write quest brief to `.quest/<id>/quest_brief.md` including:
   - User input (original prompt)
   - Questioner summary (if questioning occurred)
   - **Router classification JSON** (the final routing decision that sent the quest to workflow). This is the classification produced by the most recent router evaluation — if the router ran twice (once before questioning, once after), record the second (final) classification.
4. Copy `.ai/allowlist.json` to `.quest/<id>/logs/allowlist_snapshot.json`
5. Initialize `state.json`:
   ```json
   {
     "quest_id": "<id>",
     "slug": "<slug>",
     "phase": "plan",
     "status": "pending",
     "plan_iteration": 0,
     "fix_iteration": 0,
     "created_at": "<timestamp>",
     "updated_at": "<timestamp>"
   }
   ```
