# Slice 2: dispatch, installation and acceptance

Status: Implemented, independently reviewed, live acceptance passed. Covers AC2-AC6.

## Before editing: prove the integration boundary

Inspect scripts/quest_claude_runner.py, scripts/quest_runtime/claude_runner.py, scripts/quest_claude_bg_run.py, scripts/quest_preflight.sh and all Claude dispatch sites in .skills/quest/SKILL.md and .skills/quest/delegation/workflow.md. Inspect canonical role instructions and their native wrappers.

Write a short mapping for all nine canonical roles: instruction source, prompt inputs, allowed actions, artifact contract, orchestrator entrypoint. Shared reviewer files must retain A/B identity and distinct saved settings. Determine how the existing background runner receives instructions and restricts tools/writes. A native agent name alone does not load its instructions into a new background session. Do not equate add-dir, prompt instructions or bypass mode with an enforced write boundary.

## Implementation steps

1. Update select_role_runtime in scripts/quest_runtime/claude_runner.py so Claude roles under either orchestrator select the existing runner, gated by actual transport readiness. Preserve Codex and Gemini entrypoints. Avoid unrelated naming/refactor changes.
2. Extend existing preflight/startup wiring to probe Claude background readiness when a selected role needs it, including Claude-led startup. Reuse cache and setup guidance. Handle mixed-runtime selections. A native Claude parent does not prove background readiness. Do not add another probe framework.
3. At the Quest role entrypoint, read saved model and effort from orchestration.json. Saved settings govern role dispatch; conflicting role-level flags must not silently override them. Preserve standalone low-level runner flags if already supported outside Quest. Scope this distinction explicitly in help/docs.
4. Forward saved effort through the existing Claude runner into the background command. Reuse existing model normalization and runtime effort validation. No native Task fallback and no agent-file mutation. Preserve explicit bridge behavior shipped on main only as required by the shared interface; no bridge expansion or live API call.
5. Compose prompts from existing canonical role instructions plus existing phase inputs. Preserve role permissions, workspace/quest path separation, artifact subset behavior and current-attempt handoff validation. Pass explicit permission settings matching the role contract; do not inherit the wrapper's bypassPermissions default without assessing the actual boundary. If necessary restrictions cannot be preserved with existing controls, report the blocker rather than build a new permission framework.
6. Wire saved effort through scripts/quest_runtime/codex_runner.py for Claude-led Codex roles and native-subagent instructions for Codex-led roles. Keep native control availability checks and requested/effective distinctions. Never use nested Codex CLI as a Codex-led workaround.
7. Update workflow.md dispatch matrix, per-phase examples, startup descriptions and setup docs together. Starting from main, simply omit #179's generated frontmatter and native guard. Do not delete native agent files or unrelated support.
8. Run disposable fresh-install and customized-old-install cases using actual installer logic with local source payloads. First test whether stale skill/runtime files can produce mixed dispatch. If incompatible, prefer existing explicit overwrite/refusal mechanisms. Add a narrow installer fix only for a reproduced failure; pause for scope review if this requires general installer redesign. Never destroy customized files silently.

## Deterministic verification

Extend existing tests/unit/test_quest_runtime.py, test_codex_runner.py, test_quest_claude_bg_run.py and test_quest_dispatch_guardrails.py as appropriate; add tests/integration/test_quest_effort_dispatch.py only for cross-component behavior lacking a home. Use real temp configuration/artifacts and replace the external process boundary only. Do not build an LLM simulator.

