---
title: Wrong-Location Guardrails
purpose: Stop wrong-branch / wrong-directory / wrong-quest-path edits before they happen and detect sub-agent path drift before handoff acceptance.
audience:
  - quest-users
  - quest-maintainers
scope: PreToolUse hook for branch/dir visibility, plus post-invocation artifact-path validation for sub-agents.
status: proposed
date: 2026-05-17
supersedes:
  - ideas/2026-04-15-pretooluse-branch-dir-verification-hook.md
  - ideas/2026-04-15-subagent-path-constraints-hardening.md
related:
  - .claude/settings.json
  - .claude/hooks/session-start.sh
  - .skills/quest/delegation/workflow.md
  - scripts/quest_runtime/artifacts.py
  - ideas/handoff-validation-and-failure-ux.md
---

# Wrong-Location Guardrails

## Why this exists

The Quest evaluation logged **55 "Wrong Approach" events** as the top friction class — edits landing in the wrong branch, wrong directory, or nested `.quest/` path; sub-agents dropping artifacts outside their declared scope across **268 Agent invocations**. Every Quest user inherits this pain on day one with multiple worktrees or repos.

Two existing idea docs target the same root cause from different angles:

- `2026-04-15-pretooluse-branch-dir-verification-hook.md` — surface branch/dir context before every Edit/Write
- `2026-04-15-subagent-path-constraints-hardening.md` — validate sub-agent artifact paths after invocation

This doc consolidates them into one shippable quest. They are additive, share a single user-pain narrative, and both ride out through the installer to every Quest user.

## Goal

Ship two small, additive guardrails that reduce wrong-location edits in any repo that installs Quest:

1. **Pre-edit visibility** — a `PreToolUse` hook prints `branch | pwd` before every Edit/Write so the agent (and the user reading the log) sees the workspace context just before mutation.
2. **Post-invocation path validation** — a deterministic check that sub-agent artifacts declared in `handoff.json` actually landed inside the role's expected path boundary; mismatches fail loudly, not silently.

## Non-Goals

- No redesign of delegation architecture.
- No new policy surface beyond what `.skills/quest/delegation/workflow.md` already references.
- No git-required behavior; both guardrails must degrade safely when `vcs_available == false`.
- No correctness guarantee — visibility + post-validation, not pre-flight rejection of every misaimed edit.
- Does not touch the Codex MCP runtime or the Claude bridge.

## Deliverables

### 1. PreToolUse branch/dir hook

- Add a `PreToolUse` entry in `.claude/settings.json` matching `Edit|Write` that prints branch and working directory before the tool runs.
- Implement the command via a small helper at `.claude/hooks/branch-dir-context.sh` so the JSON stays clean and the script can grow if needed.
- The helper must:
  - Print `pwd` unconditionally.
  - Print `git branch --show-current` when git is available; otherwise emit `no git` and exit 0.
  - Never fail the tool call (exit 0 always; the hook is observational).
  - Emit a single line, deterministic format: `[quest-context] branch=<name> dir=<path>` (or `branch=no-git`).
- Merge **additively** with the existing `SessionStart` hook and the `PostToolUse Write|Edit` audit line in `.claude/settings.json` — do not replace either.

### 2. Sub-agent artifact path validator

- Add `scripts/quest_artifact_postflight.py` that, given a quest dir and a role, compares the artifact paths declared in `handoff.json` against the on-disk filesystem state and the expected path boundary returned by `expected_artifacts_for_role(...)` in `scripts/quest_runtime/artifacts.py`.
- For each declared artifact, validate:
  - The file exists.
  - The path is inside the role's expected boundary (no path traversal, no nested `.quest/<id>/.quest/...`).
  - The path matches the canonical filename for that role+phase where `expected_artifacts_for_role` returns deterministic names.
- On mismatch: append a structured record to `.quest/<id>/logs/path_compliance.log` (one JSON line per mismatch with `phase`, `role`, `declared`, `actual`, `reason`) and exit non-zero.
- Wire the validator into the workflow at handoff acceptance for sub-agent roles in `.skills/quest/delegation/workflow.md` — fail-loud, not silent. Mention it under the existing `expected_artifacts_for_role` / `prepare_artifact_files` pointer.
- The validator must be filesystem-based, not git-dependent.

### 3. Installer + documentation

- Add the new hook script and validator to `.quest-manifest` so the installer ships them to every Quest user. Use the right section (`copy-as-is` for the script and validator; `merge-carefully` if `.claude/settings.json` needs partial merge — choose whichever the installer already supports for settings.json).
- Add one short paragraph to `AGENTS.md` (or whatever the canonical policy pointer file is) describing the rule: "Quest surfaces branch+dir before edits and validates sub-agent artifact paths post-invocation; both guardrails are advisory by default and can be disabled by editing the hook/validator."
- Update `.skills/quest/delegation/workflow.md` to reference the postflight validator in the same section as `expected_artifacts_for_role` / `prepare_artifact_files`.

### 4. Focused tests

Place under `tests/unit/`:

- `test_branch_dir_context_hook.sh` (or `.py` if a Python wrapper is added): exercises the hook in a git repo, a non-git directory, and a directory with a detached HEAD. Asserts the output format and exit code (always 0). Asserts the hook does not block the tool call.
- `test_quest_artifact_postflight.py`: covers
  - all declared artifacts present and inside boundary → exit 0, no log
  - one artifact missing → exit non-zero, mismatch record written
  - one artifact outside boundary (path traversal or nested `.quest/<id>/.quest/...`) → exit non-zero, mismatch record written
  - declared path does not match canonical filename → exit non-zero, mismatch record written
  - `expected_artifacts_for_role` returns no paths for the role (no scratch artifacts) → exit 0, no log
