## Procedure

When starting, say: "Now I understand the Quest." Then proceed directly with the steps below.

Follow these steps in order. After each step that modifies state, update `.quest/<id>/state.json`.

**State update helper:** Use `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition <phase> ...` for state mutations instead of hand-editing `state.json`. The `--transition` flag validates the transition against `validate-quest-state.sh` before writing — if validation fails, state.json is not modified. Use `--phase` only for non-transition updates (e.g., setting status without changing phase).

### Defaults (Opinionated)

Quest is opinionated: default to **thorough**, but be **progressive** and avoid wasted repo exploration.

- **Intake before exploration:** Do not start repo exploration until the quest brief is stable (Step 1 complete), unless the user explicitly asks you to “just run with it”.
- **Progressive exploration:** Start from the context digest + allowlist + plan. Only deep-dive into the repo when the plan/implementation needs it.
- **Timebox structure discovery:** Avoid full repo inventories. Do a quick top-level scan + targeted `rg` searches instead of browsing directory-by-directory.
- **If the user wants speed:** Offer to proceed with minimal questions + explicit assumptions (fast intake).

### Codex Availability Probe (Run Once Per Session — Applies to ALL Codex MCP calls)

Tool naming is platform-specific (depends on the MCP server name in config):
- Claude Code: `mcp__codex-cli__codex` (server name `codex-cli`, registered via `claude mcp add`)
- OpenCode: `codex_codex`

In this document, `mcp__codex__codex` is used as an **abstract placeholder** meaning "the platform's Codex session-start MCP tool". Substitute the actual tool name for your platform.

If the preflight result was already cached by SKILL.md Step 2b, use the cached values. Otherwise, probe now:

**Claude-led sessions:**
1. Run `scripts/quest_preflight.sh --orchestrator claude` and parse the JSON output.
2. Cache the `available` field as `codex_available` (boolean) for the rest of the session.
3. If `codex_available` is false:
   - Log: `"Codex MCP not available — using Claude runtime fallback for all roles."`
   - **Global rule:** Every `mcp__codex__codex` invocation in this workflow (Reviewer B slots, Builder, Fixer — any role) is replaced with the equivalent Claude runtime fallback for that role. Use the same prompt (minus the non-interactive rule), the same output file paths, and the same handoff contract. Do not retry Codex. Do not treat this as an error.

**Codex-led sessions:**
1. `codex_available` is always true (Codex is the active runtime — no MCP needed).
2. Run `scripts/quest_preflight.sh --orchestrator codex` and parse the JSON output.
3. Cache the `available` field as `claude_bridge_available` (boolean) for the rest of the session.
4. If `claude_bridge_available` is false: Claude-designated roles block unless that step defines an explicit Codex fallback (see Claude Bridge Probe section below).
4. If `codex_available` is true:
   - Proceed normally with Codex invocations per the workflow below.

**This rule is global.** Individual steps do not repeat the `codex_available` check — they just say `mcp__codex__codex` and this section governs what actually happens. The orchestrator applies the substitution transparently.

**Why:** MCP servers are loaded at session startup. If the Codex MCP server failed to connect (binary not on PATH, server crash, etc.), it cannot be recovered mid-session. Probing once avoids repeated failed invocations and misleading error messages.

### Claude Bridge Probe And Runtime Dispatch (Run Once Per Session — Applies to Claude-designated roles when orchestrator is Codex)

Quest may need to run Claude-designated roles in environments where native Claude `Task(...)` execution is unavailable. In Codex-led sessions, the supported Claude runtime adapter is `scripts/claude_cli_bridge.py`.

Before the first Claude-designated role invocation in a Codex-orchestrated session, the orchestrator MUST probe bridge availability:

1. Verify `scripts/claude_cli_bridge.py` exists.
2. Verify Claude CLI is reachable, authenticated, and able to write Quest artifacts by running the real probe helper:
   - `python3 scripts/quest_claude_probe.py --quest-dir .quest/<id> --model opus`
   - This probe is the source of truth for bridge readiness. It writes a tiny artifact plus `probe_handoff.json` under `.quest/<id>/logs/bridge_probe/`.
3. Cache the result as `claude_bridge_available` (boolean) for the rest of the session.
4. If `claude_bridge_available` is false:
   - Log: `"Claude bridge unavailable in this Codex-led session — Claude-designated slots requiring Claude runtime will block unless that step defines an explicit Codex path."`
   - Do not keep retrying the probe for later Claude roles.
5. If `claude_bridge_available` is true:
   - Claude-designated roles may be invoked through the bridge with the same artifact paths and handoff contract used by native Claude execution.
   - **Preferred Codex-led execution path:** use `python3 scripts/quest_claude_runner.py` instead of calling `scripts/claude_cli_bridge.py` directly. The helper sets `--permission-mode bypassPermissions` by default, adds explicit repo/quest filesystem access via `--add-dir`, polls `handoff.json`, and appends the `context_health.log` line for `runtime=claude`.

**Global runtime-selection rule:** the workflow chooses execution path by selected model/runtime, not by role label alone.

- If the selected role model/runtime is Codex, use `mcp__codex__codex` (or Codex agent tools).
- If the selected role model/runtime is Claude and native `Task(...)` is available in the orchestrator, use `Task(...)`.
- If the selected role model/runtime is Claude and the orchestrator is Codex, use `python3 scripts/quest_claude_runner.py` when `claude_bridge_available` is true. `scripts/claude_cli_bridge.py` stays the transport layer behind that runner.
- If the selected role model/runtime is Claude, native `Task(...)` is unavailable, and the bridge probe failed, block that step unless the workflow section for that role defines an explicit Codex execution path.

This rule is global. Individual steps below name the target runtime and artifact contract; the orchestrator applies native Claude task execution, bridge execution, or Codex execution based on the selected model/runtime and session capabilities.

**Role permissions:** Per-role file and bash access is enforced by `.claude/hooks/enforce-allowlist.sh`, which reads `role_permissions` from `.ai/allowlist.json` on every tool invocation. See the allowlist for the current permission grants per role.

### Quest Mode Check

On entry, read `quest_mode` from `.quest/<id>/state.json`. Default to `"workflow"` if missing.

Quest mode determines agent dispatch and iteration limits:

| Aspect              | workflow (default) | solo              |
|---------------------|-------------------|-------------------|
| Plan reviewers      | Dual (A + B)      | Single (A only)   |
| Arbiter             | Yes               | No — Reviewer A's verdict is used directly |
| Code reviewers      | Dual (A + B)      | Single (A only)   |
| Max fix iterations  | From allowlist gates (default 3) | min(solo.max_fix_iterations, allowlist gates) |

**Solo verdict remapping:** In solo mode, Reviewer A's handoff says `next: "arbiter"` per the reviewer agent contract. The workflow remaps this: when `quest_mode == "solo"` and Reviewer A says `next: "arbiter"`, treat it as `next: "builder"` (approved). Write the remapped value to state for downstream consumers. If Reviewer A says `next: "planner"`, it means revision needed — no remapping.

### Hard Phase Gate (No Pre-Build Source Edits)

Before Step 4 (Build Phase), the orchestrator and all agents MUST NOT edit source/product files.

- In phases `plan`, `plan_reviewed`, `presenting`, and `presentation_complete`, writes are limited to quest artifacts under `.quest/**` only.
- Any implementation request received before Build must be captured as plan feedback (`.quest/<id>/phase_01_plan/user_feedback.md`) and deferred to Step 4.
- If any pre-Build action would modify non-`.quest/**` files, STOP and ask the user whether to proceed to Build first.

### Context Retention Rule

