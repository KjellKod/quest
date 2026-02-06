# Quest Council Planning Track ("Quest Council" vs "Quest")

## What
Introduce an explicit, higher-level planning track selection at the start of `/quest`:

- **Quest Council**: create **two plan candidates**, compare them, and synthesize a **single merged “best plan”**.
- **Quest**: the current “standard” flow (single plan → dual review → arbiter → iterate/approve).

This makes the “two plans → compare → pick one → merge best parts” pattern a **first-class**, discoverable feature of Quest.

### User-facing prompts (final copy)

**1) Planning track selection**
```text
Which planning track?
- Quest Council (Recommended): slower, explores 2 approaches and merges into 1 best plan
- Quest: faster, single plan + review loop
Choose [C/q] (Enter = Council):
```

**2) Default roster confirmation**
```text
Quest setup (defaults): Planner: Claude | Reviews: Claude + GPT | Arbiter: Claude
Continue? [Y/n] (type "options" to change)
```

**3) Options menu (only on “n” or “options”)**
```text
What would you like to change?
1) Planning track: Council / Quest
2) Arbiter: Claude / GPT
3) Reviews: both / Claude-only / GPT-only
4) Review mode: auto / fast / full
5) Gates: ask before implementation/fixes (on/off)
Select 1–5:
```

## Why
- **Better plans for complex work**: migrations/refactors benefit from exploring competing approaches early.
- **Discoverability**: users won’t know they can change arbiter/reviewers/gates unless prompted.
- **Auditability**: candidate plans + comparison + merge rationale become durable artifacts in `.quest/`.
- **Low friction**: small work stays fast (“Quest” track), while bigger work opts into more rigor.

## Approach

### 1) Add a new planning mode to config
Add a planning config block to `.ai/allowlist.json` (names are examples; final schema can vary):

- `planning.mode`: `"auto" | "standard" | "council"`
  - `standard` maps to the user-facing label **“Quest”**.
- `planning.ask`: `"auto_recommend" | "ask_always" | "never"`
- `planning.council_candidates`: `2` (fixed at 2 initially)

**Recommendation behavior**
- When `planning.ask: auto_recommend`, the orchestrator picks a default (Council vs Quest) using a simple heuristic and still asks for confirmation (Enter accepts the recommendation).
- When `planning.ask: ask_always`, always ask.
- When `planning.ask: never`, never ask (use `planning.mode`).

**Heuristic (explainable, not magical)**
Recommend **Quest Council** when the user prompt contains keywords like:
- `migrate`, `refactor`, `rewrite`, `architecture`, `cutover`, `multi-phase`, `strategy`, `plan`
…or when the prompt is long/ambiguous.

### 2) Persist selection in quest state
Extend `.quest/<id>/state.json` to record:
- `planning_track`: `"quest" | "council"`
- `arbiter.tool`, `reviewers.mode`, and any overrides chosen via `options`

Resume behavior: `/quest <id>` does **not** re-ask; it continues based on state.

### 3) Council artifacts (phase_01_plan)
When `planning_track: council`, create these additional plan artifacts:

- `.quest/<id>/phase_01_plan/plan_candidates/plan_a.md`
- `.quest/<id>/phase_01_plan/plan_candidates/plan_b.md`
- `.quest/<id>/phase_01_plan/plan_comparison.md`
- `.quest/<id>/phase_01_plan/plan.md` (the only plan that downstream phases consume)

Candidate plans can reuse `.ai/templates/plan.md` with a short prefix like:
- “Approach A: conservative / lowest-risk”
- “Approach B: faster / more invasive”

(Exact A/B themes can be decided by the planner prompt and/or a small policy knob.)

### 4) Council workflow (minimal disruption to existing `/quest`)
Add a conditional branch inside the existing **Plan Phase** (`.skills/quest/SKILL.md`, Step 3):

**Standard (Quest) track**
- Unchanged: planner writes `plan.md` → reviewers review `plan.md` → arbiter verdict.

**Quest Council track**
1. Planner writes `plan_candidates/plan_a.md` and `plan_candidates/plan_b.md`.
2. Both plan reviewers review *both* candidates (or review a comparison + both candidates).
3. Arbiter:
   - chooses a base plan
   - merges the best ideas from the other plan **only if they reduce risk / increase clarity / increase testability**
   - writes:
     - `plan_comparison.md` (why this plan won; what was merged; key tradeoffs)
     - `plan.md` (the final merged plan)
     - normal `arbiter_verdict.md` (approve/iterate)

After that, proceed exactly as today (interactive presentation → human gate → build → code review → fix loop).

### 5) Keep prompts short (KISS)
- Council should add rigor, not ceremony.
- Reuse existing roles/skills/templates rather than inventing new ones.
- Keep the interactive prompts tight; only expand when user opts into `options`.

## Acceptance Criteria
1. Starting `/quest "<large migration prompt>"` shows the planning track prompt and defaults to **Quest Council** (Enter accepts).
2. Starting `/quest "<small change>"` recommends **Quest** (or at least offers the choice) without adding friction.
3. In Council mode, the four artifacts are created (`plan_a`, `plan_b`, `plan_comparison`, merged `plan.md`).
4. The roster confirmation prompt appears, and typing `options` allows overrides without editing JSON.
5. Resume (`/quest <id>`) continues without re-asking prompts.
6. Existing behavior remains unchanged when `planning.mode` is `standard` and prompts are disabled.

## Open Questions
- Should the council candidates be explicitly “conservative vs aggressive”, or should the planner choose two materially different options automatically?
- Do we want a dedicated template for `plan_comparison.md` (likely yes), or can it be free-form?
- When `arbiter.tool` is GPT, do we want the roster default to remain Claude, or track “arbiter=GPT” as the recommended default for Council?

## Status
idea