- test_claude_role_uses_background_for_either_orchestrator: both selections use runner; unavailable transport blocks; no native/API fallback.
- test_saved_model_and_effort_reach_background_command: pass real config through wrapper to captured external argv. Divergent reviewer A/B values remain distinct; stale allowlist does not win.
- test_claude_led_startup_requires_background_probe: existing preflight fixture covers available and unavailable background runtime alongside Codex readiness.
- test_role_prompt_contains_canonical_instructions: inspect actual prompt assembly/dispatch artifact, not just a documentation substring; verify A/B role identity.
- test_codex_role_forwards_saved_effort: exact selected arguments; mismatched/unavailable native controls block.
- Reuse existing tests for denied permission, missing/malformed/stale handoff, timeout, cancellation and teardown_failed. Add cases only where the changed entrypoint is not covered. Success requires runner completion and valid current-attempt artifacts, not merely an early handoff file.
- Integration installation fixture: fresh install, customized old files, incompatible saved quest. Assert the agreed complete-or-actionable-refusal behavior. Demonstrate a failure before adding any installer fix.

Run focused modified suites, then final checks once on the candidate revision:

```sh
PYTHONPATH=scripts python3 -m pytest tests/ -q
python3 -m black --check .
python3 scripts/quest_sync_model_defaults.py --check
bash tests/test-quest-preflight.sh
bash tests/test-quest-runtime.sh
bash tests/test-quest-orchestration.sh
bash tests/test-validate-handoff-contracts.sh
bash tests/test-validate-quest-state.sh
bash scripts/quest_validate-manifest.sh
bash scripts/quest_validate-quest-config.sh
bash scripts/quest_validate-quest-state.sh "<valid-fixture-quest-dir>" "<fixture-target-phase>"
```

Replace the state-validator placeholders with an actual valid test quest and its intended phase; invoking that script without arguments is not a check. Use the environment established by pyproject.toml and current CI; record unavailable tools instead of claiming checks passed. Inspect current CI for required checks added since planning.

## Live acceptance, executable by agents

Preconditions: disposable installed repository from candidate SHA, synthetic inputs only, existing authenticated subscriptions, recorded CLI versions, normal role timeout 1800 seconds. No production writes, automatic API fallback, permission broadening or new billing setup. Use existing runner artifact checks; silence alone is not failure.

1. Codex-led Claude review: dispatch a review role using saved model/effort and real role instructions. Verify read/review result, canonical findings/handoff and clean teardown. Record command arguments and independent Claude transcript model/effort metadata.
2. Claude-led Claude review: a real Claude orchestrator follows the updated installed workflow and invokes the role runner. Verify it does not use native Task or paid bridge. Use a different supported saved effort from case 1 to expose hardcoded defaults; verify requested and observed values.
3. Claude write role: dispatch builder or fixer in a synthetic repo with one tiny approved edit and canonical handoff. Verify expected edit, artifact paths and cleanup. Test a controlled denied action with actual permission controls; do not treat a model declining a prompt as proof of enforcement.
4. Codex regression: invoke a Codex role from each orchestrator through its established entrypoint. Verify tiny synthetic artifacts and requested model/effort. If runtime metadata cannot establish effective values, record unknown explicitly; never infer from model self-report or token count.
5. Setup failure: exercise unavailable background setup with the existing deterministic fixture; check blocked state and actionable guidance. Real cancellation may be tested with one bounded disposable session if changed code invalidates existing evidence. Do not force repeated paid timeouts to duplicate deterministic lifecycle coverage.

MANUAL TEST, only if authentication/setup blocks agent execution: human completes the specific login/setup action described by the existing setup guide, then agents rerun the blocked case. Report that dependency and exact test status. Human judgment is needed for default-effort policy, not repeated mechanical acceptance.

## Result ledger and reviewer stop conditions

Record case, SHA, CLI versions, requested model/effort, observed model/effort or unknown, result, sanitized evidence location, and cleanup state. Passing old-PR tests are historical evidence only. Do not commit raw transcripts, credentials or machine-specific auth files.

Independent reviewer must confirm: every changed file traces to AC1-AC6, no new config hierarchy, no effort frontmatter, no silent fallback, no role-instruction/permission regression, no unrelated policy/model defaults. Fix concrete blockers, defer optional improvements. Report any untested runtime behavior precisely. Deliver a small reviewable patch even if required cross-layer files make its file count nontrivial; do not game a line-count target.
