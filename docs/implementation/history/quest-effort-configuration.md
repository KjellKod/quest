# Slice 1: saved effort contract

Status: Implemented and independently reviewed. Decisions recorded in [parent plan](quest-effort-replacement.md).

## Observable outcome

A quest has an unambiguous saved effort for every active Claude/Codex role. Later repository default changes cannot change an existing quest's dispatch request. Invalid settings fail before model invocation. Covers AC1 and configuration portions of AC3/AC5.

## Steps for builder

1. On fresh main, inspect current orchestration writer, reader, resume, snapshot/restore and solo-mode paths. Compare only relevant hunks of #179. List what already exists on main before adding anything.
2. Add the approved effort shape to .ai/schemas/allowlist.schema.json and approved values to .ai/allowlist.json. Keep models, review_mode and iteration limits at main's values unless separately approved. If the proposed required-map contract is accepted, remove codex_reasoning_effort from the saved-orchestration writer/chooser call chain; new saved configurations emit only the map. Retain the allowlist/schema scalar exclusively for standalone /gpt, whose existing medium default is out of scope. Allowlist snapshots include standalone settings, so restoration selects only the effort map. Do not retire unrelated standalone CLI settings. Reject mixed old/new saved configuration with explicit recovery guidance rather than retain ambiguous precedence.
3. Modify scripts/quest_runtime/orchestration.py: reuse canonical roles; add/reuse a small validator and effort_for_role resolver; snapshot the allowlist at quest creation; validate on load/resume/restore without rewriting saved settings. Apply the agreed missing-field policy. Resolve model family before validating effort support. Reuse the existing runtime validators instead of adding a provider catalog.
4. Update scripts/quest_validate-quest-state.sh and the startup chooser in .skills/quest/SKILL.md to match the contract. Display saved settings using the existing startup summary. Avoid a new effort override parser/UI.
5. Inspect scripts/quest_sync_model_defaults.py. Only change its existing Python-default generation if required by actual creation paths. Never generate effort into .claude/agents/*.md or .opencode/opencode.json. Do not create another defaults table by hand. If no duplicate Python defaults are needed, leave generator unchanged.
6. Reject unsupported settings with role, runtime and recovery guidance before invocation. Do not claim to validate provider support beyond verified installed CLI capabilities. Unknown model-specific support must surface as a provider error, not be silently remapped.
7. Update .ai/quest.md and docs/guides/quest_setup.md only where the configuration contract or restart/reconfigure instructions change.

## Focused tests

Use tests/unit/test_quest_effort.py (new on main if absent) and existing orchestration/state tests. Mock only launch boundaries; use real temporary JSON files and real config functions. Write a failing regression before fixing a reproduced defect.

| Proposed test | Expected |
| --- | --- |
| test_new_quest_snapshots_approved_role_effort | Real shipped allowlist through the real default/startup writer produces exact approved active-role values, map only, and passes saved-state validation |
| test_resume_uses_saved_effort_after_allowlist_changes | Saved values unchanged, including snapshot restore |
| test_missing_required_effort_rejects_before_dispatch | Actionable rejection; launch boundary never called |
| test_unknown_role_or_invalid_effort_rejects | Invalid map rejected; no partial config write |
| test_solo_unused_role_needs_no_effort | Null inactive role accepted |
| test_gemini_effort_pin_rejects_without_launch | Existing Gemini dispatch accepted without pin; explicit unsupported effort fails |
| test_conflicting_legacy_scalar_and_map_rejects | No hidden precedence |

Adapt names/policies to section 1's final decisions, not vice versa. Parameterize only genuinely shared cases. Do not port guard/frontmatter tests from #179.

Run from the replacement worktree with its Python environment:

```sh
PYTHONPATH=scripts python3 -m pytest tests/unit/test_quest_effort.py -q
bash tests/test-quest-orchestration.sh
bash tests/test-validate-quest-state.sh
python3 scripts/quest_sync_model_defaults.py --check
```

## Integration and handoff

Allowlist schema, startup writer, saved-state validation and restore can disagree: exercise the same fixture through each real entrypoint. Generator drift can change unrelated defaults: inspect its diff and check output. Report changed files/functions, accepted decision table, exact commands/results and remaining unknowns to the dispatch builder. No live model call needed for this slice.

## Execution evidence

- Implemented against main 2cf4d5815fae1af258af52097e851ae86288494e in feat/quest-effort-dispatch. No model or review-policy changes.
- Saved Quest config uses the map only; the allowlist scalar remains a standalone /gpt default. Snapshot restoration selects the map, ignores the standalone scalar, and rejects incompatible saved quests without rewriting them.
- Active-role completeness uses quest mode. Gemini omission is accepted and explicit pins reject. Unused solo roles can omit pins or retain valid unused defaults.
- Red regression: test_role_forwards_saved_per_role_effort failed because the actual Codex argv omitted saved builder low. Same test passes after the consumer change. Evidence: /tmp/quest-effort-config-red.log.
- Focused Python suite: 92 passed, followed by 3 added no-launch cases passing and 17 configuration cases passing after whitespace-model validation. Logs: /tmp/quest-effort-config-python.log.
- Shell checks: orchestration 36/36, state validation 72/72. Logs: /tmp/quest-effort-config-orchestration.log and /tmp/quest-effort-config-state.log.
- Formatting passed on owned Python files. Model-default generator check passed with no generator changes.
- State validation reuses the canonical Python validator. Disposable copied-script test fixtures now include the existing runtime package, matching installation.
- No live model call in this slice; dispatch acceptance remains assigned to the dispatch/coordinator slice.
