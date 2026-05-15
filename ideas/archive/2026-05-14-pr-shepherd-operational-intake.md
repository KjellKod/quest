---
title: PR Shepherd Operational Intake and Idempotent Replies
purpose: Reduce PR shepherding drift, duplicate comments, and token-heavy GitHub state inspection by moving deterministic PR plumbing into small scripts.
audience: Quest maintainers and agents that run PR lifecycle workflows
scope: PR checkout, PR state collection, comment dedupe, review-intake normalization, CI log collection, operational stop states, and the boundary with pr-assistant
status: done
owner: maintainers
date: 2026-05-14
implemented: 2026-05-15
journal: ../docs/quest-journal/pr-shepherd-operational-intake_2026-05-15.md
---

# PR Shepherd Operational Intake and Idempotent Replies

## Problem

PR shepherding currently asks the agent to inspect raw GitHub state, infer which
comments were already handled, decide whether CI is still useful to wait on, and
remember the boundary between PR creation and PR shepherding. That creates three
avoidable costs:

- repeated token spend on mechanical GitHub inspection;
- risk of duplicate or misplaced replies on repeat shepherd runs;
- ambiguity about whether the current branch/worktree is the PR being shepherded.

The improvement should keep human judgment and review triage in the existing
review-intelligence path. The scripts proposed here should only collect,
normalize, dedupe, and post mechanical PR data.

## Ownership Boundary

`pr-assistant` should own draft PR creation and PR body updates.

`pr-shepherd` should own an existing PR after creation:

- locate or check out the PR branch;
- wait for CI within a bounded budget;
- collect CI, review, and comment intake;
- route normalized findings through review intelligence;
- make safe fix commits when appropriate;
- post targeted replies with durable markers;
- mark the PR ready only when CI is green and active feedback is handled.

The current `pr-shepherd` Step 1 overlaps with `pr-assistant`. That overlap
should be removed or reframed as: "If no PR exists, stop and ask the user to run
`pr-assistant` first."

## Proposed Changes

### 1. Add Explicit PR Targeting

Allow `pr-shepherd` to accept a PR number, PR URL, or branch name. Before
checking out another PR, require a clean worktree.

Example:

```bash
gh pr checkout 482
gh pr checkout https://github.com/OWNER/REPO/pull/482
gh pr checkout feature-branch
```

This lets the user say "shepherd PR 482" from any branch while preserving the
existing branch/worktree guard before commits and pushes.

Worktree contract:

- Do not auto-create a new worktree in the first implementation.
- If the current directory is a dedicated worktree for another branch, refuse to
  switch branches unless the target PR already matches the current branch.
- If the explicit target is already the current branch's PR, state collection may
  proceed, but edits/commits still require the normal context guard.
- Any checkout failure stops before edits and reports the `gh pr checkout`
  diagnostic.

Acceptance criteria:

- Dirty worktree blocks checkout with a clear message.
- Explicit PR number or URL checks out that PR head branch before state
  collection.
- Current-branch behavior still works when no PR target is supplied.
- Fork PRs are either supported by `gh pr checkout` or fail with a clear
  diagnostic before any edits.
- Running inside a worktree has deterministic behavior: match current PR or stop;
  do not silently switch an unrelated worktree.

### 2. Add Idempotent Reply Markers

Every reply posted by `pr-shepherd` should include a hidden marker:

```html
<!-- pr-shepherd:addressed v1 -->
```

Deferred follow-up replies should include:

```html
<!-- pr-shepherd:followup v1 -->
```

The goal is not to resolve GitHub threads automatically. The goal is to make a
repeat run able to answer: "Did this shepherd pass already respond to this
thread or comment, and has new human feedback arrived since then?"

Suggested activity states:

- `active`: no marker exists, or human activity happened after the last marker.
- `addressed`: the latest relevant activity is the shepherd marker.
- `uncertain`: only bot or automation activity happened after the marker.

Marker scope:

- For `review_thread` records, activity state is scoped to that GitHub review
  thread.
- For `issue_comment` records, activity state is scoped to that top-level PR
  comment.
- For parsed review-body items or check annotations without a thread, marker
  ownership is scoped by stable fingerprint.

`uncertain` should be inspected, not ignored. The first implementation should use
a simple deterministic rule: if automation activity appears after the marker,
surface it as `uncertain` with compact evidence. The agent or review-intelligence
path decides whether it is actionable.

Top-level marker ownership should be one shepherd-owned summary comment per PR,
updated across passes. That comment may contain many fingerprints. Inline review
threads should still receive thread replies when a thread reply target exists.
Marker version bumps must treat older marker versions as valid history unless a
future migration explicitly says otherwise.

First-run behavior: existing PRs have no shepherd markers, so existing unresolved
comments are treated as active once. The first shepherd pass should stamp handled
feedback; later passes use marker recency and fingerprints to avoid duplicate
replies.

Acceptance criteria:

- Repeat runs do not repost replies to already handled comments.
- Human comments after a marker reactivate the thread.
- Automation comments after a marker are surfaced as `uncertain` with compact
  evidence.
