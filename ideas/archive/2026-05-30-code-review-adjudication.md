---
title: Code-Review Adjudication — enforce per-slot findings, then add a code-review arbiter
purpose: Close two linked gaps in the code-review phase — silently-repairable findings JSON, and the absence of an LLM adjudicator — so A-vs-B findings are guaranteed present and then judged for truth, instead of leaning on the orchestrator/human.
audience: Quest maintainers
scope: .skills/quest workflow Step 5, agent contracts, review-intelligence scripts, orchestration model config
status: shipped
owner: kjell
---

# Code-Review Adjudication

> **Shipped in PR #124.** This idea is implemented; archived for history.

## Two linked gaps

The code-review phase (`workflow.md` Step 5, ~773–987) has two weaknesses that
compound each other:

1. **Findings JSON is not enforced.** Reviewers are *asked* in the prompt to
   write `review_findings_<slot>.json`, but nothing fails if a reviewer skips or
   malforms it. In a real run, Codex wrote prose but no findings JSON, and the
   orchestrator **hand-authored** the file so `merge-findings` had something to
   consume. `validate-findings` only runs on the *merged* file (line 966) —
   after the merge has already absorbed whatever each slot did or didn't write.
2. **No adjudicator.** `merge-findings` + `build-backlog` are deterministic
   Python: they union/dedupe and classify by severity/confidence. **Nothing
   judges whether a finding is true.** When Reviewer A returned "clean" (0) and
   Reviewer B raised 4, a human confirmed B's findings were real before routing
   to the fixer.

These are sequenced, not independent: **an arbiter that judges hand-authored or
missing findings is garbage-in.** Part 1 must land before (or with) Part 2.

We have already moved this direction — `handoff.json` is enforced fail-closed
via the three-tier ladder (Handoff File Polling §6), `validate-findings` exists,
and the plan arbiter writes `[]` rather than skipping when clean. The work is
*extending an established pattern to one more artifact*, then *reusing the plan
arbiter shape in the build phase*.

## What's already decided

1. **Separate arbiter role — the fixer must NOT be the arbiter.** An arbiter's
   value is being a *disinterested judge*. Letting the actor (fixer) decide
   whether its own work is needed reintroduces the blind spot and biases toward
   dismissing findings to avoid work. Mirrors why the planner is not the plan
   arbiter.
2. **The arbiter does NOT call the fixer.** Agents don't invoke agents — the
   **orchestrator owns control flow**. A "role that calls the fixer" is rejected;
   it breaks the thin-orchestrator principle.
3. **Keep context windows small.** Both the enforcement and the arbiter consume
   structured findings JSON, not full reviewer markdown transcripts.

---

## Part 1 — Enforce per-slot canonical findings JSON (fail closed) · PREREQUISITE

Make the findings JSON a **hard contract like `handoff.json`**, validated
per-slot the moment a reviewer returns — not silently repaired at merge time.

### Sharper than "validate when next == fixer"
The orchestrator's instinct was: *if `handoff.next == "fixer"` but the findings
file is missing/unparsable, treat as non-compliant.* Stronger and simpler:
**the findings JSON is ALWAYS required.** A clean review writes `[]`, exactly as
the plan arbiter already does (`arbiter.md` line 40). Then validation is
unconditional and there is no "missing because clean vs. missing because
skipped" ambiguity to disambiguate against `next`.

### Changes

**`.skills/quest/agents/code-reviewer.md`**
- Promote the findings JSON from a responsibility (line 44) to a **required
  output in the Output Contract** (alongside handoff.json, lines 64–100).
- State explicitly: write `[]` when there are no findings; never omit the file.

**`workflow.md` Step 5, after each reviewer returns (extend §4 / Handoff File
Polling §6)**
- After reading a slot's `handoff.json`, immediately run
  `validate-findings --input review_findings_code-reviewer-<slot>.json` on **that
  slot's file** (not just the merged file).
