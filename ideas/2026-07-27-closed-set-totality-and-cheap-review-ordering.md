---
title: Closed-Set Totality Review Dimension and Cheap-Review Ordering
purpose: Close two structural review-coverage gaps exposed when a single cheap automated pass found six real defects after a full Quest pipeline returned clean.
audience: Quest maintainers
scope: AGENTS.md coding principles, code-reviewer skill review dimensions, and the interaction between Quest's draft-PR policy and draft-gated automated reviewers
status: proposed
owner: maintainers
date: 2026-07-27
---

# Closed-Set Totality and Cheap-Review Ordering

Two independent gaps, found by the same incident. Both are generic; neither is
specific to the repo that surfaced them.

## Evidence

A full-workflow Quest (`ui_work: true`, high risk) ran to completion:

- 2 plan iterations, dual plan review, arbiter — approved
- build, then 3 code-review rounds with dual reviewers and a review-arbiter
- 2 fix iterations
- final round: **both reviewers returned `[]`**, zero findings

The PR was marked ready. A draft-gated CI reviewer then fired for the first
time and posted **7 findings, 6 of them real and confirmed against source**.
Two were user-facing falsehoods in a payments surface. All six were fixed with
regression tests written failing-first.

Roughly ten agent invocations across two model families had passed the same
code clean. This was not a model-quality problem.

## Gap 1 — No review dimension covers totality over closed sets

Every one of the six real defects had the same shape:

| Defect | Closed set that was not enumerated |
|---|---|
| `else` branch asserted a specific cause | the reason-code enum |
| Fields rendered regardless of state | the state enum |
| `a ?? b ?? c` precedence chain | the set of concurrent error sources |
| Stale cached value outranked fresh authoritative one | `{cached, fresh} × {ok, error}` |
| Edit-during-pending re-enabled submit | the mutation lifecycle states |
| Latched boolean never cleared | the set of exit transitions |

The existing dimensions — correctness, security, contract fidelity, test
quality — are all satisfiable while every one of these ships. Reviewers were
asked to verify *each change*; nobody was asked to enumerate *the input space*.

### The principle

> When code branches on a **closed set** — an enum, a discriminated union, a
> fixed error-code list, a lifecycle's states — handle every member explicitly.
> A catch-all `else` may not assert a **specific** fact about the members it
> silently absorbs.

The dangerous pattern is not the catch-all itself; it is a catch-all that makes
a positive claim. `else → "unknown error, retry"` is honest. `else → "you hit
the evaluation limit"` is a lie for every member the author did not think of.

Half of this is compiler-enforceable. An exhaustive `Record<Enum, T>` or a
match with no default fails to build when a member is added; an `if/else` does
not. Prefer the construct that breaks loudly.

### Proposed change — `AGENTS.md`

Add one bullet under Core Principles, adjacent to **Strong typing**:

> - **Totality over closed sets** — When branching on a closed set (enum,
>   discriminated union, fixed error-code list, lifecycle states), handle every
>   member explicitly. Prefer an exhaustive map or match so the compiler catches
>   a newly added member. A catch-all must not assert a specific fact about the
>   members it absorbs; if you cannot enumerate them, say "unknown", not
>   something concrete.

### Proposed change — `.skills/code-reviewer/SKILL.md`

Add a review dimension:

> **Totality.** Locate every branch over a closed set in the diff — enum
> switches, error-code maps, status handling, state machines, `??`/`||`
> precedence chains over multiple sources. For each one: is every member
> handled, and does any catch-all assert something specific about members it did
> not enumerate? Name the unenumerated members. Also check the inverse: a value
> the backend retains for a reason (restoration, audit, continuity) needs an
> explicit per-state decision about whether it is *presented*, not just whether
> it is *stored*.

The last sentence catches the class where nothing branches at all — a field
rendered unconditionally because the decision was recorded as a storage fact and
never as a presentation rule.

## Gap 2 — Quest's draft policy hides cheap reviewers behind expensive ones

`pr-assistant` mandates `--draft` for every PR it creates. Draft-gated CI
reviewers — a common configuration, e.g.:

```yaml
on:
  pull_request:
    types: [ready_for_review, synchronize]
jobs:
  review:
    if: github.event.pull_request.draft == false
```

therefore **cannot run until the Quest pipeline has already concluded and
declared the work done**. The cheapest, highest-yield reviewer is structurally
guaranteed to arrive last. In the incident above it cost one CI job and found
six real bugs that ~10 agent invocations had missed.

This is an ordering bug created by the interaction of two individually
reasonable policies. It reproduces in any repo that pairs Quest's draft-always
PR creation with a draft-gated reviewer.

### The principle

> Cheap automated review must run **before** the expensive gates conclude, so
> its findings become inputs to the fix loop rather than post-hoc surprises
> arriving after the pipeline reports success.

### Proposed changes

Either is sufficient; the first is preferred.

1. **Un-gate the reviewer from draft status** in the consuming repo — drop the
   `draft == false` condition and add `opened` to the trigger types. A
   `concurrency` group with `cancel-in-progress: true` keeps rapid draft pushes
   collapsed to one run. Cost: the reviewer comments during active development,
   which some maintainers will find noisy.
2. **Make `pr-shepherd` responsible for the ordering** — after marking ready,
   explicitly wait for automated review to land, ingest it through the existing
   Step 4 intake, run the fix loop, and only then treat the PR as ready. This
   keeps drafts quiet but means "ready for review" is briefly untrue.

Option 1 is the ordering fix; option 2 is a workaround that preserves current
draft ergonomics. If Quest wants a framework-level answer rather than a
per-repo one, `pr-assistant` could document the draft-gating interaction as a
known hazard and `quest_preflight.sh` could warn when it detects a draft-gated
reviewer workflow in the consuming repo.

## Why this is worth doing

The failure mode is not "the pipeline is weak". It is that pipeline depth
produces confidence that outruns coverage. Ten agents agreeing is weak evidence
when they were all pointed at the same questions — model diversity does not
help when the prompts share a blind spot. A named review dimension is a
structural fix; a cheap reviewer running early is a cheap independent sample.

## Follow-ups

- Audit the existing code-reviewer dimensions for other whole classes that no
  dimension names.
- Consider whether the plan-reviewer needs the same totality question at plan
  time. In the incident, both defects that reached users were decidable from the
  plan alone: the plan specified a binary branch over a non-binary enum, and it
  recorded a preserved-field contract without a render rule.
