## Procedure

When starting, say: "Now I understand the Quest." Then proceed directly with the steps below.

Follow these steps in order. After each step that modifies state, update `.quest/<id>/state.json`.

### Defaults (Opinionated)

Quest is opinionated: default to **thorough**, but be **progressive** and avoid wasted repo exploration.

- **Intake before exploration:** Do not start repo exploration until the quest brief is stable (Step 1 complete), unless the user explicitly asks you to “just run with it”.
- **Progressive exploration:** Start from the context digest + allowlist + plan. Only deep-dive into the repo when the plan/implementation needs it.
- **Timebox structure discovery:** Avoid full repo inventories. Do a quick top-level scan + targeted `rg` searches instead of browsing directory-by-directory.
- **If the user wants speed:** Offer to proceed with minimal questions + explicit assumptions (fast intake).

### Context Retention Rule

After every subagent invocation (`mcp__codex__codex`), the orchestrator retains ONLY:
1. The **artifact path(s)** from the ARTIFACTS line of the handoff
2. The **one-line SUMMARY** from the SUMMARY line of the handoff
3. The **STATUS** and **NEXT** values for routing decisions

Everything else from the subagent response (plan text, review content, build output, fix details) is not carried forward in the orchestrator's working context. The orchestrator does not retain, summarize, or re-process subagent output beyond these handoff fields.

**Bounded exceptions** (content is used immediately and not carried forward):
1. **Step 3.5 (Interactive Plan Presentation):** The orchestrator loads plan content for human interaction. This is bounded and deliberate.
2. **Q&A loop (`needs_human`):** The orchestrator extracts questions from the subagent response text (before `---HANDOFF---`) to present to the user. The question text is used for the human exchange and not retained after re-invocation.
3. **Artifact recovery:** If an expected artifact file (e.g., `plan.md`) is not written by a subagent, the orchestrator extracts it from the response and writes it to disk. The response content is discarded immediately after writing.

**Why this works:** Every subagent reads files itself. The orchestrator's job is routing and state management, not content relay.

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

### Step 1: Precondition Check

This workflow expects to be invoked with a quest brief already prepared.

1. Verify `.quest/<id>/quest_brief.md` exists
2. If it does not exist, STOP and report error: "Quest brief not found. The routing layer should have created it before invoking workflow."
3. If it exists, proceed to Step 2

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

2. **Invoke Planner** (`mcp__codex__codex(model: "gpt-5.3-codex")`):
   - Prompt: Reference file paths only, do not embed artifact content:
     - Quest brief: `.quest/<id>/quest_brief.md`
     - Arbiter verdict (iteration 2+): `.quest/<id>/phase_01_plan/arbiter_verdict.md`
     - User feedback (if present): `.quest/<id>/phase_01_plan/user_feedback.md`
   - Require the prompt to include:
     - Write plan to: `.quest/<id>/phase_01_plan/plan.md`
     - End with: `---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY`
     - `NEXT: plan_review`
   - Wait for response
   - Verify `.quest/<id>/phase_01_plan/plan.md` exists
   - If not written, extract from response and write it

3. **Read review config from allowlist:**
   - `review_mode` (default: `auto`)
   - `fast_review_thresholds` (not used for plan review)
   - `codex_context_digest_path` (default: `.ai/context_digest.md`)
   - For plan review: treat `auto` as `full`. Use `fast` only if explicitly set.

4. **Invoke BOTH Plan Reviewers IN PARALLEL** (same message, two Codex tool calls):

   Run the same review prompt twice with different output paths:
   - Slot A output: `.quest/<id>/phase_01_plan/review_claude.md` (compatibility filename)
   - Slot B output: `.quest/<id>/phase_01_plan/review_codex.md`

   Use the digest path and **mode-specific** prompt for each slot:

   **Full mode** (default for plan review):
   ```
   mcp__codex__codex(
     model: "gpt-5.3-codex",
     prompt: "You are the Plan Review Agent (Codex).

     Read your instructions: .ai/roles/plan_review_agent.md
     Read context digest: <codex_context_digest_path>
     (Optional, full mode only, if needed) Read: .skills/BOOTSTRAP.md, AGENTS.md

     Quest brief: .quest/<id>/quest_brief.md
     Plan to review: .quest/<id>/phase_01_plan/plan.md

     Write your review to: <slot output path>

     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: arbiter"
   )
   ```
   **Fast mode** (only if `review_mode: fast`):
   ```
   mcp__codex__codex(
     model: "gpt-5.3-codex",
     prompt: "You are the Plan Review Agent (Codex).

     Read context digest: <codex_context_digest_path>
     Quest brief: .quest/<id>/quest_brief.md
     Plan to review: .quest/<id>/phase_01_plan/plan.md

     List up to 5 issues, highest severity first.
     Write your review to: <slot output path>

     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: arbiter"
   )
   ```
   - Wait for BOTH responses, verify both review files written