- If the slot's findings file is missing or fails validation, treat it as a
  **non-compliant return** and route it through the existing three-tier ladder.
  Two refinements specific to findings:
  - **The retry is "structure what you already wrote," not a fresh review.** If a
    valid prose review exists for the slot, re-invoke with: *"You already wrote
    `review_code-reviewer-<slot>.md`. Emit the structured findings JSON from it —
    `[]` if none."* The **reviewer** transcribes its own prose — cheap, reliable,
    and explicitly NOT the orchestrator inventing findings.
  - **Cross-runtime fallback applies** (per the ladder): a Codex findings failure
    falls back to a Claude reviewer for that slot before any block. So a true
    block is rare — it follows a retry *and* a different model.
- Net: same "fail closed" discipline handoff.json already has — which is *why*
  handoff compliance hit 100% this run.

### Governing principle: fail closed on the contract, fail open on the value
Refuse to **silently fabricate** structured data (the anti-pattern Part 1 kills),
but **never discard** the human-readable review the reviewer actually wrote. A
missing findings JSON almost always means *the structured form is missing, not the
findings* — the prose review still holds them.

### When recovery genuinely fails — a decision point, not a dead-end
Only if the retry *and* the cross-runtime fallback still yield no valid structured
findings do we stop — and even then the user sees everything salvageable and
chooses. This reuses the existing `needs_human_decision` presentation
(`workflow.md` ~976–982), with the prose review attached:

```
⚠ Reviewer B completed its review but didn't produce structured findings
  (after a retry and a Claude-runtime fallback). Its written review is
  shown below — the content isn't lost, only the machine-readable form:

      [renders review_code-reviewer-b.md — the findings, in prose]

  Reviewer A's structured findings (N items) are valid and ready.

  How do you want to proceed?
    1. Proceed with A's findings; attach B's review to the backlog as an
       unstructured note for manual follow-up
    2. Triage B's review with me now — you confirm which items are real,
       I add them as findings (explicit, your call, logged as degraded)
    3. Re-run Reviewer B
    4. Pause here
```

Option 2 is the **explicit, human-confirmed** escape hatch — the opposite of the
silent automatic mid-happy-path repair we are banning. It is logged as a degraded
run. A hard `blocked` state remains only for "user chose pause" or the truly
nothing-salvageable case (both slots failed *and* no prose — extremely rare).

### Observability — make the new gate visible
Today `context_health.log` tracks a **single** compliance dimension —
`handoff.json` (`found` / `text_fallback` / `found (retry)`). Part 1 introduces a
**second** dimension (findings JSON), and a real run shows why this matters: a
reviewer can log `handoff=text_fallback` (a known graceful path) while its
*missing findings JSON was silently hand-authored by the orchestrator* — invisible
in the log. **Extend the compliance log with a findings-compliance status** per
slot (e.g. `findings=found` / `found(retry: structured from prose)` /
`cross-runtime fallback` / `MISSING→block`), so every retry, fallback, and block
the new gate produces is as auditable as handoff compliance already is. Without
this, the gate's activity is only half-captured.

**`scripts/quest_review_intelligence.py`**
- Confirm `validate-findings` treats `[]` as valid and missing/unparsable as a
  hard failure. No new subcommand expected; per-slot validation reuses the
  existing one with a different `--input`.

### Standalone value
Part 1 is worth shipping even without the arbiter: it removes silent
orchestrator repair from *today's* merge path and guarantees both slot files are
real before `merge-findings`/`build-backlog` run.

---

## Part 2 — Code-review arbiter (build-phase adjudication parity)

With per-slot findings guaranteed valid, insert an arbiter as a **peer judgment
step that replaces the deterministic `merge-findings` union** in workflow mode —
symmetric to the plan arbiter, which already produces `review_findings.json`
itself rather than delegating the merge to a script.

```
  builder
    → dual reviewers (A, B) write per-slot findings JSON     [unchanged]
    → [Part 1] per-slot validate-findings — fail closed      [NEW gate]
    → [Part 2] code-review arbiter: read both findings + diff,
               judge each finding's validity, emit canonical
               review_findings.json + verdict                [replaces merge-findings, workflow mode]
    → validate-findings (merged)                             [unchanged]
    → build-backlog (severity/confidence policy)             [unchanged]
    → orchestrator routes → fixer                            [unchanged]
```

### The code-review arbiter is NOT a copy of the plan arbiter
Same independence and handoff mechanics; **opposite risk posture on
correctness.**

