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
1. Read `.quest/<id>/state.json` and resume from the recorded phase. If that file does not exist but `.quest/archive/<id>/` does, the quest is complete and archived — tell the user so (pointing at the journal entry in `docs/quest-journal/`) instead of failing; archived quests are not resumable.
1a. **Orchestration config migration.** On resume, run `quest_runtime.orchestration.migrate_from_snapshot` before dispatch (it is tested; keep the behavior in one place):
   - **Missing `orchestration.json`** → it is written from `.quest/<id>/logs/allowlist_snapshot.json` (`models`). Only explicitly legacy-compatible newly-introduced roles (`LEGACY_COMPAT_BACKFILL_ROLES`, currently `review-arbiter`) are backfilled from `DEFAULT_MODELS`; a snapshot missing any **other** canonical role (e.g. `builder`) is **malformed** — fail closed, never invent a default (that would bypass the saved per-quest model contract). A structurally invalid snapshot (unreadable, not valid JSON, or no `models` object) is also malformed.
   - **Existing `orchestration.json`** → it is backfilled in place with any newly-introduced canonical roles at their default and with the Claude transport keys (`claude_role_transport: "auto"`, `claude_transport_resolved: null`, `claude_transport_downgraded: false`) when missing, preserving every existing value/metadata field, and left byte-identical when nothing is missing — so an in-flight quest that predates a new required role or the transport keys does not fail validation/dispatch on resume.
   - Preserve saved `codex_auth_mode`; missing legacy mode means `cached`, never import a new allowlist auth choice on resume. Pass the saved mode to Claude-led preflight. An explicit later auth change requires probing that choice and saving it before dispatch.
   - **Never prompt the chooser on resume.**
2. Delegate to `delegation/workflow.md`

If the user says `/quest status` or `$quest status`, handle as a utility command (see `delegation/workflow.md` Utility Commands).

### Step 2: Classify Input (New Quest)

If no quest ID is provided:
1. Read `delegation/router.md`
2. Evaluate the user's input against the 7 substance dimensions
3. Produce the routing decision JSON: `{route, confidence (0.0-1.0), risk_level, complexity, ui_work, ui_work_evidence, reason, missing_information}`

### Step 2b: Second Model Availability Probe (New Quest Only)

**MANDATORY, run before Step 3.** Resolve Codex auth before checking readiness: explicit session/user choice via `--codex-auth` wins, otherwise `.ai/allowlist.json` `codex_auth_mode`, otherwise `cached`. Validate `cached|api-key`; a present key alone never selects billing. An API-key-only user can select `api-key` in the allowlist or startup request before this probe, without a cached login.

Run the preflight script from the installation root, or invoke it by absolute installed path when target cwd differs:

```bash
./scripts/quest_preflight.sh --orchestrator claude --codex-auth <resolved-mode>   # if you are Claude
./scripts/quest_preflight.sh --orchestrator codex    # if you are Codex
```

The script is under the **installation root** (`scripts/quest_preflight.sh`), NOT inside the skill directory. Target cwd remains the intended workspace.

