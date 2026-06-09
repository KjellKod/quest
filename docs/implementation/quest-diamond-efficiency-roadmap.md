---
title: Quest Diamond Efficiency Roadmap
purpose: Step-by-step implementation plan to cut Quest token burn and raise review quality, with a measurable before/after comparison against main.
audience: Mid-level engineers and implementing agents (work packages are quest-prompt ready).
scope: Orchestration docs, agent contracts, review pipeline, CI prompt assembly, and efficiency telemetry.
status: active
owner: maintainers
last_updated: 2026-06-09
related:
  - .skills/quest/delegation/workflow.md
  - .skills/quest/agents/
  - .ai/allowlist.json
  - .ai/schemas/handoff.schema.json
  - ideas/2026-05-31-quest-model-capability-improvements.md
  - scripts/quest_runtime/review_intelligence.py
---

# Quest Diamond Efficiency Roadmap

## Goal

Quest's architecture is already strong: handoff polling discards agent response
bodies, prompts pass file paths instead of contents, and review synthesis is
deterministic Python. The remaining waste is concentrated in three places:

1. **Fixed orchestrator context** — `.skills/quest/delegation/workflow.md` is
   1,476 lines (~25k tokens) and is held in the orchestrator's context for the
   entire quest, even though each phase needs only a fraction of it.
2. **The fix loop** — every fix iteration re-runs a full dual code review plus
   the review-arbiter, even when the fix touched two files.
3. **Contract drift** — roles are defined in three places
   (`.skills/quest/agents/`, `.claude/agents/`, `.opencode/agents/`) with real
   disagreements, including two incompatible severity taxonomies.

This roadmap fixes those in impact order, and—critically—**measures the
improvement**. The guiding principle: *the cheapest token is the iteration you
never run.* One avoided plan iteration saves a planner + two reviewers + an
arbiter round; quality improvements that raise first-pass approval rates beat
prompt micro-trimming.

This roadmap follows the measurement-first discipline established in
[`ideas/2026-05-31-quest-model-capability-improvements.md`](../../ideas/2026-05-31-quest-model-capability-improvements.md):
instrument before changing, prove before deleting.

## Branch strategy

All work lands on a long-lived integration branch so the finished result can be
compared against `main` as one unit:

```
main ──► diamond (integration branch, created from main)
            ▲
            ├── PR: wp0-efficiency-telemetry
            ├── PR: wp1-contract-unification
            ├── PR: wp2-workflow-split
            ├── ...
            └── PR: wp9-comparison-report
```

Rules:

- Create `diamond` from `main` once, at the start.
- Each work package (WP) is its own branch + draft PR **into `diamond`**, using
  the normal Quest gates (dual review, arbiter, fix loop). Small, reviewable PRs.
- Rebase `diamond` on `main` weekly so the final comparison is honest.
- WP9 runs the benchmark on both branches and produces the comparison report.
  Only then does `diamond` merge to `main`.

## Measuring efficiency

Yes, this is measurable — and the seams already exist. The bridge runner has a
telemetry hook (`QUEST_RUNNER_TELEMETRY_LOG` in `scripts/quest_claude_runner.py`),
`claude --print --output-format json` reports token usage and cost, the Codex
MCP/CLI reports token counts, and every quest already writes
`logs/context_health.log` and iteration counters into `state.json`.

**Per-quest metrics file:** `.quest/<id>/logs/metrics.jsonl`, one JSON line per
role invocation:

```json
{"ts": "...", "phase": "code_review", "agent": "code-reviewer-a",
 "runtime": "claude", "model": "claude-opus-4-8",
 "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0,
 "duration_s": 0, "iteration": 1, "outcome": "handoff_json"}
```

**Quest-level rollup** (computed by `quest_complete.py`, embedded in the
journal entry next to the existing celebration data):

| Metric | Why it matters |
|---|---|
| Total tokens (in/out/cached) per quest, split by role | The headline cost number |
| Plan iterations / fix iterations | Each iteration is the biggest cost multiplier |
| First-pass plan approval (plan_iteration == 1) | Measures planner + lessons-loop quality |
| Findings precision: `fix_now` ÷ total findings | Measures reviewer noise (dismissed/dropped findings cost fixer + re-review tokens) |
| Review-arbiter overhead: arbiter tokens ÷ review tokens | Decides WP4's arbiter-gating question |
| Wall-clock per phase | Parallelism health |

