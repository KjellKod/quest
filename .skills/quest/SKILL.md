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

When starting, say: "Now I understand the Quest." Then proceed directly with the steps below.

Follow these steps in order. After each step that modifies state, update `.quest/<id>/state.json`.

### Step 0: Resume Check

If the user provides a quest ID (matches pattern `*_YYYY-MM-DD__HHMM`):

1. Check if `.quest/<id>/state.json` exists
2. If yes, read it and resume from the recorded phase
3. If the user also provided an instruction, route it (Step 2)
4. If no instruction, auto-resume based on state:
   - `phase: plan` + no arbiter verdict → continue plan phase
   - `phase: plan` + arbiter approved → proceed to Step 3.5 (Interactive Presentation)
   - `phase: plan_reviewed` → proceed to Step 3.5 (Interactive Presentation)
   - `phase: presenting` → proceed to Step 3.5 (Interactive Presentation)
   - `phase: presentation_complete` → proceed to Step 4 gate check (ask to proceed with build)
   - `phase: building` → check for builder output, route to review
   - `phase: reviewing` → check if fixes needed
   - `phase: complete` → show summary

### Step 1: Intake (New Quest)

If no quest ID provided:

1. Parse the user's instruction
2. Suggest a slug (lowercase, hyphenated, 2-5 words)
3. Ask user to confirm or override the slug
4. Create quest folder: `.quest/<slug>_YYYY-MM-DD__HHMM/`
5. Create subfolders: `phase_01_plan/`, `phase_02_implementation/`, `phase_03_review/`, `logs/`
6. Write quest brief to `.quest/<id>/quest_brief.md` using the user's instruction
7. Copy `.ai/allowlist.json` to `.quest/<id>/logs/allowlist_snapshot.json`
8. Initialize state.json:
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

### Step 2: Route Intent

Determine the action based on instruction + current state:

| Instruction contains | State | Action |
|---------------------|-------|--------|
| "plan", "design", or new quest | any | → Plan Phase |
| "implement", "build", "code" | plan approved | → Build Phase |
| "review" | has implementation | → Review Phase |
| "fix" | has review issues | → Fix Phase |
| no instruction | pending plan | → Plan Phase |
| no instruction | plan_reviewed | → Step 3.5 (Interactive Presentation) |
| no instruction | presenting | → Step 3.5 (Interactive Presentation) |
| no instruction | presentation_complete | → Step 4 (Build Phase) |
| no instruction | plan approved (arbiter verdict exists, phase is still `plan`) | → Step 3.5 (Interactive Presentation) |
| no instruction | built | → Review Phase |

### Step 3: Plan Phase

**Read allowlist gates:**
```
auto_approve_phases.plan_creation
auto_approve_phases.plan_review
auto_approve_phases.plan_refinement
gates.max_plan_iterations (default: 4)
```

**Loop:**

1. **Update state:** `plan_iteration += 1`, `status: in_progress`, `last_role: planner_agent`

2. **Invoke Planner** (Task tool with `planner` agent):
   - Prompt: Include quest brief, and if iteration > 1, include arbiter verdict
   - **If `.quest/<id>/phase_01_plan/user_feedback.md` exists, include it in the planner prompt as additional context for the revision**
   - Wait for response
   - Verify `.quest/<id>/phase_01_plan/plan.md` exists
   - If not written, extract from response and write it

3. **Read review config from allowlist:**
   - `review_mode` (default: `auto`)
   - `fast_review_thresholds` (not used for plan review)
   - `codex_context_digest_path` (default: `.ai/context_digest.md`)
   - For plan review: treat `auto` as `full`. Use `fast` only if explicitly set.

