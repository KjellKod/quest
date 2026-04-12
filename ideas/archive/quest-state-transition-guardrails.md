# Quest State Transition Guardrails

## Status: done

## Problem

Quest currently has a state-transition footgun in the orchestration path:

1. The workflow requires validation before mutating `state.json`.
2. The documented helper for state mutation is `python3 scripts/quest_state.py`.
3. That helper does not exist.
4. The real mutation code lives in `scripts/quest_runtime/state.py`, which is a library module, not an operator-facing CLI.

In practice, that pushes operators into manual `state.json` edits during live quest runs. One wrong ordering step is enough to dead-end the validator with transitions like `building -> building`, even when the underlying build work is valid.

There is also a policy/runtime mismatch:

- `workflow.md` says interactive plan presentation is a mandatory stop before build.
- `quest_validate-quest-state.sh` still allows direct `plan_reviewed -> building`.

So the documented contract is stricter than the enforced state machine.

## Incident That Exposed This

During a real Quest-driven Legion slice:

- plan review completed successfully
- presentation completed
- build was approved and implemented
- the orchestrator manually updated quest state to `building`
- then ran the `building` validation gate

The validator correctly rejected the transition because the state was already `building`.

This was operator error, but the framework made the mistake easy:

- the documented state helper does not exist
- validation and mutation are separate manual steps
- the validator enforces one sequence while the workflow text relies on the operator to remember it

## Goals

1. Make the correct phase transition path the easiest path.
2. Remove the need for manual `state.json` edits during normal quest operation.
3. Align enforced transitions with the “mandatory” workflow gates.
4. Catch broken helper references in Quest’s own validation scripts.
5. Reduce duplicated timeout defaults in the Claude bridge path.

## Proposed Changes

### 1. Ship a real `scripts/quest_state.py` CLI

Add the operator-facing CLI that `workflow.md` already tells people to use.

Minimum behavior:

- `--quest-dir`
- `--phase`
- `--status`
- `--last-role`
- `--last-verdict`
- update `updated_at`

It should be a thin wrapper around `scripts/quest_runtime/state.py`.

This closes the current doc/runtime mismatch immediately.

### 2. Add an atomic transition command

Better than a generic setter:

```bash
python3 scripts/quest_state.py \
  --quest-dir .quest/<id> \
  --transition building \
  --status in_progress \
  --last-role builder_agent
```

That command should:

1. read current state
2. run the same transition validation logic
3. fail with a clear error if the transition is invalid
4. write the new state only if validation succeeds

This removes the split-brain workflow of “validate first, then mutate separately.”

### 3. Enforce the presentation gate if it is truly mandatory

Today:

- workflow says presentation is mandatory
- validator allows skipping directly from `plan_reviewed` to `building`

Choose one:

1. enforce presentation by removing `plan_reviewed -> building`, or
2. keep the shortcut but stop calling presentation mandatory

The current middle state creates false confidence.

### 4. Strengthen Quest’s self-validation

`scripts/quest_validate-handoff-contracts.sh` currently checks that `workflow.md` mentions `scripts/quest_state.py`, but it does not verify that the script exists.

Add checks that:

- every referenced helper script actually exists
- key workflow references point to executable or importable helpers

This would have caught the missing helper before runtime.

### 5. Centralize Claude timeout defaults

The current timeout defaults are duplicated across:

- `scripts/quest_claude_bridge.py`
- `scripts/quest_claude_runner.py`
- `scripts/quest_claude_probe.py`

Move that to one shared constant or config source so timeout policy changes do not require touching multiple files.

## Suggested Implementation Order

1. add `scripts/quest_state.py`
2. switch `workflow.md` references to the real helper
3. add atomic validated transitions
4. tighten `quest_validate-handoff-contracts.sh`
5. decide whether presentation is actually mandatory, then align validator and workflow
6. centralize timeout defaults

## Acceptance Criteria

- `scripts/quest_state.py` exists and works as documented
- orchestrators no longer need to hand-edit `state.json` for normal quest progression
- invalid transitions fail before state is mutated
- Quest validation fails if workflow references a missing helper script
- workflow and validator agree on whether presentation may be skipped
- Claude timeout defaults are defined in one place

## Non-Goals

- No redesign of the overall Quest phase model
- No new UI around quest state
- No broad refactor of the Claude bridge runtime

## Why This Matters

This is not polish. State progression is Quest’s control plane. If the documented helper is missing and the enforced state machine differs from the documented workflow, operators will keep falling into avoidable bookkeeping failures even when the underlying coding work is correct.
