# Quest hardening

Date: 2026-07-11
Status: `proposed`
Source analysis: `.ws/findings.md`

## Status contract

Every workstream must use exactly one of these markers:

- `[todo]` — implementation has not started.
- `[ongoing]` — implementation has started, but no PR exists yet.
- `[done]` — a PR has been created for the complete workstream. Record the PR number and link beside the marker.

`[done]` tracks PR creation, not merge. CI, review, readiness, and merge remain visible on the linked PR.

When every workstream is `[done]`, move this file to
`ideas/archive/2026-07-11-quest-hardening.md` and update `ideas/README.md` from
the active index to the done index. Do not archive while any workstream is
`[todo]` or `[ongoing]`.

## Overview

### Problem

The Quest installer PR in Candid Talent Edge produced 25 review findings. A
source-backed Codex analysis and an independent Fable-5 bridge review agreed
that nine findings still drive concrete value. They cover trust boundaries,
state integrity, operational helper contracts, transport fidelity, and
installed-document accuracy.

### Impact

Completing this plan will:

- prevent an allowlisted basename from approving a different absolute binary;
- stop preflight from claiming an unauthenticated Codex runtime is available;
- reject structurally invalid Quest state before shared callers use it;
- make expected-phase transitions atomic rather than best-effort;
- make applied branch synchronization trust the operation actually requested;
- preserve caller prompt and answer content across both Claude transports;
- prevent PR-summary upserts from targeting comments owned by another actor;
- remove obsolete configuration guidance; and
- keep installed Quest documentation from linking into unowned or stale host files.

### Scope boundaries

In scope: original findings **#1, #3, #4, #9, #16, #17, #18, #20, and #22**.

Out of scope:

- deferred findings #6 and #13;
- rejected findings #12 and #25;
- Candid-owned Markdown corrections #10 and #11;
- changes to Candid Talent Edge;
- broad refactors, new state-versioning machinery, or new installer ownership;
- resolving, replying to, or otherwise mutating PR #190 review threads.

## PR strategy

Use three independent PRs. A single PR would mix security-sensitive command
matching, concurrency, git behavior, Claude transport fidelity, PR-comment
ownership, and installed documentation across too many review surfaces. Nine
separate PRs would add ceremony without improving isolation. These three
vertical slices balance reviewability and delivery speed and may proceed in
parallel.

| Status | PR workstream | Original findings | Branch suggestion | PR |
|---|---|---|---|---|
| [done] | A. Runtime trust and state boundaries | #1, #4, #18, #22 | `hardening/runtime-boundaries` | [#149](https://github.com/KjellKod/quest/pull/149) |
| [todo] | B. Operational helper and transport correctness | #3, #9, #20 | `hardening/operational-contracts` | — |
| [todo] | C. Installed documentation accuracy | #16, #17 | `hardening/installed-docs` | — |

## Workstream A — Runtime trust and state boundaries [done] — [PR #149](https://github.com/KjellKod/quest/pull/149)

### Goal

Close the highest-risk false-approval and state-integrity gaps without adding a
general policy framework.

### Acceptance criteria

1. **#4:** A bare allowlist entry accepts its normal PATH-resolved executable,
   but does not accept an arbitrary absolute binary with the same basename.
   Explicitly allowlisted absolute paths continue to work.
2. **#22:** Claude-led preflight reports Codex available only when the CLI is
   installed, MCP is registered, and a bounded `codex login status` succeeds.
   Missing or failed login is reported as unauthenticated rather than as a
   generic preflight crash.
3. **#18:** Shared Quest state loading rejects valid JSON whose top-level value
   is not an object. `quest_complete.py` and state-transition callers return a
   deterministic, user-readable failure instead of an attribute traceback.
4. **#1:** An expected-phase transition holds a per-state lock across its final
   read, comparison, mutation, and atomic replacement. A competing conforming
   writer cannot overwrite a phase that changed after validation.