After every subagent invocation (`Task`, `python3 scripts/quest_claude_runner.py`, or `mcp__codex__codex`), the orchestrator retains ONLY:
1. The **artifact path(s)** from the ARTIFACTS line of the handoff
2. The **one-line SUMMARY** from the SUMMARY line of the handoff
3. The **STATUS** and **NEXT** values for routing decisions

Everything else from the subagent response (plan text, review content, build output, fix details) is not carried forward in the orchestrator's working context. The orchestrator does not retain, summarize, or re-process subagent output beyond these handoff fields.

**Primary mechanism:** The orchestrator reads the agent's `handoff.json` file (see Handoff File Polling) to obtain status, artifacts, next, and summary. The full agent response body is discarded immediately. If `handoff.json` is unavailable or cannot be parsed as valid JSON, fall back to parsing the text `---HANDOFF---` block from the response.

**Bounded exceptions** (content is used immediately and not carried forward):
1. **Step 3.5 (Interactive Plan Presentation):** The orchestrator loads plan content for human interaction. This is bounded and deliberate.
2. **Q&A loop (`needs_human`):** The orchestrator extracts questions from the subagent response text (before `---HANDOFF---`) to present to the user. The question text is used for the human exchange and not retained after re-invocation.
3. **Artifact recovery:** If an expected artifact file (e.g., `plan.md`) is not written by a subagent, the orchestrator extracts it from the response and writes it to disk. The response content is discarded immediately after writing.

**Why this works:** Every subagent reads files itself. The orchestrator's job is routing and state management, not content relay.

### Handoff File Polling

After any subagent completes, the orchestrator reads the agent's `handoff.json` file for routing decisions instead of parsing the full response.

**Pattern:**
1. Wait for the subagent to complete (Task completion or MCP response)
2. Read the expected `handoff.json` file (tiny JSON, ~200 bytes)
3. Use its `status`, `next`, `summary`, and `artifacts` fields for routing and user display
4. Discard the full agent response -- do not retain, summarize, or process it
5. **Artifact preparation (before every role invocation):**
   Before invoking any role, the orchestrator MUST:
   1. Resolve artifact paths: `expected_artifacts_for_role(quest_dir, phase, agent)`
   2. Prepare files: `prepare_artifact_files(paths)` — creates parent directories and truncates files
   3. Include in the role prompt:
      ```
      Artifact files have been prepared for you. Overwrite these files directly:
      - <path1>
      - <path2>
      Do not create Quest artifacts via shell redirection, heredocs, or echo.
      ```
   This applies to ALL orchestrators (Claude-led and Codex-led) and ALL runtimes (native Claude, bridge Claude, Codex). The preparation logic does not branch on orchestrator identity.

   **Codex sandbox permissions:** The orchestrator passes `sandbox_permissions: "workspace-write"` by default for Codex invocations. Tier B may escalate to `"danger-full-access"` ONLY when the user has explicitly approved that broader access or an equivalent persisted approval exists (see below). It is never automatic.

6. **Three-tier fallback ladder for missing/unparsable handoff.json:**

   Use `classify_failure_kind(result, artifact_paths, workspace_root)` to determine which tier applies. Classification order: timeout → invocation → write-boundary (out-of-workspace + missing artifacts) → permission → model.

   **Tier A — Normal run (already completed, failed):**
   The initial invocation with standard permissions and artifact preparation.

   **Tier B — Permission/transport retry (same runtime, same model):**
   Triggered ONLY when failure is classified as `write_boundary` or `permission`.
   - **Codex:** Retry with `sandbox_permissions: "danger-full-access"` only when the user has explicitly approved that broader access or an equivalent persisted approval exists. Otherwise stop and request that approval instead of silently changing the sandbox.
   - **Bridge-invoked Claude:** Add the out-of-workspace artifact directory to `--add-dir`.
   - **Native Claude `Task(...)`:** Widen tool permissions for the specific directory.
   - Prompt is unchanged (same task, same contract). Only the permission posture changes.
   - If Tier B also fails, proceed to Tier C.

   **Tier C — Cross-runtime fallback or block:**
   Triggered when:
   - Tier B was attempted and still failed, OR
   - Failure is NOT write-boundary/permission (timeout, model failure, invocation error)

   **Claude runtime invocation (Tier C):**
   - **Native Claude `Task(...)`:** If `handoff.json` is missing/unparsable, parse text `---HANDOFF---` as fallback.
   - **Bridge-invoked Claude (`python3 scripts/quest_claude_runner.py`):**
     - **Timeout:** Retry the same Claude role once with a reduced artifact-first prompt: no questions, no `needs_human`, read only the listed files, and write the required artifacts plus `handoff.json` before any optional commentary. If the second attempt also times out, treat the step as `blocked`.
     - **Auth/CLI/environment failure** (for example Claude CLI missing from `PATH`, not authenticated, or bridge script missing): Do NOT retry. Treat the step as `blocked` and surface the stderr summary to the user.
     - **Other failures** (missing/unparsable handoff, malformed output, `blocked`): Re-run the same Claude role once with a reduced artifact-first prompt and a strict reminder to write the expected artifact files and `handoff.json`. If the second attempt still fails, parse text `---HANDOFF---` as last-resort compatibility fallback; if no parseable text handoff exists, treat the step as `blocked`.

   **Codex invocation — Tier C (`mcp__codex__codex`):**
   - **Timeout (`McpError` / request timed out):** Do NOT retry. Fall back to the equivalent Claude `Task` immediately.
   - **Other failures** (missing/unparsable handoff, non-compliant output, `blocked`): Re-run the same Codex role once with a strict reminder. If the second attempt still fails, invoke the equivalent Claude `Task` fallback for that step.
   - Only after this fallback chain, if the final attempt still has no parseable `handoff.json`, parse text `---HANDOFF---` as last-resort compatibility fallback.

**Expected handoff.json locations:**

| Phase | Agent | handoff.json path |
|-------|-------|------------------|
| Plan | Planner | `.quest/<id>/phase_01_plan/handoff.json` |
| Plan Review | Slot A | `.quest/<id>/phase_01_plan/handoff_plan-reviewer-a.json` |
| Plan Review | Slot B | `.quest/<id>/phase_01_plan/handoff_plan-reviewer-b.json` |
| Plan Review | Arbiter | `.quest/<id>/phase_01_plan/handoff_arbiter.json` |
| Build | Builder | `.quest/<id>/phase_02_implementation/handoff.json` |
| Code Review | Slot A | `.quest/<id>/phase_03_review/handoff_code-reviewer-a.json` |
| Code Review | Slot B | `.quest/<id>/phase_03_review/handoff_code-reviewer-b.json` |
| Fix | Fixer | `.quest/<id>/phase_03_review/handoff_fixer.json` |

The orchestrator NEVER reads full review files, plan content, or build output for routing decisions. Only handoff.json (and, for Step 3.5, the plan file itself as a bounded exception).

**Claude bridge response handling:** In Codex-led sessions, prefer `python3 scripts/quest_claude_runner.py` for Claude-designated roles. It polls the expected `handoff.json` file, defaults to `--permission-mode bypassPermissions`, adds explicit repo/quest filesystem access via `--add-dir`, and logs `runtime=claude` to `context_health.log`. If the helper cannot be used, a raw `python3 scripts/claude_cli_bridge.py` call is still allowed, but the orchestrator must manually perform the same file polling, filesystem access, and logging steps.

**Codex MCP response handling:** After a `mcp__codex__codex` call returns, the orchestrator reads the corresponding `handoff.json` file and does NOT retain the Codex response body in working context. The response may still appear in the conversation history (platform limitation), but the orchestrator treats it as consumed and does not reference it for any subsequent decision.

