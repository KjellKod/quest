# PR Shepherd

Push a draft PR and iterate until CI passes and review comments are resolved, then mark ready for review.

## Default Commenting Mode

Use **inline-first** commenting by default.

- For code-specific feedback, always post/reply on the exact line thread.
- Use top-level PR comments only for cross-cutting concerns that do not map to one line, or outage/fallback summaries.
- When both are possible, choose inline.

## Procedure

### Step 1: Push & Create Draft PR
1. Commit staged changes (use git-commit-assistant conventions).
2. Push the branch to origin.
3. Create a **draft** PR via `gh pr create --draft`.

### Step 2: Wait for CI
1. Sleep ~60 seconds to let CI workflows start and (hopefully) finish.
2. Run `gh pr checks <PR_NUMBER>` to observe CI status.

### Step 3: Evaluate CI Results
- **All checks pass** → proceed to Step 4.
- **Failures** → read the failing job logs (`gh run view <RUN_ID> --log-failed`), diagnose the root cause, fix it, commit, push, and loop back to Step 2.

### Step 4: Check PR Comments
1. Fetch **inline** review comments: `gh api repos/{owner}/{repo}/pulls/{pr}/comments`
2. Fetch **general** PR comments: `gh pr view <PR_NUMBER> --comments`
3. For each comment, respond **on the comment itself** (threaded reply), never move an inline discussion to the general PR thread:
   - **Inline review comments** → reply via `gh api repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies -f body="..."`
   - **General discussion comments** → reply via `gh pr comment <PR_NUMBER> --body "..."`
4. Decision per comment:
   - **Agree?** → Fix the code, commit, push. Reply on the comment acknowledging the fix.
   - **Disagree?** → Reply on the comment with clear reasoning explaining why.
   - **Question/clarification?** → Reply on the comment with the answer.

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
`Nice cleanup here. One tiny gremlin: <specific issue>. Could we <specific fix>?`

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
`Nice improvement here. One small gremlin: <issue>. This can cause <impact>. Suggestion: <specific change>.`
`- Reviewed by <model>, in collaboration with <github username>`

### Step 5: Re-check CI (if changes were made)
If any fixes were pushed in Step 4, loop back to Step 2.

### Step 6: Mark Ready for Review
Once CI is green AND all comments are addressed:
```
gh pr ready <PR_NUMBER>
```
Inform the user the PR is ready for their review.

## Key Principles
- Never mark ready-for-review while CI is failing.
- Never ignore review comments — always respond.
- Keep fix commits small and focused; don't bundle unrelated changes.
- If stuck in a loop (>3 fix iterations), stop and ask the user for guidance.
