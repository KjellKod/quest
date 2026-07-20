# Quest Diamond Efficiency Roadmap

Status: proposed umbrella roadmap
Refreshed: 2026-07-20
PR: [#135](https://github.com/KjellKod/quest/pull/135)

## Why This Roadmap Lives In Ideas

This document sequences future, independently reviewable efficiency work. It does
not describe an implementation currently in flight, so `ideas/` is its truthful
home. When a work package is selected, it gets its own Quest, implementation
plan, approval gates, and PR to current `main`.

The objective is to reduce unnecessary prompt, review, and iteration cost without
weakening correctness or review diversity. Measurement comes first: WP0 is the
only recommended next implementation slice.

## Ownership Boundaries

Diamond owns efficiency goals, current-state evidence for WP0-WP9, package
sequencing, benchmark comparison, and the measurement-first decision order. It
links to, but does not redefine, these canonical plans:

- [Policy canonicalization and enforcement](quest-policy-canonicalization-and-enforcement-roadmap.md)
  owns policy families and enforcement mechanics.
- [Instruction architecture](2026-04-13-instruction-architecture.md) owns
  selective loading, policy-pack structure, prompt assembly, and pointer-only
  role wiring.
- [CI review, allowlist, and quality maturity](2026-05-04-ci-review-allowlist-quality-roadmap.md)
  owns CI-review taxonomy, output honesty, prompt-pipeline structure, allowlist
  work, and CI lane separation.
- [Multi-phase execution](quest-multi-phase-execution.md) owns execution
  topology: one program roadmap, then one bounded Quest and PR per executable
  package.
- [Memory architecture](2026-04-13-quest-memory-architecture.md) owns reflective
  lesson persistence, record structure, retrieval, freshness, and privacy
  guardrails.
- [Memory evaluation loop](2026-04-13-quest-memory-evaluation-loop.md) owns the
  benchmark that proves whether retrieved memory is useful.

## Status Legend

- `done`: every retained outcome has merged implementation evidence; no
  execution prompt remains.
- `partial`: named outcomes shipped and named outcomes remain; both are stated
  with evidence or disposition.
- `proposed`: no retained outcome is implemented and the package may start once
  its dependencies hold.
- `blocked`: the package remains in scope but cannot start until named unblock
  conditions are satisfied.
- `superseded`: another named canonical roadmap owns the remaining work, so the
  package is not independently executable.

Each package has exactly one status in the audit table. Detail sections repeat
the package name, not the status, so the table remains the canonical status
record.

## Current-Main Audit

Evidence baseline: `origin/main` at `fb5ee46` (2026-07-20).

| Package | Status | Current-main evidence | Canonical owner | Dependencies or unblock conditions | Next action |
|---|---|---|---|---|---|
| WP0 telemetry and baseline | proposed | `QUEST_RUNNER_TELEMETRY_LOG` is an opt-in transport test seam; there is no per-quest `metrics.jsonl`, `scripts/quest_runtime/metrics.py`, or `tests/benchmark/` suite. | Diamond | None beyond a current clean `main`. | First executable slice: define the schema, capture three baselines, and stop before optimization. |
| WP1 contract unification | partial | Canonical findings and confidence-aware decisions shipped, while platform role files still repeat handoff and policy text. | Policy roadmap plus instruction architecture | Preserve existing findings compatibility; pointer work follows the instruction-architecture value gate. | Treat shipped contracts as foundations and plan remaining pointer/canonicalization work under the named owners. |
| WP2 selective workflow loading | proposed | `.skills/quest/delegation/workflow.md` is 1,535 lines and no phase-loading directory exists. | Instruction architecture | WP0 baseline plus proof that invocation-time context changes, not merely file layout. | Measure first, then propose selective phase/role loading under the runtime-value gate. |
| WP3 delta re-review and caps | proposed | There is no numbered review-checkpoint or review-delta artifact; iteration bounds remain warning-based. | Policy roadmap | WP0 measurement and an approved failure/escalation contract. | Specify bounded delta review and fail-safe escalation in a dedicated Quest. |
| WP4 reviewer signal and arbiter cost | partial | Confidence-aware routing sends uncertain findings to `verify_first` or `defer`; `.skills/review-anti-patterns.md` remains small and no measured arbiter-selection policy exists. | Diamond for measurement; CI roadmap for CI-facing signal | WP0 data before changing reviewer or arbiter defaults. | Measure signal/cost, then improve anti-pattern guidance or selection only when data supports it. |
| WP5 planning lessons | proposed | No bounded `planning_lessons` artifact or archived per-iteration lesson extraction exists. | Memory architecture plus memory evaluation loop; Diamond owns sequencing and efficiency measurement | WP0 measurement, an approved memory MVP, and an approved selective-loading architecture. | Sequence a measured planning-efficiency comparison after the canonical memory owners define and validate the lesson contract. |
| WP6 CI prompt consolidation | proposed | `.github/scripts/codex_review.py` still prepares both PR-head file context and bounded Deep CI context. | CI quality roadmap | Coordinate with CI quality Track 7 to avoid conflicting pipeline edits. | Measure duplicate context, then implement any consolidation in the canonical CI roadmap. |
| WP7 per-role model plumbing | done | PRs [#119](https://github.com/KjellKod/quest/pull/119), [#142](https://github.com/KjellKod/quest/pull/142), and [#144](https://github.com/KjellKod/quest/pull/144) shipped per-quest orchestration, exact model pass-through, JSON overrides, and explicit role defaults. | Shipped runtime contracts | None. | No execution prompt; preserve behavior through existing tests. |
| WP8 completion experience | partial | PR [#112](https://github.com/KjellKod/quest/pull/112) shipped persisted celebration artifacts and brief/journal links. The source proposal still records unresolved regeneration, provenance metadata, and ownership-list completion work. | [Persisted celebrations proposal](2026-04-17-persisted-celebrations-and-brief-in-cheers.md) | A separate decision on which unresolved outcomes still provide value. | Keep explicit commit, push, and PR approval gates; scope any remaining celebration work separately. |
| WP9 benchmark comparison | blocked | Comparable baseline/after rollups and pinned comparison commits do not exist. | Diamond | WP0 merged with three baselines; chosen optimization packages merged independently; frozen briefs and model matrix; both SHAs recorded. | Execute only after every unblock condition is satisfied. |

## Execution Topology

1. Start every executable package from current `main` in an isolated worktree.
2. Give it one bounded Quest, one implementation/review/fix lifecycle, and one
   independently reviewable PR.
3. Merge packages independently when their own evidence is sufficient.
4. Compare pinned baseline and later `main` commits using identical briefs and
   role assignments. No persistent integration branch is required.
5. Preserve explicit human approval before commits, pushes, and PR mutations.

## WP0: Telemetry And Baseline

### Outcome

Create the smallest trustworthy measurement layer for Quest efficiency without
changing orchestration decisions. Record per-role invocation, input/output token
counts when the runtime exposes them, elapsed time, retries, phase iterations,
runtime/model identity, and review-result counts. Produce one schema-valid
rollup for each of three representative briefs.

Existing transport telemetry must remain a test seam and must not be presented
as the new per-quest measurement contract.

### Acceptance Criteria

- A versioned per-quest metrics schema distinguishes observed values from
  unavailable values and records the source of every metric.
- Telemetry is best-effort: recording failure never changes prompts, retries,
  handoffs, or Quest outcome.
- Three pinned representative briefs produce schema-valid baseline rollups with
  the commit SHA and per-role model assignments.
- The journal reports a compact rollup without exposing prompt contents,
  secrets, or personally identifying data.
- Documentation explains known gaps and refuses invented token estimates.

### Automated Validation

- Unit-test schema validation, missing provider usage, partial runs, retries,
  and write failures.
- Assert telemetry failures leave role prompts, attempts, and handoffs unchanged.
- Validate exactly three baseline rollups with unique brief IDs, commit SHAs,
  and complete role-to-model maps.
- Recompute journal totals from the underlying invocation records.

### Manual Validation

Run the same three briefs from clean worktrees at the pinned commit. Compare
runtime logs, handoffs, and rollups; confirm unavailable provider data is labeled
unknown, secrets and prompt bodies are absent, and disabling telemetry produces
the same Quest result.

### Touchpoints

Runner result envelopes, Quest phase dispatch, journal generation, archive
retention, and source-only benchmark fixtures. Consumer installation ownership
must be decided explicitly before any new path is added to the manifest.

### Paste-Ready Quest Prompt

```text
$quest "Implement Diamond WP0: trustworthy Quest telemetry and three pinned
baseline rollups. Keep recording best-effort and behavior-neutral; never infer
missing token counts. Define a versioned schema, privacy boundaries, focused
tests, journal aggregation, and three representative baseline briefs. Do not
implement any optimization package. Validate installed-consumer ownership and
preserve all commit, push, and PR approval gates."
```

## WP1: Contract Unification

### Shipped Foundation

Canonical findings use a stable severity vocabulary and review intelligence
maps confidence to deterministic backlog decisions. Those contracts must remain
compatible.

### Remaining Outcome

Reduce duplicated role/policy text and make canonical ownership inspectable.
Implementation details belong to the policy and instruction-architecture
roadmaps; Diamond measures whether the resulting prompt surface is smaller and
equally effective.

### Acceptance Criteria

- Each affected rule family has one named canonical owner.
- Platform role files contain wiring and pointers, not competing normative text.
- Existing findings, handoff, and review-backlog schemas remain compatible.
- WP0 comparison data shows whether prompt size changed without losing findings.

### Automated Validation

Use canonical-ownership contract tests, platform parity tests, schema fixtures,
and WP0 rollup comparison. Avoid line-count-only success criteria.

### Manual Validation

Trace one plan and one code-review rule from each platform entrypoint to its
canonical source. Run a representative Quest and confirm handoffs and decisions
retain their current meaning.

### Dependencies And Touchpoints

Depends on WP0 and the instruction architecture's runtime-value gate. Touches
platform agent wrappers, role skills, findings schemas, and policy validators.

## WP2: Selective Workflow Loading

### Outcome

Load only the phase/role instruction material needed for a dispatch while
retaining a deterministic, inspectable composition order. Splitting a file
without changing invocation-time context does not satisfy this package.

### Acceptance Criteria

- An invocation manifest records selected instruction units and composition
  order for every role.
- Unrelated phase policy is absent from at least the agreed representative role
  prompts.
- Existing gate, resume, fallback, and handoff behavior remains intact.
- WP0 data compares token and iteration effects against the pinned baseline.

### Automated Validation

Contract-test the role-to-instruction matrix, deterministic assembly, missing
unit failures, and parity of existing orchestration fixtures. Validate rollup
deltas from the pinned commits.

### Manual Validation

Inspect prompt manifests for planner, builder, and code reviewer runs; verify
each includes its required policies and excludes unrelated phase material. Run
resume and fallback paths before accepting the change.

### Dependencies And Touchpoints

Depends on WP0 and approval of the canonical instruction architecture. Touches
prompt assembly, role dispatch, resume behavior, and all platform entrypoints.

## WP3: Delta Re-Review And Iteration Caps

### Outcome

Give review iterations an explicit checkpoint/delta contract and enforce bounded
loops without hiding unresolved findings or converting infrastructure failures
into approval.

### Acceptance Criteria

- Every re-review records the prior checkpoint and exact changed range or files.
- Full re-review remains available when the delta contract is missing or unsafe.
- Plan and fix iteration limits have deterministic stop/escalation behavior.
- No unresolved actionable finding disappears solely because a cap was reached.

### Automated Validation

Test checkpoint creation, delta selection, missing/stale checkpoint fallback,
cap boundaries, unresolved-finding preservation, and manual-escalation output.

### Manual Validation

Exercise a fix iteration with one changed file and one deliberately stale
checkpoint. Confirm the safe path expands review or stops with actionable
guidance and that the original findings remain visible.

### Dependencies And Touchpoints

Depends on WP0 and policy-roadmap ownership of enforcement. Touches review
artifacts, state validation, arbiter/fixer loops, and resume semantics.

## WP4: Reviewer Signal And Arbiter Cost

### Shipped Foundation

Confidence-aware routing already distinguishes actionable findings from those
that need verification or deferral.

### Remaining Outcome

Measure disagreement, false-positive disposition, and arbiter cost; then improve
review anti-pattern guidance or selection policy only where data demonstrates a
quality or efficiency gain. CI-facing signal remains owned by the CI roadmap.

### Acceptance Criteria

- Metrics distinguish reviewer agreement, arbiter disposition, verification,
  deferral, and dropped low-value findings.
- Any reviewer/arbiter default change is justified by pinned comparison data.
- Critical/high-finding recall is not worse than the baseline set.
- CI taxonomy and rendering stay governed by the CI quality roadmap.

### Automated Validation

Validate disposition rollups, reviewer-slot attribution, comparison math, and
unchanged CI taxonomy contracts. Fail closed on missing comparison inputs.

### Manual Validation

Review disagreements from all three baseline briefs and sample each disposition.
Confirm measurement labels match the underlying findings and that any proposed
policy change follows the observed evidence.

### Dependencies And Touchpoints

Blocked from changing defaults until WP0 data exists. Touches review
intelligence, anti-pattern guidance, arbiter dispatch, and CI review boundaries.

## WP5: Planning Lessons

### Outcome

Determine whether planning lessons provided by the canonical
[Memory architecture](2026-04-13-quest-memory-architecture.md) improve later
plans without increasing unnecessary context or iteration cost. The
[Memory evaluation loop](2026-04-13-quest-memory-evaluation-loop.md) owns the
usefulness benchmark. Those documents are the canonical owners of persistence,
record structure, retrieval, freshness/privacy guardrails, and memory-quality
evaluation. Diamond owns only package sequencing and efficiency measurement; it
does not define a second memory contract.

### Acceptance Criteria

- The approved memory architecture and evaluation contracts are linked as the
  sole normative sources for lesson records, retrieval, safety, and usefulness.
- The comparison uses pinned WP0 briefs, commits, role assignments, and memory
  evaluation cases so changes in plan quality and efficiency are attributable.
- WP0 rollups report context and iteration effects without duplicating or
  weakening the memory evaluation's quality scoring.
- If the combined evidence does not show a useful gain, no Diamond-specific
  lesson mechanism is introduced.

### Automated Validation

Run the canonical memory architecture and memory-evaluation suites, then compare
their pinned cases with the corresponding WP0 efficiency rollups. Assert that
both result sets identify the same commits, briefs, and role assignments; fail
closed when comparison inputs are missing.

### Manual Validation

Trace each selected lesson and quality score to the canonical memory artifacts,
then inspect the matching WP0 rollup. Record whether a concrete plan decision
improved and whether context, elapsed time, or review iterations changed; retain
neutral and negative results.

### Dependencies And Touchpoints

Depends on WP0, an approved memory MVP, the memory evaluation loop, and the
selected instruction-loading architecture. Diamond consumes their artifacts at
the benchmark boundary; memory storage, retrieval, planner integration, and
freshness/privacy policy remain owned by the canonical memory roadmaps.

## WP6: CI Prompt Consolidation

### Outcome

Remove demonstrably duplicated CI review context while preserving trusted-base
security, changed-line anchoring, oversized-file behavior, and honest omission
reporting. The CI roadmap owns the implementation contract.

### Acceptance Criteria

- A before/after manifest identifies each removed duplicate context source.
- Selected and omitted files retain stable, truthful reasons.
- Inline anchoring and changed-line validation remain correct.
- Prompt size falls without reducing critical/high findings on the pinned set.

### Automated Validation

Extend CI context-manifest, chunking, omission, range, malformed-output, and
security guard tests. Recompute prompt-size and finding deltas from pinned runs.

### Manual Validation

Inspect rendered context for small, oversized, deleted, excluded, and unavailable
files. Compare review results for the benchmark PRs and verify no PR-head content
is executed in a trusted context.

### Dependencies And Touchpoints

Sequence with CI quality Track 7 after WP0. Touches CI prompt preparation,
context manifests, review posting, and trusted/untrusted checkout boundaries.

## WP7: Per-Role Model Plumbing

Merged evidence: PRs [#119](https://github.com/KjellKod/quest/pull/119),
[#142](https://github.com/KjellKod/quest/pull/142), and
[#144](https://github.com/KjellKod/quest/pull/144), plus current
`.quest/<id>/orchestration.json` dispatch and orchestration tests. No remaining
Diamond implementation prompt exists.

## WP8: Completion Experience

### Shipped Foundation

PR [#112](https://github.com/KjellKod/quest/pull/112) persists celebration
artifacts and links briefs, journals, and celebrations.

### Remaining Outcome

The source proposal still contains unresolved regeneration/overwrite behavior,
origin and revision metadata, and ownership-list completion. These are not
implied requirements: a future Quest must first decide which outcomes still
provide enough value. Commit, push, and PR approval gates remain explicit.

### Acceptance Criteria

- Shipped and unshipped behaviors are documented separately with evidence.
- Any retained regeneration behavior preserves the context-rich original by
  default and presents changes before writing.
- Provenance metadata has one canonical schema and migration story.
- Source-only completion artifacts do not silently enter consumer ownership.

### Automated Validation

If work is approved, test no-overwrite defaults, origin/revision schema,
source-only ownership, archive lookup, and unchanged approval-gate contracts.

### Manual Validation

Generate an original celebration and attempt a cold regeneration with and
without changed PR context. Confirm the original is protected, the proposed
revision is visible before writing, and all external mutations still pause for
approval.

### Dependencies And Touchpoints

Depends on a separate scope/value decision. Touches celebration persistence,
Quest completion, journal links, archive lookup, and source/consumer ownership.

## WP9: Benchmark Comparison

### Unblock Conditions

- WP0 is merged with three schema-valid baseline rollups and a recorded baseline
  commit.
- Selected optimization packages are merged independently to `main`.
- The three brief identities and per-role model assignments are frozen.
- Both comparison commit SHAs are recorded.

### Acceptance Criteria

- The report presents every WP0 metric per brief for pinned before/after commits.
- It records brief/model parity and both SHAs.
- It evaluates the stated token-reduction target and reports misses honestly.
- The after run misses no baseline `critical` or `high` finding.
- A missed efficiency target is a valid measured outcome with an explanation.

### Automated Validation

- Validate baseline and after rollup schemas and required metric keys.
- Assert exactly three matching brief IDs and matching role-to-model assignments.
- Recompute report deltas from checked-in rollups.
- Fail when recorded SHAs or inputs do not match the report.

### Manual Validation

On clean worktrees at the two pinned commits, run the same three briefs with the
frozen model matrix. Inspect anomalous token/iteration deltas and finding-quality
differences. Verify the report links each result to its input rollup and commit,
and record environmental deviations rather than normalizing them silently.

### Touchpoints

WP0 rollups, benchmark briefs, Git commit identity, model assignments, review
findings, and the final comparison report.

## Integration Touchpoints

| Touchpoint | Risk | Required validation |
|---|---|---|
| Runtime result envelopes and role dispatch | Measurement could alter role behavior | Best-effort failure tests and prompt/handoff parity |
| Prompt and instruction assembly | Structural cleanup may not reduce active context | Invocation manifests plus WP0 comparison |
| Review schemas and state transitions | Efficiency changes could hide findings or bypass gates | Schema compatibility, cap-boundary, and unresolved-finding tests |
| CI trusted/untrusted boundaries | Context reduction could weaken security | Existing security guard and context-manifest tests |
| Source/consumer ownership | Source-only telemetry or planning assets could leak into installs | Strict manifest validation and installed-consumer fixture |
| Cross-package sequencing | Concurrent work could invalidate the baseline | Pinned SHAs, independent PRs, and WP9 parity checks |

## Top Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Optimizing before trustworthy measurement | WP0 is the sole recommended next slice; later default changes depend on pinned data. |
| Token reduction hides important context | Preserve critical/high baseline findings and validate role-specific inclusion manifests. |
| Roadmaps become competing policy sources | Keep normative rules in the four named canonical plans and use reciprocal links. |
| Telemetry changes behavior or leaks data | Make recording best-effort, test failure neutrality, and prohibit prompt/secret capture. |
| Long programs blur review and approval | Use one bounded Quest and PR per executable package from current `main`. |
| Baselines drift across models or revisions | Pin brief IDs, role assignments, and commit SHAs; fail comparison on mismatch. |

## Stop Conditions

Stop and return to planning when measurement cannot distinguish unavailable data
from zero, a proposed optimization changes approval or security boundaries, a
package requires another canonical roadmap to change concurrently, or benchmark
brief/model/commit parity cannot be established.

## Historical Provenance

Earlier model-capability exploration is archived at
[2026-05-31-quest-model-capability-improvements.md](archive/2026-05-31-quest-model-capability-improvements.md).
It is historical evidence, not the current implementation source.