| | Plan arbiter | Code-review arbiter |
|---|---|---|
| Bias when uncertain | Toward **approve** (don't spin) | Toward **preserving** correctness/security findings (don't let real bugs be dismissed) |
| Filters | Nitpicks, scope-creep, speculative complexity | Style/naming nitpicks only; never a plausible correctness/security finding |
| Dismissing a finding | Allowed freely (anti-spin) | Requires rationale tied to the diff; uncertain correctness findings route to `verify_first`, not dropped |
| Solo findings (one reviewer) | Evaluate on merit | Evaluate on merit — **the asymmetric-coverage case (A clean, B found 4) is the primary reason this role exists** |

In planning, over-spinning is the failure mode. In code review, **dismissing a
real bug is the dangerous failure mode.** Rule of thumb: "when in doubt, keep it
and mark `verify_first`."

### Changes

**New `.skills/quest/agents/review-arbiter.md`** (model on `arbiter.md`)
- Inputs: both `review_findings_code-reviewer-{a,b}.json`, the diff/changed
  files, brief acceptance criteria, plan. **Not** the full reviewer markdown.
- Outputs: canonical `review_findings.json` (same schema) + `review_arbiter_verdict.md`
  + `handoff_review-arbiter.json`. Writes to `.quest/<id>/phase_03_review/` via
  `*.next` staging, `.quest/**` only.
- Decision posture per the table; no silent drops; rationale required to dismiss.

**`workflow.md` Step 5 §5 (~959–974)**
- Workflow mode: replace `merge-findings` with the arbiter invocation that writes
  `review_findings.json`; `validate-findings` + `build-backlog` run unchanged.
- Solo mode: skip the arbiter (single reviewer = nothing to adjudicate); keep the
  single-input `merge-findings` passthrough. Mirrors plan-phase solo.
- Runs **every review round** (Step 6 re-review re-invokes both reviewers → arbiter
  runs again), like the plan arbiter per plan iteration.

**Orchestration / model config**
- Add a model slot (proposed `models.review-arbiter`, default `claude`) to
  `orchestration.json` and allowlist defaults, distinct from `models.arbiter`.

**Observability**
- Add `(phase=review, agent=review-arbiter)` to the parallelism/compliance
  enumeration and the `agents/README.md` index.

### Context budget (keeps the window small)
Arbiter input = 2 × compact findings JSON + the diff (already the review scope) +
brief/plan. **Excludes** the reviewers' full markdown reasoning — the findings
JSON is the canonical compact representation. Context stays ~diff-sized, not
diff + two review essays.

---

## Sequencing
1. **Part 1 first** (or same PR, ordered first): enforce per-slot findings.
   Independently valuable; required for Part 2 to be sound.
2. **Part 2** builds on it. Bonus synergy: if the arbiter falls back to the
   deterministic merge (Open Q2), Part 1 guarantees that fallback's inputs are
   valid too.

## Non-goals
- Not changing the deterministic severity/confidence backlog policy.
- Not having the arbiter mutate code or call the fixer.
- Not adding adjudication to solo mode.
- Not merging the plan and code-review arbiter contracts (risk postures differ).

## Decided (this session)
- **Q1 — Findings JSON is always required** (`[]` when clean). Validation is
  unconditional, not contingent on `next`.