**Benchmark suite:** three canned quest briefs checked into
`tests/benchmark/briefs/` (one small bugfix, one medium feature, one
docs/config change). WP0 runs them on `main` to record the baseline; WP9
re-runs them on `diamond`. Identical briefs, identical models, compare the
rollups. That is the `diamond` vs `main` comparison.

## Model orchestration layout

Current model names: **Fable 5** (`claude-fable-5`, Claude Code's default
orchestrator model), **Opus 4.8** (`claude-opus-4-8`), **GPT-5.5** (Codex).

| Role | Runtime today | Model today | Target after WP7 |
|---|---|---|---|
| Quest Agent (orchestrator) | Claude Code main loop | Fable 5 | Fable 5 |
| Planner | Codex | GPT-5.5 (effort high) | GPT-5.5 |
| Plan Reviewer A | Claude `Task(...)` | "claude" (inherits session model) | Opus 4.8 or Fable 5, explicit |
| Plan Reviewer B | Codex | GPT-5.5 | GPT-5.5 |
| Plan Arbiter | Claude `Task(...)` | "claude" | Opus 4.8 or Fable 5, explicit |
| Builder | Codex | GPT-5.5 | GPT-5.5 |
| Code Reviewer A | Claude `Task(...)` | "claude" | Opus 4.8 or Fable 5, explicit |
| Code Reviewer B | Codex | GPT-5.5 | GPT-5.5 |
| Review Arbiter | Claude `Task(...)` | "claude" | Opus 4.8 or Fable 5, explicit |
| Fixer | Codex | GPT-5.5 | GPT-5.5 |

### Can we switch between Fable 5 and Opus 4.8 per subagent today?

**Yes — the capability exists at every layer; what's missing is Quest plumbing:**

1. **Native Claude-led runs:** Claude Code's `Task(...)` / Agent tool accepts a
   per-invocation model override (`opus`, `fable`, `sonnet`, `haiku`), and
   subagent definitions support a `model:` frontmatter field. A Fable 5
   orchestrator can dispatch an Opus 4.8 reviewer right now.
2. **Bridge runs (Codex-led):** the Claude CLI accepts
   `--model claude-opus-4-8` (verified locally, see the model-capability idea
   doc) and the bridge already passes `--model` through.
3. **The gap:** Quest's `models` map only distinguishes `"claude"` vs
   `"gpt-5.5"` — the orchestrator never tells `Task(...)` *which* Claude model
   to use, so Claude slots silently inherit the session model. WP7 closes this
   by allowing specific model strings (e.g. `"claude-opus-4-8"`) in the
   allowlist and passing them through both dispatch paths.

Don't pre-assign which Claude model each role "should" use — WP0's metrics plus
WP7's plumbing make that an experiment, not folklore.

## Work packages

Dependency / parallelism map:

```
WP0 (telemetry + baseline) ──┬──────────────────────────► WP9 (comparison)
WP1 (contracts)        ──────┤  parallel with WP0           ▲
WP2 (workflow split)   ──────┤  after WP1                   │
WP3 (fix-loop delta)   ──────┤  after WP2                   │
WP4 (reviewer signal)  ──────┤  after WP2; needs WP0 data   │
WP5 (planning lessons) ──────┤  after WP2 ──────────────────┤
WP6 (CI prompt cleanup)──────┤  parallel anytime ───────────┤
WP7 (model plumbing)   ──────┤  parallel anytime ───────────┤
WP8 (completion UX)    ──────┴  after WP2; needs WP0 data ──┘
```

Sequence the workflow-file work (WP1 → WP2 → WP3/WP4/WP5/WP8) because they
edit the same files. WP6 and WP7 touch disjoint files and can run in parallel
with anything after WP0.

---

### WP0 — Efficiency telemetry and baseline

**Why first:** every later WP claims an efficiency win; without a baseline none
of those claims are checkable. Also generates the data WP4 and WP7 need.

**Steps:**

1. Add `scripts/quest_runtime/metrics.py` with `record_invocation(...)` that
   appends one JSON line to `.quest/<id>/logs/metrics.jsonl`. Capture: phase,
   agent, runtime, model, input/output/cached tokens, duration, iteration,
   outcome. Token fields are best-effort: parse Claude CLI JSON output usage
   fields; parse Codex CLI/MCP token counts; write `null` when unavailable —
   never fail the run.
