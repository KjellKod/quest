---
title: Instruction Architecture -- Selective Loading, Policy Ownership, and Workflow-First Skills
purpose: Unified proposal for Quest instruction architecture at the prompt-loading and workflow-structure layer
audience: Quest maintainers
status: proposed
date: 2026-04-13
supersedes:
  - .ws/2026-04-13-focused-rule-packs.md
  - .ws/2026-04-13-orchestration-improvement-workflow.md
related:
  - ideas/quest-policy-canonicalization-and-enforcement-roadmap.md
  - docs/implementation/backlog/quest-diamond-efficiency-roadmap.md
  - .skills/quest/delegation/workflow.md
  - .skills/quest/SKILL.md
  - .skills/code-reviewer/SKILL.md
  - .skills/plan-reviewer/SKILL.md
---

# Instruction Architecture
This proposal merges two overlapping idea notes into one coherent direction.
The scope is documentation and architecture guidance only.
No runtime wiring, script creation, or `.skills/` edits are part of this proposal.

The central design objective is to improve runtime instruction relevance and inspectability without introducing policy fragmentation.

## Relationship To Diamond

This proposal is the canonical owner for Diamond WP1/WP2 implementation details:
selective invocation-time loading, the policy-pack structure, deterministic
prompt assembly, and pointer-only role/policy wiring. The
[Diamond efficiency roadmap](../docs/implementation/backlog/quest-diamond-efficiency-roadmap.md) owns sequencing
and measurement. A file split alone does not satisfy either roadmap; runtime
prompt inclusion must change observably and be compared against the WP0 baseline.

## Preservation Rules

1.
   > **Preservation Rule 1 -- Runtime-gated value.** This proposal only has meaningful value if runtime prompt loading actually changes. File reshuffling without selective loading at invocation time is low-impact cleanup, not the point.

2.
   > **Preservation Rule 2 -- No pack explosion.** Keep the pack count small (target 5-6 core packs). Reject micro-packs.

3.
   > **Preservation Rule 3 -- Role wiring separate from policy packs.** `.skills/quest/agents/*.md` stay as role wiring files; they reference packs but do not duplicate normative policy.

4.
   > **Preservation Rule 4 -- Workflows as executable recipes.** `## Workflows` sections are short, numbered, and each recipe has an explicit entry condition and exit condition/artifact. Not prose; not full reference material.

5.
   > **Preservation Rule 5 -- One coherent proposal beats two overlapping ones.** This consolidation itself demonstrates the rule -- prefer one medium-value coherent proposal over two overlapping doc-shape ideas.

## 1. Selective Rule-Pack Loading

### Problem statement

Quest already has substantial instruction coverage across `AGENTS.md`, `.ai/quest.md`, `.skills/quest/SKILL.md`, `.skills/quest/delegation/workflow.md`, agent role files, and reusable role skills.
The problem is not missing policy.
The problem is broad prompt surfaces that mix unrelated concerns by default.

Today, role prompts can include policy that belongs to different phases or responsibilities:
routing logic in role contexts that do not route,
review-loop constraints in planning contexts,
runtime dispatch assumptions in roles that should not reason about transport.

This introduces predictable costs:

1. More irrelevant context in the active prompt bundle.
2. Higher risk of instruction collision across unrelated policy families.
3. Harder debugging because inclusion logic is implicit.
4. Increased maintenance overhead when one policy family changes.

### Design constraints

Selective loading should be implemented under explicit constraints:

1. Value must be runtime-observable, not just structural.
2. Pack count must stay small and medium-grained.
3. Policy-family ownership must remain explicit.
4. Role wiring and policy storage must remain separated.
5. Composition order must be deterministic and inspectable.
6. Migration must be incremental with rollback points.

### Proposed pack set

The v1 architecture uses six packs:

1. `quest-overview`
2. `routing-rules`
3. `artifact-contract-rules`
4. `plan-phase-rules`
5. `review-phase-rules`
6. `bridge-runtime-rules`

No additional micro-packs in v1.
No standalone evaluation pack in v1.

### Pack responsibilities

#### `quest-overview`

Purpose:
always-on Quest identity and invariants.

Includes:
high-level phase sequence,
gate philosophy,
cross-phase invariant rules.

