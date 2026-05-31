# Quest Orchestration Skill

Multi-agent workflow for planning, reviewing, building, and fixing features through coordinated agent handoffs.

## Usage

```
/quest "Add a loading skeleton to the candidate list"
$quest "Add a loading skeleton to the candidate list"
/quest "Implement the transparency audit plan"
/quest transparency-v2_2026-02-02__1831
/quest transparency-v2_2026-02-02__1831 "now review the code"
/quest status
```

---

## Procedure

When starting, say: "Now I understand the Quest." Then proceed.

### Step 1: Resume Check

If the user provides a quest ID matching either supported Quest ID format (`<slug>_YYYY-MM-DD__HHMM` or `YYYY-MM-DD_HHMM__<slug>`):
1. Read `.quest/<id>/state.json` and resume from the recorded phase
1a. **Orchestration config migration.** On resume, run `quest_runtime.orchestration.migrate_from_snapshot` before dispatch (it is tested; keep the behavior in one place):
   - **Missing `orchestration.json`** → it is written from `.quest/<id>/logs/allowlist_snapshot.json` (`models`). Only explicitly legacy-compatible newly-introduced roles (`LEGACY_COMPAT_BACKFILL_ROLES`, currently `review-arbiter`) are backfilled from `DEFAULT_MODELS`; a snapshot missing any **other** canonical role (e.g. `builder`) is **malformed** — fail closed, never invent a default (that would bypass the saved per-quest model contract). A structurally invalid snapshot (unreadable, not valid JSON, or no `models` object) is also malformed.
   - **Existing `orchestration.json`** → it is backfilled in place with any newly-introduced canonical roles at their default, preserving every existing value/metadata field, and left byte-identical when nothing is missing — so an in-flight quest that predates a new required role does not fail validation/dispatch on resume.
   - **Never prompt the chooser on resume.**
2. Delegate to `delegation/workflow.md`

If the user says `/quest status` or `$quest status`, handle as a utility command (see `delegation/workflow.md` Utility Commands).

### Step 2: Classify Input (New Quest)

If no quest ID is provided:
1. Read `delegation/router.md`
2. Evaluate the user's input against the 7 substance dimensions
3. Produce the routing decision JSON: `{route, confidence (0.0-1.0), risk_level, complexity, ui_work, ui_work_evidence, reason, missing_information}`

### Step 2b: Second Model Availability Probe (New Quest Only)

**MANDATORY — run before Step 3.** From the repository root, execute the preflight check:

```bash
./scripts/quest_preflight.sh --orchestrator claude   # if you are Claude
./scripts/quest_preflight.sh --orchestrator codex    # if you are Codex
```

The script is at the **repository root** (`scripts/quest_preflight.sh`), NOT inside the skill directory.

1. Parse the JSON output. Cache `available` as a boolean for the session.
2. If `available` is false:
   - Display **every line** of the `warning` array from the JSON output as a blockquote before route options. The array contains the heading, setup commands, and instructions — show them all.
   - Then pause quest startup and offer these choices:
     ```
     Second-model setup is not currently available.

     Options:
       1. Fix it now and rerun preflight (recommended)
       2. Continue with a single-model quest for this run
       3. Cancel
     ```
   - If the user selects "fix it now", do not create the quest folder yet. Let them complete the remediation, then rerun Step 2b.
   - For Codex-led sessions, prefer `claude auth login` as the default interactive fix when Claude CLI auth is missing. If the warning indicates a restricted sandbox may be hiding auth state, rerun the preflight with whatever permissions are needed to read the real Claude CLI auth state.
   - For Claude-led sessions, use the warning lines to guide Codex MCP install/auth remediation before rerunning Step 2b.
   - Append "(Claude-only)" or "(Codex-only)" to solo/full quest option labels.
3. If `available` is true, proceed normally.
4. For Codex-led sessions, if the JSON includes `runtime_requirement: "host_context"`, treat that as authoritative:
   - Claude bridge probing and Claude-designated role execution must use the same host-visible context that can see Claude CLI auth.
   - Do not assume a sandbox-local `claude auth status` result is enough.
   - The script retains a successful probe in `.quest/cache/claude_bridge_codex.json` by default, so a recent host-verified success can be reused across quest starts without repeating browser login.

This result carries into workflow.md — do not re-probe there.

### Step 3: Route

