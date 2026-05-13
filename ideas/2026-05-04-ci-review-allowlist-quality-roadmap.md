---
title: CI Review, Allowlist, and Quality Maturity Roadmap
purpose: Consolidate active CI/review/allowlist improvement ideas into one implementation-ready roadmap.
audience: Quest maintainers and CI-touching agents
scope: CI review helpers, allowlist enforcement, PR readiness helpers, bug-fix discipline, and review ergonomics
status: active-roadmap
owner: maintainers
date: 2026-05-04
---

# CI Review, Allowlist, and Quality Maturity Roadmap

This roadmap supersedes the scattered CI, review, allowlist, pre-commit, and
bug-fix idea docs listed at the end. Treat those files as historical source
material; implement from this roadmap.

## Baseline Already Implemented

- Deep CI whole-file logic review exists in `.github/scripts/codex_review.py`.
  Eligible changed code files are reviewed from PR-head file snapshots, not only
  diff hunks.
- Deep CI context manifests are established. The runtime writes
  `/tmp/deep_ci_context_manifest.json` with file modes, selected files, chunk
  windows, budget accounting, and omitted candidates.
- Deep CI omission reasons are stable machine-readable strings, including
  excluded path segment, lockfile, unsupported extension, minified file,
  deleted file, metadata too large, fetch too large, total cap exhausted, no
  changed line ranges, chunk cap exhausted, and unavailable.
- Chunking fallback is established for oversized eligible code files. Changed
  right-side line ranges are preserved where possible, with omitted changed
  lines surfaced in rendered review context.
- Existing inline CI review comments already have script-owned severity
  formatting for `blocker`, `must-fix`, and `should-fix`, plus an advisory
  footer. Keep that behavior until Track 1 replaces the taxonomy deliberately.
- Existing CI review deduplication reads prior inline comments and avoids
  reposting matching unresolved findings.
- The current workflow separates trusted base checkout from PR-head content
  fetching for the secret-bearing review job.
- Archived Review Intelligence and Deep CI plans are baseline history, not open
  implementation plans.

## Proposed Work Not Yet Implemented

The remaining work is quality maturity: better review signal, acceptance
coverage, allowlist correctness, enforceable policy, safer bug-fix loops, and
commit/PR discipline. Implement it in small slices that can land independently.

## Roadmap Tracks

### Track 1: Review Signal Quality

Goal: make CI review comments easier to triage, safer to parse, and less noisy.

Scope:

- Replace the current three-level review taxonomy with:
  `critical`, `high`, `medium`, `low`, `praise`.
- Render visual severity markers in script-owned formatting, not prompt-owned
  prose.
- Keep findings inline-first whenever GitHub can anchor them.
- Keep top-level summaries concise and explicitly non-exhaustive.
- Normalize structured fields for each finding:
  `severity`, `issue`, `impact`, `concern`, `path`, `line`, `side`.
- Harden malformed model output handling: unknown severities, missing optional
  fields, extra fields, invalid JSON wrappers, and non-dict comments should not
  crash posting.
- Deduplicate against unresolved prior bot comments before posting.
- Add review-input scope hygiene before context preparation: allow a validated
  set of review-excluded path patterns to filter generated, vendored, lockfile,
  or otherwise low-signal paths before chunking/review selection. Record each
  exclusion in the Deep CI manifest with a stable reason such as
  `excluded-by-review-path-policy`.

Acceptance criteria:

- The formatter accepts only the new severity taxonomy and renders deterministic
  visual markers.
- Existing model output using old severities is either migrated predictably or
  rejected with a warning; it must not silently mislabel findings.
- Inline comments include issue, impact, and concern when present, without
  requiring the model to hand-format markdown.
- Malformed review output produces warnings and skips only invalid findings.
- Duplicate unresolved findings are not reposted after synchronize.
- Review-excluded paths are filtered before Deep CI selection and recorded in
  the manifest with omission reason and source policy.

Tests:

- Unit tests for severity normalization and formatter idempotence.
- Unit tests for malformed output resilience.
- Unit tests for duplicate detection against unresolved bot comments.
- Contract tests for the workflow/prompt boundary: the prompt requires
  structured fields and the script owns rendering.
- Unit tests for review-excluded path validation: reject NUL bytes, absolute
  paths, leading `..`, pathspec magic, and oversized exclusion lists.
- Manifest tests proving excluded paths are omitted before chunking and recorded
  with `excluded-by-review-path-policy`.

### Track 2: Intent Coverage Review

Goal: add a PR-conversation review surface that checks whether the diff matches
declared intent and acceptance criteria.

Scope:

- Derive intent from PR title, PR body, and changed docs that look like quest
  prompts, idea docs, or acceptance criteria.
