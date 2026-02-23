# Draft PR Review Comment Gate (KISS/YAGNI/SRP)

## Policy
Before merge, every feature PR should have:
1. Draft PR created from a feature branch.
2. Explicit PR review comment posted on the draft/ready PR.
3. Merge decision made only after filtering low-value NIT feedback and applying KISS, YAGNI, and SRP judgment.

## Why
- Prevents merge-by-default without conscious review decisions.
- Keeps review focus on meaningful quality/risk issues instead of churn.
- Improves auditability: rationale is captured in PR comments, not just chat.

## Suggested Enforcement
- Add a workflow step requiring a posted PR review comment before merge.
- Add branch/ruleset guidance that merge happens only after this review gate is satisfied.
