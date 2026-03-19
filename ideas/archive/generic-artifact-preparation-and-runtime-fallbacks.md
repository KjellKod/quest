# Generic Artifact Preparation And Runtime Fallbacks

Status: archived

Archived: 2026-03-18

Outcome:
- Implemented on branch `codex-artifact-staging`
- Draft PR: `#74`
- Kept as archive context now that the active proposal has been executed

## Question

How should Quest reduce artifact-write permission failures and shell-based artifact creation noise in a way that stays generic across Claude-led and Codex-led runs?

## Position

Treat this as one runtime-neutral orchestration problem with three linked rules:

1. Quest-owned artifacts should be workspace-local by default.
2. The orchestrator should prepare expected artifact files before each role invocation.
3. Fallbacks should distinguish permission/transport failures from model/runtime failures.

This should apply whether:
- Claude orchestrates Claude natively
- Claude orchestrates Codex
- Codex orchestrates Claude through the bridge
- Codex orchestrates Codex

For Codex, assume `gpt-5.4` is the target model.

## What We Learned

The most important insight is:

- missing `handoff.json` was often a **write failure**, not a handoff-contract failure

In the failing case, Codex was asked to write quest artifacts to an absolute `.quest` path outside the active repo workspace. Under sandboxed execution, that caused:

1. artifact write failure
2. missing `handoff.json`
3. Quest falling back to text `---HANDOFF---`

So the root cause was primarily:
- artifact path / writable-workspace mismatch

not:
- handoff schema quality
- text parsing
- Codex reasoning quality

## Problem Statement

Quest currently mixes together several concerns:

- where quest artifacts live
- who creates/truncates them
- how agents write them
- what fallback should happen when a write fails

This creates noisy permission prompts and fragile handoff compliance, especially for Codex roles.

The wrong fix is broadening permissions globally.

The better fix is to define a generic orchestration model that:
- keeps normal artifact paths workspace-local
- preps files before invocation
- escalates permissions only when the failure is specifically a write-boundary issue
- changes runtime/model only after permission/transport fallback is exhausted

## Scope

In scope:
- Quest-owned artifacts under `.quest/**`
- artifact path policy
- artifact preparation before role invocation
- fallback policy for artifact-write failures
- documentation/tests for Claude/Codex parity expectations

Out of scope:
- product/source file creation policy during build/fix
- changing handoff schema
- changing gate sequence
- changing non-Quest artifact locations outside the quest contract

## Core Design

### 1. Workspace-local artifact root by default

Quest should default to writing artifacts under the active repo root:

- `<repo>/.quest/<id>/...`

This is the default that works best for sandboxed runtimes.

If a quest run wants to place `.quest` outside the active workspace, that should be treated as an explicit exceptional mode with corresponding runtime implications.

### 2. Generic artifact preparation before invocation

Before each role invocation, the orchestrator should:

1. resolve the expected artifact paths for the current role
2. ensure parent directories exist
3. create or truncate those files
4. tell the agent to overwrite those prepared files directly
5. tell the agent not to use shell redirection/heredocs for Quest artifact creation

This rule should key off:
- phase
- agent
- quest mode
- iteration when needed

It should not branch on:
- orchestrator identity
- Claude vs Codex

### 3. Fallback ladder must separate write failures from runtime failures

Quest currently tends to think in terms of "runtime fallback." That is too coarse.

The fallback ladder should be:

#### A. Normal run
- configured runtime/model
- normal sandbox/permission posture

#### B. Permission/transport fallback
- same runtime
- same model
- more permissive filesystem/sandbox posture only if the failure is specifically an artifact-write boundary issue

Examples:
- Codex `gpt-5.4`: `workspace-write` -> `danger-full-access` only when required because artifact path is outside writable workspace
- Claude bridge: widen `--add-dir` / transport permissions if the write boundary is the blocker

#### C. Cross-runtime fallback
- only after the permission/transport retry still fails
- or when the failure is not a write-boundary problem

This preserves the distinction between:
- "the model could not write the file"
- "the model could not do the task"

Those are not the same problem and should not share the same first fallback.

## Expected Artifact Contract

Quest already has stable role artifacts such as:

- planner:
  - `plan.md`
  - `handoff.json`
- plan reviewers:
  - `review_plan-reviewer-a.md`
  - `review_plan-reviewer-b.md`
  - `handoff_plan-reviewer-a.json`
  - `handoff_plan-reviewer-b.json`
- arbiter:
  - `arbiter_verdict.md`
  - `handoff_arbiter.json`