5. Existing valid allowlist commands, authenticated preflight, valid state
   updates, and raw state-setting behavior remain compatible.

### Implementation approach

**#4 — executable identity**

- Modify `/Users/kjell/ws/extra/quest/scripts/quest_allowlist_matcher.py`.
- Resolve a bare allowlist executable through `shutil.which()` and compare
  normalized/resolved executable paths when the command token is absolute.
- Preserve literal bare-token matching, explicit path entries, blocked shell
  metacharacters, blocked `find` actions, and blocked `rg --pre*` flags.
- Deliberately revise tests that currently encode basename-only absolute-path
  acceptance; those tests pin the defective contract.

**#22 — authenticated runtime signal**

- Modify `/Users/kjell/ws/extra/quest/scripts/quest_preflight.sh`.
- Run `codex login status` with the smallest portable timeout mechanism already
  used by this script/repository.
- Add a machine-readable authentication check to the emitted JSON.
- Keep API-key discovery diagnostic-only unless the CLI itself confirms that it
  is sufficient for the configured runtime.
- Update stale remediation text from `codex auth` to the supported login command.

**#18 and #1 — shared state boundary**

- Modify `/Users/kjell/ws/extra/quest/scripts/quest_runtime/state.py`.
- Make `load_state()` require a JSON object and raise a specific readable error
  for arrays, scalars, invalid JSON, decode failures, and I/O failures.
- Add a per-`state.json` lock used by the mutation helper. Keep the lock scope to
  the final read/check/write transaction; do not introduce state revisions or a
  database.
- Write through a sibling temporary file plus `os.replace()` so a crash cannot
  expose a partial JSON document.
- Modify `/Users/kjell/ws/extra/quest/scripts/quest_state.py` so
  `--expect-phase` is enforced inside the locked mutation, and so clearing a
  parked background session does not perform a second unlocked write.
- Modify `/Users/kjell/ws/extra/quest/scripts/quest_complete.py` to translate
  shared state-load failures into its existing deterministic CLI error flow.

### Validation

**Automated test — #4 executable identity**

- **File:** `/Users/kjell/ws/extra/quest/tests/unit/test_allowlist_matcher.py`
- **Tests:** update the legitimate absolute-path cases and add
  `test_bare_entry_rejects_same_basename_outside_resolved_path()` plus explicit
  absolute-entry coverage.
- **Run:** `pytest -q tests/unit/test_allowlist_matcher.py`
- **Mocking:** monkeypatch `shutil.which`; no subprocess mocks.
- **Expected:** the resolved installed tool is accepted, `/tmp/rg` and
  `/tmp/find` are rejected, and existing dangerous-flag protections pass.

**Automated test — #22 authentication matrix**

- **File:** `/Users/kjell/ws/extra/quest/tests/test-quest-preflight.sh`
- **Tests:** fake Codex CLI cases for logged in, logged out, timeout/nonzero, and
  missing CLI; keep MCP registration independently controlled.
- **Run:** `bash tests/test-quest-preflight.sh`
- **Mocking:** fake boundary executables on a temporary PATH.
- **Expected:** only installed + registered + authenticated reports available.

**Automated test — #18 state shape**

- **Files:** `/Users/kjell/ws/extra/quest/tests/unit/test_quest_state.py` and
  `/Users/kjell/ws/extra/quest/tests/unit/test_quest_complete.py`
- **Tests:** invalid JSON, JSON array/scalar, unreadable file, and valid object.
- **Run:** `pytest -q tests/unit/test_quest_state.py tests/unit/test_quest_complete.py`
- **Mocking:** filesystem permissions only where portable; otherwise patch the
  read boundary narrowly.
- **Expected:** invalid state returns a deterministic failure without traceback;
  valid object behavior is unchanged.

**Automated test — #1 lock transaction**

- **File:** `/Users/kjell/ws/extra/quest/tests/unit/test_quest_state.py`
- **Tests:** lock acquisition/release, expected-phase success, expected-phase
  mismatch without mutation, atomic replacement, and parked-session clearing in
  the same transaction.