5. **Invoke Arbiter** (`mcp__codex__codex(model: "gpt-5.3-codex")`):
   - Use a short prompt with path references only:
     ```
     You are the Arbiter Agent.

     Read your instructions: .ai/roles/arbiter_agent.md

     Quest brief: .quest/<id>/quest_brief.md
     Plan: .quest/<id>/phase_01_plan/plan.md
     Review A: .quest/<id>/phase_01_plan/review_claude.md
     Review B: .quest/<id>/phase_01_plan/review_codex.md

     Write verdict to: .quest/<id>/phase_01_plan/arbiter_verdict.md
     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: builder (approve) or planner (iterate)
     ```
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
      - Planner will be invoked with user_feedback.md referenced (per Step 3, item 2 -- Planner invocation above)
      - plan_iteration increments as normal
      - Full review cycle (Codex slot A + Codex slot B + Arbiter) runs
      - After approval, Step 3.5 presentation starts fresh from step 1

### Step 4: Build Phase

**Gate check:**
- Read `auto_approve_phases.implementation` from allowlist
- If false: Ask user "Plan approved. Proceed with implementation?"
- Wait for confirmation before continuing

**Build:**

1. **Update state:** `phase: building`, `status: in_progress`, `last_role: builder_agent`

2. **Invoke Builder** (`mcp__codex__codex(model: "gpt-5.3-codex")`):
   - Prompt: Reference file paths only, do not embed content:
     - Approved plan: `.quest/<id>/phase_01_plan/plan.md`
     - Quest brief: `.quest/<id>/quest_brief.md`
   - Require the prompt to include:
     - Write output artifacts under: `.quest/<id>/phase_02_implementation/`
     - End with: `---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY`
     - `NEXT: code_review`
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
   - Compute from git (the canonical source for what changed):
     - File list: `git diff --name-only`
     - Diff stats: `git diff --stat`
     - LOC totals: `git diff --numstat` and sum added + deleted.
   - Use the LOC totals and file count for `review_mode: auto`:
     - If file_count ≤ max_files AND loc_total ≤ max_loc → **fast**
     - Otherwise → **full**

4. **Invoke BOTH Code Reviewers IN PARALLEL** (same message, two Codex tool calls):

   Run the same review prompt twice with different output paths:
   - Slot A output: `.quest/<id>/phase_03_review/review_claude.md` (compatibility filename)
   - Slot B output: `.quest/<id>/phase_03_review/review_codex.md`

   Use the digest path and **mode-specific** prompt for each slot:

   **Full mode**:
   ```
   mcp__codex__codex(
     model: "gpt-5.3-codex",
     prompt: "You are the Code Review Agent (Codex).

     Read your instructions: .ai/roles/code_review_agent.md
     Read context digest: <codex_context_digest_path>
     (Optional, full mode only, if needed) Read: .skills/BOOTSTRAP.md, AGENTS.md

     Quest: .quest/<id>/quest_brief.md
     Plan: .quest/<id>/phase_01_plan/plan.md

     Changed files: <file list>
     Diff summary: <git diff --stat>

     Review ONLY the files listed above. Use git diff for details.
     Write review to: <slot output path>

     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: fixer (if issues) or null (if clean)"
   )
   ```
   **Fast mode**:
   ```
   mcp__codex__codex(
     model: "gpt-5.3-codex",
     prompt: "You are the Code Review Agent (Codex).

     Read context digest: <codex_context_digest_path>
     Quest: .quest/<id>/quest_brief.md
     Plan: .quest/<id>/phase_01_plan/plan.md

     Changed files: <file list>
     Diff summary: <git diff --stat>

     Review ONLY the files listed above.
     List up to 5 issues, highest severity first.
     Write review to: <slot output path>

     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: fixer (if issues) or null (if clean)"
   )
   ```
   - **Note:** The `<file list>` and `<git diff --stat>` values embedded in these prompts are intentional small metadata (summary statistics and file names, typically a few lines). This is operational data for scoping the review, not subagent artifact content, and does not conflict with the Context Retention Rule.
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

2. **Invoke Fixer** (`mcp__codex__codex(model: "gpt-5.3-codex")`):
   - Prompt: Reference file paths only, do not embed content:
     - Code review A: `.quest/<id>/phase_03_review/review_claude.md`
     - Code review B: `.quest/<id>/phase_03_review/review_codex.md`
     - Changed files: <file list from git diff>
     - Quest brief: `.quest/<id>/quest_brief.md`
     - Plan: `.quest/<id>/phase_01_plan/plan.md`
   - Require the prompt to include:
     - Write feedback to: `.quest/<id>/phase_03_review/review_fix_feedback_discussion.md`
     - End with: `---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY`
     - `NEXT: code_review`
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
   - Append a row to `docs/quest-journal/README.md` index table (date, quest link, one-line outcome)
   - If quest originated from an idea file:
     - Quote the original idea content under "This is where it all began..."
     - Update the idea file's `## Status` to `implemented`

3. **Archive the quest working directory:**
   - Create `.quest/archive/` if it doesn't exist
   - Move `.quest/<id>/` to `.quest/archive/<id>/`
   - The journal entry in `docs/quest-journal/` is the permanent record; the archive preserves raw artifacts for reference
   - `.quest/` root should only contain active quests, `archive/`, and `audit.log`