Based on the router decision:

**If route = "questioner":**
1. Read `delegation/questioner.md`
2. Follow the questioning procedure (1-3 questions at a time, max 10 total)
3. Collect the structured summary
4. Re-run router (Step 2) with enriched input (original prompt + summary)
5. If route is now "workflow", "solo", or "manual": proceed to the matching handler below
6. If route is still "questioner": allow one more short questioning pass (10-question total cap still applies), then proceed to workflow regardless

**If route = "manual":**
1. Present the routing classification with override options:
   ```
   Quest Assessment:
     Risk: <risk_level>
     Complexity: <complexity>
     Recommended: manual (no pipeline)

   Options:
     1. Just do it (recommended) — no quest pipeline
     2. Run as solo quest — single reviewer, lightweight
     3. Run as full quest — dual reviews, arbiter
     4. Cancel
   ```
2. If user selects "just do it": exit quest system. No quest folder is created. The user works directly.
3. If user selects "solo" or "full": proceed to the matching handler below with the overridden route.
4. If user selects "cancel": exit quest system immediately. No quest folder, journaling, or celebration.

**If route = "solo":**
1. Present the routing classification with override options:
   ```
   Quest Assessment:
     Risk: <risk_level>
     Complexity: <complexity>
     Recommended route: solo (lightweight quest)

   Options:
     1. Run as solo quest (recommended) — single plan review, single code review
     2. Run as full quest — dual reviews, arbiter, the works
     3. Cancel
   ```
2. If user selects "solo": create quest folder with `quest_mode: "solo"`, proceed to workflow
3. If user selects "full": create quest folder with `quest_mode: "workflow"`, proceed to workflow
4. If user selects "cancel": exit quest system immediately. No quest folder, journaling, or celebration.

**If route = "workflow":**
1. Present the routing classification with override options:
   ```
   Quest Assessment:
     Risk: <risk_level>
     Complexity: <complexity>
     Recommended route: full quest

   Options:
     1. Run as full quest (recommended)
     2. Run as solo quest (lighter) — single reviewer
     3. Cancel
   ```
2. If user selects "full": create quest folder with `quest_mode: "workflow"`, proceed to workflow
3. If user selects "solo": create quest folder with `quest_mode: "solo"`, proceed to workflow
4. If user selects "cancel": exit quest system immediately. No quest folder, journaling, or celebration.

**After route selection (solo or workflow):**
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
2. Display the UI classification:
   - If `ui_work` is `true`: **"UI work: yes — <ui_work_evidence>"**
   - If `ui_work` is `false`: "UI work: no"
   - If `ui_work` is missing or not a boolean: "UI work: malformed router data — treating as no until corrected"
3. If the quest went through the questioner path, note this: "Questioning phase completed — gaps addressed before planning."
4. Wait for user acknowledgment before proceeding (for high risk only). For medium and low, display and continue.

### Quest Folder Structure

`.quest/` contains:
- Active quest directories (created per-run)
- `archive/` — completed quests moved here after journaling (see Step 7 in workflow.md)
- `audit.log` — persistent log across all quest runs

### Quest Folder Creation

1. Generate a slug (lowercase, hyphenated, 2-5 words) and inform the user
2. **Ask the user** which workspace mode to use for this quest. Present these options:
   - **branch** — create a `quest/<slug>` feature branch (switches away from current branch)
   - **worktree** — create a `quest/<slug>` branch in a separate worktree (current branch stays checked out)
   - **none** — stay on the current branch as-is
   
   If already on a non-default branch, inform the user and skip the prompt — the quest will use the current branch.
   If the current workspace is not inside a git repository, skip the prompt — Quest must stay in the current workspace with `vcs_available: false`.

3. Run quest startup branch preparation with the user's choice:
   - Execute: `python3 scripts/quest_startup_branch.py --slug <slug> --mode <choice>`
   - Parse the JSON result
   - If `status` is `"blocked"`: show the returned `message`, do NOT create the quest folder yet, and stop for the user to resolve the git state or config
   - If `status` is `"created"` or `"skipped"`: continue and surface the returned `message` to the user
   - Surface the returned `quest_symlink` outcome after startup:
     - `created`: note that the worktree `.quest/` symlink was created.
     - `present`: note that the worktree `.quest/` symlink was already present.
     - `migrated`: tell the user that an existing worktree `.quest/` was safely migrated into the shared store.
     - `conflict`: warn the user that same-name `.quest/` entries were preserved under `.quest_conflicts/` and need manual review.
     - `n/a`: no linked-worktree symlink action was needed.
   - Record these fields for `state.json` initialization:
     - `vcs_available`
     - `branch`
     - `branch_mode`
     - `worktree_path` (if present)
     - `quest_symlink`