Excludes:
role-specific behavior details,
runtime transport policy.

#### `routing-rules`

Purpose:
startup and route-classification behavior.

Includes:
questioner gate behavior,
mode routing criteria,
risk/complexity/confidence routing boundaries.

Excludes:
plan-loop policy,
review severity policy.

#### `artifact-contract-rules`

Purpose:
artifact and handoff contracts.

Includes:
path and naming conventions in `.quest/<id>/...`,
required artifact fields and contract expectations,
ownership and retention expectations for artifacts.

Excludes:
role judgment policy,
review severity decisions.

#### `plan-phase-rules`

Purpose:
planning and plan-review loop behavior.

Includes:
planner constraints,
plan-reviewer expectations,
arbiter anti-spin and iteration policy for plan phase.

Excludes:
code review and fix-loop policy.

#### `review-phase-rules`

Purpose:
code-review and fix-loop behavior.

Includes:
review severity model,
scope boundaries for findings,
fixer boundaries and stop conditions.

Excludes:
routing startup behavior,
plan-loop arbitration policy.

#### `bridge-runtime-rules`

Purpose:
runtime dispatch and fallback assumptions.

Includes:
preflight expectations,
fallback and timeout behavior assumptions,
host-visible runtime context expectations.

Excludes:
phase-specific role guidance unless needed for a runtime-dependent role contract.

### Role-to-pack matrix (illustrative)

| Role/Path | quest-overview | routing-rules | artifact-contract-rules | plan-phase-rules | review-phase-rules | bridge-runtime-rules |
|---|---:|---:|---:|---:|---:|---:|
| Router | Y | Y | Y | N | N | Y |
| Planner | Y | N | Y | Y | N | N |
| Plan Reviewer | Y | N | Y | Y | N | N |
| Arbiter (plan path) | Y | N | Y | Y | N | N |
| Builder | Y | N | Y | N | N | N |
| Code Reviewer | Y | N | Y | N | Y | N |
| Fixer | Y | N | Y | N | Y | N |
| Orchestrator runtime | Y | Y | Y | phase-dependent | phase-dependent | Y |

### What this section is not proposing

1. No broad redesign of Quest orchestration in one pass.
2. No claim that token reduction alone is architectural value.
3. No policy duplication across packs and role files.
4. No expansion to many tiny packs.

> Runtime-value gate (Preservation Rule 1): this section is worthwhile only if runtime role/phase loading changes materially. If runtime loading does not change, stop at documentation cleanup and do not frame it as an architecture improvement.

## 2. Canonical Ownership of Policy Families

Selective loading only works when policy ownership is unambiguous.
If ownership remains fuzzy, pack extraction can create duplicate normative sources.

### Ownership table (migration map)

| Current file | Policy family today | New pack target | Action |
|---|---|---|---|
| `AGENTS.md` | repo-wide engineering rules | none | keep canonical; packs reference it where needed |
| `.ai/quest.md` | high-level Quest usage and artifact layout | `quest-overview` | move Quest-specific operating summary; keep user-facing quick reference in `.ai/quest.md` |
| `.skills/quest/SKILL.md` | routing/startup behavior | `routing-rules` | move normative routing rules; leave command UX and step order here |
| `.skills/quest/delegation/workflow.md` | artifact rules, runtime dispatch, phase behavior | `artifact-contract-rules`, `bridge-runtime-rules`, `plan-phase-rules`, `review-phase-rules` | split normative policy into packs; keep workflow sequencing here |
| `.skills/quest/agents/planner.md` | planner-specific wiring | `plan-phase-rules` reference only | keep file as role wiring; do not duplicate plan policy here |
| `.skills/quest/agents/plan-reviewer.md` | reviewer wiring | `plan-phase-rules` reference only | keep file as role wiring |
| `.skills/quest/agents/arbiter.md` | arbiter rules | `plan-phase-rules` reference only | keep file as role wiring |
| `.skills/quest/agents/code-reviewer.md` | code review wiring | `review-phase-rules` reference only | keep file as role wiring |
| `.skills/quest/agents/fixer.md` | fixer wiring | `review-phase-rules` reference only | keep file as role wiring |

### Conflict rule

When a rule appears in both a new pack and a legacy file:
the pack becomes authoritative after migration,
and the legacy location is reduced to a pointer or removed.

