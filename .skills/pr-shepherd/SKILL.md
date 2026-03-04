# PR Shepherd

Push a draft PR and iterate until CI passes and review comments are resolved, then mark ready for review.

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
3. For each comment, respond **on the comment itself** (threaded reply), never in the general PR discussion:
   - **Inline review comments** → reply via `gh api repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies -f body="..."`
   - **General discussion comments** → reply via `gh pr comment <PR_NUMBER> --body "..."`
4. Decision per comment:
   - **Agree?** → Fix the code, commit, push. Reply on the comment acknowledging the fix.
   - **Disagree?** → Reply on the comment with clear reasoning explaining why.
   - **Question/clarification?** → Reply on the comment with the answer.

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
