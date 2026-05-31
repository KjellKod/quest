# PR Shepherd

Shepherd an existing PR through CI and review comments, then mark ready for review when clean.

At activation, announce the skill name and scope in one line. Example: `[pr-shepherd] shepherding PR #97`.

See `.skills/review-anti-patterns.md` for the shared rule set.

## Default Commenting Mode

Use **inline-first** commenting by default.

- For code-specific feedback, always post/reply on the exact line thread.
- Use top-level PR comments only for cross-cutting concerns that do not map to one line, or outage/fallback summaries.
- When both are possible, choose inline.

## Procedure

### Step 1: Locate Existing PR
`pr-assistant` owns draft PR creation and PR body updates. If no PR exists for
the current branch, stop and ask the user to run `pr-assistant` first.

Accepted targets:
- current branch
- PR number
- PR URL
- branch name

Use inspection-first checkout:
```
python3 scripts/pr_shepherd_checkout.py [<target>] --json
```

This command must not mutate the current worktree unless `--apply` is supplied.
If the current branch already matches the PR head branch, it returns
`action: "none"` and must not run `gh pr checkout`.

Only use mutation when the user explicitly targets a different PR and the
worktree is clean:
```
python3 scripts/pr_shepherd_checkout.py <target> --apply --json
```

Dirty worktrees block mutation paths, not read-only inspection.

### Step 1.5: Commit/Push Context Guard
Before every commit or push performed by this skill, verify that the local
workspace still matches the PR branch:

1. Run `git status --short --branch`.
2. Run `git branch --show-current`.
3. If a PR already exists, run `gh pr view <PR_NUMBER> --json headRefName --jq .headRefName`.
4. If a PR already exists, confirm the current branch exactly matches the PR
   `headRefName`; otherwise, before PR creation, confirm the current branch is
   the intended branch for this PR.
5. If shepherding from a known worktree, verify the current directory/repo root
   is that worktree before committing.
6. If branch or workspace verification fails, stop and ask the user to confirm
   the intended workspace before editing, committing, or pushing.
7. After workspace verification, sync with the remote default branch from this
   PR worktree using the shared helper only when the worktree is clean. If the
   worktree is dirty because a local fix is being prepared, do not apply sync
   over those edits; finish and validate the fix commit first, then rerun this
   guard before pushing:
   - For normal shepherding of an already-open PR, run
     `python3 scripts/pr_sync_default_branch.py --strategy merge --apply --json`.
     Merge is the default shepherd strategy because it avoids rewriting an
     under-review PR's commit SHAs and preserves inline review-thread anchoring.
   - If the payload is `status: "up_to_date"` or `status: "synced"`, continue.
   - If the payload is `status: "conflict"`, surface `conflict_files` and the
     specific hunks when they are available. The inspect path can be
     filename-only; when hunks or conflict markers are not available, pause
     instead of guessing. Resolve only clearly safe, non-destructive conflicts
     (additive / adjacent / whitespace / import-or-list ordering where nothing
     from `main` is dropped); otherwise pause and ask the human. Never use
     blanket `-X theirs` or `-X ours`.
   - If the payload is `status: "error"`, stop before any commit or push and
     surface the `reason` and `message` fields. Do not continue shepherding from
     a stale or partially checked sync state.
   - If a repo-specific decision uses `--strategy rebase` instead, honor the
     helper payload: push with `git push --force-with-lease` when
     `force_with_lease: true`; otherwise push normally. This is the same narrow
     lease-protected own-PR-branch exception documented in
     `.skills/pr-assistant/SKILL.md` under `Force-with-lease exception`.

This guard is mandatory before:
- any CI-fix commit/push in Step 3,
- any review-comment fix commit/push in Step 4 or Step 4.4.

### Step 2: Wait for CI
Use a hard polling budget for CI waits:
- `interval_seconds = 30`
- `max_retries = 30`
- Hard cap: 15 minutes (15-minute cap, `30 seconds x 30 retries`)

Loop:
1. Run `gh pr checks <PR_NUMBER>` to get the current status.
2. Stop when all checks are green, a confirmed failure is present, or the polling budget is exhausted.
3. If checks are still pending and budget remains, sleep 30 seconds before the next retry.

### Step 3: Evaluate CI Results
- **All checks pass** → proceed to Step 4.
- **Failures** → read the failing job logs (`gh run view <RUN_ID> --log-failed`), diagnose the root cause, write a one-sentence diagnosis note naming the failing check, root cause, and intended fix, run the Step 1.5 context guard, fix it, commit, push, and loop back to Step 2.

### Step 4: Check PR Comments
1. Collect compact records-shaped intake:
   - `python3 scripts/pr_shepherd_collect_intake.py --pr <PR_NUMBER> --output <intake.json>`
2. Normalize and annotate:
   - `python3 scripts/quest_review_intelligence.py normalize-pr-intake --input <intake.json> --output <review_findings.json>`
   - `python3 scripts/pr_shepherd_annotate_scope.py --pr <PR_NUMBER> --findings <review_findings.json> --output <review_findings_scoped.json>`
3. For each comment, respond **on the comment itself** (threaded reply), never move an inline discussion to the general PR thread:
   - **Inline review comments** → use `python3 scripts/pr_shepherd_post_reply.py --pr <PR_NUMBER> --thread-id <id> --body "..."`
   - **Fingerprint-only/general summaries** → use the marker-owned summary mode in `pr_shepherd_post_reply.py`
4. Decision per comment:
   - **Agree?** → Fix the code, commit, push. Reply on the comment acknowledging the fix.
   - **Disagree?** → Reply on the comment with clear reasoning explaining why.
   - **Question/clarification?** → Reply on the comment with the answer.

