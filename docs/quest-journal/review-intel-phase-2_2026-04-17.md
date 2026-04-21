# Quest Journal: Review Intelligence Phase 2 (Targeted Validation + Batched PR Response)

- Quest ID: `review-intel-phase-2_2026-04-17__2101`
- Completed: 2026-04-17
- Mode: workflow
- Quality: Gold
- PR: [#94](https://github.com/KjellKod/quest/pull/94)
- Celebration: [`celebrations/review-intel-phase-2_2026-04-17.md`](celebrations/review-intel-phase-2_2026-04-17.md)
- Outcome: Phase 2 of review-intelligence-canonical shipped. pr-shepherd now normalizes incoming review items into the canonical Phase 1 contract, decides per-finding action via the shared review-decisions policy, batches actionable fixes by write_scope + validation scope, runs the smallest falsifying checks (Level 0/1/2), and pushes once per validated batch with explicit bounded stop conditions.

## What Shipped

**Problem:** pr-shepherd previously iterated per-comment, ran whatever tests happened to feel right, and used only a generic ">3 iterations ask user" heuristic. Quest's canonical Phase 1 finding/decision/backlog language did not reach PR review intake at all.

**Impact:** PR review and in-quest review now share one finding schema, one decision policy, one batch-key derivation, and one deferred-findings reservoir. pr-shepherd can no longer silently loop past the cap; remaining items are always converted to `defer` or `needs_human_decision` with full lineage persisted to `.quest/backlog/deferred_findings.jsonl` via the existing `append-deferred` CLI.

## Files Changed

- `.quest-manifest`
- `.skills/pr-shepherd/SKILL.md` (new Step 4.4: canonical intake → decisions → batches → validation → push)
- `scripts/README.md`
- `scripts/quest_review_intelligence.py` (+3 subcommands)
- `scripts/quest_runtime/pr_review_cycle.py` (new)
- `scripts/quest_select_tests.py` (new CLI)
- `tests/unit/test_pr_review_cycle.py` (new)
- `tests/unit/test_quest_select_tests.py` (new)
- `tests/unit/test_review_intelligence.py` (+regressions)

## Iterations

- Plan iterations: 2
- Fix iterations: 1

## Agents

- **The Planner** (planner): Codex GPT-5.4
- **Plan Reviewer A**: Claude Opus 4.7 (1M)
- **Plan Reviewer B**: Codex GPT-5.4
- **The Judge** (arbiter): Claude Opus 4.7 (1M)
- **The Implementer** (builder): Codex GPT-5.4
- **Code Reviewer A**: Claude Opus 4.7 (1M)
- **Code Reviewer B**: Codex GPT-5.4 (iter 1) → Claude fallback (iter 2, Codex MCP disconnected mid-session)
- **The Fixer** (fixer): Claude Opus 4.7 (1M) fallback (Codex unavailable)

## Quest Brief

Implement Phase 2 of review-intelligence-canonical: targeted validation and batched PR response.

Reference: `ideas/archive/2026-04-13-review-intelligence-canonical.md` (Section 3: Targeted Validation Strategy, Section 4: Bounded Fix-Loop Rules — PR shepherd loop)

### Deliverables

1. Normalize PR review intake (CI checks, inline comments, general comments, existing findings) into canonical `review_findings.json` matching Phase 1 schema.
2. Emit `review_backlog.json` with decisions from the allowed set via the shared `review-decisions` policy (no policy fork).
3. Batched fix loop: group `fix_now`/`verify_first` items by `write_scope` + validation scope; no overlapping `write_scope` per batch; one batch → one validation pass → one push.
4. `scripts/quest_select_tests.py` helper returning ordered `validation_steps` across Level 0/1/2 with per-step reason; graceful degradation when scaffolding is missing.
5. Explicit stop conditions for the pr-shepherd loop (24-cell truth table over `ci_state × actionable × iteration`, default cap 3). At cap every remaining finding is tagged `defer`, `needs_human_decision`, or accepted debt. No silent looping.
6. Focused pytest coverage covering normalization, batching, select_tests heuristic, and stop-condition classification.

### Integration Touchpoints

- `.skills/pr-shepherd/SKILL.md` — new Step 4.4 canonical loop; cap-behavior guidance supersedes the old ">3 iterations ask user" text.
- `scripts/quest_runtime/pr_review_cycle.py` — runtime helpers (`normalize_pr_review_intake`, `build_fix_batches`, `select_validation_steps`, `classify_pr_loop_stop`, `retag_backlog_at_cap`).
- `scripts/quest_review_intelligence.py` — new subcommands: `normalize-pr-intake`, `build-fix-batches`, `classify-pr-stop`.
- `scripts/quest_select_tests.py` — thin CLI wrapper over the selector.

### Out of Scope

- Review memory loading (`ideas/2026-04-13-quest-memory-architecture.md`). Follow-up quest.
- Arbiter/planner changes beyond consuming Phase 1 contract.
- Deep-review CI job additions (canonical Phase 3).
- Backlog retention/staleness sweeps.
- Rewriting pr-shepherd PR creation or approval-posting logic.

## Plan Review Notes (iteration 1 → 2)

Both reviewers converged on APPROVE WITH MUST_RESOLVE and independently flagged six specification-precision gaps: validation-scope equivalence definition + Phase 2/3 dependency inversion; cap-retag reuse + batch-key derivation; `write_scope` overlap semantics (prefix + trailing slash); 24-cell stop-condition truth table (pending/unknown + iter>cap); CLI-level test per new subcommand; intake source→canonical-field mapping + deterministic sort keys.

Iteration 2 revision folded all six into the plan (merging former Phases 2 and 3, promoting overlap rule to AC3, adding the truth table to AC5, requiring `select_decision(..., at_loop_cap=True)` reuse, and adding an intake mapping table to AC1). Both reviewers approved iteration 2 clean.

## Code Review Notes (iteration 1)

- Reviewer A (Claude): APPROVE clean — every AC deliverable present, Phase 1 reuse verified end-to-end, all 24 stop-condition cells parametrized.
- Reviewer B (Codex): 2 fix_now findings — both independently verified by the arbiter:
  - **CRB-001**: `.quest-manifest` missing `scripts/quest_runtime/pr_review_cycle.py` → quality gate failed.
  - **CRB-002**: `_scope_intersects_shared_boundary` used only `startswith(prefix)` against slash-suffixed prefixes, so bare-directory scopes (`scripts/quest_runtime`) skipped Level 2 escalation.

Fixer addressed both strictly within scope, added one regression test for CRB-002, and confirmed all gates: manifest exit 0; targeted suite 59 passed (58 → 59); full suite 351 passed.

## Validation

- Manifest gate: `bash scripts/quest_validate-manifest.sh` → exit 0.
- Targeted suite: `python3 -m pytest tests/unit/test_pr_review_cycle.py tests/unit/test_quest_select_tests.py tests/unit/test_review_intelligence.py -q` → 59 passed.
- Full suite: `python3 -m pytest -q` → 351 passed, no warnings.
- Findings schema: `python3 scripts/quest_review_intelligence.py validate-findings` → ok on all three phase artifacts.

## Architecture Notes

pr-shepherd and the quest arbiter now share:

1. **Schema**: `validate_findings()` gates every finding regardless of source.
2. **Decision policy**: `build_review_backlog()` / `select_decision()` is the single decision authority.
3. **Batch-key derivation**: `_batch_from_finding()` (first sorted write_scope, fallback path, then "misc").
4. **Cap behavior**: both consumers route through `select_decision(..., at_loop_cap=True)` and persist deferred-at-cap entries through the same `append-deferred` CLI.

The `quest_select_tests` helper is deterministic (pure function over finding + optional repo inventory) and degrades gracefully when scaffolding is missing — Level 0 guards are always emitted, falling back to `true` with an explicit reason string when commands are not declared.
