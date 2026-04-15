# Quest Review Intelligence Canonical Proposal

## Status: proposed

## Why this note exists

Quest already has strong review values, but review findings, decisions, validation choices, and loop stop conditions are still too coupled in practice.

This canonical proposal keeps scope tight and defines one review-intelligence baseline that future implementation quests can execute without ambiguity.

## Governing rules (must stay true)

1. Code and tests remain authoritative.
2. Memory is optional and only used when uncertainty remains.
3. Findings must be normalized before arbitration or fixing.
4. Easy/local tasks must not pay extra process cost.

## Scope boundaries

- In scope: finding normalization, review decisions, targeted validation, bounded loops, and memory-use triggers during review.
- Out of scope: memory-system architecture, prompt-assembly/rule-pack design, feedback routing design, and evaluation benchmark design.

## Sibling doc dispositions

| Sibling doc | Disposition | Rationale |
|---|---|---|
| `2026-04-13-quest-memory-architecture.md` | Cross-referenced | Defines the canonical memory architecture, retrieval rules, and memory-layer record design. This document remains the schema authority for finding structure. |
| `2026-04-13-quest-memory-evaluation-loop.md` | Left as-is | Benchmarks memory quality; not part of review finding/decision/validation/loop mechanics. |
| `2026-04-13-feedback-intent-routing.md` | Cross-referenced | Canonical feedback-routing proposal for clarify/replan/second-opinion/escalation behavior. Relevant adjacent design, but still outside this document's review-intelligence scope. |
| `.ws/2026-04-13-feedback-aware-delegation-keywords.md` | Historical working note | Earlier routing-specific draft retained only as background material after consolidation into `2026-04-13-feedback-intent-routing.md`. |
| `.ws/2026-04-13-intent-anchored-example-prompts.md` | Historical working note | Earlier prompt-authoring draft retained only as background material after consolidation into `2026-04-13-feedback-intent-routing.md`. |

## Section 1: Canonical Finding Schema

### Goal

Normalize review inputs from all sources into one stable internal contract.

### Canonical finding artifact

`review_findings.json`

Produced in:

- `.quest/<id>/phase_01_plan/review_findings.json`
- `.quest/<id>/phase_03_review/review_findings.json`

Optional PR-flow temp artifact:

- `.quest/<id>/phase_03_review/pr_review_findings.json`

### Possible finding sources

- Quest code reviewer
- Quest CI reviewer
- Inline PR comments
- Top-level PR comments
- Static checks
- Test failures
- Optional future local/hosted review engines

### Canonical finding schema

```json
{
  "finding_id": "review-a-003",
  "source": "code-reviewer-a",
  "kind": "correctness",
  "severity": "must_fix",
  "confidence": "high",
  "path": "src/auth/session.ts",
  "line": 84,
  "summary": "session token may be persisted before validation completes",
  "why_it_matters": "can create invalid durable state on first-run path",
  "evidence": [
    "validateSession() is called after writeSession()",
    "error path does not delete the persisted record"
  ],
  "action": "fix_now",
  "needs_test": true,
  "write_scope": [
    "src/auth/session.ts",
    "tests/unit/auth/session.test.ts"
  ],
  "related_acceptance_criteria": [
    "AC-03"
  ]
}
```

### Why this is worth it

- Arbiter can merge and dedupe findings consistently.
- Fixer can batch work by write scope.
- Validation can use `needs_test` and `write_scope`.
- Stale/weak findings can be dropped with explicit reasons.
- CI review and interactive review can share one contract.

### Non-goal

Do not build a giant schema framework. Start with one JSON shape and one validator.

## Section 2: Review Decisions / Backlog Stage

### What this stage does

Review decisions are a separate stage between detection and fixing:

1. Determine if a finding is still real.
2. Determine if evidence is strong enough to act.
3. Determine whether to fix now, verify further, defer, drop, or escalate.
4. Determine required validation before closure.

### Default ownership

- Plan review phase: arbiter.
- Code review phase: arbiter.
- PR comment/CI response flow: `pr-shepherd`.

### Inputs

- Normalized `review_findings.json`
- Diff/changed files
- Current code snapshot
- Acceptance criteria (if available)
- Test inventory (if available)

### Outputs

- `review_backlog.json`
- `review_backlog.md`

### Backlog entry schema