Do not keep dual normative ownership.
Pointer mirrors are acceptable.
Parallel normative text is not.

### Role wiring boundary

Role files remain role wiring, not policy warehouses.
They should describe role inputs, outputs, and handoff contracts.
They should reference packs for normative policy.
This is required for Preservation Rule 3 and keeps behavior edits localized.

### Explicit relationship to the enforcement roadmap

`ideas/quest-policy-canonicalization-and-enforcement-roadmap.md` is complementary and remains separate.
This proposal addresses prompt-loading structure and workflow document shape.
That roadmap addresses enforcement mechanics, canonicalization safeguards, and CI-level hardening.

In short:
this document defines how policy should be loaded and consumed by roles,
the roadmap defines how policy conformance is enforced and audited.

This proposal does not absorb roadmap content.

## 3. Workflow-First Skill Structure

### Structural split

For skills with multiple operations, separate:

1. `## Usage`
reference and capability information.

2. `## Workflows`
short, named, numbered execution recipes.

This prevents execution logic from being buried in descriptive prose.

### Why this matters

Numbered recipes under explicit workflow headings are interpreted as execution instructions.
Equivalent prose is interpreted as context.
The change is structural, but it improves execution consistency with low risk.

### Required traits of a workflow recipe

Each workflow recipe should include all three traits:

1. Entry condition:
when this workflow is selected.

2. Sibling cross-reference:
which artifact/role/sibling recipe it depends on.

3. Exit condition/artifact:
what must be produced or what state must be reached to complete the workflow.

These traits make workflows executable and auditable.

### Naming conventions

1. Use explicit names such as:
`Plan-then-build workflow (default)`,
`Solo workflow`,
`Draft-to-ready workflow`.

2. Use role labels (`planner`, `plan-reviewer-a`, `arbiter`) instead of runtime/model names.

3. Use full Quest artifact path patterns in steps:
`.quest/<id>/phase_XX_.../artifact.md`.

4. Keep each step concise:
one action + one output expectation when possible.

### Quest adoption examples

#### Plan-then-build workflow (default)

1. Router writes quest brief.
2. Planner writes plan.
3. Plan reviewers write parallel reviews.
4. Arbiter writes plan verdict.
5. Replan loop occurs if verdict routes back to planner.
6. Build phase starts when verdict routes to builder.
7. Builder writes implementation artifacts.
8. Code reviewers write review artifacts.
9. Arbiter/fixer loop runs until review exit state is satisfied.

#### Solo workflow

1. Router marks solo mode in quest brief.
2. Single reviewer path is used for planning.
3. Single reviewer path is used for code review.
4. Artifact contracts and explicit exit states remain unchanged.

### Risks and mitigations

Risk: recipe calcification.
Mitigation:
treat workflow blocks as contracts; pipeline behavior changes require workflow updates.

Risk: over-specification replacing needed judgment.
Mitigation:
keep workflow recipes focused on sequence and state transitions; keep judgment detail in role docs.

Risk: duplication with deep reference docs.
Mitigation:
use workflow section as an index recipe; keep detailed rationale in reference documents with links.

### Preservation mapping

This section directly enforces Preservation Rule 4.
A workflow recipe missing entry condition, sibling cross-reference, or exit condition/artifact is incomplete.

## 4. Prompt Assembly / Debugging Model

### Assembly goal

Prompt assembly should be explicit, role-aware, phase-aware, and inspectable.
Given role and phase inputs, assembly should resolve a stable context bundle with clear inclusion and exclusion reasoning.

### Inspectable bundle model

Each assembled bundle should capture:

1. role and phase identifiers,
2. ordered included packs/files,
3. intentionally excluded packs/files with reasons,
4. ownership family hints for included policy,
5. effective runtime context metadata.

This enables targeted debugging and comparison across runs.

### Explain mode expectations

An explain/debug view should answer:

1. What was loaded, in what order?
2. What was intentionally excluded, and why?
3. Which policy family owns each included normative rule set?
4. Is bundle composition deterministic for the same role/phase input?
5. What changed between two bundle snapshots?

### How this improves operations

1. Prompt bug diagnosis becomes traceable to specific included sources.
2. Role behavior becomes more deterministic due to explicit context boundaries.
3. Pipeline audits become feasible via bundle-level review.
4. Policy drift can be detected earlier by comparing expected vs actual bundles.

