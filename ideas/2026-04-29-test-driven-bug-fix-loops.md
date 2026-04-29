---
title: Test-Driven Bug-Fix Iteration Loops
purpose: Define a safer Quest bug-fix mode that proves reproduction first, tries bounded distinct strategies, and preserves failed-attempt evidence without destructive rollback.
audience:
  - quest-maintainers
  - skill-authors
  - quest-users
status: proposed
date: 2026-04-29
related:
  - AGENTS.md
  - .skills/quest/agents/fixer.md
  - .skills/implementer/SKILL.md
  - ideas/2026-04-22-review-ergonomics-and-team-preference-memory.md
  - ideas/2026-04-15-claude-insights-priorities.md
---

# Summary

Quest already has the core bug-fix rule:

> Bug fixes: add a test that reproduces the bug (fails first), fix the code
> without changing that test, then re-run it to verify it passes.

The suggested improvement is a stronger bug-fix loop for hard bugs:

1. Convert the bug report into a failing test first.
2. Generate a small set of distinct fix strategies before editing production
   code.
3. Try strategies one at a time against the same failing test.
4. Preserve failed-attempt evidence.
5. Stop after a hard cap instead of endlessly tweaking the same approach.

This is valuable, but should not be implemented with automatic
`git reset --hard`. Quest routinely works in dirty user worktrees and
multi-agent worktrees; destructive rollback can erase unrelated work. Use
explicit checkpoints, isolated worktrees, or patch snapshots instead.

# Value

High for ambiguous or recurring bugs where agents tend to loop on near-miss
patches.

Medium or low for simple, obvious bug fixes where the existing failing-test
rule is enough.

This mode improves:

- proof that the bug was reproduced before fixing,
- auditability of failed attempts,
- avoidance of same-strategy thrash,
- final PR confidence because the reproduction test stays stable.

# Risks

| Risk | Mitigation |
|---|---|
| Overhead on simple bugs | Trigger only for explicit bug reports, reproduced failures, or when the fixer fails once. |
| Test encodes the wrong behavior | Require the test to quote or reference the bug report and fail for the observed misbehavior. |
| Strategy theater | Limit to 2-3 materially different strategies with one-sentence rationales. |
| Destructive rollback | Do not use `git reset --hard`; use worktrees, commits, or patch snapshots. |
| Hiding useful partial progress | Preserve attempt notes, test output, and diffs before discarding a failed strategy. |
| Infinite loops | Hard cap attempts and stop with evidence when all fail. |

# Recommended Behavior

Add an optional bug-fix mode for Quest fixer/builder flows:

1. Confirm the task is a bug fix.
2. Write or identify the narrow failing test that reproduces the bug.
3. Run only the reproduction test and record the failing output.
4. Generate up to three distinct strategy candidates before editing production
   code.
5. Try each strategy in sequence.
6. After each attempt:
   - run the reproduction test,
   - record pass/fail,
   - if it fails, preserve the diff and test output,
   - revert only the attempted changes using a safe mechanism.
7. When the reproduction test passes:
   - run targeted related tests,
   - run the broader validation suite required by the plan,
   - record the winning strategy and tests in the handoff.
8. If all attempts fail, stop and report:
   - failing test path,
   - output per strategy,
   - hypothesis for why strategies failed,
   - suggested next question or diagnostic.

# Safe Rollback Options

Preferred options, in order:

1. **Dedicated worktree per attempt** for larger or riskier bugs.
2. **Temporary checkpoint commit** before each attempt, reverted with normal
   Git operations after preserving evidence.
3. **Patch snapshot** using `git diff > .quest/<id>/phase_03_review/attempts/<strategy>.patch`
   plus explicit file restoration only for files touched by that attempt.

Avoid:

- `git reset --hard` in shared or dirty worktrees,
- deleting untracked files automatically,
- changing the reproduction test after production-code attempts begin.

# Artifact Layout

```text
.quest/<id>/phase_03_review/bug_fix_attempts/
  reproduction.md
  strategies.md
  strategy_a.patch
  strategy_a_test_output.txt
  strategy_b.patch
  strategy_b_test_output.txt
  strategy_c.patch
  strategy_c_test_output.txt
  summary.md
```

`reproduction.md` should include:

- bug report excerpt or source,
- expected behavior,
- observed behavior,
- test path,
- initial failing command and output summary.

`strategies.md` should include:

```markdown
## Strategy A
Rationale: ...

## Strategy B
Rationale: ...

## Strategy C
Rationale: ...
```

`summary.md` should include:

- winning strategy, or `none`,
- attempts made,
- test commands run,
- remaining uncertainty,
- files changed.

# Integration Points

Minimal first step:

- Update `.skills/quest/agents/fixer.md` to expand the existing bug-fix
  responsibility into a bounded prove-it loop when the fix is non-trivial.
- Update `.skills/implementer/SKILL.md` with a bug-fix mode subsection.

Larger later step:

- Add helper script support for attempt directories and patch snapshots.
- Add completion-summary reporting for bug-fix attempts.
- Consider a standalone `bug-fix-loop` skill only if the pattern proves useful
  outside Quest.

# Non-Goals

- Do not make every bug fix use three strategies.
- Do not require commits for every attempt in normal Quest runs.
- Do not auto-open PRs from this mode.
- Do not bypass Quest review/fix loops.
- Do not use destructive rollback.

# Open Questions

- Should the loop trigger immediately for every explicit bug report, or only
  after the first ordinary fix attempt fails?
- Should attempt artifacts live under phase 02 for builder-discovered bugs and
  phase 03 for reviewer/fixer bugs?
- Should a passing reproduction test be allowed if the broader suite still
  fails for unrelated reasons?
- Should the strategy cap be 2 or 3 by default?