2. Wire it into the two dispatch paths: `scripts/quest_claude_runner.py`
   (bridge) and the orchestrator workflow instructions for native `Task(...)` /
   Codex MCP calls (one "append metrics line" step after each handoff read,
   next to the existing `context_health.log` line).
3. Extend `quest_complete.py` to compute the rollup table (totals by role,
   iterations, findings precision, arbiter overhead) and embed it in the
   journal entry.
4. Create `tests/benchmark/briefs/` with three briefs (small fix, medium
   feature, config change) and `docs/guides/benchmark.md` describing how to run
   them: `git checkout main`, run each brief through `/quest`, archive the
   metrics rollups as `tests/benchmark/baseline/<brief>.json`. Briefs must be
   self-contained: they target a scratch fixture area
   (`tests/benchmark/fixture/`) so runs are repeatable and the produced quest
   branches are throwaway.
5. Run the baseline on `main` and commit the three rollup files.

**Acceptance criteria:**

- [ ] A quest run produces `metrics.jsonl` with ≥1 line per role invocation; missing token data appears as `null`, never crashes a run.
- [ ] Journal entries for new quests contain the rollup table.
- [ ] `tests/benchmark/baseline/` holds three rollups generated from `main`.
- [ ] Unit tests cover the rollup math (tokens summed by role, precision ratio).
- [ ] `.quest-manifest` lists the new runtime/benchmark files (`scripts/quest_runtime/*.py` is installer-managed); `quest_validate-manifest.sh` passes.

**Quest prompt:**

> Implement efficiency telemetry for Quest per WP0 of
> `docs/implementation/quest-diamond-efficiency-roadmap.md`: a metrics.jsonl
> recorder in scripts/quest_runtime/metrics.py, wiring in the bridge runner and
> the workflow handoff-read steps, a rollup in quest_complete.py embedded in
> the journal, and a 3-brief benchmark suite under tests/benchmark/. Best-effort
> token capture — never fail a run on missing usage data. Include unit tests
> for the rollup.

---

### WP1 — Contract unification (severity, schemas, platform stubs)

**Why early:** every later WP edits role definitions; unifying contracts first
avoids re-doing work. This is also a live correctness bug.

**The bug:** `.skills/code-reviewer/SKILL.md` instructs reviewers in
Blocker / Must fix / Should fix / Nit, while the canonical findings schema in
`.skills/quest/agents/code-reviewer.md` (and `review_intelligence.py`
validation) requires `critical|high|medium|low|info`. A reviewer following the
SKILL produces findings the backlog automation can't classify.

**Steps:**

1. Adopt `critical|high|medium|low|info` as the single machine taxonomy
   (already what `review_intelligence.py` validates). In
   `.skills/code-reviewer/SKILL.md` and `.skills/plan-reviewer/SKILL.md`, map
   the human labels once: Blocker→critical, Must fix→high, Should fix→medium,
   Nit→low/info — then use the machine enum everywhere a finding is written
   **as a Quest artifact** (findings JSON, backlogs, handoffs).
   **Deliberate carve-out:** human-facing PR-comment output
   (`.skills/ci-code-reviewer/SKILL.md` and the CI review pipeline)
   intentionally keeps Blocker/Must fix/Should fix as display labels — they
   are the display form of the same mapping, not a second taxonomy, and are
   out of scope for the enum swap.