- A workflow-contract test asserting `.skills/quest/delegation/workflow.md` references both new surfaces and the existing `expected_artifacts_for_role` helper without drift.
- An installer-manifest test asserting the new hook script and validator are listed under `.quest-manifest`.

## Acceptance Criteria

1. `.claude/settings.json` has an additive `PreToolUse` entry matching `Edit|Write` that invokes `.claude/hooks/branch-dir-context.sh`. Existing `SessionStart` and `PostToolUse` hooks are unchanged.
2. The hook prints `[quest-context] branch=<name|no-git> dir=<path>` to stdout, exits 0 in git, non-git, and detached-HEAD contexts, and never blocks the wrapped tool call.
3. `scripts/quest_artifact_postflight.py` exists, is invoked at sub-agent handoff acceptance per `.skills/quest/delegation/workflow.md`, and writes structured mismatches to `.quest/<id>/logs/path_compliance.log`.
4. The validator compares declared paths against `expected_artifacts_for_role(...)` and the on-disk filesystem; mismatches cause non-zero exit and are not silently accepted.
5. `.quest-manifest` lists both new files so the installer copies them to every downstream Quest install.
6. All tests above pass under `python3 -m pytest tests/unit/` plus the relevant shell test runner.
7. No regression in existing tests, including `bash tests/test-quest-runtime.sh` and `bash tests/test-validate-handoff-contracts.sh`.
8. `AGENTS.md` (or the canonical pointer) gains one short paragraph naming both guardrails and pointing to the hook + validator.

## Out of Scope (explicit)

- Auto-rollback or auto-correction of wrong-location edits. Detect and log; do not "fix" mid-flight.
- Pre-edit rejection of writes to "wrong" paths. The hook is observational; the validator runs post-invocation.
- New configuration surface (no `allowlist.json` keys, no new env vars). Both guardrails are on by default and disabled by editing the hook/validator directly.
- Memory or learnings from path-compliance logs. Logging only; no retrieval.
- Changes to the Codex MCP runtime, the Claude bridge, or the preflight script.
- Cross-repo enforcement (e.g., refusing edits when branch differs from a stored expectation). Future work.

## Kill Criteria

Roll back if any of these hold after one week of dogfooding:

- The hook output is so noisy that users disable it.
- The validator produces false-positive mismatches that block valid handoffs (path normalization wrong, edge cases in `expected_artifacts_for_role`).
- Non-git contexts hit unhandled paths in either guardrail.
- Adding the validator measurably slows quest handoff acceptance (target: < 50 ms per role; > 200 ms is a regression).

## Suggested Quest Prompt

```text
/quest "Implement Wrong-Location Guardrails: a PreToolUse branch/dir hook and a
post-invocation sub-agent artifact-path validator. Both ship to every Quest
user via the installer.

Reference: ideas/2026-05-17-wrong-location-guardrails.md

DELIVERABLES

1. PreToolUse hook
   - Add `.claude/hooks/branch-dir-context.sh` that prints
     `[quest-context] branch=<name|no-git> dir=<path>` and always exits 0.
   - Wire it additively into `.claude/settings.json` under `PreToolUse` with
     matcher `Edit|Write`. Do not modify existing SessionStart or PostToolUse
     hooks.
   - Handle git, non-git, and detached-HEAD contexts. Never block the tool
     call.

2. Post-invocation artifact validator
   - Add `scripts/quest_artifact_postflight.py` that compares declared
     artifacts in `handoff.json` against `expected_artifacts_for_role(...)`
     from `scripts/quest_runtime/artifacts.py` and the on-disk filesystem.
   - Validate: file exists, path inside expected boundary, path matches
     canonical filename, no nested `.quest/<id>/.quest/...`, no traversal.
   - On mismatch: append a JSON line to
     `.quest/<id>/logs/path_compliance.log` with `phase`, `role`,
     `declared`, `actual`, `reason`, and exit non-zero.
   - Filesystem-based, not git-dependent.
   - Wire it into `.skills/quest/delegation/workflow.md` at sub-agent
     handoff acceptance, in the same section that references
     `expected_artifacts_for_role` and `prepare_artifact_files`.

3. Installer + docs
   - Add the new hook script and validator to `.quest-manifest` so the
     installer ships them downstream.
   - Add one short paragraph to `AGENTS.md` describing both guardrails and
     how to disable them.

4. Focused tests
   - Hook tests covering git / non-git / detached-HEAD contexts, output
     format, and non-blocking exit.
   - Validator tests covering: all-clean, missing artifact, outside boundary,
     non-canonical filename, no-scratch-artifacts role.
   - Workflow-contract test that `.skills/quest/delegation/workflow.md`
     references both new surfaces.
   - Manifest test that both new files are listed in `.quest-manifest`.

OUT OF SCOPE

- Auto-rollback or auto-correction of wrong-location edits.
- Pre-edit rejection of writes (hook is observational only).
- New configuration surface keys.
- Cross-repo enforcement.
- Memory/learnings from path-compliance logs.
- Changes to Codex MCP runtime, Claude bridge, or preflight.

KILL CRITERIA

Roll back if the hook is noisy enough to be disabled, the validator produces
false-positive mismatches that block valid handoffs, non-git contexts hit
unhandled paths, or validator latency exceeds 200 ms per role.

Ship one coherent bundle: hook + validator + manifest + docs + tests."
```