**Codex non-interactive contract (all `mcp__codex__codex` calls):**
- Codex must not ask the user questions and must not return `STATUS: needs_human`.
- If context is incomplete, Codex makes explicit assumptions in the artifact and continues.
- If it cannot proceed safely, Codex returns `STATUS: blocked` with a concrete reason.
- Orchestrator handling for Codex failures follows the **three-tier fallback ladder** (see Handoff File Polling):
  - **Tier B** (write-boundary/permission): Same Codex runtime, `sandbox_permissions: "danger-full-access"` only with explicit user approval or an equivalent persisted approval.
  - **Tier C** (timeout, model, or Tier B exhausted):
    - **Timeout (`McpError`):** Skip retry. Fall back to the equivalent Claude `Task` role immediately.
    - **Other failures** (`needs_human`, non-compliant output, missing/unparsable handoff, `blocked`):
      1. Re-invoke the same Codex role once with a strict reminder: "no questions, no `needs_human`, make explicit assumptions."
      2. If the second attempt still fails, fall back to the equivalent Claude `Task` role for that step.
  - Only after the fallback chain may text `---HANDOFF---` parsing be used as a last-resort compatibility path.
  - Only enter human Q&A if the Claude runtime fallback returns `STATUS: needs_human`.

**MANDATORY — Context health logging:** Every single time you read a handoff.json file (or fall back to text parsing), you MUST append one line to `.quest/<id>/logs/context_health.log` BEFORE making any routing decision. This is not optional. Do this for every agent, every phase, no exceptions. Create the `.quest/<id>/logs/` directory first if it does not exist. `scripts/quest_claude_runner.py` already does this for bridge-invoked Claude roles.

**Format:**
```
<timestamp> | phase=<phase> | agent=<agent_name> | runtime=claude|codex | iter=<plan_iteration or fix_iteration> | handoff_json=found|missing|unparsable | source=handoff_json|text_fallback
```

Use `plan_iteration` for plan/plan_review phases, `fix_iteration` for code_review/fix phases, and `1` for build (single pass).
Set `runtime` to the runtime actually used for that invocation (`claude` or `codex`).
Never infer runtime from the agent label/name (for example `plan-reviewer-a`); labels are role identifiers, not backend evidence.

Runtime attribution rule (authoritative):
- Log `runtime=claude` only when the invocation actually used Claude `Task(...)` or `python3 scripts/quest_claude_runner.py`.
- Log `runtime=codex` when invocation used `mcp__codex__codex` or Codex agent tools (`spawn_agent`/`worker`/`explorer`).
- If a role expected to be Claude is executed with Codex fallback, keep the same role label but log `runtime=codex`.

**Example log for a quest with 2 plan iterations:**
```
2026-02-15T00:12:00Z | phase=plan | agent=planner | runtime=claude | iter=1 | handoff_json=found | source=handoff_json
2026-02-15T00:15:00Z | phase=plan_review | agent=plan-reviewer-a | runtime=claude | iter=1 | handoff_json=found | source=handoff_json
2026-02-15T00:15:00Z | phase=plan_review | agent=plan-reviewer-b | runtime=codex | iter=1 | handoff_json=missing | source=text_fallback
2026-02-15T00:18:00Z | phase=plan_review | agent=arbiter | runtime=claude | iter=1 | handoff_json=found | source=handoff_json
2026-02-15T00:25:00Z | phase=plan | agent=planner | runtime=claude | iter=2 | handoff_json=found | source=handoff_json
2026-02-15T00:28:00Z | phase=plan_review | agent=plan-reviewer-a | runtime=claude | iter=2 | handoff_json=found | source=handoff_json
2026-02-15T00:28:00Z | phase=plan_review | agent=plan-reviewer-b | runtime=codex | iter=2 | handoff_json=found | source=handoff_json
2026-02-15T00:31:00Z | phase=plan_review | agent=arbiter | runtime=claude | iter=2 | handoff_json=found | source=handoff_json
```

This log is how we measure whether the handoff.json pattern is working. It is displayed to the user at quest completion (Step 7). If you skip logging, the compliance report will be incomplete.

### Step 0: Resume Check

If the user provides a quest ID (matches pattern `*_YYYY-MM-DD__HHMM`):

1. Check if `.quest/<id>/state.json` exists
2. If yes, read it and resume from the recorded phase
3. If the user also provided an instruction, route it (Step 2)
4. If no instruction, auto-resume based on state:
   - `phase: plan` + no approval verdict → continue plan phase
   - `phase: plan` + approved (arbiter verdict in workflow, or reviewer-a verdict with remapped `next: "builder"` in solo; accept legacy `next: "arbiter"` too) → proceed to Step 3.5 (Interactive Presentation)
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

0. **Clear stale handoff files:** If `plan_iteration >= 1` (i.e., any refinement pass after the first), delete any existing `handoff*.json` files in `.quest/<id>/phase_01_plan/` to prevent stale data from a previous iteration being read.

1. **Update state:** `plan_iteration += 1`, `status: in_progress`, `last_role: planner_agent`

2. **Invoke Planner:**
   - Read `models.planner` from allowlist.
   - If planner model is Claude, invoke through Claude runtime (native `Task(...)` when available, bridge in Codex-led sessions).
   - If planner model is Codex, invoke via `mcp__codex__codex`.
   - **Artifact preparation** (per Handoff File Polling §5): Resolve and prepare `plan.md` and `handoff.json` in `.quest/<id>/phase_01_plan/`.
   - Prompt: Reference file paths only, do not embed artifact content:
     - Quest brief: `.quest/<id>/quest_brief.md`
     - Arbiter verdict (iteration 2+): `.quest/<id>/phase_01_plan/arbiter_verdict.md`
     - User feedback (if present): `.quest/<id>/phase_01_plan/user_feedback.md`
   - Require the prompt to include:
     - Artifact files have been prepared. Overwrite them directly:
       - `.quest/<id>/phase_01_plan/plan.md`
       - `.quest/<id>/phase_01_plan/handoff.json`
     - Do not create Quest artifacts via shell redirection, heredocs, or echo.
     - handoff.json schema: `{"status", "artifacts", "next", "summary"}`
     - End with: `---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY`
     - `NEXT: plan_review`
   - Wait for the selected runtime to complete
   - Read `.quest/<id>/phase_01_plan/handoff.json` for status/routing
   - Verify `.quest/<id>/phase_01_plan/plan.md` exists (from handoff.artifacts)
   - Apply deterministic precedence from **Handoff File Polling** for native Claude task vs bridge execution
   - Fallback: if handoff.json missing or unparsable after that precedence, parse text handoff from response; if plan.md not written, extract from response and write it

3. **Read review config from allowlist:**
   - `review_mode` (default: `auto`)
   - `fast_review_thresholds` (not used for plan review)
   - For plan review: treat `auto` as `full`. Use `fast` only if explicitly set.