### Step 4.4: Canonical Intake → Decisions → Validation → Batches → Push
Run the review loop through the canonical review-intelligence pipeline. **Order matters:** validation steps must be attached to backlog items before batching, otherwise `build-fix-batches` falls back to one-item batches keyed by `finding_id` and the "batched PR response" behavior is lost.

1. Collect one intake payload per cycle:
   - `records`
   - compact unavailable diagnostics, if any
   - for failed checks with an inspectable run id, first run `python3 scripts/pr_shepherd_fetch_failed_logs.py --run-id <RUN_ID> --check-name "<check>" --raw-log-url <url> --output <failed-log.json>`, then pass it to the collector with `--failed-log-summary <failed-log.json>`
2. Normalize intake to canonical findings:
   - `python3 scripts/quest_review_intelligence.py normalize-pr-intake --input <intake.json> --output <review_findings.json>`
3. Annotate changed-line scope:
   - `python3 scripts/pr_shepherd_annotate_scope.py --pr <PR_NUMBER> --findings <review_findings.json> --output <review_findings_scoped.json>`
4. Build decision backlog with shared policy:
   - `python3 scripts/quest_review_intelligence.py build-backlog --findings <review_findings_scoped.json> --output <review_backlog.json>`
5. Select concrete validation per actionable finding and persist onto the backlog:
   - `python3 scripts/quest_review_intelligence.py select-batch-validation --backlog <review_backlog.json> [--repo-inventory <repo_inventory.json>]`
   - Updates each actionable item's `validation_steps` in place so batching sees real signatures.
   - Single-finding preview (debugging only): `python3 scripts/quest_select_tests.py --finding <finding.json> [--repo-inventory <repo_inventory.json>]`.
6. Build actionable non-overlapping batches:
   - `python3 scripts/quest_review_intelligence.py build-fix-batches --backlog <review_backlog.json> --output <fix_batches.json>`
   - Items sharing `batch_key` + `validation_scope` signature group together, split by write-scope overlap as needed.
7. Execute one batch at a time:
   - Apply only that batch's `fix_now` / `verify_first` items.
   - Run validation steps in order (Level 0 → Level 1 → Level 2 when present).
   - Before committing or pushing the batch, run the Step 1.5 context guard.
   - Push once after that batch validates.
8. Classify loop stop after each cycle:
   - `python3 scripts/quest_review_intelligence.py classify-pr-stop --ci-state <green|failing|pending|unknown> --actionable <count> --iteration <n> --backlog <review_backlog.json> --pass-facts <pass_facts.json>`
   - If cap is enforced, classification handles in-place retagging and deferred backlog append for newly deferred findings.
   - Continue only when classification outcome is `continue`.

### Step 4.5: Inline Commenting Playbook
Use this for every inline review reply so comments feel coaching-oriented and actionable.

Inline posting defaults:
- New review findings should be posted as inline PR comments (`pulls/{pr}/comments`) whenever a valid `path` + `line` exists.
- If line mapping fails for one finding, continue posting other valid inline findings.
- If all inline postings fail, post a single PR-visible fallback summary comment.

Comment formula:
1. Start with a small positive anchor.
2. Name the issue precisely (what and why).
3. Suggest a concrete fix (or two).
4. Keep tone warm; humor is optional and brief.

Example shape:
`Nice cleanup here. One issue: <specific issue>. Could we <specific fix>?`

Tone rules:
- Be kind, not vague.
- Be direct, not sharp.
- Prefer "could we" / "suggest" over commands.
- Avoid sarcasm.
- Avoid bundling unrelated nits into one comment.

Inline scope rules:
- One comment = one issue.
- Place the comment exactly on the relevant line.
- Use top-level PR comments for larger cross-cutting concerns.
- If blocking, state why it is blocking in one sentence.

Severity labels (optional but recommended):
- `blocker`: correctness, security, broken behavior
- `important`: maintainability/readability risk
- `nit`: style or polish

Signature requirement for every posted review comment:
`- Reviewed by <model>, in collaboration with <github username>`

Ready-to-use template:
`Nice improvement here. One issue: <issue>. This can cause <impact>. Suggestion: <specific change>.`
`- Reviewed by <model>, in collaboration with <github username>`

### Step 4.6: Decision Policy Alignment
When reducing findings to actionable buckets, align with `.skills/review-decisions/SKILL.md`:
- Use only `fix_now`, `verify_first`, `defer`, `drop`, `needs_human_decision`
- Keep reasoning explicit for deferred and dropped findings
- At loop cap, convert unresolved items to `defer` (accepted debt) or `needs_human_decision`

### Step 5: Re-check CI (if changes were made)
If any fixes were pushed in Step 4, loop back to Step 2.

### Step 6: Mark Ready for Review
Once CI is green AND all comments are addressed:
```
gh pr ready <PR_NUMBER>
```
Only run this from operational state `clean`.
Inform the user the PR is ready for their review.

## Key Principles
- Never mark ready-for-review while CI is failing.
- Never ignore review comments — always respond.
- Keep fix commits small and focused; don't bundle unrelated changes.
- Use `classify-pr-stop` for loop-cap enforcement; do not prompt the user before cap retagging is applied. Prompt only if post-retag items still require `needs_human_decision`.

## Command Invocation

Run `gh` commands directly — not through `bash -lc`, `sh -c`, or other shell wrappers.
Permission prefixes (e.g. `["gh","pr"]`) only match when `gh` is the top-level command.
Wrapping in a shell defeats prefix matching and triggers repeated permission prompts.
Use shell wrappers only when you need pipes, redirects, or multi-command composition.