2. Make `.ai/schemas/handoff.schema.json` the referenced source of truth:
   replace the ~18 inline handoff.json restatements across
   `.skills/quest/agents/*.md`, `.claude/agents/*.md`, `.opencode/agents/*.md`
   with one-line pointers ("Handoff contract: `.ai/schemas/handoff.schema.json`,
   example in `.skills/quest/agents/README.md`"). Keep exactly one worked
   example, in the README.
3. Shrink `.claude/agents/*.md` and `.opencode/agents/*.md` to thin pointers at
   the canonical `.skills/quest/agents/<role>.md` (≤15 lines each: role name,
   pointer, platform-specific invocation notes only). Resolve the known drift:
   planner question-handling (`needs_human` vs forbidden) follows the canonical
   rule; reviewer output formats follow the canonical findings schema.
   **Exception:** `.opencode/agents/quest.md` is the OpenCode orchestrator
   stub with no per-role canonical file — leave it pointing at
   `.skills/quest/SKILL.md` and the workflow docs; it is out of scope for the
   stub contraction.
4. Add a guard test (`tests/unit/`) that fails if a platform stub redefines
   severity values or handoff fields (simple grep-style assertions), so drift
   can't silently return.

**Acceptance criteria:**

- [ ] All canonical Quest findings artifacts (findings JSON, backlogs, quest agent contracts) use the `critical|high|medium|low|info` enum exclusively; human display labels appear only as the mapping table in the reviewer SKILLs and in human-facing PR-comment output (which keeps its display labels per the carve-out above).
- [ ] `grep -rn '"status".*complete.*needs_human' .skills .claude .opencode` finds the handoff schema spelled out in ≤2 places (schema file + one example).
- [ ] Platform stubs are ≤15 lines and contain no contract definitions.
- [ ] Guard test passes and demonstrably fails when a stub re-adds a severity list.
- [ ] An end-to-end solo quest on a toy change still completes (contracts didn't break dispatch).

**Quest prompt:**

> Unify Quest role contracts per WP1 of
> `docs/implementation/quest-diamond-efficiency-roadmap.md`: one severity enum
> (critical/high/medium/low/info) with a human-label mapping table in the
> reviewer SKILLs, handoff schema referenced from
> `.ai/schemas/handoff.schema.json` instead of restated inline, platform stubs
> in .claude/agents and .opencode/agents reduced to ≤15-line pointers at the
> canonical .skills/quest/agents files, and a drift guard test.

---

### WP2 — Split workflow.md into lazy-loaded phase files

**Why:** the orchestrator pays ~25k tokens of fixed context per quest for
instructions of which each phase needs ~20%. Largest single fixed-cost cut
available, and purely mechanical.

**Steps:**

1. Split `.skills/quest/delegation/workflow.md` along its existing step
   boundaries into:
   - `workflow/core.md` (~150 lines): shared invariants only — handoff polling
     precedence, three-tier fallback ladder, state transition commands, artifact
     preparation, context_health/metrics logging.
   - `workflow/intake.md` — routing, brief, quest setup (Steps 1–2).
   - `workflow/plan.md` — planner, dual review, arbiter, presentation (Step 3–4).
   - `workflow/build.md` — builder gate + invocation (Step 5 part 1).
   - `workflow/review-fix.md` — dual code review, review-arbiter, backlog, fix
     loop (Steps 5 part 2 + 6).
   - `workflow/complete.md` — celebration, journal, archive (Step 7).
2. Update `.skills/quest/SKILL.md`: load `core.md` at quest start, then load
   exactly one phase file at phase entry (the phase is already in
   `state.json`). On resume, load core + the current phase file only.
3. Keep all step numbering and anchor names stable so cross-references in other
   docs and tests keep working. Update `.quest-manifest` and any path
   references (grep for `delegation/workflow.md` across the repo, including
   tests and installer manifests). The new `workflow/` directory is one level
   deeper than the manifest validator's current scan patterns — extend
   `scripts/quest_validate-manifest.sh` coverage to that depth so future phase
   files can't be silently omitted from the installer.
4. Leave a 10-line `workflow.md` tombstone pointing at the new layout (external
   docs/ideas reference it).

**Acceptance criteria:**

- [ ] No phase file exceeds 450 lines; `core.md` ≤ 200 lines.
- [ ] Sum of (core + largest phase file) ≤ 50% of the old workflow.md line count.
- [ ] `grep -rn "delegation/workflow.md"` shows only the tombstone and history docs.
- [ ] A full workflow-mode quest and a solo quest complete end-to-end on a toy change.
- [ ] `.quest-manifest` and checksums updated; `quest_validate-manifest.sh` passes **and its scan patterns cover the new `workflow/` depth** (test: an unlisted file added under `workflow/` fails validation).

**Quest prompt:**

> Split `.skills/quest/delegation/workflow.md` into lazy-loaded phase files per
> WP2 of `docs/implementation/quest-diamond-efficiency-roadmap.md`: a shared
> core.md plus intake/plan/build/review-fix/complete files, SKILL.md loading
> core + only the current phase at phase entry, stable step anchors, manifest
> updates, and a tombstone. No semantic changes to any instruction — this is a
> mechanical split.

---

### WP3 — Delta re-review in the fix loop + hard iteration caps

**Why:** with `max_fix_iterations=3`, a quest can pay for up to four full dual
reviews plus arbiter rounds. Iteration 2+ should verify fixes, not re-review
the world. And iteration caps are currently warnings, not stops — the most
expensive failure mode has only an advisory guard.

**Steps:**

1. **Review checkpoint contract first** (Quest applies builder/fixer changes
   as working-tree edits — there is no "last reviewed commit" to diff
   against): at the end of each review round the orchestrator snapshots the
   exact patch the reviewers saw to
   `.quest/<id>/phase_03_review/review_checkpoint_<n>.patch` (the
   review-arbiter flow already writes this as `review_diff.patch` — reuse it,
   numbered per round).
2. In `workflow/review-fix.md` (post-WP2), change re-review (fix_iteration ≥ 1)
   to a **delta review**: the orchestrator writes `review_delta.patch` — the
   interdiff between the previous round's checkpoint and the current
   working-tree diff — plus the list of backlog items the fixer addressed;
   reviewers are instructed to (a) verify each addressed item, (b) scan only
   the changed regions for regressions. Full-PR review remains for iteration 0.
   **Fallbacks:** if the interdiff is empty-but-backlog-nonempty, unreliable,
   or the quest has no VCS (`vcs_available: false`), fall back to the current
   full re-review with a one-line note.
3. Drop to a **single re-reviewer** (reviewer-a) on iterations ≥ 2; the dual +
   arbiter pass already covered the full diff. Make both behaviors explicit in
   `code-reviewer.md` (a short "re-review mode" section).
4. Convert iteration caps to hard stops: when `plan_iteration` or
   `fix_iteration` would exceed the allowlist gate,
   `quest_validate-quest-state.sh` fails the transition (exit non-zero) instead
   of warning, and the orchestrator routes to `needs_human` with the remaining
   backlog summarized. Keep the existing defer-to-backlog path
   (`append_deferred_findings`) as the exit ramp.
5. Update solo-mode caps the same way (`solo.max_fix_iterations`).

**Acceptance criteria:**

- [ ] Fix iteration ≥ 1 invokes reviewers with the delta patch + addressed-items list, not the full-PR context; iteration ≥ 2 uses one reviewer.
- [ ] Exceeding a cap blocks the state transition (validator test proves non-zero exit) and surfaces `needs_human` with deferred findings written.
- [ ] Benchmark medium brief shows reduced review-phase tokens vs baseline when a fix iteration occurs (directional check, recorded in PR description).
- [ ] Shell tests in `tests/` cover the validator's hard-stop behavior.

**Quest prompt:**

> Implement delta re-review and hard iteration caps per WP3 of
> `docs/implementation/quest-diamond-efficiency-roadmap.md`: fix-loop
> iterations re-review only the diff-since-last-review plus addressed backlog
> items, single reviewer from iteration 2, and quest_validate-quest-state.sh
> turns iteration-cap breaches into hard transition failures routed to
> needs_human with deferred findings persisted. Include validator shell tests.

---

### WP4 — Reviewer signal quality + review-arbiter cost tuning

**Why:** reviewer false positives are the system's token multiplier — each one
costs a fixer pass plus a re-review round. `.skills/review-anti-patterns.md` is
18 lines; confidence is captured in the findings schema but unused by backlog
policy. The always-on review-arbiter (truth-judging every finding) may be
overkill for clean reviews — WP0's data decides.

**Steps:**

1. Expand `.skills/review-anti-patterns.md` (~60–80 lines): concrete false
   positive families with examples — style preferences, "while you're here"
   scope creep, theoretical refactors, speculative perf concerns, restating the
   plan as a finding, duplicate-of-other-reviewer phrasing. Link it from both
   reviewer SKILLs and both reviewer agent files (pointer, not copy).
2. Add confidence rules to `build_review_backlog()` in
   `scripts/quest_runtime/review_intelligence.py`: `confidence: low` findings
   with severity ≤ medium route to `verify_first` or `defer`, never `fix_now`.
   Unit-test the policy table.
3. Review-arbiter gating experiment (data-driven, from WP0 metrics): add
   `review_arbiter_mode: "always" | "on_conflict"` to the allowlist
   (default `always`, current behavior). `on_conflict` invokes the arbiter only
   when reviewers disagree on severity for a deduped finding, findings exceed a
   count threshold, or any finding is `needs_human_decision`; otherwise the
   deterministic `merge-findings` union applies. Decide the default in WP9
   from arbiter-overhead metrics.

**Acceptance criteria:**

- [ ] Anti-patterns doc lists ≥6 named false-positive families with one example each; both reviewer paths reference it.
- [ ] Backlog policy unit tests prove low-confidence/medium-or-below findings never land in `fix_now`.
- [ ] `review_arbiter_mode: on_conflict` skips the arbiter on a clean dual review (test with two empty/agreeing findings files) and invokes it on a severity conflict.
- [ ] Default behavior unchanged (`always`) until WP9 decides.

**Quest prompt:**

> Improve Quest reviewer signal per WP4 of
> `docs/implementation/quest-diamond-efficiency-roadmap.md`: expand
> review-anti-patterns.md into named false-positive families referenced by both
> reviewer paths, add confidence-based backlog routing rules to
> review_intelligence.py with unit tests, and add a review_arbiter_mode
> allowlist knob (always | on_conflict, default always) implemented in the
> review phase instructions.

---

### WP5 — Planning lessons feedback loop

**Why:** raising first-pass plan approval is the single biggest token saver
(each avoided plan iteration ≈ planner + 2 reviewers + arbiter). The machinery
already exists for code findings (`deferred_findings.jsonl`); this applies the
same pattern to plan quality. Depends on WP2 (it edits `workflow/plan.md`);
otherwise independent.

**Steps:**

1. **Archive iterate verdicts first** — the plan-review flow overwrites
   `arbiter_verdict.md` on each iteration, so non-final rejection reasons are
   gone by completion time. In the plan phase (post-WP2 `workflow/plan.md`),
   when the arbiter returns `iterate`, the orchestrator copies the verdict to
   `arbiter_verdict_iter<n>.md` before the next planning round.
2. At quest completion, `quest_complete.py` extracts the iterate-reasons from
   the archived per-iteration verdicts and appends one-line lessons to
   `.quest/backlog/planning_lessons.md` (capped at 30 lines, FIFO — newest
   lessons replace oldest; dedupe identical lessons).
3. The planner prompt (in `workflow/plan.md`) references the lessons file when
   it exists: "Known causes of past plan rejections: read
   `.quest/backlog/planning_lessons.md` and avoid repeating them."
4. Lessons are repo-local state (gitignored under `.quest/`), same lifecycle as
   the deferred findings reservoir.

**Acceptance criteria:**

- [ ] Completing a quest whose plan took ≥2 iterations appends deduped lessons; a first-pass quest appends nothing.
- [ ] File is capped at 30 lines (oldest evicted) — unit-tested.
- [ ] Planner prompt includes the reference only when the file exists and is non-empty.
- [ ] First-pass plan approval rate is tracked in the WP0 rollup so WP9 can evaluate the effect.

**Quest prompt:**

> Add a planning lessons loop per WP5 of
> `docs/implementation/quest-diamond-efficiency-roadmap.md`: quest_complete.py
> distills arbiter iterate-reasons into a capped, deduped
> .quest/backlog/planning_lessons.md, and the planner prompt references it when
> non-empty. Unit-test extraction, dedupe, and the 30-line cap.

---

### WP6 — CI prompt consolidation

**Why:** `codex_review.py` sends both legacy head-file snapshots (up to 12
files × 12KB) and deep-CI selected files (up to 60KB) in the same prompt —
overlapping content, paid on every CI review.

**Steps:**

1. Remove `fetch_head_files` and the `PLACEHOLDER_PR_HEAD_FILES` section from
   `.github/scripts/codex_review.py` and `.github/codex-review-prompt.md`; deep
   CI selection becomes the only whole-file context.
2. Re-check deep-CI selection covers the gap: raise the selected-file cap from
   3 to 5 within the existing 60KB total budget (the budget, not the file
   count, remains the limiter).
3. Update `tests/unit/test_codex_review.py` accordingly.

**Acceptance criteria:**

- [ ] One whole-file context mechanism remains; prompt template has no head-files placeholder.
- [ ] Deep-CI total budget unchanged (60KB); file cap 5; tests updated and passing.
- [ ] A real PR review on the diamond branch produces comparable findings (spot-check, noted in PR description).

**Quest prompt:**

> Consolidate the Codex CI review prompt per WP6 of
> `docs/implementation/quest-diamond-efficiency-roadmap.md`: remove the legacy
> head-file snapshot path from codex_review.py and the prompt template, raise
> the deep-CI file cap to 5 within the existing 60KB budget, and update the
> unit tests.

---

### WP7 — Per-role Claude model plumbing (Fable 5 / Opus 4.8 / Sonnet)

**Why:** Claude slots currently say `"claude"` and silently inherit the session
model; `quest_claude_runner.py:56` and `quest_claude_probe.py:17` hardcode
`"opus"`. Explicit per-role models make cost/quality an experiment instead of
an accident, and let cheap roles (delta re-review, probes) run on cheaper
models later.

**Steps:**

1. Allow specific Claude model strings in the allowlist `models` map
   (e.g. `"claude-opus-4-8"`, `"claude-fable-5"`, `"claude-sonnet-4-6"`);
   bare `"claude"` stays valid and means "session default" (backward
   compatible). Document the accepted values in `.ai/allowlist.json`'s schema
   (`allowlist.schema.json`).
2. Pass the model through both dispatch paths: native `Task(...)` model
   parameter (workflow instructions) and bridge `--model` (already supported —
   remove the hardcoded `"opus"` defaults; default to the configured value or
   session default).
3. Record the resolved model in WP0's metrics line (already a field) so role ×
   model cost comparisons fall out of the data.
4. Do **not** change any default model in this WP — plumbing only, per the
   measurement-first rule.

**Acceptance criteria:**

- [ ] `"plan-reviewer-a": "claude-opus-4-8"` dispatches a Task/bridge call with that model (assert via metrics line / bridge args in tests).
- [ ] Bare `"claude"` behaves exactly as today; no defaults changed.
- [ ] No hardcoded model strings remain in `scripts/` (`grep -rn '"opus"' scripts/` is clean except parser fallbacks reading config).
- [ ] `allowlist.schema.json` validates the new values; config validator tests updated.

**Quest prompt:**

> Add per-role Claude model plumbing per WP7 of
> `docs/implementation/quest-diamond-efficiency-roadmap.md`: allowlist model
> values may name specific Claude models, passed through Task(...) and the
> bridge --model flag; bare "claude" keeps meaning session default; remove
> hardcoded "opus" defaults from runner and probe; record resolved model in
> metrics. Plumbing only — no default changes. Update schema + tests.

---

### WP8 — Completion experience: mandatory celebration, value feedback, default draft PR

**Why:** completion is where Quest pays the user back, and today the payoff is
optional. Celebration can be configured away (`on_complete: ask |
archive_silent`), the metrics WP0 collects stay buried in the journal, and a
draft PR is only opened when the user remembers to ask for pr-assistant. Make
the payoff automatic: always celebrate, show the user what they got and what
it cost, and open the draft PR by default — with the opt-out living in the
allowlist and stated up front at quest startup.

**Steps:**

1. Make celebration unconditional in `workflow/complete.md` (post-WP2 file):
   remove the `ask` and `archive_silent` branches and retire
   `quest_completion.on_complete` (legacy values migrate with a deprecation
   warning, never a crash). **Do not introduce a new style knob** — the
   existing `quest_completion.animation_style`
   (`minimal | standard | epic | silly`) keeps controlling presentation,
   unchanged; non-interactive/CI runs always render the markdown celebration
   at `minimal`. Keep the existing fire-and-forget rule: a celebration render
   failure never blocks journal + archive.
2. Add a **quest value report** block to the celebration (celebrate skill +
   `scripts/quest_celebrate/`): WP0 rollup highlights (total tokens by role,
   plan/fix iterations, findings precision), inherited/deferred findings
   counts, and planning lessons applied. This is user-facing VALUE feedback,
   not raw logs — the celebration reads the rollup `quest_complete.py` already
   embeds in the journal; it never recomputes.
3. **Default draft PR:** after celebration and archive, when
   `quest_completion.auto_pr` is `true` (new allowlist key, default `true`):
   quest completion currently leaves implementation changes uncommitted, and
   pr-assistant builds PR content from branch commits — so auto-PR first runs
   the existing **gated commit flow** (git-commit-assistant; the allowlist
   `gates` for commit/push still require approval). Only after the quest
   branch has committed changes does the orchestrator invoke
   `.skills/pr-assistant/SKILL.md` to open the draft PR. Skip with an explicit
   one-line note when: the user declines the commit gate, the branch has no
   committed changes, `vcs_available` is false, `branch_mode` is `none`, or
   `auto_pr: false`.
   **Deliberate contract change to pr-assistant:** update the Approval section
   of `.skills/pr-assistant/SKILL.md` so that `quest_completion.auto_pr: true`
   constitutes standing approval for quest-completion draft-PR creation —
   pr-assistant still renders the generated title/body in chat, but does not
   block waiting for confirmation. Manual/interactive invocations of
   pr-assistant keep the explicit-approval contract unchanged.
4. **Surface the opt-out at startup:** the intake step (where models/runtimes
   are confirmed and `orchestration.json` is written) snapshots `auto_pr` and
   `celebration_style` and states them in the startup summary, e.g. "On
   completion: celebration + draft PR (auto_pr=true — opt out in
   `.ai/allowlist.json`)." No mid-quest surprises.
5. Update `allowlist.schema.json` and the config validator: legacy
   `on_complete: ask | archive_silent` values migrate to the style default
   with a deprecation warning — never a crash.

**Acceptance criteria:**

- [ ] No configuration or environment path skips the celebration render; non-interactive runs use `minimal` style; `animation_style` values and behavior are untouched (validator test proves legacy `on_complete: archive_silent` migrates with a warning).
- [ ] Celebration includes the value report when `metrics.jsonl` exists, and degrades gracefully (omits the block) when it doesn't.
- [ ] A quest completing on a branch with `auto_pr` unset or `true` routes through the gated commit flow and ends with a draft PR opened via pr-assistant; declining the commit gate, an empty branch, `auto_pr: false`, and no-VCS quests all skip with an explicit note (no empty/stale PRs).
- [ ] The startup summary states completion behavior and where to change it.
- [ ] pr-assistant's SKILL documents the `auto_pr` standing-approval carve-out; manual invocations still require explicit approval (test or doc assertion).
- [ ] Schema + validator tests updated; `quest_validate-quest-config.sh` passes on both new and legacy allowlists.

**Quest prompt:**

> Implement the Quest completion experience per WP8 of
> `docs/implementation/quest-diamond-efficiency-roadmap.md`: celebration
> becomes unconditional (on_complete retired with warning-based migration,
> existing animation_style untouched), the celebration gains a value-report
> block sourced from the quest metrics rollup, and quest completion runs the
> gated commit flow then opens a draft PR via pr-assistant by default, gated
> by a new quest_completion.auto_pr allowlist key (default true) that the
> startup summary surfaces. Update allowlist schema, validator, and tests.

---

### WP9 — Benchmark comparison and merge decision

**Why:** this is the payoff — the diamond vs main comparison the branch
strategy exists for.

**Steps:**

1. Rebase `diamond` on `main`, then **refresh the baseline** so the
   comparison isn't stale (the WP0 baseline predates any weekly rebases):
   cherry-pick the WP0 telemetry commits onto current `main` in a throwaway
   branch (`main` + instrumentation only, no optimizations) and re-run the
   three briefs there. Record both commit SHAs.
2. Re-run the three benchmark briefs on `diamond` with the same models as the
   refreshed baseline.
3. Produce `docs/implementation/history/diamond-comparison-report.md`: side-by-side
   rollups (tokens by role, iterations, findings precision, arbiter overhead,
   wall-clock), plus a qualitative note on review quality (did delta re-review
   miss anything the baseline caught?).
4. Decide data-driven defaults: `review_arbiter_mode` (WP4) and any per-role
   model suggestions (WP7) — as follow-up proposals, not silent changes.
5. Merge `diamond` → `main` via the normal PR gate.

**Acceptance criteria:**

- [ ] Report shows per-brief before/after for every WP0 metric; baseline and diamond rollups derive from the same `main` commit, with both SHAs recorded in the report.
- [ ] Target: ≥30% reduction in orchestrator+review token totals on the medium brief, no regression in findings quality (no missed `critical|high` that baseline caught).
- [ ] If the target is missed, the report says which WP underdelivered and why — that's a valid outcome; the data is the deliverable.

---

## Out of scope (deliberately)

Per the measurement-first idea doc, these stay deferred until the WP0/WP9 data
says otherwise:

- Transport-owned structured artifacts (`--json-schema` / `--output-schema`
  handoff writing) — needs the fallback base-rate measurement first.
- Per-role reasoning-effort knobs as config.
- Prompt-cache-driven prompt reordering.
- Lowering iteration caps below current defaults.
- Cross-quest semantic memory beyond deferred findings + planning lessons.