4. Read `quest_id_format` from `.ai/allowlist.json` using `quest_runtime.quest_ids.load_quest_id_format`; missing config defaults to `slug-first`.
5. Create the Quest ID with `quest_runtime.quest_ids.format_quest_id(slug, datetime.now(), quest_id_format)`. Pass a `datetime.datetime` object, not a preformatted timestamp string; the helper formats date/time internally.
   - Default slug-first: `<slug>_YYYY-MM-DD__HHMM`
   - Optional date-first: `YYYY-MM-DD_HHMM__<slug>`
6. Create `.quest/<id>/` with subfolders:
   `phase_01_plan/`, `phase_02_implementation/`, `phase_03_review/`, `logs/`
7. Write quest brief to `.quest/<id>/quest_brief.md` including:
   - User input (original prompt)
   - Questioner summary (if questioning occurred)
   - **Router classification JSON** (the final routing decision that sent the quest to workflow). This is the classification produced by the most recent router evaluation — if the router ran twice (once before questioning, once after), record the second (final) classification.
8. Copy `.ai/allowlist.json` to `.quest/<id>/logs/allowlist_snapshot.json`
8.5. **Per-quest orchestration chooser.** Display the active `models` block from `.ai/allowlist.json`. For each role unused in the chosen `quest_mode` (e.g., `plan-reviewer-b`, `arbiter`, `code-reviewer-b`, and `review-arbiter` in solo mode), append `  (unused in this mode)` after the model name. Then prompt:

   ```
   Quest orchestration for `<slug>` (<mode>):

     planner           <model>
     plan-reviewer-a   <model>
     plan-reviewer-b   <model>  (unused in this mode)   [solo only]
     arbiter           <model>  (unused in this mode)   [solo only]
     builder           <model>
     code-reviewer-a   <model>
     code-reviewer-b   <model>  (unused in this mode)   [solo only]
     review-arbiter    <model>  (unused in this mode)   [solo only]
     fixer             <model>

   Customize for this quest only? [y/N]
   ```

   **On N (default; single Enter):** before writing, validate every active-role model from the expanded default block against the Step 2b preflight result using the same availability rules as overrides below. If Step 2b was healthy, reject any unavailable active-role model as malformed config and stop before dispatch. If the user explicitly chose the single-model continuation after Step 2b failed, remap unavailable active-role models to this orchestrator's native runtime (`claude` for Claude-led sessions, `gpt-5.5` for Codex-led sessions) before writing so `orchestration.json` only contains runnable active-role assignments. Then write `.quest/<id>/orchestration.json` with:
   - `version: 1`
   - `models`: `.ai/allowlist.json` `.models` expanded to all 9 canonical keys; omitted keys use the documented defaults (`planner=claude`, `plan-reviewer-a=claude`, `plan-reviewer-b=gpt-5.5`, `arbiter=claude`, `builder=gpt-5.5`, `code-reviewer-a=claude`, `code-reviewer-b=gpt-5.5`, `review-arbiter=claude`, `fixer=gpt-5.5`)
   - `source: "default"`
   - `overridden_roles: []`
   - `preflight_validated_at: <ISO8601 now>`

   **On Y:** present the shorthand override prompt:

   ```
   Enter overrides as comma-separated role=model pairs.
   Roles: planner, plan-reviewer-a, plan-reviewer-b, arbiter, builder, code-reviewer-a, code-reviewer-b, review-arbiter, fixer
   Models: any model name your preflight reports as available (e.g., claude, codex, gpt-5.5)
   Example: planner=claude, builder=claude
   (empty input = no overrides, equivalent to N)

   Overrides:
   ```

   **Parse contract (each full override-line submission is one attempt; cap re-prompts at 3, abort on the 4th rejection):**

   1. **Tokenize.** Split the outer input on `,`. Trim each resulting piece. Empty pieces are silently skipped (so a trailing comma is fine).
   2. **One `=` per piece.** Each non-empty piece must contain exactly one `=` character. Reject pieces with zero `=` or two or more `=` characters using `Override syntax error: '<piece>' (expected role=model). Re-enter overrides.`
   3. **Role name (LHS of `=`).** Trim, normalize to lowercase, then exact-match against the canonical role list (`planner`, `plan-reviewer-a`, `plan-reviewer-b`, `arbiter`, `builder`, `code-reviewer-a`, `code-reviewer-b`, `review-arbiter`, `fixer`). Reject unknown names with `Unknown role: <input> (valid: planner, plan-reviewer-a, plan-reviewer-b, arbiter, builder, code-reviewer-a, code-reviewer-b, review-arbiter, fixer)` and re-prompt.
   4. **Model name (RHS of `=`).** Trim. Lexeme is `[^,=]+` non-empty. No further character constraints — `gpt-5.5`, `claude-opus-4.7`, `o1-mini` and similar tokens are all accepted at the parser level.
   5. **Unused-in-mode roles** (`plan-reviewer-b`, `arbiter`, `code-reviewer-b`, and `review-arbiter` in solo). Warn `Role <name> is unused in <mode> mode — override ignored.` and skip the override; do not record it in `overridden_roles`.
   6. **Availability check.** Classify Claude-family model names as `claude` and `claude-*` (for example `claude-opus-4.7`); every other model name is Codex-backed. In Claude-led sessions, Claude-family models are available and Codex-backed models require Codex MCP availability from the Step 2b preflight result. In Codex-led sessions, Codex-backed models are available and Claude-family models require the top-level `available` boolean from the Step 2b preflight result, which represents Claude bridge availability. If the relevant cache/result is missing or stale (older than the preflight TTL), rerun `scripts/quest_preflight.sh --orchestrator <self>` once and reuse the fresh result. Reject unavailable models with the preflight `warning` text and re-prompt the override line.
   7. **Re-prompt cap.** An "attempt" is one full override-line submission, not one role=model pair. Three rejected attempts in a row abort startup with `Override validation failed after 3 attempts — quest startup cancelled.`

   Once all overrides pass validation, build the merged `models` block (defaults from `.ai/allowlist.json`, with omitted role keys filled from the documented defaults above, overlaid with the validated overrides — `overridden_roles` excludes ignored-because-unused entries) and write `.quest/<id>/orchestration.json` with:
   - `version: 1`
   - `models`: merged block (all 9 keys present; unused-in-mode roles still carry the default value)
   - `source: "overridden"`
   - `overridden_roles`: list of role names that were actually overridden
   - `preflight_validated_at: <ISO8601 now>`

