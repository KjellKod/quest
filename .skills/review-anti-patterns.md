# Review Anti-Patterns

Shared rules for review-adjacent Quest skills. Reference these rules instead of duplicating local anti-chat guidance.

## Rules

1. Do not add reply comments justifying a finding.
   - Rationale: the finding belongs in the review; extra thread replies create noise unless they answer a user or reviewer question.
2. Do not restate inline findings as top-level PR comments.
   - Rationale: inline-first review keeps code-specific feedback attached to the exact line.
3. Do not ask which issues to fix when severity is unambiguous.
   - Rationale: blockers and Must-fix items are fixed; ask only for Should-fix or Nit selection when the plan does not decide it.
4. Do not introduce requirements the plan or PR description did not ask for.
   - Rationale: review feedback should protect correctness and scope, not expand the feature.
5. Do not pad clean reviews with empty PASS sections.
   - Rationale: clean output should stay short enough for a reviewer to scan quickly.
6. Bias toward action on iteration 3 and later.
   - Rationale: only blockers justify another loop; defer the rest through `.skills/review-decisions/SKILL.md`.