- **Q2 — Retry budget: one strict retry, then ride the existing ladder**
  (cross-runtime fallback), then — only if still no valid structured findings —
  the graceful decision point above. The retry is "structure your existing
  review," not a fresh review. No second same-runtime retry. **A block is never a
  bare dead-end:** salvageable value (prose review + the other slot's findings) is
  always surfaced, and the user chooses. Governing rule: *fail closed on the
  contract, fail open on the value.*

- **Q3 (model key) — Separate `models.review-arbiter`, default `claude`.**
  Default set in `.ai/allowlist.json` `models` block (alongside the existing 8
  role keys); per-quest override via `orchestration.json` (#119). **Must also
  update the documented-defaults table in `workflow.md`** in lockstep, or
  migration backfill drifts. Rationale: every role has its own key; independent
  tunability + bias-avoidance vs. reviewer model families.
- **Q4 (arbiter failure) — Fail-open to the deterministic `merge-findings`
  union**, after one retry / cross-runtime attempt, and **logged + surfaced** as
  a one-line degraded note. Extends the Part 1 rule (*fail open on the value*);
  worst case lands at today's behavior, never worse. "Drive with value while
  pushing for more deterministic results."
- **Q5 (`next` hint & safety check) — Arbiter emits `next: fixer|null`; the Step
  5 safety check is re-anchored to compare the *arbiter's* verdict against the
  backlog.** Per-reviewer hints become diagnostic-only. **When the arbiter is
  skipped** (solo mode, or Q6 both-empty), the existing per-reviewer check
  applies instead.
- **Q6 (cost gate) — Skip the arbiter only when BOTH reviewers return empty
  (`[]`/`[]`); otherwise always run.** The orchestrator already knows whether
  inputs are empty (it triggers the arbiter), so the gate is free. Do NOT attempt
  to detect "identical non-empty findings" — fuzzy, and the arbiter still adds
  nitpick-filtering value when reviewers agree.
- **Q7 (coverage summary) — Always surface an A-vs-B coverage summary
  (agreed / A-only / B-only / dismissed-with-reason) to the human**, and persist
  dismissed findings + rationale to a log (alongside `deferred_findings.jsonl`).
  - **Respect auto-approve:** `auto_approve_phases.code_review` is `true` by
    default. When approved-without-human-response, **communicate the coverage
    summary and continue** — do not block waiting. The human-gated decision point
    only applies when auto-approve is off or a `needs_human_decision` item exists.
  - The summary is human-facing (`review_arbiter_verdict.md`), not read by the
    fixer → zero downstream context bloat. A-vs-B inputs are durably persisted in
    `.quest/<id>/phase_03_review/` (both review markdowns + both findings JSON +
    the arbiter verdict), recoverable after the session.
- **Q8 (arbiter applies coding principles) — The code-review arbiter adjudicates
  findings through `AGENTS.md` principles** (YAGNI, SRP, KISS, DRY, Quality),
  exactly as the plan arbiter already filters via KISS/YAGNI/SRP/Readability
  (`arbiter.md` 10–14). **Caveat (risk posture):** principles filter *nitpick and
  scope-creep findings* (e.g. reject a finding demanding speculative complexity);
  they MUST NOT be used to drop a correctness/security finding under the guise of
  "YAGNI/KISS." This is consistent with the risk-posture table above.

## Architecture / file layout (decided)
- **Agent responsibilities stay in separate agent contract files** under
  `.skills/quest/agents/` — the existing pattern. The code-review arbiter is a new
  `review-arbiter.md`; its judgment rules (incl. Q8) live there, NOT in
  `workflow.md`. The orchestrator does not load agent files — subagents do — so
  this adds near-zero orchestrator context (just thin Step 5 wiring).
- **`workflow.md` (1391 lines) stays whole for this feature.** Routing is
  cross-phase (fix → re-review → complete); fragmenting it would increase, not
  decrease, confusion. It is the control-flow spine.
- **Separate follow-up (not this feature):** if `workflow.md` size is itself a
  context concern, decompose per-phase *procedure* blocks (Step 3/4/5/6) into
  phase files loaded on phase entry (progressive disclosure), keeping a routing
  spine in `workflow.md`. Scope as its own idea doc.

## Open questions
- None outstanding. Awaiting any further input from kjell before promotion to a
  build plan.

## References
- Code-reviewer contract: `.skills/quest/agents/code-reviewer.md` (findings at line 44; Output Contract 64–100)
- Plan arbiter contract: `.skills/quest/agents/arbiter.md` (writes `[]` when clean, line 40)
- Code-review phase: `.skills/quest/delegation/workflow.md` Step 5 (~773–987; merged validate at 966)
- Handoff enforcement pattern to mirror: `workflow.md` Handoff File Polling §6 (~156–186)
- Deterministic policy: `scripts/quest_review_intelligence.py` (`merge-findings`, `validate-findings`, `build-backlog`)
- Origin of deterministic merge in code review: PR #92 (commit ed4562e, 2026-04-17)