4. **Invoke Plan Reviewers:**

   **If `quest_mode == "solo"`:** Invoke ONLY Reviewer A. Skip Reviewer B entirely. Log: `Plan review: dispatched=single (solo mode)` to `.quest/<id>/logs/parallelism.log`.

   **If `quest_mode == "workflow"` (default):** Invoke BOTH Plan Reviewers IN PARALLEL.

   Read `models.plan-reviewer-a` and `models.plan-reviewer-b` from allowlist to determine runtime for each slot. If model is Claude, use Claude runtime; if Codex, use `mcp__codex__codex`.

   Two different models review independently for model diversity:
   - **Reviewer A**: dispatched by orchestrator → `.quest/<id>/phase_01_plan/review_plan-reviewer-a.md`
   - **Reviewer B** (workflow only): dispatched by orchestrator → `.quest/<id>/phase_01_plan/review_plan-reviewer-b.md`

   **Artifact preparation** (per Handoff File Polling §5): Before issuing reviewer calls, resolve and prepare artifacts for both Reviewer A (`review_plan-reviewer-a.md`, `handoff_plan-reviewer-a.json`) and Reviewer B (`review_plan-reviewer-b.md`, `handoff_plan-reviewer-b.json`) in `.quest/<id>/phase_01_plan/`.

   **Slot A** (runtime per `models.plan-reviewer-a`; full and fast modes):
   **Full mode** (default for plan review):
   ```
   Task(
     subagent_type: "plan-reviewer",
     prompt: "You are Plan Reviewer A.

     Read your instructions: .skills/quest/agents/plan-reviewer.md

     (Optional, full mode only, if needed) Read: .skills/BOOTSTRAP.md, AGENTS.md

     Quest brief: .quest/<id>/quest_brief.md
     Plan to review: .quest/<id>/phase_01_plan/plan.md

     Artifact files have been prepared for you. Overwrite these files directly:
     - .quest/<id>/phase_01_plan/review_plan-reviewer-a.md
     - .quest/<id>/phase_01_plan/handoff_plan-reviewer-a.json
     Do not create Quest artifacts via shell redirection, heredocs, or echo.

     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: arbiter"
   )
   ```
   **Fast mode** (only if `review_mode: fast`):
   ```
   Task(
     subagent_type: "plan-reviewer",
     prompt: "You are Plan Reviewer A.


     Quest brief: .quest/<id>/quest_brief.md
     Plan to review: .quest/<id>/phase_01_plan/plan.md

     List up to 5 issues, highest severity first.

     Artifact files have been prepared for you. Overwrite these files directly:
     - .quest/<id>/phase_01_plan/review_plan-reviewer-a.md
     - .quest/<id>/phase_01_plan/handoff_plan-reviewer-a.json
     Do not create Quest artifacts via shell redirection, heredocs, or echo.

     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: arbiter"
   )
   ```

   **Reviewer B** (full and fast modes):

   **Full mode** (default for plan review):
   ```
   mcp__codex__codex(
     model: <models.plan-reviewer-b from allowlist>,
     prompt: "You are Plan Reviewer B.
     Non-interactive rule: do not ask questions and do not return STATUS: needs_human. If details are missing, make explicit assumptions and continue.

     Read your instructions: .skills/quest/agents/plan-reviewer.md

     (Optional, full mode only, if needed) Read: .skills/BOOTSTRAP.md, AGENTS.md

     Quest brief: .quest/<id>/quest_brief.md
     Plan to review: .quest/<id>/phase_01_plan/plan.md

     Artifact files have been prepared for you. Overwrite these files directly:
     - .quest/<id>/phase_01_plan/review_plan-reviewer-b.md
     - .quest/<id>/phase_01_plan/handoff_plan-reviewer-b.json
     Do not create Quest artifacts via shell redirection, heredocs, or echo.

     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: arbiter"
   )
   ```
   **Fast mode** (only if `review_mode: fast`):
   ```
   mcp__codex__codex(
     model: <models.plan-reviewer-b from allowlist>,
     prompt: "You are Plan Reviewer B.
     Non-interactive rule: do not ask questions and do not return STATUS: needs_human. If details are missing, make explicit assumptions and continue.


     Quest brief: .quest/<id>/quest_brief.md
     Plan to review: .quest/<id>/phase_01_plan/plan.md

     List up to 5 issues, highest severity first.

     Artifact files have been prepared for you. Overwrite these files directly:
     - .quest/<id>/phase_01_plan/review_plan-reviewer-b.md
     - .quest/<id>/phase_01_plan/handoff_plan-reviewer-b.json
     Do not create Quest artifacts via shell redirection, heredocs, or echo.

     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: arbiter"
   )
   ```
   - **Before issuing the calls**, record the current wall-clock time as `dispatch_start`
   - Issue BOTH calls in the SAME message for parallel execution
   - Wait for BOTH to complete
   - Record the current wall-clock time as `dispatch_end`
   - Read `.quest/<id>/phase_01_plan/handoff_plan-reviewer-a.json` and `handoff_plan-reviewer-b.json`
   - Verify both review files exist (from handoff.artifacts)
   - Apply the **three-tier fallback ladder** from **Handoff File Polling** §6:
     - Claude slot follows the Claude-runtime precedence: native task may use direct text fallback; bridge path applies Tier B (permission escalation via `--add-dir`) for write-boundary/permission failures, then Tier C (retry once for timeout/malformed output, block immediately on auth/CLI failures).
     - Codex slot: classify failure via `classify_failure_kind` logic. Tier B (write-boundary/permission): retry with `sandbox_permissions: "danger-full-access"` only with explicit user approval or an equivalent persisted approval; otherwise stop and surface the approval need. Tier C (timeout, model, or Tier B exhausted): timeout → Claude runtime fallback immediately; other failures → retry once with strict non-interactive reminder, then Claude runtime fallback.

   **Parallelism check (orchestrator-timed):**
   1. Create `.quest/<id>/logs/` directory if it doesn't exist
   2. Append a line to `.quest/<id>/logs/parallelism.log`:
      ```
      Plan review: dispatched=concurrent (wall: <dispatch_start>-<dispatch_end>)
      ```
      The wall-clock duration covers both agents. Since both calls are issued in the same message, they run concurrently by construction. Agent self-reported timestamps are unreliable and must NOT be used for parallelism verification.

5. **Invoke Arbiter or use Solo verdict:**

   **If `quest_mode == "solo"`:** Skip Arbiter entirely. Use Reviewer A's verdict directly with remapping:
   - Read `.quest/<id>/phase_01_plan/handoff_plan-reviewer-a.json`
   - If `next: "arbiter"` → remap to `next: "builder"` (approved in solo mode)
   - If `next: "planner"` → plan needs revision (no remapping)
   - Log: `Plan review: arbiter=skipped (solo mode, using reviewer-a verdict)` to `.quest/<id>/logs/parallelism.log`

   **If `quest_mode == "workflow"` (default):** Read `models.arbiter` from allowlist. Invoke Arbiter through the corresponding runtime:
   - **Artifact preparation** (per Handoff File Polling §5): Resolve and prepare `arbiter_verdict.md` and `handoff_arbiter.json` in `.quest/<id>/phase_01_plan/`.
   - Use a short prompt with path references only:
     ```
     You are the Arbiter Agent.

     Read your instructions: .skills/quest/agents/arbiter.md

     Quest brief: .quest/<id>/quest_brief.md
     Plan: .quest/<id>/phase_01_plan/plan.md
     Review A: .quest/<id>/phase_01_plan/review_plan-reviewer-a.md
     Review B: .quest/<id>/phase_01_plan/review_plan-reviewer-b.md

     Artifact files have been prepared for you. Overwrite these files directly:
     - .quest/<id>/phase_01_plan/arbiter_verdict.md
     - .quest/<id>/phase_01_plan/handoff_arbiter.json
     Do not create Quest artifacts via shell redirection, heredocs, or echo.
     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: builder (approve) or planner (iterate)
     ```
   - Wait for the selected runtime to complete
   - Read `.quest/<id>/phase_01_plan/handoff_arbiter.json`
   - Route based on `next` field ("builder" = approved, "planner" = iterate)
   - Apply deterministic precedence from **Handoff File Polling** for native Claude task vs bridge execution
   - Fallback: if handoff.json missing or unparsable after that precedence, parse text handoff from response