- Map each intent or acceptance item to code/test/documentation evidence.
- Emit `PASS`, `WARN`, or `FAIL`.
- Report missing coverage, partial coverage, unclear evidence, and scope creep.
- Update one marker-keyed PR comment instead of posting duplicates.
- Keep this separate from inline bug findings. Intent review answers "did we do
  the promised work?", while inline review answers "is this change risky or
  wrong?"

Acceptance criteria:

- The job writes or updates exactly one marker-keyed PR comment.
- The comment contains status, summary, coverage table, missing/partial items,
  scope creep, and notes.
- Re-running on synchronize patches the existing comment.
- Empty or weak PR descriptions produce a clear `WARN`, not a crash.
- The workflow is advisory unless maintainers explicitly choose a blocking mode.

Tests:

- Renderer tests for PASS/WARN/FAIL.
- Upsert tests for existing marker comment vs absent marker comment.
- Parsing tests for PR body acceptance lists and changed docs.
- Contract tests that the workflow does not create duplicate comments.

### Track 3: Allowlist Hygiene

Goal: make allowlist content and matching semantically correct before any
stronger enforcement is activated.

Scope:

- Reject broad bare entries such as `bash`, `python`, and `python3` unless they
  are exact-match entries with explicit tests proving the intended behavior.
- Reject shell metacharacter bypasses for non-exact matches.
- Use token-prefix matching, not raw string prefix matching and not regex.
- Add semantic validation beyond JSON schema.
- Add focused unit tests for matcher behavior.

Acceptance criteria:

- No role relies on broad bare interpreter entries for prefix matching.
- `gh pr view` style permissions use token-prefix semantics, not fake regex.
- Compound commands containing shell metacharacters are denied unless explicitly
  allowed byte-for-byte.
- The semantic validator fails CI on unsafe patterns.

Tests:

- Matcher tests for exact match, token-prefix match, wrong token, bare
  interpreter, and metacharacter bypasses.
- Validator tests for unsafe allowlist entries.
- Contract test proving the hook-side matcher and CI-side validator agree.

### Track 4: Allowlist Enforcement

Goal: activate enforcement only after Track 3 proves the allowlist is safe to
interpret.

Prerequisite: Track 3 must land first.

Scope:

- Resolve role identity through a documented mechanism.
- Wire the enforcement hook only after matcher/validator tests exist.
- Test correct role, wrong role, missing role, compound commands, path
  traversal, and malformed payloads.
- Document fail-open vs fail-closed choices explicitly.
- Make CI prove the hook and matcher still agree.

Acceptance criteria:

- Hook activation is documented and covered by tests.
- Correct-role commands pass and wrong-role commands fail.
- Missing role behavior is intentional, documented, and tested.
- Malformed hook payloads cannot silently grant broader access than intended.
- Path traversal attempts are rejected for path-scoped tool use.

Tests:

- Hook invocation tests with representative PreToolUse payloads.
- Role-resolution tests for present, absent, and malformed role sources.
- Compound-command and traversal bypass tests.
- CI contract test comparing hook decisions with shared matcher decisions.

### Track 5: Bug-Fix Discipline

Goal: make hard bug fixes auditable without destructive rollback.

Scope:

- Bug fixes should start with a failing test when feasible.
- Preserve failed attempts as artifacts or notes when retry loops run.
- Bound retry strategies.
- Avoid destructive rollback unless explicitly approved.
- Keep the process lightweight for obvious one-pass fixes.

Acceptance criteria:

- A bug-fix-loop skill or workflow documents reproduction-first behavior.
- Failed attempts preserve test output and diff evidence.
- Retry attempts are capped and materially distinct.
- The final handoff identifies the reproducing test, winning strategy, and
  validation commands.

Tests:

- Skill-surface tests for installed wrapper files if a new skill is added.
- Unit tests for artifact path construction and attempt caps if helpers are
  scripted.
- Integration fixture proving failed-attempt artifacts are written without
  destructive git commands.

### Track 6: Commit / PR Readiness

Goal: reduce PR and commit helper drift before writes happen.

Scope:

- Require status and diffstat before commit/push helpers act.
- Ensure PR review prompts do not claim tests were run when CI-only review
  cannot run them.
- Support maintainer-triggered reruns such as `/review` without duplicating
  comments.
- Separate model execution from GitHub write-permission posting jobs where
  applicable.

Acceptance criteria:

- Commit helpers inspect branch, status, staged files, and diffstat before
  proposing or creating commits.
- PR helpers verify referenced commands and paths exist before presenting a PR
  body.
- CI-only review text distinguishes "not run" from "run in CI".
- Maintainer-triggered review reruns update or dedupe existing surfaces.
- Write-permission jobs are narrowly scoped and do not execute PR-head code.

Tests:

- Skill/wrapper tests for commit and PR helper instructions.
- Unit tests for PR body validation helpers if scripted.
- Workflow contract tests for permission separation and trusted checkout.

