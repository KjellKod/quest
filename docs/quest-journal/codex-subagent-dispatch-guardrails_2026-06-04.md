# Quest Journal: Codex Subagent Dispatch Guardrails

- Quest ID: `codex-subagent-dispatch-guardrails_2026-06-04__1341`
- Slug: codex-subagent-dispatch-guardrails
- Completed: 2026-06-04
- Mode: workflow
- Quality: Platinum
- Celebration: [`celebrations/codex-subagent-dispatch-guardrails_2026-06-04.md`](celebrations/codex-subagent-dispatch-guardrails_2026-06-04.md)
- Outcome: Fix Quest Codex-led role dispatch so Codex roles use local subagents, never Codex MCP. Context: In Codex-led Quest runs, agents are still sometimes trying to invoke Codex through MCP (`mcp__codex*`...

## What Shipped

**Problem:** Codex-led Quest role dispatch still documents and selects Codex MCP for Codex roles in several Codex-facing paths. In a Codex-orchestrated session this can route a Codex role back through `mcp__codex*`, `codex_codex`, or Codex CLI model aliases, causing model/account failures that ar...

## Files Changed

- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_01_plan/plan.md`
- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_01_plan/arbiter_verdict.md`
- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_01_plan/review_findings.json`
- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_01_plan/review_backlog.json`
- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_01_plan/handoff_arbiter.json`
- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_01_plan/review_plan-reviewer-b.md`
- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_02_implementation/pr_description.md`
- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_02_implementation/builder_feedback_discussion.md`
- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_03_review/review_code-reviewer-a.md`
- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_03_review/review_findings_code-reviewer-a.json`
- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_03_review/review_code-reviewer-b.md`
- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_03_review/review_findings_code-reviewer-b.json`
- `.quest/codex-subagent-dispatch-guardrails_2026-06-04__1341/phase_03_review/review_fix_feedback_discussion.md`
- `.skills/quest/agents/plan-reviewer.md`
- `.skills/quest/agents/code-reviewer.md`
- `.skills/quest/agents/arbiter.md`
- `tests/unit/test_quest_dispatch_guardrails.py`

## Iterations

- Plan iterations: 0
- Fix iterations: 1

## Agents

- **The Judge** (arbiter): 
- **The Implementer** (builder): 
- **The Bug Slayer** (fixer): 

## Quest Brief

Fix Quest Codex-led role dispatch so Codex roles use local subagents, never Codex MCP.

Context:
In Codex-led Quest runs, agents are still sometimes trying to invoke Codex through MCP (`mcp__codex*`, `codex_codex`, Codex CLI model aliases) instead of using the local Codex subagent tool path. This causes account/model compatibility failures such as `The '<model>' model is not supported when using Codex with a ChatGPT account.` The desired behavior is: when the orchestrator itself is Codex and a Quest role is assigned to Codex, dispatch that role through local subagents (`multi_agent_v1.spawn_agent` or the repo-supported equivalent), inheriting the current Codex model by default. Do not set a Codex model name unless the user explicitly requested one or the repo has a tested reason.

Workspace:
Use a separate worktree branch. Create a worktree branch named `quest/codex-subagent-dispatch-guardrails` from current `origin/main`. Preserve unrelated dirty files. Do not modify source/product files before the Build gate.

Scope:
Make surgical improvements only. Focus on Quest runtime-selection instructions, Codex-facing skill wrappers, validation/tests, and clear failure guidance. Do not broadly redesign Quest.

Required changes:
1. Update Quest dispatch instructions so the runtime-selection contract is unambiguous:
   - Codex-led + Codex runtime role => local Codex subagent path, not Codex MCP.
   - Codex-led + Claude runtime role => `scripts/quest_claude_runner.py` bridge path when available.
   - Claude-led + Codex runtime role => Codex MCP may be used.
   - Claude-led + Claude runtime role => native Claude `Task(...)`.
   - Make clear that `model` and `transport/entrypoint` are different concepts.
2. Update `.skills/gpt/SKILL.md` surgically:
   - It may remain the Claude-led Codex MCP skill.
   - It must clearly say it is not the Codex-led Quest role dispatch path.
   - It must clearly say: if you are already Codex, do not call Codex MCP to create another Codex role; use local subagents for Quest role delegation.
   - Remove or qualify any wording that says Quest routes Codex roles through this MCP skill unconditionally.
3. Update Codex-facing Quest wrapper/instructions:
   - `.agents/skills/quest/SKILL.md` or an adjacent Codex-specific overlay must explicitly state that Codex-led Quest roles assigned to Codex use local subagents.
   - The Codex-facing surface must not direct Codex to use `mcp__codex*`, `codex_codex`, or Codex CLI model aliases for Codex roles.
4. Add or update tool-level guardrails:
   - Add static tests/canaries that fail if Codex-facing Quest instructions contain forbidden Codex MCP dispatch language.
   - Add tests that enforce the dispatch matrix:
     - orchestrator=`codex`, runtime=`codex` => entrypoint=`subagent`
     - orchestrator=`codex`, runtime=`claude` => entrypoint=`quest_claude_runner.py` or blocked with bridge guidance
     - orchestrator=`claude`, runtime=`codex` => entrypoint=`codex_mcp`
     - orchestrator=`claude`, runtime=`claude` => entrypoint=`Task`
   - Prefer a small typed helper if the repo already has a runtime-selection helper. Do not leave this only as prose if a small tested helper is practical.
5. Fail fast with clear correction guidance:
   - If a Codex-led Quest attempts to dispatch a Codex runtime role through MCP, the workflow must treat it as an orchestration violation, not a model-selection problem.
   - The error/guidance should say exactly how to correct it: use local Codex subagents for Codex-led Codex roles; only use Codex MCP from Claude-led sessions.
   - Logging should distinguish `runtime` from `entrypoint` where practical, so future failures show whether a role used `subagent`, `codex_mcp`, `Task`, or `quest_claude_runner.py`.

Acceptance criteria:
- In Codex-led Quest instructions, Codex roles no longer instruct or imply use of Codex MCP.
- `.skills/gpt/SKILL.md` clearly excludes Codex-led Quest role dispatch and points to subagents instead.
- Static tests fail if Codex-facing Quest docs regress to `mcp__codex*`, `codex_codex`, or Codex CLI model alias dispatch for Codex-led Codex roles.
- Runtime-selection tests cover the four orchestrator/runtime combinations above.
- Any fail-fast path gives actionable guidance, not a vague model/account compatibility message.
- Existing Quest tests still pass.
- Changes are surgical and do not rewrite unrelated Quest workflow behavior.

Validation:
- `python3 -m pytest tests/unit/test_codex_skill_wrappers.py`
- `python3 -m pytest tests/unit/test_runtime_agent_role_files_reference_canonical.py`
- `bash tests/test-quest-orchestration.sh`
- `bash tests/test-quest-preflight.sh`
- `bash tests/test-quest-runtime.sh`
- Any new focused tests added for dispatch helper or static canaries
- `git diff --check`

PR and completion:
After implementation and validation, use `pr-assistant` to open a draft PR. The PR description must include problem summary, dispatch matrix, acceptance criteria mapping, validation commands and results, and remaining risk. Then complete the Quest normally: review/fix loop, archive the Quest when complete, and trigger celebration.

## Carry-Over Findings

- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- Full celebration: [`celebrations/codex-subagent-dispatch-guardrails_2026-06-04.md`](celebrations/codex-subagent-dispatch-guardrails_2026-06-04.md)
- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/codex-subagent-dispatch-guardrails_2026-06-04.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "workflow",
  "agents": [
    {
      "name": "arbiter",
      "model": "",
      "role": "The Judge"
    },
    {
      "name": "builder",
      "model": "",
      "role": "The Implementer"
    },
    {
      "name": "fixer",
      "model": "",
      "role": "The Bug Slayer"
    }
  ],
  "achievements": [
    {
      "icon": "[BUG]",
      "title": "Gremlin Slayer",
      "desc": "Tackled 6 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 6 reviews"
    },
    {
      "icon": "[WIN]",
      "title": "Quest Complete",
      "desc": "All phases finished successfully"
    }
  ],
  "metrics": [
    {
      "icon": "📊",
      "label": "Plan iterations: 0"
    },
    {
      "icon": "🔧",
      "label": "Fix iterations: 1"
    },
    {
      "icon": "📝",
      "label": "Review findings: 6"
    }
  ],
  "quality": {
    "tier": "Platinum",
    "grade": "P"
  },
  "inherited_findings_used": {
    "count": 0,
    "summaries": []
  },
  "findings_left_for_future_quests": {
    "count": 0,
    "summaries": []
  },
  "test_count": null,
  "tests_added": null,
  "files_changed": 18
}
```
<!-- celebration-data-end -->