4. **Invoke BOTH Plan Reviewers IN PARALLEL** (same message, two tool calls):

   **Claude reviewer** (Task tool with `plan-reviewer` agent):
   - Prompt: Include quest brief + plan path
   - Writes to `.quest/<id>/phase_01_plan/review_claude.md`

   **Codex reviewer** (mcp__codex__codex) — call in the SAME message:
   - Use the digest path and **mode-specific** prompt:

     **Full mode** (default for plan review):
     ```
     mcp__codex__codex(
       model: "gpt-5.2",
       prompt: "You are the Plan Review Agent (Codex).

       Read your instructions: .ai/roles/plan_review_agent.md
       Read context digest: <codex_context_digest_path>
       (Optional, full mode only) Read: .skills/BOOTSTRAP.md, AGENTS.md

       Quest brief: .quest/<id>/quest_brief.md
       Plan to review: .quest/<id>/phase_01_plan/plan.md

       Write your review to: .quest/<id>/phase_01_plan/review_codex.md

       When done, output: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY"
     )
     ```
     **Fast mode** (only if `review_mode: fast`):
     ```
     mcp__codex__codex(
       model: "gpt-5.2",
       prompt: "You are the Plan Review Agent (Codex).

       Read context digest: <codex_context_digest_path>
       Quest brief: .quest/<id>/quest_brief.md
       Plan to review: .quest/<id>/phase_01_plan/plan.md

       List up to 5 issues, highest severity first.
       Write your review to: .quest/<id>/phase_01_plan/review_codex.md

       When done, output: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY"
     )
     ```
   - Wait for BOTH responses, verify both review files written

5. **Invoke Arbiter:**
   - Check `.ai/allowlist.json` → `arbiter.tool` (default: "codex")
   - If "codex": use mcp__codex__codex with SHORT prompt:
     ```
     You are the Arbiter Agent.

     Read your instructions: .ai/roles/arbiter_agent.md

     Quest brief: .quest/<id>/quest_brief.md
     Plan: .quest/<id>/phase_01_plan/plan.md
     Claude review: .quest/<id>/phase_01_plan/review_claude.md
     Codex review: .quest/<id>/phase_01_plan/review_codex.md

     Write verdict to: .quest/<id>/phase_01_plan/arbiter_verdict.md
     NEXT must be: builder (approve) or planner (iterate)
     ```
   - If "claude": use Task tool with `arbiter` agent
   - Parse verdict for NEXT field

6. **Check verdict:**
   - If `NEXT: builder` → Plan approved! Update state: `phase: plan_reviewed`, proceed to **Step 3.5** (Interactive Presentation)
   - If `NEXT: planner` → Check iteration count
     - If `plan_iteration >= max_plan_iterations`: Warn user, ask to proceed anyway or review manually
     - If `auto_approve_phases.plan_refinement` is false: Ask user to approve refinement
     - Otherwise: Loop back to step 1

### Step 3.5: Interactive Plan Presentation

After plan approval, present the plan interactively before proceeding to build.

**On entry:** Update state: `phase: presenting`

**1. Show Brief Summary:**
   Extract a 1-3 sentence summary using this precedence:
   - **Primary:** Extract from the plan's Overview section (the "Problem" and "Impact" lines)
   - **Fallback 1:** If no Overview section exists, use the first non-heading paragraph of the plan (skip YAML frontmatter, skip lines starting with `#`)
   - **Fallback 2:** If no suitable paragraph found, display: "See plan for details:"

   Then display:
   - "Plan approved! Here's a brief summary:"
   - The extracted summary (or fallback text)
   - "Full plan available at: .quest/<id>/phase_01_plan/plan.md"
   - Arbiter verdict summary (NEXT line only)
   - Ask: "Would you like to see the detailed phase-by-phase walkthrough? (yes/no)"

**2. Handle Response:**
   - If user declines ("no", "n", "nope", "skip", "proceed", etc.) -> Update state: `phase: presentation_complete`, then proceed to Step 4 (Build Phase)
   - If user accepts ("yes", "y", "yeah", "sure", "detailed", etc.) -> Continue to phase extraction