- Follow-up markers are searchable so deferred work can be enumerated later.
- Parsed review-body items and check annotations dedupe by fingerprint when no
  first-class GitHub thread ID exists.
- Fork PRs without permission to post thread replies degrade to a top-level
  marker-owned summary comment.

### 3. Normalize Review Sources Without Tool-Specific Behavior

The normalized intake should not branch behavior by reviewer product name. All
feedback should be handled through the same shape after collection.

Recommended fields:

```json
{
  "source_kind": "review_thread",
  "source_label": "github-review-thread",
  "fingerprint": "stable-content-hash",
  "activity_state": "active",
  "author": "reviewer-login",
  "author_kind": "human",
  "path": "src/example.py",
  "line": 42,
  "body": "Comment body",
  "url": "https://github.com/OWNER/REPO/pull/1#discussion_r..."
}
```

`source_kind` is useful because GitHub exposes feedback through different
surfaces with different reply mechanics:

- `review_thread`: reply with a review-thread mutation.
- `issue_comment`: reply with a PR comment or update a marker-owned comment.
- `check_run`: collect logs or annotations; usually no threaded reply target.
- `review_body_item`: a parsed item from a larger review body; usually summarized
  in one marker-owned top-level comment.

Avoid `source_tool` as a decision input. A diagnostic `source_label` can be kept
for humans, but review decisions should not depend on whether feedback came from
one named tool or another. Once normalized, feedback should flow through the same
review-intelligence policy.

Acceptance criteria:

- Intake handles inline threads, general PR comments, check-run failures, and
  parsed review-body items through one schema.
- Decision policy does not special-case named review tools.
- Product names, when available, are metadata only for diagnostics and summaries.
- Stable fingerprints prevent duplicate handling for parsed review-body items
  that do not have first-class GitHub thread IDs.

### 4. Add Changed-Line Scope Annotation

Scope annotation should answer a narrow question before review-intelligence
triage: "Is this feedback anchored to code changed by this PR?"

This is not the final decision. It is evidence for the existing decision system.

Suggested values:

- `in_diff`: anchor overlaps an added, removed, or modified line in the PR diff.
- `out_of_diff`: feedback is outside the changed lines with no clear coupling.
- `unknown`: the collector cannot determine scope reliably.

Examples:

- Comment on an added line in `src/foo.py` -> `in_diff`.
- Comment asking for a broad unrelated refactor in an untouched file ->
  `out_of_diff`.
- Comment from an external check with no file/line annotation -> `unknown`.

How this ties into review intelligence:

- `in_diff` plus high-confidence correctness evidence is a strong `fix_now`
  candidate.
- `out_of_diff` should usually become `defer` or `drop` unless it is a clear
  security, data-loss, crash, or trivial correctness issue in the PR execution
  path.
- `unknown` should bias toward `verify_first` or `needs_human_decision` when the
  impact is material.

Do not make the scope script infer semantic coupling. If a reviewer comment on an
unchanged line appears related to the PR, the collector should mark it `unknown`
and preserve the evidence. Review intelligence, backed by agent judgment, can then
decide whether the finding is coupled to the change.

Acceptance criteria:

- Scope annotation is stored on normalized findings before backlog decisions.
- The existing decision taxonomy remains unchanged:
  `fix_now`, `verify_first`, `defer`, `drop`, `needs_human_decision`.
- Out-of-diff findings are not silently ignored; they are explicitly deferred,
  dropped, or escalated with a reason.
- Scope rules are covered by fixture tests for added lines, removed lines,
  context lines, missing files, and annotation-less checks.

### 5. Add Operational Stop States

Review-intelligence triage decides what to do with findings. PR shepherding also
needs a separate operational result for the whole pass:

- `clean`: CI is green and all active feedback has an addressed, deferred, or
  dropped outcome.
- `progressing`: the pass made commits or posted replies, and another CI or
  feedback cycle may still be needed.
- `stuck`: no safe action was taken and the PR is still blocked.

Common `stuck` reasons:

- CI is still pending after the wait budget.
- CI failed because of auth, missing secrets, provider outage, or external checks
  with no inspectable logs.
- Merge conflicts exceed the conservative auto-resolution bar.
- Feedback requires a human product or scope decision.
- The local branch/worktree does not match the PR head branch.

This should not become a second finding-decision engine. Prefer extending the
existing `quest_review_intelligence.py classify-pr-stop` command with an
operational output mode, or have a thin wrapper call that command and add only
per-pass facts: CI state, whether commits were pushed, whether replies were
posted, and whether active feedback remains.

Acceptance criteria:

- Every shepherd pass ends with exactly one operational state.
- `gh pr ready` runs only from `clean`.
- `stuck` includes a concrete blocker and next action.
- `progressing` includes what changed and what the next pass should wait for.

### 6. Move Mechanical Actions Into Scripts

Add small scripts that produce compact JSON and perform bounded posting actions.
The agent should consume their output, make judgment calls, and run existing
review-intelligence commands.