- builder:
  - `pr_description.md`
  - `builder_feedback_discussion.md`
  - `handoff.json`
- code reviewers:
  - `review_code-reviewer-a.md`
  - `review_code-reviewer-b.md`
  - `handoff_code-reviewer-a.json`
  - `handoff_code-reviewer-b.json`
- fixer:
  - `review_fix_feedback_discussion.md`
  - `handoff_fixer.json`

This means the work is not inventing a new artifact model; it is enforcing a better orchestration invariant around the one Quest already has.

## Proposed Implementation Shape

### Artifact helper

Add a helper such as:

- `scripts/quest_runtime/artifacts.py`

Suggested API:

```python
expected_artifacts_for_role(phase, agent, quest_mode="workflow") -> list[str]
prepare_artifact_files(paths: list[str]) -> None
assert_workspace_local_or_explain(paths: list[str], workspace_root: str) -> result
```

### Workflow integration

Update Quest orchestration so that before every role invocation it:

1. resolves the current role's artifact paths
2. checks whether they are workspace-local for the active runtime
3. prepares the files
4. records any exceptional path/escalation decision

### Prompt updates

Prompts should consistently say:

- these files already exist
- overwrite them directly
- do not create Quest artifacts via shell redirection/heredocs

This wording should be generic and used across Claude/Codex runtime paths.

## Runtime Matrix

### Claude -> Claude native

Still uses the generic artifact preparation rule.

### Claude -> Codex (`gpt-5.4`)

Uses the generic artifact preparation rule plus workspace-local path discipline.
If artifact paths are outside workspace and the write fails, retry first with Codex permission escalation before switching runtime.

### Codex (`gpt-5.4`) -> Claude bridge

Uses the same artifact preparation rule.
If the bridge cannot write due to path/access boundary, handle that as a transport/permission problem before treating it as a model/runtime problem.

### Codex (`gpt-5.4`) -> Codex (`gpt-5.4`)

Same rules again. No Codex-specific artifact contract.

## Acceptance Criteria

1. Quest-owned artifacts are repo-local by default for sandboxed runtime paths.
2. Before each role invocation, Quest prepares only that role's expected artifact files.
3. Prepared files are created/truncated generically across runtime paths.
4. Artifact preparation logic does not branch on orchestrator identity.
5. Prompts consistently instruct agents to overwrite prepared artifact files directly and avoid shell redirection/heredocs for Quest artifact creation.
6. Fallback logic distinguishes permission/transport failure from cross-runtime failure.
7. For artifact-write failures, the first retry is same runtime + same model + increased permission posture when appropriate.
8. Cross-runtime fallback happens only after permission/transport fallback is exhausted or when the failure is not a write-boundary issue.
9. `handoff.json` compliance improves for Codex roles because file-write failures are addressed at the root cause.
10. No broad default escalation to `danger-full-access`; it remains explicit and exceptional.

## Validation Strategy

Automated:
- unit tests for artifact resolution/preparation
- unit tests for workspace-local path checks
- tests for fallback classification: write-boundary vs non-write failure
- runtime tests covering planner/reviewer/builder/fixer artifact prep

Manual:
1. Run a repo-local quest where Codex writes to `<repo>/.quest/...` and confirm `handoff.json` succeeds.
2. Run an out-of-workspace artifact-path case and confirm Quest uses same-runtime permission fallback before cross-runtime fallback.
3. Verify Claude-led and Codex-led runs both follow the same high-level ladder.

## Risks

1. Path-policy enforcement could conflict with existing setups that intentionally use a shared parent `.quest`.
   Mitigation: support explicit exceptional mode rather than silent failure.

2. Permission escalation could become overused.
   Mitigation: tie escalation only to declared artifact-write boundary failures.

3. Generic helper drift vs workflow docs.
   Mitigation: validator/test coverage for role-to-artifact mapping and fallback policy.

## Files Likely To Change

- `.skills/quest/delegation/workflow.md`
- `.ai/quest.md`
- `scripts/quest_runtime/artifacts.py` (new)
- `scripts/quest_runtime/claude_runner.py`
- runtime/fallback tests
- validator/docs for the generic invariant

## Recommendation

Do not implement this as a Codex patch.

Implement it as a generic Quest runtime rule set:
- workspace-local artifact paths by default
- generic artifact preparation before invocation
- same-runtime permission fallback before cross-runtime fallback

That solves the real failure mode while preserving parity between Claude-led and Codex-led orchestration.