**3. Extract Phases from Plan:**
   Parse plan.md to identify phases using these patterns (in order of precedence):

   a. **Explicit phase headers** - Look for:
      - `### Phase 1:` or `### Phase 1 -` (h3 with "Phase N")
      - `## Phase 1:` or `## Phase 1 -` (h2 with "Phase N")
      - `**Phase 1:**` or `**Phase 1 -**` (bold with "Phase N")

   b. **Phases section with list** - Look for:
      - `## Phases` header followed by numbered or bulleted list items
      - Each list item becomes a phase

   c. **Numbered change sections** - Look for:
      - `#### Change 1:` or `### Change 1:`
      - Treat each change as a phase

   d. **Fallback (single-phase)** - If none of the above patterns found:
      - Treat entire Implementation section as a single phase
      - Display with title "Implementation Overview"

**4. Extract Per-Phase Acceptance Criteria:**
   For each identified phase, extract acceptance criteria using these patterns:

   a. **Per-phase AC subheading** - Look within each phase section for:
      - `**Acceptance Criteria:**` or `#### Acceptance Criteria`
      - Extract the list items following this heading

   b. **AC references** - Look for parenthetical references like:
      - `(AC1)`, `(AC2)`, `(Covers AC 3)`, `(Addresses acceptance criterion 1)`
      - Map these to the global Acceptance Criteria section and display those specific items

   c. **Fallback (global ACs)** - If phase has no explicit ACs:
      - Display global acceptance criteria from the plan's main `## Acceptance Criteria` section
      - Prefix with: "This phase contributes to the following acceptance criteria:"

**5. Present Each Phase:**
   For each phase:
   a. Display phase title (e.g., "Phase 1: Add Presentation Logic")
   b. Display phase description/goal (first paragraph of phase section)
   c. Display key implementation details:
      - Files to change (look for file paths or "Files:" subsection)
      - Functions to add/modify (look for function names or "Key Functions:" subsection)
   d. Display acceptance criteria for this phase (from step 4)
   e. Ask: "Questions about this phase? Or changes you'd like to request? (continue/question/change)"

**6. Handle Phase Response:**
   - If "continue" (or "c", "next", "ok", "looks good", etc.) -> Move to next phase, or if last phase: update state `phase: presentation_complete` and proceed to Step 4
   - If "question" (or "q", "?", user asks a question directly) -> Answer the question using plan context, then re-ask: "Any other questions, or ready to continue? (continue/question/change)"
   - If "change" (or "modify", "revise", "update", user requests a change directly) -> Proceed to Change Handling

**7. Change Handling:**
   When user requests changes:
   a. Prompt user: "Please describe the changes you'd like:"
   b. Record the user's response
   c. Create or append to `.quest/<id>/phase_01_plan/user_feedback.md`:
      ```
      ## Change Request (Iteration <plan_iteration + 1>)
      Date: <timestamp>
      Phase: <current phase number or "General">
      Request: <user's change request verbatim>
      ```
   d. **Update state:** `phase: plan`, `status: in_progress`
   e. Display: "Re-running plan with your feedback..."
   f. Return to Step 3, item 1:
      - Planner will be invoked with user_feedback.md included (per Change 1 above)
      - plan_iteration increments as normal
      - Full review cycle (Claude + Codex + Arbiter) runs
      - After approval, Step 3.5 presentation starts fresh from step 1

### Step 4: Build Phase

**Gate check:**
- Read `auto_approve_phases.implementation` from allowlist
- If false: Ask user "Plan approved. Proceed with implementation?"
- Wait for confirmation before continuing

**Build:**

1. **Update state:** `phase: building`, `status: in_progress`, `last_role: builder_agent`

2. **Invoke Builder** (Task tool with `builder` agent):
   - Prompt: Include approved plan + quest brief
   - Wait for response
   - Verify artifacts written

3. **Update state:** `phase: reviewing`

4. Proceed to Step 5

### Step 5: Review Phase

1. **Update state:** `status: in_progress`, `last_role: code_review_agent`