Proposed scripts:

- `scripts/pr_shepherd_collect_intake.py`: collect PR metadata, CI summary,
  review threads, PR comments, check annotations, existing shepherd markers, and
  compact raw links.
- `scripts/pr_shepherd_fetch_failed_logs.py`: fetch failed check logs with
  bounded output and classify unavailable external checks separately.
- `scripts/pr_shepherd_annotate_scope.py`: compute changed-line ranges from the
  PR diff and annotate normalized findings with `scope` and `scope_reason`.
- `scripts/pr_shepherd_post_reply.py`: post a thread reply or marker-owned PR
  comment and append the correct marker.
- `scripts/pr_shepherd_classify_state.py` or an extension to
  `quest_review_intelligence.py classify-pr-stop`: combine CI status, active
  feedback, actions taken, and backlog decisions into `clean`, `progressing`, or
  `stuck`. Prefer extending the existing command if that keeps the contract
  simpler.

Pipeline integration:

- Replace manual PR comment and CI state fetching in `pr-shepherd` Step 4 with
  `pr_shepherd_collect_intake.py`.
- Feed collected records into `normalize-pr-intake`; do not replace
  `normalize-pr-intake`.
- Run `pr_shepherd_annotate_scope.py` after normalization and before
  `build-backlog`, so `scope` and `scope_reason` are available when decisions are
  built.
- Keep `build-backlog`, `select-batch-validation`, and `build-fix-batches` as the
  decision and batching path.
- Use `pr_shepherd_post_reply.py` only after a finding has a decision and a reply
  target or marker-owned summary target.
- Run operational stop-state classification after CI/comment processing and after
  existing `classify-pr-stop` has handled loop-cap behavior.

Script boundary:

- Scripts may collect data, compute deterministic fingerprints, append markers,
  and validate schema.
- Scripts should not decide semantic correctness of code.
- Scripts should not broaden scope or invent fixes.
- Scripts should not merge PRs.

Acceptance criteria:

- Scripts have unit tests around parsing, dedupe, fingerprints, marker recency,
  and stop-state classification.
- Script output is compact enough for an agent to read without dumping full PR
  conversations or full CI logs by default.
- Raw URLs are preserved for drill-down when the compact summary is insufficient.
- Existing `quest_review_intelligence.py` remains the decision engine for
  findings.
- Failed-log output has a deterministic truncation contract, such as first N and
  last M lines per failed job plus a raw log URL.

## Expected Speed and Token Impact

This should reduce tokens and wall-clock time because the agent stops repeatedly
reconstructing mechanical state from raw `gh` output.

Expected savings:

- fewer full PR comment dumps in context;
- fewer repeated CI log reads after failures are summarized;
- fewer duplicate replies and fewer agent-side comparisons against old comments;
- less branch/PR state reasoning in prose;
- faster retries because the next pass can trust markers and fingerprints.

Do not optimize by hiding evidence. Compact output should include enough URLs,
IDs, file paths, line numbers, and reasons for the agent or human to audit the
classification.

## Non-Goals

- No autonomous merge.
- No new PR creation path inside `pr-shepherd`.
- No named-tool-specific review policy.
- No replacement for `quest_review_intelligence.py`.
- No attempt to auto-fix ambiguous CI, flaky tests, secrets, or infra outages.
- No broad headless loop until idempotent markers and stop states are proven.

## Suggested Implementation Slices

### First Slice

1. Split the documented `pr-assistant` / `pr-shepherd` ownership boundary.
2. Add PR targeting and clean-worktree checkout guard.
3. Add marker parsing and posting helpers for thread replies and one top-level
   marker-owned summary comment.
4. Add operational stop-state classification, preferably by extending existing
   `classify-pr-stop` behavior rather than introducing a competing decision path.

Keep this slice intentionally boring:

- one marker version;
- one normalized JSON schema;
- no plugin registry for review tools;
- no generalized workflow engine.

### Second Slice

1. Add generic PR intake collection with stable fingerprints.
2. Add changed-line scope annotation and feed it into normalized findings.
3. Update `pr-shepherd` to consume the collector and scope annotator while keeping
   the existing review-intelligence decision path.

Quality bar for both slices:

- repeat runs are deterministic;
- every helper is independently runnable;
- GitHub auth, PR lookup, and check-log failures produce clear errors;
- fixture tests cover marker recency, duplicate fingerprints, changed-line
  overlap, dirty-worktree checkout refusal, and stop-state classification.

## Constraints To Preserve

Defer until there is evidence:

- a config file for per-repo shepherd behavior;
- scheduled/headless loops;
- product-specific parsers beyond simple generic review-body extraction;
- automatic merge-conflict resolution beyond trivial safe cases.

The highest-signal outcome is repeatable state:

- which PR is being shepherded;
- which feedback is active;
- what was already answered;
- what CI failed and whether it is actionable;
- whether the pass is clean, progressing, or stuck.

Anything that does not improve one of those answers should stay out of the first
implementation.