```json
{
  "finding_id": "review-a-003",
  "decision": "fix_now",
  "decision_confidence": "high",
  "reason": "real bug, narrow write scope, low regression risk",
  "needs_validation": [
    "unit_test",
    "typecheck"
  ],
  "owner": "fixer",
  "batch": "auth-session-batch-1"
}
```

### Decision rules

Allowed decisions:

- `fix_now`
- `verify_first`
- `defer`
- `drop`
- `needs_human_decision`

Default rules:

- `fix_now`: correctness/security/reliability/data-integrity or broken tests, clear evidence, narrow scope.
- `verify_first`: plausible issue but incomplete evidence or uncertain runtime/module behavior.
- `defer`: worthwhile but not merge-blocking.
- `drop`: stale/already fixed/false positive/too weak.
- `needs_human_decision`: product policy or high-risk behavior tradeoff.

### Where this stage sits

Plan phase:

- After dual plan review and before final approval.
- Unresolved `must_resolve` findings block walkthrough approval.

Code review phase:

- After dual code review and before fixer starts.
- Fixer receives only `fix_now` and `verify_first`.

PR response flow:

- Before `pr-shepherd` replies or pushes.
- Normalize comments/findings/CI failures, then batch by scope.

### Arbiter contract change

For plan and code review phases, arbiter must produce both:

- `arbiter_verdict.md`
- `arbiter_backlog.json`

Minimum `arbiter_backlog.json` fields:

- merged findings
- deduped findings
- dropped findings with reason
- actionable findings grouped by batch
- unresolved human-decision items

### Subagent policy

- `0` extra agents when there are `0-1` actionable findings.
- `2` validation agents when there are `2-4` independent actionable findings.
- `3` max in normal operation.
- One validation agent per independent file set.
- No overlapping write scopes.
- Use agents to validate/isolate, not to spray edits.

## Section 3: Targeted Validation Strategy

### Goal

Run the smallest validation that can actually falsify each actionable change.

### Validation levels

Level 0 (cheap local guards):

- formatting
- lint
- typecheck
- shellcheck
- manifest validation
- config/schema validation

Level 1 (impacted tests):

- touched unit tests
- nearest module tests
- one integration test for the affected workflow

Level 2 (broader suite):

- shared infrastructure changed
- interfaces changed
- auth/persistence/build tooling/orchestration changed
- targeted tests do not exist
- finding touches a cross-cutting invariant

### Test selection heuristic

1. If backlog item names a test path, run it.
2. Else run nearest tests by directory and naming convention.
3. Else run repo-allowed module-level tests.
4. Escalate to broader suite only when scope crosses shared boundaries.

### Batch-before-push rule

- Do not push after every single comment fix.
- Batch independent `fix_now` items that share validation scope.
- Run targeted validation once per batch.
- Push once per validated batch.

### Recommended CI job shape

`review-intake`:

- Validate PR description, manifest, and required checks.
- Collect changed files/diff stats.
- Produce initial `review_findings.json` for structural failures.
- Blocking: yes for missing required PR/manifest structure.

`review-logic`:

- Run main CI reviewer on the diff.
- Emit normalized findings.
- Optionally deep-review a bounded subset of risky changed files.
- Blocking: yes for `blocker` and `must_fix`; deep whole-file logic can start warn-only.

`review-coverage`:

- Map acceptance criteria to test/validation evidence.
- Emit missing-evidence findings.
- Blocking: yes when automated criteria lack evidence.

`review-commenter`:

- Merge findings from prior jobs.
- Dedupe against unresolved PR comments.
- Post one concise summary plus inline findings as needed.
- Blocking: no (reporting only).

## Section 4: Bounded Fix-Loop Rules

### Goal

Stop loops with explicit conditions in plan review, code review, and PR response flows.

### Plan review loop

Flow:

1. Merge findings.
2. Make review decisions.
3. Revise plan.
4. Re-review only if unresolved `must_resolve` items remain.

Stop when:

- no `must_resolve` items remain
- only `should_consider` items remain
- iteration cap reached (`2` by default)

At cap:

- arbiter writes a short tradeoff note
- unresolved non-blocking items are shown explicitly

### Code review loop

Flow:

1. Merge findings.
2. Make review decisions.
3. Batch actionable items.
4. Fix.
5. Run targeted validation.
6. Re-review only affected areas when needed.

Stop when:

- no `blocker`/`must_fix` findings remain
- only `should_fix`/`nit` remain and user chose "good enough"
- iteration cap reached (`2` default, `3` max)