6. **Check verdict:**
   - If `NEXT: builder` → Plan approved! Transition state atomically: `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition plan_reviewed --status complete --last-verdict approve` — if this fails, report the validation error to the user and STOP. Do NOT modify state.json manually. Then proceed to **Step 3.5** (Interactive Presentation). Do not attempt the `presenting` transition while state still says `phase: plan`.
   - If `NEXT: planner` → Check iteration count
     - If `plan_iteration >= max_plan_iterations`: Warn user, ask to proceed anyway or review manually
     - If `auto_approve_phases.plan_refinement` is false: Ask user to approve refinement
     - Otherwise: Loop back to step 0 (stale handoff cleanup)

### Step 3.5: Interactive Plan Presentation (MANDATORY HUMAN GATE)

After plan approval, present the plan interactively before proceeding to build.

**THIS IS A MANDATORY STOP POINT.** You MUST present the plan to the human user, ask for their approval, and STOP execution until the human responds. Do not assume approval. Do not skip this step. Do not auto-approve. Do not proceed to Step 4 until the human has explicitly approved.

**On entry:** Transition state atomically: `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition presenting --status in_progress` — if this fails, report the validation error to the user and STOP. Do NOT modify state.json manually.

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
   - If user declines ("no", "n", "nope", "skip", "proceed", etc.) -> Transition state atomically: `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition presentation_complete --status complete` — if this fails, report the validation error to the user and STOP. Do NOT modify state.json manually. Then proceed to Step 4 (Build Phase)
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
   - If "continue" (or "c", "next", "ok", "looks good", etc.) -> Move to next phase, or if last phase: Transition state atomically: `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition presentation_complete --status complete` — if this fails, report the validation error to the user and STOP. Do NOT modify state.json manually. Then proceed to Step 4
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
      - Full review cycle (Claude slot A + Codex slot B + Arbiter) runs
      - After approval, Step 3.5 presentation starts fresh from step 1

### Step 4: Build Phase

**MANDATORY GATE CHECK — Do not skip this:**
- Read `auto_approve_phases.implementation` from allowlist
- If false (default): You MUST ask the user "Plan approved. Proceed with implementation?" and then STOP and wait for the human to respond. Do not proceed until the human explicitly says yes. Do not assume approval. Do not auto-approve.
- If true: You may proceed without asking
- **If you have not received explicit human approval from Step 3.5 or this gate, STOP NOW and ask.**

**Build:**

1. **Atomic transition:** `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition building --status in_progress --last-role builder_agent` — if this fails, report the validation error to the user and STOP. Do NOT modify state.json manually.

2. **Invoke Builder** (default Codex `mcp__codex__codex`, Claude runtime fallback):
   - Read `models.builder` from allowlist.
   - If builder model is Codex, invoke via `mcp__codex__codex` with `sandbox_permissions: "workspace-write"`.
   - If builder model is Claude, invoke through Claude runtime (native `Task(...)` when available, bridge in Codex-led sessions).
   - **Artifact preparation** (per Handoff File Polling §5): Resolve and prepare `pr_description.md`, `builder_feedback_discussion.md`, and `handoff.json` in `.quest/<id>/phase_02_implementation/`.
   - Prompt: Reference file paths only, do not embed content:
     - Approved plan: `.quest/<id>/phase_01_plan/plan.md`
     - Quest brief: `.quest/<id>/quest_brief.md`
   - Require the prompt to include:
     - If using Codex path: `Read your instructions: .skills/quest/agents/builder.md`
     - Artifact files have been prepared. Overwrite them directly:
       - `.quest/<id>/phase_02_implementation/pr_description.md`
       - `.quest/<id>/phase_02_implementation/builder_feedback_discussion.md`
       - `.quest/<id>/phase_02_implementation/handoff.json`
     - Do not create Quest artifacts via shell redirection, heredocs, or echo.
     - handoff.json schema: `{"status", "artifacts", "next", "summary"}`
     - End with: `---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY`
     - `NEXT: code_review`
   - Wait for selected tool call to complete
   - Read `.quest/<id>/phase_02_implementation/handoff.json` for status/routing
   - Verify artifacts written (from handoff.artifacts)
   - Apply the **three-tier fallback ladder** from **Handoff File Polling** §6:
     - Classify failure via `classify_failure_kind` logic.
     - **Tier B** (write-boundary/permission): Codex → retry with `sandbox_permissions: "danger-full-access"` only with explicit user approval or an equivalent persisted approval. Bridge Claude → add out-of-workspace dirs via `--add-dir`. Native Claude → widen tool permissions.
     - **Tier C** (timeout, model, invocation, or Tier B exhausted):
       - **Timeout (`McpError`):** Skip retry. Invoke Claude runtime fallback for builder immediately.
       - **Other failures** (`needs_human`, malformed output, missing/unparsable handoff, `blocked`):
         1. Re-run same runtime once with strict non-interactive reminder ("no questions, no `needs_human`, explicit assumptions").
         2. If still non-compliant, invoke Claude runtime fallback for builder with the same artifact-path contract.
     - If the Claude runtime fallback uses the bridge, apply bridge failure handling from **Handoff File Polling**.
     - Only ask the user questions if the Claude runtime fallback returns `needs_human`.
   - If the final selected attempt still has missing/unparsable handoff.json, parse text handoff from response as last-resort compatibility fallback.

3. **Atomic transition:** `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition reviewing --status in_progress` — if this fails, report the validation error to the user and STOP. Do NOT modify state.json manually.

4. Proceed to Step 5

### Step 5: Review Phase

1. **Update state:** `status: in_progress`, `last_role: code_review_agent`

2. **Read review config from allowlist:**
   - `review_mode` (default: `auto`)
   - `fast_review_thresholds.max_files` (default: 5)
   - `fast_review_thresholds.max_loc` (default: 300)


3. **Build a change summary for Codex:**
   - Compute from git (the canonical source for what changed):
     - File list: `git diff --name-only`
     - Diff stats: `git diff --stat`
     - LOC totals: `git diff --numstat` and sum added + deleted.
   - Use the LOC totals and file count for `review_mode: auto`:
     - If file_count ≤ max_files AND loc_total ≤ max_loc → **fast**
     - Otherwise → **full**

