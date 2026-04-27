---
name: pre-commit-review
description: Review local staged and unstaged tracked-file changes before committing or before a pull request exists. Use when the user invokes /pre-commit-review, asks for a pre-commit review, asks to review local changes before commit, or wants a local working-tree review before a PR exists.
---

# Pre-Commit Review

Review the local working-tree diff before a commit exists for review. At activation, announce the skill name and scope in one line:

`[pre-commit-review] reviewing local working-tree diff before commit`

## Required Inputs And Preflight

Run these checks before reviewing:

1. Verify this is a git repository:
   - Run `git rev-parse --is-inside-work-tree`.
   - If it fails, stop with: `pre-commit-review requires a git repository; no review was run.`
2. Refuse during an in-progress merge, rebase, or cherry-pick:
   - Resolve git metadata paths with `git rev-parse --git-path MERGE_HEAD`, `git rev-parse --git-path CHERRY_PICK_HEAD`, `git rev-parse --git-path rebase-merge`, and `git rev-parse --git-path rebase-apply`.
   - Check the resolved paths, not direct `.git/...` paths.
   - If any resolved path exists, stop with: `pre-commit-review will not review during an in-progress merge/rebase/cherry-pick; finish or abort the operation first.`
3. Verify the repository has a `HEAD` commit:
   - Run `git rev-parse --verify HEAD`.
   - If it fails, stop with: `pre-commit-review requires at least one commit; no review was run.`
4. Check for tracked-file changes:
   - Run `git diff --cached --quiet --` and `git diff --quiet --`.
   - If both are quiet, stop with: `No staged or unstaged tracked-file diff found; pre-commit review has nothing to review.`
5. Warn about untracked files:
   - Run `git status --porcelain`.
   - If any line begins with `??`, say that untracked files are not part of this review until staged and offer to stop so the user can run `git add` first.

Default review diff:

```bash
git diff --no-ext-diff HEAD --
```

This reviews staged plus unstaged tracked-file changes. Untracked files are not included until they are staged.

## Review Process

1. Read `AGENTS.md` if present and apply repo rules.
2. Read `.skills/code-reviewer/SKILL.md` for the severity model only:
   - `Blocker`
   - `Must fix`
   - `Should fix`
   - `Nit`
3. Read `.skills/review-anti-patterns.md` and apply the shared review anti-pattern guidance.
4. Focus on correctness, security hygiene, tests for touched behavior, maintainability, and commit-readiness.
5. Keep feedback high signal. Omit `Nit` findings by default unless they are bundled with a higher-value issue or the user explicitly requested nits.

Do NOT inherit PR-only behavior from `code-reviewer`:

- No PR comment placement rules.
- No GitHub inline-first review handling.
- No manifest validation Step 0.
- No acceptance-criteria test coverage mapping unless the user provided specific acceptance criteria for the local change.
- No `PR Comment` output section.
- No GitHub CI, PR creation, PR update, or push workflow.

## Output Format

Findings come first. Emit numbered findings in current-review order:

`[N] Blocker|Must fix|Should fix|Nit - path:line - finding and concrete fix`

Examples:

`[1] Must fix - src/app.py:42 - The error branch swallows failed writes, so callers can commit data loss. Fix: return a non-zero result or raise the existing domain exception.`

`[2] Should fix - tests/test_app.py:18 - The changed validation path has no regression coverage. Fix: add a focused test for the invalid input case.`

If there are no findings, say there are no findings, then proceed to the terminal decision flow.

## Terminal Decision Flow

After findings, present these exact user-facing choices:

1. `fix all Must`
2. `fix selected [N...]`
3. `skip`
4. `commit`

If any `Blocker` or `Must fix` findings exist, recommend fixing them before commit.

Choice behavior:

- `fix all Must`: fix all `Blocker` and `Must fix` findings that are actionable in the working tree.
- `fix selected [N...]`: fix only the requested numbered findings.
- `skip`: leave the working tree unchanged.
- `commit`: create a local commit only if the user explicitly asks. Use `git-commit-assistant` where applicable.

These labels are only terminal decision labels. This skill runs outside the Quest pipeline and must not write `review_backlog.json` or any other Quest decision artifact.

Never push from this skill.