4. **Show summary:**
   - Quest ID
   - Files changed (from `git diff --name-only` and `state.json` artifact paths)
   - Total iterations (plan + fix, from `state.json`)
   - Location of artifacts (now in `.quest/archive/<id>/`)
   - Location of journal entry

5. **Next steps suggestion:**
   ```
   Review changes: git diff
   Commit: git add -p && git commit
   ```

5. **Check for Quest updates:**
   After the quest completes, check if a Quest update is available (if enough time has passed since the last check).

   **Configuration:**
   - Read `update_check` from `.ai/allowlist.json`:
     - `enabled` (default: true) - set to false to disable update checks
     - `interval_days` (default: 7) - minimum days between checks

   **Logic:**
   ```bash
   # Check for Quest updates (after completion)
   ALLOWLIST_FILE=".ai/allowlist.json"
   LAST_CHECK_FILE=".quest-last-check"
   NOW=$(date +%s)

   # Read config (default enabled=true, interval=7)
   UPDATE_ENABLED=$(jq -r '.update_check.enabled // true' "$ALLOWLIST_FILE" 2>/dev/null)
   INTERVAL_DAYS=$(jq -r '.update_check.interval_days // 7' "$ALLOWLIST_FILE" 2>/dev/null)

   if [ "$UPDATE_ENABLED" != "false" ]; then
     INTERVAL_SECONDS=$((INTERVAL_DAYS * 24 * 60 * 60))
     SHOULD_CHECK=true

     if [ -f "$LAST_CHECK_FILE" ]; then
       LAST_CHECK=$(cat "$LAST_CHECK_FILE")
       if [ $((NOW - LAST_CHECK)) -lt $INTERVAL_SECONDS ]; then
         SHOULD_CHECK=false
       fi
     fi

     if $SHOULD_CHECK; then
       if [ -f "scripts/quest_installer.sh" ] && [ -f ".quest-version" ]; then
         LOCAL_SHA=$(cat .quest-version 2>/dev/null || echo "")
         UPSTREAM_SHA=$(git ls-remote "https://github.com/KjellKod/quest.git" "refs/heads/main" 2>/dev/null | cut -f1)

         if [ -n "$LOCAL_SHA" ] && [ -n "$UPSTREAM_SHA" ] && [ "$LOCAL_SHA" != "$UPSTREAM_SHA" ]; then
           echo ""
           echo -n "Quest update available. Update now? [Y/n] "
           read -r response
           if [ "$response" != "n" ] && [ "$response" != "N" ]; then
             ./scripts/quest_installer.sh
           fi
         fi
         echo "$NOW" > "$LAST_CHECK_FILE"
       fi
     fi
   fi
   ```

   **Behavior:**
   - If `update_check.enabled` is `false`, skip entirely
   - If `.quest-last-check` exists and is recent (within `interval_days`), skip (no network call)
   - Compare local `.quest-version` SHA with upstream via `git ls-remote`
   - If different, prompt: "Quest update available. Update now? [Y/n]"
   - If user accepts (Y or Enter), run the installer
   - Update `.quest-last-check` with current timestamp (regardless of update availability)
   - Network errors are silently ignored (graceful degradation)

---

## Q&A Loop Pattern

If any agent returns `STATUS: needs_human`:

1. Extract questions from the response (text before `---HANDOFF---`) -- this is an intentional, bounded content read for human interaction, similar to Step 3.5
2. Present questions to user
3. Collect answers
4. Re-invoke the same agent with answers appended to context, referencing the same artifact paths
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
Optional (full mode only, if needed): .skills/BOOTSTRAP.md, AGENTS.md

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
- Agents should do **targeted** exploration guided by the quest brief/plan (avoid full-repo inventory)
- The digest captures stable context and reduces repeated reads

---

## Performance: Codex MCP Latency

Codex MCP calls can be slower when each run must:
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
  model: "gpt-5.3-codex",
  prompt: "Review .quest/<id>/phase_01_plan/plan.md

  List any issues (max 5 bullets). Write to .quest/<id>/phase_01_plan/review_codex.md

  End with: ---HANDOFF--- STATUS: complete ARTIFACTS: .quest/<id>/phase_01_plan/review_codex.md NEXT: arbiter SUMMARY: <one line>"
)
```

**Tradeoff:** Simpler prompts = faster but less thorough review.

---

## Error Handling

- If an agent fails to produce a handoff: Extract any artifacts from the response, log the error, ask user how to proceed
- If Codex MCP fails: mark the step `blocked`, surface the failure, and ask user whether to retry
- If max iterations reached: Stop, show current state, ask user for guidance
- If artifact file missing after agent run: Try to extract from response text and write it

---

## Utility Commands

**`/quest status`** — List all quests with their current phase

**`/quest status <id>`** — Show detailed status for a specific quest

**`/quest allowlist`** — Display current allowlist configuration