9. Initialize `state.json`:
   ```json
   {
     "quest_id": "<id>",
     "slug": "<slug>",
     "phase": "plan",
     "status": "pending",
     "quest_mode": "workflow",
     "vcs_available": true,
     "branch": "quest/<slug> or current branch",
     "branch_mode": "branch | worktree | none",
     "worktree_path": "/absolute/path/to/worktree (worktree mode only)",
     "quest_symlink": "created | present | migrated | conflict | n/a",
     "plan_iteration": 0,
     "fix_iteration": 0,
     "created_at": "<timestamp>",
     "updated_at": "<timestamp>"
   }
   ```
   Set `quest_mode` to the user's final selection: `"workflow"` (default) or `"solo"`. This field is read by `workflow.md` to determine agent dispatch and by `validate-quest-state.sh` for artifact checks.
   `vcs_available` must be copied directly from `scripts/quest_startup_branch.py` output. Do not infer it from `branch_mode`.
   `branch_mode` records the actual startup mode used for this quest run after no-op handling. If Quest starts on an existing feature branch, set `branch_mode` to `"none"` and record that branch in `branch`.
   `quest_symlink` must be copied directly from `scripts/quest_startup_branch.py` output. Do not infer it from `branch_mode` or `worktree_path`.

### UI Work Propagation

When the recorded router classification has `ui_work: true`, downstream dispatch must load the UX skills:

- Planner, builder, fixer agents auto-load `.skills/ux-context/SKILL.md`
- Plan-reviewer and code-reviewer agents auto-load `.skills/ux-review/SKILL.md`

The agent files in `.skills/quest/agents/` enforce this — the orchestrator's job is to preserve the full router JSON in the brief so each agent can read it.