### Separation enforcement during assembly

Bundle composition should preserve the boundary between:
role wiring inputs and policy-pack content.

If migrated policy appears in role wiring files, explain output should expose that drift.
This helps maintain Preservation Rule 3 over time.

### Example bundle sketches (illustrative)

Planner bundle:
`quest-overview` + `artifact-contract-rules` + `plan-phase-rules` + planner reusable skill + planner wiring file.

Code reviewer bundle:
`quest-overview` + `artifact-contract-rules` + `review-phase-rules` + code-reviewer reusable skill + reviewer wiring file.

Orchestrator runtime bundle:
`quest-overview` + `routing-rules` + `artifact-contract-rules` + `bridge-runtime-rules` + workflow reference context.

## 5. Migration Plan

Rollout should be incremental and stoppable.
Each step should provide local value and include an explicit runtime-value checkpoint against Preservation Rule 1.

### Step A -- Extract packs without behavior change

Action:
define the six packs and relocate normative policy families to those pack documents.

Local value:
clear ownership boundaries and reduced policy ambiguity before runtime wiring.

Checkpoint:
Preservation Rule 1 gate:
confirm this step is enabling eventual runtime selective loading, not ending as static file reshuffling.

Stop rule:
if ownership clarity does not improve, pause before further work.

### Step B -- Add `## Workflows` sections (pilot `pr-shepherd`, then `quest`)

Action:
adopt the Usage/Workflows split where multi-step procedures exist.

Local value:
more executable sequence guidance and clearer onboarding for operators and agents.

Checkpoint:
Preservation Rule 1 gate:
confirm workflow structure is improving execution shape and remaining aligned with runtime-loading goals.

Stop rule:
if workflow sections increase confusion or duplication, tighten conventions before proceeding.

### Step C -- Add entry/exit condition blocks to reviewer skills

Action:
introduce explicit entry conditions and exit artifact/state declarations in reviewer-related skill workflows.

Local value:
clear invocation boundaries and completion criteria for review paths.

Checkpoint:
Preservation Rule 1 gate:
verify this clarity contributes to executable behavior contracts that runtime prompt assembly can use.

Stop rule:
if review behavior remains ambiguous, fix recipe quality before moving forward.

### Step D -- Add prompt context assembler concept

Action:
define the role/phase-to-pack resolution model and inspectable explain output shape.

Local value:
concrete observability for prompt composition decisions.

Checkpoint:
Preservation Rule 1 gate:
show that role/phase resolution can drive real runtime selection decisions, not only static reporting.

Stop rule:
if include/exclude reasoning is not reliable, do not wire runtime behavior yet.

### Step E -- Wire pack-aware prompt assembly

Action:
build role prompts from role/phase pack matrix plus role wiring and reusable skills.

Local value:
actual reduction of irrelevant role context and better policy targeting by phase.

Checkpoint:
Preservation Rule 1 gate:
require demonstrable runtime loading differences by role/phase before calling this successful.

Stop rule:
if behavior does not improve or reliability degrades, halt and revert to previous assembly path.

### Step F -- Add tests for role-specific pack loading

Action:
add tests for include/exclude expectations and deterministic order by role/phase.

Local value:
guards against drift and accidental context broadening.

Checkpoint:
Preservation Rule 1 gate:
tests must validate runtime loading behavior, not static document presence.

Stop rule:
if tests cannot express stable contracts, simplify pack mapping before expansion.

### Rollout controls

1. Keep six packs as the default ceiling in v1.
2. Maintain rollback points after each migration step.
3. Avoid bundling ownership normalization and runtime wiring in one high-risk change.

### Completion criteria for this proposal track

1. Role prompt assembly is explicit and inspectable by role/phase.
2. Policy-family ownership has one canonical source with pointer-only mirrors.
3. Workflow recipes are short, executable, and auditable.
4. Prompt assembly/debugging can explain inclusion and exclusion decisions.
5. Runtime value is evidenced, not inferred from document restructuring.

### Explicit non-goals

1. No direct implementation of enforcement validators here.
2. No CI gate rollout details here.

Those remain in the separate policy-canonicalization and enforcement roadmap.