4. **Invoke Code Reviewers:**

   **If `quest_mode == "solo"`:** Invoke ONLY Reviewer A. Skip Reviewer B entirely. Log: `Code review: dispatched=single (solo mode)` to `.quest/<id>/logs/parallelism.log`.

   **If `quest_mode == "workflow"` (default):** Invoke BOTH Code Reviewers IN PARALLEL.

   Read `models.code-reviewer-a` and `models.code-reviewer-b` from allowlist to determine runtime for each slot. If model is Claude, use Claude runtime; if Codex, use `mcp__codex__codex`.

   Two different models review independently for model diversity:
   - **Reviewer A**: dispatched by orchestrator → `.quest/<id>/phase_03_review/review_code-reviewer-a.md`
   - **Reviewer B** (workflow only): dispatched by orchestrator → `.quest/<id>/phase_03_review/review_code-reviewer-b.md`

   **Artifact preparation** (per Handoff File Polling §5): Resolve and prepare `review_code-reviewer-a.md` and `handoff_code-reviewer-a.json` in `.quest/<id>/phase_03_review/`, and `review_code-reviewer-b.md` and `handoff_code-reviewer-b.json` for Reviewer B (workflow mode only).

   **Slot A** (runtime per `models.code-reviewer-a`; full and fast modes):
   **Full mode**:
   ```
   Task(
     subagent_type: "code-reviewer",
     prompt: "You are Code Reviewer A.

     Read your instructions: .skills/quest/agents/code-reviewer.md

     (Optional, full mode only, if needed) Read: .skills/BOOTSTRAP.md, AGENTS.md

     Quest: .quest/<id>/quest_brief.md
     Plan: .quest/<id>/phase_01_plan/plan.md

     Changed files: <file list>
     Diff summary: <git diff --stat>

     Review ONLY the files listed above. Use git diff for details.

     Artifact files have been prepared for you. Overwrite these files directly:
     - .quest/<id>/phase_03_review/review_code-reviewer-a.md
     - .quest/<id>/phase_03_review/handoff_code-reviewer-a.json
     Do not create Quest artifacts via shell redirection, heredocs, or echo.

     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: fixer (if issues) or null (if clean)"
   )
   ```
   **Fast mode**:
   ```
   Task(
     subagent_type: "code-reviewer",
     prompt: "You are Code Reviewer A.


     Quest: .quest/<id>/quest_brief.md
     Plan: .quest/<id>/phase_01_plan/plan.md

     Changed files: <file list>
     Diff summary: <git diff --stat>

     Review ONLY the files listed above.
     List up to 5 issues, highest severity first.

     Artifact files have been prepared for you. Overwrite these files directly:
     - .quest/<id>/phase_03_review/review_code-reviewer-a.md
     - .quest/<id>/phase_03_review/handoff_code-reviewer-a.json
     Do not create Quest artifacts via shell redirection, heredocs, or echo.

     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: fixer (if issues) or null (if clean)"
   )
   ```

   **Slot B — Codex MCP** (full and fast modes):

   **Full mode**:
   ```
   mcp__codex__codex(
     model: <models.code-reviewer-b from allowlist>,
     prompt: "You are Code Reviewer B.
     Non-interactive rule: do not ask questions and do not return STATUS: needs_human. If details are missing, make explicit assumptions and continue.

     Read your instructions: .skills/quest/agents/code-reviewer.md

     (Optional, full mode only, if needed) Read: .skills/BOOTSTRAP.md, AGENTS.md

     Quest: .quest/<id>/quest_brief.md
     Plan: .quest/<id>/phase_01_plan/plan.md

     Changed files: <file list>
     Diff summary: <git diff --stat>

     Review ONLY the files listed above. Use git diff for details.

     Artifact files have been prepared for you. Overwrite these files directly:
     - .quest/<id>/phase_03_review/review_code-reviewer-b.md
     - .quest/<id>/phase_03_review/handoff_code-reviewer-b.json
     Do not create Quest artifacts via shell redirection, heredocs, or echo.

     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: fixer (if issues) or null (if clean)"
   )
   ```
   **Fast mode**:
   ```
   mcp__codex__codex(
     model: <models.code-reviewer-b from allowlist>,
     prompt: "You are Code Reviewer B.
     Non-interactive rule: do not ask questions and do not return STATUS: needs_human. If details are missing, make explicit assumptions and continue.


     Quest: .quest/<id>/quest_brief.md
     Plan: .quest/<id>/phase_01_plan/plan.md

     Changed files: <file list>
     Diff summary: <git diff --stat>

     Review ONLY the files listed above.
     List up to 5 issues, highest severity first.

     Artifact files have been prepared for you. Overwrite these files directly:
     - .quest/<id>/phase_03_review/review_code-reviewer-b.md
     - .quest/<id>/phase_03_review/handoff_code-reviewer-b.json
     Do not create Quest artifacts via shell redirection, heredocs, or echo.

     End with: ---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY
     NEXT: fixer (if issues) or null (if clean)"
   )
   ```
   - **Note:** The `<file list>` and `<git diff --stat>` values embedded in these prompts are intentional small metadata (summary statistics and file names, typically a few lines). This is operational data for scoping the review, not subagent artifact content, and does not conflict with the Context Retention Rule.
   - **Before issuing the calls**, record the current wall-clock time as `dispatch_start`
   - Issue BOTH calls in the SAME message for parallel execution
   - Wait for BOTH to complete
   - Record the current wall-clock time as `dispatch_end`
   - Read `.quest/<id>/phase_03_review/handoff_code-reviewer-a.json` and `handoff_code-reviewer-b.json`
   - Verify both review files exist (from handoff.artifacts)
   - Apply the **three-tier fallback ladder** from **Handoff File Polling** §6:
     - Claude slot follows the Claude-runtime precedence: native task may use direct text fallback; bridge path applies Tier B (permission escalation via `--add-dir`) for write-boundary/permission failures, then Tier C (retry once for timeout/malformed output, block immediately on auth/CLI failures).
     - Codex slot: classify failure via `classify_failure_kind` logic. Tier B (write-boundary/permission): retry with `sandbox_permissions: "danger-full-access"` only with explicit user approval or an equivalent persisted approval; otherwise stop and surface the approval need. Tier C (timeout, model, or Tier B exhausted): timeout → Claude runtime fallback immediately; other failures → retry once with strict non-interactive reminder, then Claude runtime fallback.

   **Parallelism check (orchestrator-timed):**
   1. Create `.quest/<id>/logs/` directory if it doesn't exist
   2. Append a line to `.quest/<id>/logs/parallelism.log`:
      ```
      Code review: dispatched=concurrent (wall: <dispatch_start>-<dispatch_end>)
      ```
      The wall-clock duration covers both agents. Since both calls are issued in the same message, they run concurrently by construction. Agent self-reported timestamps are unreliable and must NOT be used for parallelism verification.

5. **Check verdicts via handoff.json (with fallback):**
   - For each reviewer slot, use the `next` value obtained in step 4:
     - If handoff.json was successfully read → use its `next` and `summary` fields
     - If fallback was triggered after applying deterministic precedence (retry/fallback chain) → use `NEXT` and `SUMMARY` from parsed text `---HANDOFF---`

   **If `quest_mode == "solo"`:** Only Reviewer A's verdict matters:
   - If `next: "fixer"` → Transition atomically: `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition fixing --status in_progress` — if fails, report to user and STOP. Issues found, proceed to Step 6
   - If `next: null` → Transition atomically: `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition complete --status complete` — if fails, report to user and STOP. Review passed! Go to Step 7
   - Present summary:
     ```
     Review complete (solo):
       Reviewer A: "<summary from handoff or fallback>"
     Full review at: .quest/<id>/phase_03_review/review_code-reviewer-a.md
     ```

   **If `quest_mode == "workflow"` (default):**
   - If EITHER slot has `next: "fixer"` → Transition atomically: `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition fixing --status in_progress` — if fails, report to user and STOP. Issues found, proceed to Step 6
   - If BOTH have `next: null` → Transition atomically: `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition complete --status complete` — if fails, report to user and STOP. Review passed! Go to Step 7
   - Present summaries to user:
     ```
     Review complete:
       Claude: "<summary from handoff or fallback>"
       Codex: "<summary from handoff or fallback (after retry/fallback precedence)>"
     Full reviews at: .quest/<id>/phase_03_review/review_code-reviewer-a.md, .quest/<id>/phase_03_review/review_code-reviewer-b.md
     ```
   - Do NOT read the full review files for routing or status display

### Step 6: Fix Phase

**Read allowlist:** `gates.max_fix_iterations` (default: 3)

**Solo override:** `solo.max_fix_iterations` (default: 2)

**Solo mode cap:** If `quest_mode == "solo"`, cap `max_fix_iterations` at `min(solo.max_fix_iterations, gates.max_fix_iterations)`.

**Gate check:**
- Read `auto_approve_phases.fix_loop` from allowlist
- If false: Ask user "Code review found issues. Proceed with fixes?"

**Loop:**

1. **Update state:** `phase: fixing`, `fix_iteration += 1`, `last_role: fixer_agent`