- **Run:** `pytest -q tests/unit/test_quest_state.py`
- **Mocking:** test the lock helper deterministically; do not rely on a timing-
  sensitive race test.
- **Expected:** comparison and mutation occur under one lock and mismatches leave
  the original bytes unchanged.

### Integration touchpoints

- **Claude permission hook:** command matching could reject legitimate absolute
  tools. Validate bare, resolved absolute, explicit absolute, and malicious
  same-basename cases.
- **Claude-led Quest startup:** authentication checks could false-negative on a
  supported login. Validate against fake CLI contracts and run one local manual
  preflight when authenticated.
- **All state consumers:** stricter object validation could expose latent corrupt
  state earlier. Run state, runtime, completion, dashboard, and validation suites.
- **Cross-platform filesystem behavior:** locking and atomic replace must work on
  supported macOS/Linux environments. Keep the helper small and standard-library
  based; fail with an actionable error if the lock cannot be established.

### Manual validation

**MANUAL TEST — authenticated preflight and state transition**

- **Why manual:** confirms real CLI login output and OS lock behavior outside
  fake test boundaries.
- **Preconditions:** authenticated local Codex CLI; temporary Quest directory.
- **Steps:** run `scripts/quest_preflight.sh --orchestrator claude`; perform one
  valid `quest_state.py --transition ... --expect-phase ...`; repeat with an
  incorrect expected phase.
- **Expected:** preflight reports authenticated availability; valid transition
  succeeds; mismatch fails without changing `state.json`.
- **Observability:** emitted preflight JSON, CLI exit codes, and final state bytes.

## Workstream B — Operational helper and transport correctness [todo]

### Goal

Make helper behavior match the operation requested and preserve caller-owned
content and GitHub comment ownership.

### Acceptance criteria

1. **#3:** Inspect mode remains non-mutating and may report `merge-tree`
   conflicts. Apply mode runs the requested rebase/merge after safety guards and
   treats that operation as the authoritative conflict result.
2. **#9:** Bridge prompts, background prompts, and background resume answers are
   rejected when whitespace-only but otherwise reach Claude byte-for-byte
   unchanged.
3. **#20:** PR-summary upsert updates only a marker comment owned by the current
   authenticated actor. A foreign human, foreign bot, or unknown author cannot
   be selected for PATCH.
4. Actual rebase/merge conflicts are aborted and reported without leaving the
   worktree mid-operation; summary creation remains idempotent for the same actor.

### Implementation approach

**#3 — applied sync authority**

- Modify `/Users/kjell/ws/extra/quest/scripts/pr_sync_default_branch.py`.
- Keep `probe_merge()` on the inspect path.
- On `--apply`, run dirty-worktree and lease checks, then call `_apply_sync()`
  even if the advisory probe predicts a conflict or cannot model the requested
  rebase.
- Preserve abort, conflict-file collection, push-required, and force-with-lease
  reporting.
- Deliberately invert the test that currently pins “probe conflict never applies.”

**#9 — transport fidelity**

- Modify `/Users/kjell/ws/extra/quest/scripts/quest_claude_bridge.py`.
- Modify `/Users/kjell/ws/extra/quest/scripts/claude_bg_run.py`.
- Validate emptiness using a stripped view, but return/pass the original prompt
  or answer content. Do not introduce content normalization.

**#20 — owned summary upsert**

- Modify `/Users/kjell/ws/extra/quest/scripts/pr_shepherd_post_reply.py`.
- Require exact, non-empty author-login equality with `_current_login()` before
  selecting a marker comment for update.
- If login discovery fails or no owned marker exists, create a new summary
  rather than PATCHing an unknown comment.
- Deliberately revise the test that currently treats any bot marker as trusted.

### Validation

**Automated test — #3 inspect versus apply**