1. Parse the JSON output. Cache `available` as a boolean for the session. For Claude-led probes, retain the resolved `checks.codex_auth_mode` through routing for the per-quest orchestration chooser (Quest Folder Creation, step 8.5), together with these exact checks: `codex_cli_installed`, `codex_exec_supported`, `codex_runner_available`, `codex_auth_mode`, `codex_auth_ready`, `codex_auth_kind`, `codex_auth_reason`. `available` requires CLI, exec, helper and selected-auth readiness; `inference_verified: false` means no model call was made. API-key readiness does not prove key validity. MCP registration does not contribute to readiness.
2. If `available` is false:
   - Display **every line** of the `warning` array from the JSON output as a blockquote before route options. The array contains the heading, setup commands, and instructions — show them all.
   - Then pause quest startup and offer these choices:
     ```
     Second-model setup is not currently available.

     Options:
       1. Fix it now and rerun preflight (recommended)
       2. Use the Claude bridge for this run (API-metered) — Codex-led sessions only
       3. Continue with a single-model quest for this run
       4. Cancel
     ```
   - **Option 2 applies only to Codex-led sessions.** There, `available: false` means the Claude background-agent transport could not be proven, and the bridge is the alternate (API-metered) Claude transport. In a Claude-led session, `available: false` instead means the Codex CLI runner or selected authentication is unavailable — the bridge is irrelevant, so omit option 2, renumber the remaining choices, and route the user to CLI installation/selected-auth remediation (fix), single-model, or cancel.
   - If the user selects "fix it now", do not create the quest folder yet. Let them complete the remediation, then rerun Step 2b.
   - If this is a Codex-led session with `claude_role_transport` unset or `auto`, the common remediation is: `claude --dangerously-skip-permissions`; accept the prompt; exit Claude; return here and rerun preflight.
   - If the user selects "Use the Claude bridge" (Codex-led sessions only), make the bridge opt-in explicit for this run before creating the quest folder: rerun preflight with `QUEST_CLAUDE_ROLE_TRANSPORT=bridge ./scripts/quest_preflight.sh --orchestrator codex`, show the API-metering warning, and carry that bridge preflight result into orchestration writing (`claude_role_transport: "bridge"`, `claude_transport_resolved: "bridge"`). If that bridge probe fails too, return to these options.
   - For Codex-led sessions, prefer `claude auth login` as the default interactive fix when Claude CLI auth is missing. If the warning indicates a restricted sandbox may be hiding auth state, rerun the preflight with whatever permissions are needed to read the real Claude CLI auth state.
   - For Claude-led sessions, use the warning lines to guide Codex CLI installation and selected-auth remediation before rerunning Step 2b.
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

   Use these defaults? [Y/n]
   ```

   **On Y (default; single Enter):** before writing, validate every active-role model from the expanded default block against the Step 2b preflight result using the same availability rules as overrides below. If Step 2b was healthy, reject any unavailable active-role model as malformed config and stop before dispatch. If the user explicitly chose the single-model continuation after Step 2b failed, remap unavailable active-role models to this orchestrator's native runtime (`claude` for Claude-led sessions, `CODEX_NATIVE_FALLBACK_MODEL` from `quest_runtime.orchestration` for Codex-led sessions) before writing so `orchestration.json` only contains runnable active-role assignments. Then write `.quest/<id>/orchestration.json` with:
   - `version: 1`
   - `models`: `.ai/allowlist.json` `.models` expanded to all 9 canonical keys by `quest_runtime.orchestration.build_default_models`; omitted keys use the shipped `DEFAULT_MODELS` fallback generated from the source allowlist. The allowlist is the repo-configured startup default; do not restate the literal fallback matrix in this procedural skill.
   - `claude_role_transport`: the transport policy selected in Step 2b — `"bridge"` when the user explicitly chose the bridge option (including a per-run `QUEST_CLAUDE_ROLE_TRANSPORT=bridge` selection that was not written to `.ai/allowlist.json`), otherwise from `.ai/allowlist.json` (default `"auto"`). Persist the resolved opt-in so a bridge choice survives resume; never record `"auto"` alongside `claude_transport_resolved: "bridge"`.
   - `claude_transport_resolved`: the `transport` field from the Step 2b preflight result (Codex-led sessions; `null` otherwise)
   - `claude_transport_downgraded`: compatibility field; write `false` for new runs (Codex-led preflight also emits `false`)
   - `codex_auth_mode`: persist the resolved Step 2b `checks.codex_auth_mode`, not a later allowlist re-read; pass it as `codex_auth_mode` to `write_default_from_allowlist`. In Codex-led startup retain the explicitly resolved mode for any later Claude-led resume; native Codex dispatch continues using the host identity.
   - `codex_reasoning_effort`: copy the optional allowlist value verbatim and pass it to `write_default_from_allowlist`; validate with `validate_codex_reasoning_effort`. Omit it for older allowlists with no setting. Show the selected effort beside the model table before accepting defaults.
   - `source: "default"`
   - `overridden_roles: []`
   - `preflight_validated_at: <ISO8601 now>`

   **On N:** present the shorthand override prompt:

   ```
   Enter overrides as comma- or newline-separated role=model pairs or a JSON models object.
   Roles: planner, plan-reviewer-a, plan-reviewer-b, arbiter, builder, code-reviewer-a, code-reviewer-b, review-arbiter, fixer
   Models: any model name your preflight reports as available (use the IDs displayed above or supported by your account)
   Pair example: planner=<codex-model-id>, builder=<claude-model-id>
   JSON example: {"models":{"planner":"<codex-model-id>","builder":"<claude-model-id>"}}
   (empty input = no overrides, equivalent to Y)

   Overrides:
   ```

   If the override submission is empty after trimming, follow the **On Y** default writer above. Do not write `source: "overridden"`, do not add `overridden_roles`, and do not count the empty submission as a rejected attempt.

   **Parse contract (each full override submission is one attempt; cap re-prompts at 3, abort on the 4th rejection):** Run `python3 scripts/quest_parse_overrides.py`, send the complete submission unchanged on stdin, and consume its JSON envelope. Exit `0` returns `{"ok": true, "overrides": [...]}`; exit `2` returns `{"ok": false, "error": "..."}` on stderr and counts as one rejected attempt. Do not manually parse or rewrite JSON into pairs. `quest_runtime.orchestration.parse_override_input` is the canonical API; `parse_override_line` remains a compatibility wrapper.

   1. **Detect format.** Input beginning with `{` is JSON. A copied `"models": {...}` fragment without outer braces is also accepted. JSON may be either `{"models": {<role>: <model>}}` or a direct `{<role>: <model>}` map. All JSON role keys and model values must be strings; model values must be non-empty. A `models` wrapper cannot have sibling top-level keys. Other input uses the pair format below.
   2. **Tokenize pairs.** Split pair input on commas, LF newlines, or CRLF newlines and trim each piece. Empty pieces are silently skipped, so trailing separators and blank lines are allowed. Each non-empty piece must contain exactly one `=` character. Reject pieces with zero or multiple `=` characters using `Override syntax error: '<piece>' (expected role=model). Re-enter overrides.`
   3. **Role name.** Trim, normalize to lowercase, then exact-match against the canonical role list (`planner`, `plan-reviewer-a`, `plan-reviewer-b`, `arbiter`, `builder`, `code-reviewer-a`, `code-reviewer-b`, `review-arbiter`, `fixer`). Reject unknown names with `Unknown role: <input> (valid: planner, plan-reviewer-a, plan-reviewer-b, arbiter, builder, code-reviewer-a, code-reviewer-b, review-arbiter, fixer)`. Reject duplicate normalized roles in either syntax with `Duplicate role: <role>. Re-enter overrides.` rather than silently choosing the last value.
   4. **Model name.** Trim the pair RHS or JSON string value. It must be non-empty and cannot contain commas, `=`, or line breaks in either syntax, so JSON and pair inputs accept the same model tokens. Example: `codex-fake-model`, `claude-fake-model`, `gemini-fake-model` and similar tokens are accepted at the parser level.
   5. **Unused-in-mode roles** (`plan-reviewer-b`, `arbiter`, `code-reviewer-b`, and `review-arbiter` in solo). Warn `Role <name> is unused in <mode> mode — override ignored.` and skip the override; do not record it in `overridden_roles`.
   6. **Availability check.** Classify Claude-family model names as `claude` and `claude-*` (including concrete Claude model IDs); Gemini-family model names (`gemini`, `gemini-*`) as Antigravity-backed; every other model name is Codex-backed. Antigravity-backed models require `antigravity_available` from `scripts/quest_preflight.sh --probe antigravity` (see the workflow's Antigravity preflight section) in either session type. In Claude-led sessions, Claude-family models are available and Codex-backed models require the top-level `available` boolean for the auth mode Step 2b resolved. Do not read `orchestration.json` here: it has not yet been written. This is setup readiness, not verification of a particular model. In Codex-led sessions, Codex-backed models are available and Claude-family models require the top-level `available` boolean from the Step 2b preflight result, which represents Claude transport availability (background-agent or bridge — the `transport` field says which). If the relevant cache/result is missing or stale (older than the preflight TTL), rerun the matching preflight once and reuse the fresh result: `scripts/quest_preflight.sh --orchestrator <self>` for Claude/Codex availability (include `--codex-auth <Step-2b-resolved-mode>` for Claude-led checks), `scripts/quest_preflight.sh --probe antigravity` for `antigravity_available` (they are separate modes and cannot be combined). Reject unavailable models with the preflight `warning` text and re-prompt the override submission.
   7. **Re-prompt cap.** An "attempt" is one full override submission, not one role=model pair. Three rejected attempts in a row abort startup with `Override validation failed after 3 attempts — quest startup cancelled.`

   Once all overrides pass validation, build the merged `models` block (the expanded startup block returned by `build_default_models`, overlaid with the validated overrides — `overridden_roles` excludes ignored-because-unused entries) and write `.quest/<id>/orchestration.json` with:
   - `version: 1`
   - `models`: merged block (all 9 keys present; unused-in-mode roles still carry the default value)
   - `claude_role_transport` / `claude_transport_resolved`: same sourcing as the Y path above; `claude_transport_downgraded: false` for compatibility
   - `codex_auth_mode`: same resolved Step 2b mode as the Y path; pass it to `write_orchestration_json`.
   - `codex_reasoning_effort`: same allowlist sourcing as the Y path; pass it to `write_orchestration_json`. Model-only overrides do not change effort; validate model support before dispatch.
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
   Set `quest_mode` to the user's final selection: `"workflow"` (default) or `"solo"`. This field is read by `workflow.md` to determine agent dispatch and by `quest_validate-quest-state.sh` for artifact checks.
   `vcs_available` must be copied directly from `scripts/quest_startup_branch.py` output. Do not infer it from `branch_mode`.
   `branch_mode` records the actual startup mode used for this quest run after no-op handling. If Quest starts on an existing feature branch, set `branch_mode` to `"none"` and record that branch in `branch`.
   `quest_symlink` must be copied directly from `scripts/quest_startup_branch.py` output. Do not infer it from `branch_mode` or `worktree_path`.

### UI Work Propagation

When the recorded router classification has `ui_work: true`, downstream dispatch must load the UX skills:

- Planner, builder, fixer agents auto-load `.skills/ux-context/SKILL.md`
- Plan-reviewer and code-reviewer agents auto-load `.skills/ux-review/SKILL.md`

The agent files in `.skills/quest/agents/` enforce this — the orchestrator's job is to preserve the full router JSON in the brief so each agent can read it.