2. **Invoke Fixer** (default Codex `mcp__codex__codex`, Claude runtime fallback):
   - Read `models.fixer` from allowlist.
   - If fixer model is Codex, invoke via `mcp__codex__codex`.
   - If fixer model is Claude, invoke through Claude runtime (native `Task(...)` when available, bridge in Codex-led sessions).
   - Prompt: Reference file paths only, do not embed content:
     - Code review A: `.quest/<id>/phase_03_review/review_code-reviewer-a.md`
     - Code review B: `.quest/<id>/phase_03_review/review_code-reviewer-b.md`
     - Changed files: <file list from git diff>
     - Quest brief: `.quest/<id>/quest_brief.md`
     - Plan: `.quest/<id>/phase_01_plan/plan.md`
   - **Artifact preparation** (per Handoff File Polling §5): Resolve and prepare `review_fix_feedback_discussion.md` and `handoff_fixer.json` in `.quest/<id>/phase_03_review/`.
   - Require the prompt to include:
     - If using Codex path: `Read your instructions: .skills/quest/agents/fixer.md`
     - Artifact files have been prepared for you. Overwrite these files directly:
       - `.quest/<id>/phase_03_review/review_fix_feedback_discussion.md`
       - `.quest/<id>/phase_03_review/handoff_fixer.json`
     - Do not create Quest artifacts via shell redirection, heredocs, or echo.
     - handoff.json schema: `{"status", "artifacts", "next", "summary"}`
     - End with: `---HANDOFF--- STATUS/ARTIFACTS/NEXT/SUMMARY`
     - `NEXT: code_review`
   - Wait for selected tool call to complete
   - Read `.quest/<id>/phase_03_review/handoff_fixer.json` for status/routing
   - Apply the **three-tier fallback ladder** from **Handoff File Polling** §6:
     - Classify failure via `classify_failure_kind` logic.
     - **Tier B** (write-boundary/permission): Codex → retry with `sandbox_permissions: "danger-full-access"` only with explicit user approval or an equivalent persisted approval. Bridge Claude → add out-of-workspace dirs via `--add-dir`. Native Claude → widen tool permissions.
     - **Tier C** (timeout, model, invocation, or Tier B exhausted):
       - **Timeout (`McpError`):** Skip retry. Invoke Claude runtime fallback for fixer immediately.
       - **Other failures** (`needs_human`, malformed output, missing/unparsable handoff, `blocked`):
         1. Re-run same runtime once with strict non-interactive reminder ("no questions, no `needs_human`, explicit assumptions").
         2. If still non-compliant, invoke Claude runtime fallback for fixer with the same artifact-path contract.
     - If the Claude runtime fallback uses the bridge, apply bridge failure handling from **Handoff File Polling**.
     - Only ask the user questions if the Claude runtime fallback returns `needs_human`.
   - If the final selected attempt still has missing/unparsable handoff.json, parse text handoff from response as last-resort compatibility fallback.

3. **Clear stale handoff files:** Delete any existing `handoff_code-reviewer-a.json` (and `handoff_code-reviewer-b.json` if workflow mode) in `.quest/<id>/phase_03_review/` to prevent stale data from the previous review iteration being read when code reviewers are re-invoked.

4. **Atomic transition:** `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition reviewing --status in_progress` — if fails, report to user and STOP. Do NOT modify state.json manually.

5. **Re-invoke Code Reviewers** (same dispatch rules as Step 5 — solo dispatches only Reviewer A, workflow dispatches both)

6. **Check verdict (with fallback):**
   - For each reviewer slot, use the `next` value obtained in step 5 (handoff.json preferred; text fallback only after deterministic precedence)

   **If `quest_mode == "solo"`:** Only Reviewer A's verdict matters:
   - If `next: null` → Fixed! Transition atomically: `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition complete --status complete` — if fails, report to user and STOP. Proceed to Step 7
   - If `next: "fixer"`:
     - If `fix_iteration >= max_fix_iterations` (capped at `min(solo.max_fix_iterations, gates.max_fix_iterations)`): Warn user, ask to proceed or review manually
     - Otherwise: Loop back to step 1

   **If `quest_mode == "workflow"` (default):**
   - If BOTH have `next: null` → Fixed! Transition atomically: `python3 scripts/quest_state.py --quest-dir .quest/<id> --transition complete --status complete` — if fails, report to user and STOP. Proceed to Step 7
   - If EITHER has `next: "fixer"`:
     - If `fix_iteration >= max_fix_iterations`: Warn user, ask to proceed or review manually
     - Otherwise: Loop back to step 1

### Step 7: Complete

1. **Update state:** `phase: complete`, `status: complete`

2. **Ask user before celebrating:**
   - Prompt: "Quest is complete! What would you like to do?"
     - **Celebrate!** — proceed to step 3 (run the celebration animation)
     - **Skip celebration** — go straight to step 4 (journal + summary, no animation)
   - In non-interactive / CI environments, skip the prompt and run the celebration automatically

3. **Run celebration (skill-first):**
   - Invoke the `celebrate` skill and provide the quest ID/path so it reads artifacts and renders rich markdown directly
   - Do NOT call the Python celebration script from this step in interactive agent flows
   - Optional fallback (non-interactive/runtime-only): `python3 scripts/quest_celebrate/celebrate.py --quest-dir .quest/<id> --style epic || true`
   - This step is fire-and-forget: if celebration fails, quest completion continues

4. **Create quest journal entry:**
    - Create `docs/quest-journal/` directory if it doesn't exist
    - Write to `docs/quest-journal/<slug>_<YYYY-MM-DD>.md`
    - Include: quest ID, completion date, summary, files changed, iterations
    - **Include a `celebration_data` JSON block** at the end of the journal entry. This block enables future `/celebrate` invocations to replay a rich celebration from the journal alone, even after the quest archive directory is cleaned up. The block should be embedded between HTML comment markers:

      ```markdown
      ## Celebration Data

      <!-- celebration-data-start -->
      ```json
      {
        "quest_mode": "workflow",
        "agents": [{"name": "...", "model": "...", "role": "..."}],
        "achievements": [{"icon": "⭐️", "title": "...", "desc": "..."}],
        "metrics": [{"icon": "📊", "label": "..."}],
        "quality": {"tier": "Gold", "icon": "🥇", "grade": "B"},
        "quote": {"text": "...", "attribution": "..."},
        "victory_narrative": "...",
        "test_count": 42,
        "tests_added": 10,
        "files_changed": 7
      }
      ```
      <!-- celebration-data-end -->
      ```

      The orchestrator should populate this from the quest artifacts it already read. Agents, achievements, and metrics should be context-aware and specific — not generic. The quality tier uses the full honest scale: Diamond/Platinum/Gold/Silver/Bronze/Tin/Cardboard/Abandoned.

      **Solo mode adjustments for celebration_data:**
      - Set `"quest_mode": "solo"` in the JSON
      - Solo quests will show fewer agents (expected) — note this in the context health report rather than treating it as missing data

    - Insert a row at the top of `docs/quest-journal/README.md` index table (after the header row) with date, quest link, and one-line outcome. The table is in reverse chronological order (newest first).
    - If quest originated from an idea file:
      - Quote the original idea content under "This is where it all began..."
      - Remove the idea file (e.g., `ideas/my-idea.md`)
      - Add a `done` row to `ideas/README.md` index: `| done | ~~idea-slug~~ | One-line pitch. See [journal](../docs/quest-journal/slug_date.md). |`

5. **Show summary:**
    - Quest ID
    - Files changed (from `git diff --name-only` and `state.json` artifact paths)
    - Total iterations (plan + fix, from `state.json`)
    - Parallel execution stats (read from `.quest/<id>/logs/parallelism.log` if it exists — show each line)
    - Location of artifacts (will be archived to `.quest/archive/<id>/`)
    - Location of journal entry