2. **Read review config from allowlist:**
   - `review_mode` (default: `auto`)
   - `fast_review_thresholds.max_files` (default: 5)
   - `fast_review_thresholds.max_loc` (default: 200)
   - `codex_context_digest_path` (default: `.ai/context_digest.md`)

3. **Build a change summary for Codex:**
   - Prefer builder handoff file list (if available in the last response).
   - If missing, compute:
     - File list: `git diff --name-only`
     - Diff stats: `git diff --stat`
     - LOC totals: `git diff --numstat` and sum added + deleted.
   - Use the LOC totals and file count for `review_mode: auto`:
     - If file_count ≤ max_files AND loc_total ≤ max_loc → **fast**
     - Otherwise → **full**

4. **Invoke BOTH Code Reviewers IN PARALLEL** (same message, two tool calls):

   **Claude reviewer** (Task tool with `code-reviewer` agent):
   - Prompt: Include quest brief, plan, and instruction to use git diff
   - Writes to `.quest/<id>/phase_03_review/review_claude.md`

   **Codex reviewer** (mcp__codex__codex) — call in the SAME message:
   - Use the digest path and **mode-specific** prompt:

     **Full mode**:
     ```
     mcp__codex__codex(
       model: "gpt-5.2",
       prompt: "You are the Code Review Agent (Codex).

       Read your instructions: .ai/roles/code_review_agent.md
       Read context digest: <codex_context_digest_path>
       (Optional, full mode only) Read: .skills/BOOTSTRAP.md, AGENTS.md

       Quest: .quest/<id>/quest_brief.md
       Plan: .quest/<id>/phase_01_plan/plan.md

       Changed files: <file list>
       Diff summary: <git diff --stat>

       Review ONLY the files listed above. Use git diff for details.
       Write review to: .quest/<id>/phase_03_review/review_codex.md

       End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
       NEXT: fixer (if issues) or null (if clean)"
     )
     ```
     **Fast mode**:
     ```
     mcp__codex__codex(
       model: "gpt-5.2",
       prompt: "You are the Code Review Agent (Codex).

       Read context digest: <codex_context_digest_path>
       Quest: .quest/<id>/quest_brief.md
       Plan: .quest/<id>/phase_01_plan/plan.md

       Changed files: <file list>
       Diff summary: <git diff --stat>

       Review ONLY the files listed above.
       List up to 5 issues, highest severity first.
       Write review to: .quest/<id>/phase_03_review/review_codex.md

       End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
       NEXT: fixer (if issues) or null (if clean)"
     )
     ```
   - Wait for BOTH responses, verify both review files written

5. **Check verdicts:**
   - If EITHER reviewer says `NEXT: fixer` → Issues found, proceed to Step 6
   - If BOTH say `NEXT: null` → Review passed! Update state: `phase: complete`, go to Step 7

### Step 6: Fix Phase

**Read allowlist:** `gates.max_fix_iterations` (default: 3)

**Gate check:**
- Read `auto_approve_phases.fix_loop` from allowlist
- If false: Ask user "Code review found issues. Proceed with fixes?"

**Loop:**

1. **Update state:** `fix_iteration += 1`, `last_role: fixer_agent`

2. **Invoke Fixer** (Task tool with `fixer` agent):
   - Prompt: Include code review + changed files
   - Wait for response

3. **Re-invoke BOTH Code Reviewers** (same as Step 5)

4. **Check verdict:**
   - If `NEXT: null` → Fixed! Proceed to Step 7
   - If `NEXT: fixer`:
     - If `fix_iteration >= max_fix_iterations`: Warn user, ask to proceed or review manually
     - Otherwise: Loop back to step 1

### Step 7: Complete

1. **Update state:** `phase: complete`, `status: complete`

2. **Create quest journal entry:**
   - Create `docs/quest-journal/` directory if it doesn't exist
   - Write to `docs/quest-journal/<slug>_<YYYY-MM-DD>.md`
   - Include: quest ID, completion date, summary, files changed
   - If quest originated from an idea file:
     - Quote the original idea content under "This is where it all began..."
     - Update the idea file's `## Status` to `implemented`