## Overlap and Merge Decisions

| Existing idea | Roadmap destination |
| --- | --- |
| Intent coverage and severity-tagged reviews | Tracks 1 and 2 |
| Codex review severity emoji | Track 1 |
| Review ergonomics and team preference memory | Track 1, with preference memory deferred until signal quality is stable |
| Allowlist pattern hygiene | Track 3 |
| Allowlist enforcement activation | Track 4 |
| Pre-commit status/diffstat discipline | Track 6 |
| Agent commit guard / pre-commit review | Track 6 |
| Test-driven bug-fix loops | Track 5 |
| PR create checklist / autonomous PR shepherd notes | Track 6 |
| Tool failure two-attempt cap | Track 5 where it applies to bug-fix retries |
| Deep CI chunked context, context manifest, and whole-file logic review | Baseline foundations |

## Prerequisites and Sequencing

1. Track 1 first: review signal quality plus review-input scope hygiene. This
   improves daily PR feedback, reduces noise, and gives later intent coverage a
   cleaner comment vocabulary.
2. Track 2 second: intent coverage review. It should reuse Track 1's structured
   rendering, malformed-output resilience, and marker-comment patterns.
3. Track 3 third: allowlist hygiene. This is the prerequisite for enforcement.
4. Track 4 fourth: allowlist enforcement. Do not activate until Track 3 lands.
5. Track 5 fifth: bug-fix discipline. This can run in parallel with Track 6 if
   ownership is separate.
6. Track 6 sixth: commit / PR readiness. Pieces may land earlier when touching
   related helpers, but avoid mixing them into CI review PRs.

## First Implementation Slice

Implement Track 1 v1: Review Signal Quality and Review-Input Scope Hygiene.

Likely files to change:

- `.github/scripts/codex_review.py`
- `.github/codex-review-prompt.md`
- `.github/workflows/codex-ci-review.yml`
- `tests/unit/test_codex_review.py`
- Any workflow contract test file that already covers `codex-ci-review.yml`
- Optional: `.github/codex-review-exclusions.json` or similar small config file
  if hardcoding exclusions in Python would make the policy less inspectable.

First-slice acceptance criteria:

- New taxonomy is `critical`, `high`, `medium`, `low`, `praise`.
- The script owns all severity labels, markers, and advisory footer rendering.
- Inline finding bodies can include structured issue, impact, and concern
  fields without model-owned markdown prefixes.
- Unknown, missing, or malformed severity data does not crash posting.
- Existing duplicate detection still runs before posting.
- A validated review-exclusion policy filters paths before Deep CI context
  selection and records omitted candidates with
  `excluded-by-review-path-policy`.
- The prompt no longer asks the model to hand-format severity labels.
- Existing Deep CI manifest/chunking tests continue to pass.

Focused first-slice test plan:

- `python3 -m pytest tests/unit/test_codex_review.py -q`
- `python3 -m py_compile .github/scripts/codex_review.py`
- Add unit tests for all five severities and unknown severity behavior.
- Add malformed-output tests for invalid finding shapes and missing fields.
- Add dedup regression tests proving formatted bodies do not break matching.
- Add path-exclusion validation tests for unsafe patterns and legitimate
  generated/vendor/lockfile exclusions.
- Add manifest tests proving excluded paths are recorded before chunking.
- Add workflow contract tests proving the workflow passes the exclusion policy
  into the Python helper and still uses trusted base checkout.

## Superseded Active Idea Docs

Mark these as superseded by this roadmap:

- `ideas/2026-04-24-intent-coverage-and-severity-tagged-reviews.md`
- `ideas/codex-review-severity-emoji.md`
- `ideas/2026-04-22-review-ergonomics-and-team-preference-memory.md`
- `ideas/2026-04-20-allowlist-pattern-hygiene.md`
- `ideas/2026-04-20-allowlist-enforcement-activation.md`
- `ideas/2026-04-15-precommit-status-diffstat-discipline.md`
- `ideas/2026-04-27-agent-commit-guard-pre-commit-review.md`
- `ideas/2026-04-29-test-driven-bug-fix-loops.md`
- `ideas/2026-04-15-pr-create-checklist-via-pr-assistant.md`
- `ideas/2026-04-15-autonomous-pr-shepherd-headless.md`
- `ideas/2026-04-15-tool-failure-two-attempt-cap.md`

Keep these archived docs as baseline history, not active implementation plans:

- `ideas/archive/2026-04-13-review-intelligence-canonical.md`
- `ideas/archive/deep-ci-chunked-context-plan.md`
- `ideas/archive/deep-ci-review-context-manifest-plan.md`
- `ideas/archive/deep-ci-whole-file-logic-review.md`
- `ideas/archive/extract-codex-review-python.md`