- **File:** `/Users/kjell/ws/extra/quest/tests/unit/test_pr_sync_default_branch.py`
- **Tests:** inspect conflict remains non-mutating; apply ignores advisory
  conflict and invokes the requested operation; actual rebase and merge conflicts
  abort and report; clean application remains correct.
- **Run:** `pytest -q tests/unit/test_pr_sync_default_branch.py`
- **Mocking:** mock the git subprocess boundary with ordered command assertions.
- **Expected:** only the actual apply result determines applied conflict status.

**Automated test — #9 exact transport content**

- **Files:** `/Users/kjell/ws/extra/quest/tests/unit/test_claude_bg_run.py` and a
  focused bridge test module if none exists.
- **Tests:** leading indentation, trailing newlines, prompt file/stdin/direct
  input, resume answer file, and whitespace-only rejection.
- **Run:** `pytest -q tests/unit/test_claude_bg_run.py` plus the bridge test module.
- **Mocking:** fake Claude subprocess boundary; assert exact argv/input content.
- **Expected:** non-empty content is unchanged across both transports.

**Automated test — #20 actor ownership**

- **File:** `/Users/kjell/ws/extra/quest/tests/unit/test_pr_shepherd.py`
- **Tests:** same-user marker updates; foreign-human, foreign-bot, unknown-author,
  and missing-current-login cases create rather than update.
- **Run:** `pytest -q tests/unit/test_pr_shepherd.py`
- **Mocking:** mock GitHub JSON and command boundaries only.
- **Expected:** PATCH is issued only for an exactly owned marker comment.

### Integration touchpoints

- **Git history/worktree:** sync behavior can rewrite a feature branch. Unit-test
  command order and run manual smoke only in a disposable repository.
- **Claude bridge/background runner:** exact whitespace preservation can alter
  snapshots that previously expected trimming. Update only tests encoding the
  old defective transport contract.
- **GitHub issue comments:** ownership changes can create one replacement summary
  instead of updating a foreign marker. That is the safe intended fallback.

### Manual validation

**MANUAL TEST — disposable sync repository**

- **Why manual:** verifies real Git rebase/merge cleanup semantics.
- **Preconditions:** temporary repository with clean and conflicting branches.
- **Steps:** run inspect on the conflict case; run `--apply` for clean rebase,
  conflicting rebase, clean merge, and conflicting merge.
- **Expected:** inspect never mutates; clean applies succeed; conflicts abort and
  restore a non-conflicted worktree with actionable JSON.
- **Observability:** exit code, JSON payload, `git status --porcelain`, and graph.

## Workstream C — Installed documentation accuracy [todo]

### Goal

Make the documentation Quest actually installs accurate without taking ownership
of host documentation.

### Acceptance criteria

1. **#16:** Setup guidance uses the supported `models.<role>` configuration and
   documents `claude_role_transport`; it no longer instructs users to configure
   `arbiter.tool` or promises an unconditional Claude fallback.
2. **#17:** Every relative link in the manifest-owned setup guide resolves from a
   clean installed-consumer fixture. The guide does not link to
   `quest_presentation.md`, which Quest does not own or install.
3. Quest does not add host-owned presentation documents or unrelated consumer
   files to `.quest-manifest`.

### Implementation approach

- Modify `/Users/kjell/ws/extra/quest/docs/guides/quest_setup.md`.
- Replace obsolete troubleshooting with current allowlist `models.<role>`,
  per-quest `orchestration.json`, preflight, and transport terminology.
- Add `claude_role_transport` to the configuration table.
- Remove the redundant deep link to `quest_presentation.md`; do not add that file
  to `/Users/kjell/ws/extra/quest/.quest-manifest`.
- Add a narrow installed-surface link test rather than a broad prose snapshot.

### Validation

**Automated test — #16 current configuration contract**

- **File:** `/Users/kjell/ws/extra/quest/tests/unit/test_documentation_contracts.py`
- **Tests:** required current configuration terms are present. A permanent ban on
  every historical spelling is optional; avoid brittle whole-paragraph snapshots.