3. **Show summary:**
   - Quest ID
   - Files changed (from builder/fixer handoffs)
   - Total iterations (plan + fix)
   - Location of artifacts
   - Location of journal entry

4. **Next steps suggestion:**
   ```
   Review changes: git diff
   Commit: git add -p && git commit
   ```

---

## Q&A Loop Pattern

If any agent returns `STATUS: needs_human`:

1. Extract questions from the response (text before `---HANDOFF---`)
2. Present questions to user
3. Collect answers
4. Re-invoke the same agent with answers appended to context
5. Repeat until agent returns `complete` or `blocked`

---

## State File Format

`.quest/<id>/state.json`:

```json
{
  "quest_id": "feature-x_2026-02-02__1430",
  "slug": "feature-x",
  "phase": "plan | plan_reviewed | presenting | presentation_complete | building | reviewing | fixing | complete",
  "status": "pending | in_progress | complete | blocked",
  "plan_iteration": 2,
  "fix_iteration": 0,
  "last_role": "arbiter_agent",
  "last_verdict": "approve | iterate",
  "created_at": "2026-02-02T14:30:00Z",
  "updated_at": "2026-02-02T14:45:00Z"
}
```

---

## Codex MCP Prompt Pattern

**IMPORTANT:** Keep Codex prompts SHORT. Point to files, let Codex read them. Prefer the context digest over full docs.

```markdown
You are the <ROLE>.

Read your instructions: .ai/roles/<role>_agent.md
Read context digest: .ai/context_digest.md
Optional (full mode only): .skills/BOOTSTRAP.md, AGENTS.md

Quest brief: .quest/<id>/quest_brief.md
<other relevant files as paths>

<specific task instruction>

Write output to: .quest/<id>/<path>

When done, output:
---HANDOFF---
STATUS: complete | needs_human | blocked
ARTIFACTS: <files written>
NEXT: <next role or null>
SUMMARY: <one line>
---
```

**Why short prompts?**
- Codex has file access — it can read what it needs
- Large inline prompts cause timeouts and context issues
- Agents should explore the codebase themselves (clean context)
- Matches how Claude subagents work (they read files too)
- The digest captures stable context and reduces repeated reads

---

## Performance: Codex MCP Latency

Codex MCP calls are slower than direct Claude tool use because Codex must:
1. Read multiple files (role instructions, digest, quest brief, plan)
2. Analyze the content
3. Write output file

**To speed up Codex reviews**, use the allowlist review controls:
- `review_mode: fast` → shorter prompts, max 5 bullets
- `review_mode: auto` → fast for small diffs, full for large
- `review_mode: full` → always full context
- `fast_review_thresholds` → tune size cutoff

**Simplification options:**
- Use the context digest instead of full docs
- Remove "Read your instructions:" and give inline instructions instead
- Ask for bullet points instead of full review

**Example minimal prompt:**
```
mcp__codex__codex(
  model: "gpt-5.2",
  prompt: "Review .quest/<id>/phase_01_plan/plan.md

  List any issues (max 5 bullets). Write to .quest/<id>/phase_01_plan/review_codex.md

  End with: ---HANDOFF--- STATUS: complete NEXT: arbiter SUMMARY: <one line>"
)
```

**Tradeoff:** Simpler prompts = faster but less thorough review.

---

## Error Handling

- If an agent fails to produce a handoff: Extract any artifacts from the response, log the error, ask user how to proceed
- If Codex MCP fails: Fall back to Task tool with Claude agent
- If max iterations reached: Stop, show current state, ask user for guidance
- If artifact file missing after agent run: Try to extract from response text and write it

---

## Utility Commands

**`/quest status`** — List all quests with their current phase

**`/quest status <id>`** — Show detailed status for a specific quest

**`/quest allowlist`** — Display current allowlist configuration