At cap:

- present remaining backlog
- every item must be tagged as one of:
  - `defer`
  - `needs_human_decision`
  - accepted debt

### PR shepherd loop

Flow:

1. Collect CI state, inline comments, general comments, and findings.
2. Normalize into finding contract.
3. Make review decisions.
4. Group by write scope and validation scope.
5. Fix batched items.
6. Run targeted validation.
7. Push.
8. Wait for CI.
9. Reply/resolve only after evidence exists.

Stop when:

- CI is green
- no unresolved `fix_now`/`verify_first` items remain
- loop cap reached (`3` default)

## Section 5: Memory-Use Triggers During Review

This section intentionally includes only memory-use triggers and guardrails for review behavior.
For retrieval mechanics, artifact shape, and implementation details, see `ideas/2026-04-13-quest-memory-architecture.md`.

### Retrieval triggers

Retrieve review memory only if one of these is true:

1. The change crosses more than one meaningful module boundary.
2. Reviewer disagreement suggests a boundary/invariant question.
3. The agent has searched several times and still has unresolved uncertainty.
4. The review touches a critical workflow with known footguns.
5. The same class of finding keeps recurring in the same area.
6. The user explicitly asks for architecture/prior-learnings context.

If none are true, do not load memory.

### Review-phase behavior

Arbiter-owned phases:

- Start with findings, diff, plan/spec, tests, and code.
- Pull memory only if disagreement or uncertainty remains.
- Use memory to resolve boundaries/invariants, not to invent new scope.

PR shepherd flow:

- Start with comments, findings, changed files, tests, and code.
- Pull architecture notes for cross-module findings.
- Pull rule/design docs for invariant disagreements.
- Pull review-learnings for repeated finding classes.
- If task scope is simple/local, do not load memory.

### Guardrails

Code wins:

- If memory and code disagree, trust code.
- Mark the memory claim stale and do not act on memory alone.

No preload default:

- Do not preload memory for local single-file review, straightforward PR comment fixes, simple validation runs, or obvious low-scope findings.

### Cross-reference for memory record inheritance

Future memory `finding`/`decision` records (see `ideas/2026-04-13-quest-memory-architecture.md`) MUST inherit and conform to the canonical finding schema defined in Section 1 of this document. This canonical document is the schema authority; memory-layer records inherit from it.

## Rollout plan

### Phase 1: finding contract and review decisions

Ship first:

- `review_findings.json`
- `review_backlog.json`
- review-decision script or reusable skill/instructions
- no memory changes yet

Success measure:

- less reviewer/fixer ambiguity
- fewer stale findings carried into fixer handoff

### Phase 2: targeted validation and PR batching

Ship next:

- test selector
- `pr-shepherd` batching rules
- fix-loop caps

Success measure:

- fewer pushes per resolved review batch
- fewer CI reruns for trivial comment handling

### Phase 3: bounded deep review

Extend CI review:

- keep diff review as default
- add whole-file logic review for a bounded subset of risky changed code files

Success measure:

- catches file-level logic bugs missed by diff-only review
- review noise does not spike

## Kill criteria

Do not keep any part of this if it causes one of these:

- reviewers emit more structured data but decisions do not improve
- PR response gets slower without better issue detection
- test selection becomes so conservative that it always escalates to full suite
- fix loops grow in iteration count without reducing escaped issues

## Suggested follow-up quests

### Quest 1: finding contract and review decisions

```text
/quest "Implement review finding normalization and review decisions for Quest. Add a canonical review_findings.json contract, a review_backlog.json artifact, and a bounded review-decision stage between review and fixer. In Quest review phases, make arbiter own review-decision output. In PR and CI response flows, make pr-shepherd reuse the same review-decision rules. Add a reusable .skills/review-decisions/SKILL.md policy file, validators, and focused tests. Keep scope limited to artifact generation, merge/dedupe, decisions, and handoff integration. Do not add memory retrieval in this quest."
```

### Quest 2: targeted validation and PR shepherd batching

```text
/quest "Implement targeted validation and batched PR response for Quest. Extend pr-shepherd so it normalizes incoming review items, groups actionable fixes by write scope and validation scope, runs the smallest falsifying checks, and pushes one validated batch at a time. Add a quest_select_tests helper, explicit stop conditions, and focused tests. Do not add review memory loading in this quest."
```