- **Run:** `pytest -q tests/unit/test_documentation_contracts.py`
- **Mocking:** none.
- **Expected:** the guide describes current model and transport configuration.

**Automated test — #17 installed link ownership**

- **File:** `/Users/kjell/ws/extra/quest/tests/unit/test_quest_manifest.py` or the
  existing installed-surface test module best aligned with installer fixtures.
- **Tests:** copy the manifest-owned setup guide into a clean consumer fixture and
  verify its local relative links resolve only to installed/owned files; assert
  `quest_presentation.md` remains outside the manifest.
- **Run:** `pytest -q tests/unit/test_quest_manifest.py`
- **Mocking:** temporary filesystem only.
- **Expected:** the installed guide has no dangling host-document dependency and
  installer ownership does not expand.

### Integration touchpoints

- **Installer manifest:** adding the presentation would create consumer conflicts.
  Validate that `.quest-manifest` remains unchanged for that file.
- **Existing source checkout:** removing the link loses one convenience link in
  the birthplace repo, but keeps the portable installed guide truthful.
- **Consumer documentation:** only Quest-owned setup content changes; host files
  remain untouched.

### Manual validation

**MANUAL TEST — clean installed-consumer guide**

- **Why manual:** quick human check of rendered guidance and link usefulness.
- **Preconditions:** temporary clean repository with Quest installed from the PR.
- **Steps:** open `docs/guides/quest_setup.md`; follow local links in the modified
  sections; confirm no presentation file was installed or overwritten.
- **Expected:** instructions are complete without the removed deep link and every
  remaining link resolves.
- **Observability:** installed file list and rendered Markdown links.

## End-to-end validation

After all three PRs exist, each PR must run its focused commands plus the relevant
repository gates. Before marking its workstream `[done]`, record the PR and verify
that its description maps acceptance criteria to tests.

Minimum combined validation:

```bash
pytest -q \
  tests/unit/test_allowlist_matcher.py \
  tests/unit/test_quest_state.py \
  tests/unit/test_quest_complete.py \
  tests/unit/test_pr_sync_default_branch.py \
  tests/unit/test_claude_bg_run.py \
  tests/unit/test_pr_shepherd.py \
  tests/unit/test_documentation_contracts.py \
  tests/unit/test_quest_manifest.py
bash tests/test-quest-preflight.sh
bash tests/test-validate-quest-state.sh
```

Also run the repository's configured lint/format checks and any focused module
added for `quest_claude_bridge.py`.

## Risks and mitigations

1. **#4 blocks legitimate absolute tool paths** — Impact: high; Likelihood:
   medium. Compare against the PATH-resolved executable and retain explicit
   absolute allowlist entries.
2. **#1 locking deadlocks or is inconsistently applied** — Impact: high;
   Likelihood: low. Centralize the transaction in the state module, bound the
   lock scope, and test acquisition/release and error paths.
3. **#22 rejects valid authenticated installations** — Impact: high;
   Likelihood: medium. Use the CLI's own bounded login-status contract and a fake
   compatibility matrix before manual verification.
4. **#3 leaves a repository mid-conflict** — Impact: high; Likelihood: low.
   Preserve abort-on-failure behavior and smoke-test in disposable repositories.
5. **Pinned tests hide intentional contract changes** — Impact: medium;
   Likelihood: high. Explicitly document that #3, #4, and #20 revise tests because
   those tests currently encode the behavior being corrected.

## Dependencies and ordering

- Workstreams A, B, and C are independent and may run in parallel.
- Within A, implement #18 before #1 so atomic mutation builds on a validated
  shared state boundary.
- Within B, no finding depends on another; keep commits independently reviewable.
- Archive this idea only after all three workstream rows have PR links and are
  marked `[done]`.

## Open questions

- None blocking. The plan assumes current support remains macOS/Linux and that a
  small standard-library file-lock helper is acceptable. If current platform
  support requires a different locking primitive, resolve that within Workstream
  A without expanding the state model.
