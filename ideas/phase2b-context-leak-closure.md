# Idea: Phase 2b - Context Leak Closure Findings

## Scope

This document captures the latest Phase 2b findings after candid review and arbitration, then defines the minimal next step that gives real improvement without adding architecture complexity.

Related docs:
- `ideas/quest-architecture-evolution.md` (roadmap)
- `ideas/quest-context-optimization.md` (original Phase 2b proposal)

## Executive Verdict

Phase 2b is the highest-value remaining architecture step.

- Do not start a new orchestration layer yet.
- Do not spend time on cosmetic restructuring first.
- Complete Phase 2b with measurable guardrails and rehearsals.

Reason: this is the only remaining step that directly improves the stated goals (laser-focused orchestration, low context pollution, KISS).

## Current Status (Candid)

### What already shipped (5/7)

| Item | Status |
|------|--------|
| `handoff.json` contract (agents write, orchestrator reads) | Done |
| Context retention rule (status/path/summary only) | Done |
| No full review reads for routing decisions | Done |
| Post-quest `/clear` suggestion | Done |
| Context health logging + compliance report pattern | Done |

### What is not done (2/7)

| Item | Status | Why it matters |
|------|--------|----------------|
| Background invocation for all Claude Task agents | Not done | Without this, full response bodies can still enter orchestrator context depending on runtime behavior |
| Background-safe Codex review path (or equivalent isolation) | Not done | Synchronous Codex response bodies can still add context pressure |

## Core Findings

1. The design pattern is mostly correct already.
- The contract and routing rules are in place.
- The gap is runtime isolation behavior, not missing architecture concepts.

2. "Do nothing" is only acceptable if context pollution is now an accepted tradeoff.
- If laser-focus and bounded context are non-negotiable, doing nothing is misaligned.

3. A remote orchestrator shim is premature.
- It may become useful later, but right now it adds glue and moving parts before the current contract is fully validated.

4. The right next step is a narrow, measurable completion pass.
- Keep the current architecture.
- Tighten behavior and validation.
- Defer optional enhancements.

## Options Assessed (Pros/Cons)

### Option 1: Do nothing

Pros:
- No engineering effort.
- No migration risk.

Cons:
- Context leakage remains.
- Thin-orchestrator claim stays partially unproven at runtime.

Verdict:
- Only choose if this problem is no longer important.

### Option 2: Complete Phase 2b (recommended)

Pros:
- Directly addresses remaining context leak behavior.
- Preserves current architecture (KISS).
- Portable contract for both local and cloud-style orchestrators.

Cons:
- Requires prompt/contract tightening and validation harness work.
- Background behavior may be platform-sensitive and needs explicit rehearsal.

Verdict:
- Best improvement-per-complexity ratio.

### Option 3: Add remote orchestrator shim now

Pros:
- Stronger long-term separation possibility.

Cons:
- More components and operational overhead now.
- Solves future concerns before finishing current runtime validation.

Verdict:
- Defer until after Phase 2b completion proves insufficient.

## Compatibility Findings

### Codex as orchestrator (local flow)

- Fully compatible with the Phase 2b contract.
- Polling `handoff.json` and appending `context_health.log` fits current file-based quest flow.

### Cloud or service orchestrator

- Also compatible if the same minimal handoff schema is preserved.
- Requires a shared URI/storage contract and polling semantics.
- No major redesign needed if contract discipline stays strict.

## Concrete Next Step (Implementation)

1. Enforce handoff polling guardrails in orchestrator flow.
- Poll window: 30 seconds total.
- Poll interval: 5 seconds.
- On missing/malformed JSON: mark `unparsable`, attempt legacy `---HANDOFF---` fallback, then fail clearly.

2. Enforce contract output from all participating agents.
- Every role writes `handoff.json` with: `status`, `artifacts`, `next`, `summary`.
- Every role still emits text `---HANDOFF---` for fallback compatibility.

3. Add explicit context leakage assertion.
- Add harness test(s) to fail when post-handoff context exceeds threshold.
- Threshold: 9000 tokens max after each handoff event.

4. Rehearse cloud-compatible contract locally.
- Validate shared-path or metadata endpoint polling behavior.
- Confirm same handoff schema works without local-only assumptions.

5. Run deliberate failure rehearsal.
- Omit/corrupt one handoff file.
- Verify fallback and operator-visible failure path are deterministic.

## Validation Requirements

- Automated:
  - Add a handoff context harness (for example `scripts/tests/test_handoff_context.py`).
  - Must fail on missing handoff, missing fallback behavior, or token cap violations.

- Manual:
  - Failure/fallback drill (missing or malformed handoff).
  - Cloud-contract rehearsal against shared path or mock metadata endpoint.

- Exit criteria:
  - Full run completes with handoff-only routing.
  - Context-health entries are complete and coherent.
  - Failure case is explicit and recoverable by design (fallback then hard fail).

## Empirical Signals from Latest Review Run

From the latest Phase 2b review cycle:
- `context_health.log` recorded 12/12 `handoff_json=found` events across planner, reviewers, and arbiter iterations.
- Parallel review dispatch records showed concurrent reviewer launches across all plan iterations.
- Arbiter approved on iteration 3 after adding concrete runtime guardrails (timeout and token cap).

Interpretation:
- The contract discipline is working.
- Remaining work is implementation hardening, not conceptual redesign.

## Non-Blocking Follow-Ups (Defer)

- Whether to rotate/delete historical handoff files per iteration.
- Whether to auto-generate a richer compliance summary report from `context_health.log`.
- Whether to provide helper tooling for older quests that predate `handoff.json`.

These are useful, but none are blockers for Phase 2b completion.

## Decision

Proceed with Option 2 now.

- Keep architecture simple.
- Complete runtime isolation checks.
- Validate with hard thresholds and rehearsals.
- Reassess only after those measurements are in place.