6. **Context health report:**
   If `.quest/<id>/logs/context_health.log` exists, display it in full:

   ```
   Context Health (handoff.json compliance):
   ---
   <contents of context_health.log, one line per agent>
   ---
   ```

   Then display a brief reflection, split by runtime and role:
   - Count entries with `source=handoff_json` vs `source=text_fallback`
   - Split by runtime using the `runtime=claude|codex` field from each log line
   - Runtime counts must come from logged runtime values only; do not infer runtime from role names.
   - Also split by role instance using `(phase, agent)` pairs (do NOT key by `agent` alone):
     - Planner = `(phase=plan, agent=planner)`
     - Plan Review Slot A = `(phase=plan_review, agent=plan-reviewer-a)`
     - Plan Review Slot B = `(phase=plan_review, agent=plan-reviewer-b)`
     - Arbiter = `(phase=plan_review, agent=arbiter)`
     - Builder = `(phase=build, agent=builder)`
     - Code Review Slot A = `(phase=code_review, agent=code-reviewer-a)`
     - Code Review Slot B = `(phase=code_review, agent=code-reviewer-b)`
     - Fixer = `(phase=fix, agent=fixer)`
   - For each role instance, report `X/Y` where:
     - `Y` = total observed invocations for that exact `(phase, agent)` pair in the log
     - `X` = observed invocations for that exact `(phase, agent)` pair with `source=handoff_json`
   - If a role/runtime did not run in this quest, display `0/0 (n/a)` instead of implying failure
   - Display:
     ```
     Handoff.json compliance:
       Claude agents: <N>/<total> (<percentage>%)
       Codex agents:  <N>/<total> (<percentage>%)
       Overall:       <N>/<total> (<percentage>%)

     Role-level compliance:
       Planner (<runtime>): <X>/<Y> (<percentage or n/a>)
       Plan Review Slot A (<runtime>): <X>/<Y> (<percentage or n/a>)
       Plan Review Slot B (<runtime>): <X>/<Y> (<percentage or n/a>)
       Arbiter (<runtime>): <X>/<Y> (<percentage or n/a>)
       Builder (<runtime>): <X>/<Y> (<percentage or n/a>)
       Code Review Slot A (<runtime>): <X>/<Y> (<percentage or n/a>)
       Code Review Slot B (<runtime>): <X>/<Y> (<percentage or n/a>)
       Fixer (<runtime>): <X>/<Y> (<percentage or n/a>)
     ```
   - For codex-only quests, explicitly show `Claude agents: 0/0 (n/a)` if no Claude entries exist.
   - If overall compliance is 100%:
     "All agents wrote handoff.json. Orchestrator routed via structured handoff files throughout."
   - If compliance is 75-99%:
     "Most agents complied. <list non-compliant agents>. Consider tweaking instructions for those agents."
   - If compliance is 50-74%:
     "Mixed compliance. Investigate non-compliant agents. Consider upgrading to run_in_background: true for native Claude Task agents."
   - If compliance is <50%:
      "Low compliance -- discard approach is not effective. Recommend upgrading to run_in_background: true."

6. **Archive the quest working directory:**
    - Create `.quest/archive/` if it doesn't exist
    - Move `.quest/<id>/` to `.quest/archive/<id>/`
    - The journal entry in `docs/quest-journal/` is the permanent record; the archive preserves raw artifacts for reference
    - `.quest/` root should only contain active quests, `archive/`, and `audit.log`

7. **Next steps suggestion:**
    ```
    Review changes: git diff
    Commit: git add -p && git commit
    ```
    - **Draft PR:** use `.skills/pr-assistant/SKILL.md` (preserve any existing bot-managed PR sections when editing PR body)
    - **PR review gate:** post an explicit review comment on the draft/ready PR, then merge only after NIT filtering using `AGENTS.md` rubric (readability-first, KISS/YAGNI/SRP/DRY, simple robust over complex elegance, avoid mocking-hell)

8. **Context reset suggestion:**
    ```
    Quest complete. Consider running /clear before your next quest to reset context.
    ```

9. **Check for Quest updates:**
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

## Q&A Loop Pattern (Claude runtime only in normal operation)

Normal rule:
- Codex paths do not enter direct human Q&A. On timeout they fall back to Claude immediately; on other failures they retry once then fall back to Claude.
- Human Q&A is used when a Claude runtime role returns `STATUS: needs_human` (native `Task(...)` or bridge-invoked Claude).

If a Claude role returns `STATUS: needs_human`:

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

## Subagent Prompt Patterns

### Agent-to-Tool Mapping

| Role | Allowlist Key | Default | Runtime |
|------|---------------|---------|---------|
| Planner | `models.planner` | `claude` | Claude runtime or Codex per config |
| Plan Reviewer A | `models.plan-reviewer-a` | `claude` | Claude runtime or Codex per config |
| Plan Reviewer B | `models.plan-reviewer-b` | `gpt-5.4` | Claude runtime or Codex per config |
| Arbiter | `models.arbiter` | `claude` | Claude runtime or Codex per config |
| Builder | `models.builder` | `gpt-5.4` | Codex or Claude runtime per config |
| Code Reviewer A | `models.code-reviewer-a` | `claude` | Claude runtime or Codex per config |
| Code Reviewer B | `models.code-reviewer-b` | `gpt-5.4` | Claude runtime or Codex per config |
| Fixer | `models.fixer` | `gpt-5.4` | Codex or Claude runtime per config |

All role-to-model assignments are read from `.ai/allowlist.json` → `models`. The defaults above apply when a key is missing. **Model diversity** in review phases gives independent perspectives from different model families. If roles are executed through Codex-backed tools, runtime attribution in `context_health.log` must record `codex`.

### Codex MCP Prompt Pattern

**IMPORTANT:** Keep Codex prompts SHORT. Point to files, let Codex read them. Prefer the context digest over full docs.

```markdown
You are the <ROLE>.

Read your instructions: .skills/quest/agents/<role>.md

Optional (full mode only, if needed): .skills/BOOTSTRAP.md, AGENTS.md

Quest brief: .quest/<id>/quest_brief.md
<other relevant files as paths>

<specific task instruction>

Write output to: .quest/<id>/<path>
Write handoff file to: .quest/<id>/<phase>/handoff.json

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
  model: <models.plan-reviewer-b from allowlist>,
  prompt: "Review .quest/<id>/phase_01_plan/plan.md

  List any issues (max 5 bullets). Write to .quest/<id>/phase_01_plan/review_plan-reviewer-b.md

  End with: ---HANDOFF--- STATUS: complete ARTIFACTS: .quest/<id>/phase_01_plan/review_plan-reviewer-b.md NEXT: arbiter SUMMARY: <one line>"
)
```

**Tradeoff:** Simpler prompts = faster but less thorough review.

---

## Error Handling

- If an agent fails to produce a handoff: Extract any artifacts from the response, log the error, ask user how to proceed
- If a bridge-invoked Claude role times out: retry once; if it times out again, treat the step as blocked and surface the timeout
- If a bridge-invoked Claude role fails due to CLI/auth/environment problems: block immediately and tell the user how to repair the local Claude bridge
- If a bridge-invoked Claude role fails with malformed output or missing handoff: retry once with a strict reminder, then use text handoff fallback if possible; otherwise block
- If Codex MCP times out: fall back to equivalent Claude role immediately (no retry — timeouts rarely recover on retry)
- If Codex MCP fails (non-timeout): retry once with strict non-interactive reminder; if failure persists, fall back to equivalent Claude role; ask user only if fallback also cannot proceed
- If max iterations reached: Stop, show current state, ask user for guidance
- If artifact file missing after agent run: Try to extract from response text and write it

---

## Utility Commands

**`/quest status`** — List all quests with their current phase

**`/quest status <id>`** — Show detailed status for a specific quest

**`/quest allowlist`** — Display current allowlist configuration
