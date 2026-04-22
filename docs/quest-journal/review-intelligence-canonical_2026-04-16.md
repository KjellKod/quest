# Quest Journal: Review Intelligence Canonical (Phase 1)

- Quest ID: `review-intelligence-canonical_2026-04-16__0218`
- Completed: 2026-04-16
- Mode: workflow
- Quality: Gold
- Outcome: Implement Phase 1 of review-intelligence-canonical: normalize review
findings and add a review-decisions stage between review and fixer.

## What Shipped

**Problem:** Quest review outputs are currently markdown-first and role-local, with no single canonical finding contract, no deterministic decision backlog artifact between review and fixer, and no persistent deferred-findings resurfacing path.

**Impact:** This phase makes review outputs machine...

## Files Changed

- `.quest/review-intelligence-canonical_2026-04-16__0218/phase_01_plan/plan.md`
- `.quest/review-intelligence-canonical_2026-04-16__0218/phase_01_plan/arbiter_verdict.md`
- `.quest/review-intelligence-canonical_2026-04-16__0218/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/review-intelligence-canonical_2026-04-16__0218/phase_01_plan/review_plan-reviewer-b.md`
- `.quest/review-intelligence-canonical_2026-04-16__0218/phase_02_implementation/pr_description.md`
- `.quest/review-intelligence-canonical_2026-04-16__0218/phase_02_implementation/builder_feedback_discussion.md`
- `scripts/quest_runtime/review_intelligence.py`
- `scripts/quest_review_intelligence.py`
- `tests/unit/test_review_intelligence.py`
- `.quest/review-intelligence-canonical_2026-04-16__0218/phase_03_review/review_code-reviewer-a.md`
- `.quest/review-intelligence-canonical_2026-04-16__0218/phase_03_review/review_code-reviewer-b.md`
- `.quest/review-intelligence-canonical_2026-04-16__0218/phase_03_review/review_fix_feedback_discussion.md`

## Iterations

- Plan iterations: 2
- Fix iterations: 1

## Agents

- **The Judge** (arbiter): 
- **The Implementer** (builder): 

## Quest Brief

Implement Phase 1 of review-intelligence-canonical: normalize review
findings and add a review-decisions stage between review and fixer.

Reference: ideas/archive/2026-04-13-review-intelligence-canonical.md

### Deliverables

1. Canonical review_findings.json schema (reference Section 1). One JSON shape plus a validator. Written to `.quest/<id>/phase_01_plan/review_findings.json` and `.quest/<id>/phase_03_review/review_findings.json`. Required fields: finding_id, source, kind, severity, confidence, path, line, summary, why_it_matters, evidence, action, needs_test, write_scope, related_acceptance_criteria.

2. review_backlog.json artifact (reference Section 2) produced by the arbiter after dual review. Records one decision per finding from the allowed set: fix_now, verify_first, defer, drop, needs_human_decision. Each entry includes decision_confidence, reason, needs_validation, owner, batch. The fixer receives only fix_now and verify_first items.

3. Reusable .skills/review-decisions/SKILL.md so the Quest arbiter and pr-shepherd share one decision policy. Encodes the default decision rules from reference Section 2.

4. Bounded review-loop rules (reference Section 4): 2 iterations default, 3 max. At cap, every remaining finding MUST be tagged defer, needs_human_decision, or accepted debt. No silent looping.

5. Deferred findings backlog at .quest/backlog/deferred_findings.jsonl (repo-level, NOT per-quest). On a defer decision, the arbiter appends a record that inherits the canonical finding schema plus four lineage fields: deferred_by_quest, deferred_at (ISO8601), defer_reason, proposed_followup. Append-only JSONL.

6. Planner-startup backlog scan. Before planning, the planner reads deferred_findings.jsonl and surfaces any entry whose write_scope intersects the upcoming quest's likely scope. Present to the user as: 'N deferred findings touch this code -- pull into scope?' Use conservative matching in v1 (exact path match only).

7. Focused tests under tests/ covering: finding-schema validation (valid / missing required fields / wrong types), decision-rule selection, merge-and-dedupe across sources, JSONL append correctness, planner backlog-scan match logic.

### Integration Touchpoints

- .skills/quest/agents/arbiter.md -- require review_backlog.json output alongside arbiter_verdict.md
- .skills/quest/agents/code-reviewer.md -- emit findings in the canonical schema
- .skills/quest/agents/planner.md -- add the backlog-scan step to planner startup
- .skills/quest/delegation/workflow.md -- document the decisions stage and the loop caps
- Validators live under scripts/ and are invoked from phase-transition checks

### Out of Scope

- Memory retrieval (ideas/2026-04-13-quest-memory-architecture.md)
- CI workflow changes (reference Phase 3)
- Targeted validation / test selector (reference Phase 2)
- pr-shepherd batching rules (reference Phase 2)
- Backlog staleness / retention sweeps (follow-up chore)
- Triage tooling for the backlog

### Kill Criteria

Roll back if reviewers emit more structured data but decisions do not improve; if fix loops grow in iteration count without reducing escaped issues; if test selection always escalates to full suite.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/review-intelligence-canonical_2026-04-16.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "workflow",
  "agents": [
    {
      "name": "arbiter",
      "model": "",
      "role": "The Judge"
    },
    {
      "name": "builder",
      "model": "",
      "role": "The Implementer"
    }
  ],
  "achievements": [
    {
      "icon": "[BUG]",
      "title": "Gremlin Slayer",
      "desc": "Tackled 34 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 5 reviews"
    },
    {
      "icon": "[PLAN]",
      "title": "Plan Perfectionist",
      "desc": "Iterated plan 2 times"
    },
    {
      "icon": "[WIN]",
      "title": "Quest Complete",
      "desc": "All phases finished successfully"
    }
  ],
  "metrics": [
    {
      "icon": "📊",
      "label": "Plan iterations: 2"
    },
    {
      "icon": "🔧",
      "label": "Fix iterations: 1"
    },
    {
      "icon": "📝",
      "label": "Review findings: 5"
    }
  ],
  "quality": {
    "tier": "Gold",
    "grade": "G"
  },
  "test_count": null,
  "tests_added": null,
  "files_changed": 12
}
```
<!-- celebration-data-end -->
