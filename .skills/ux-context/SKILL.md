# UX Context

Primer skill that loads the canonical UX guidebook and stress-test rubric so agents producing user-facing work shape it against durable principles.

At activation, announce the skill name and scope in one line. Example: `[ux-context] UX guidebook loaded — principles and stress-test rubric in scope.`

**Not user-invocable.** This skill is auto-attached by the orchestrator when the router classifies a quest as `ui_work: true`. For direct critique of existing UI, see `.skills/ux-review/SKILL.md`.

## When to Use

This skill is loaded by orchestration when the planner, builder/implementer, or fixer is about to produce user-facing work. It supplies the principles the agent should shape its output against — it does not perform a review.

Agents reading this skill should also read its resources before producing UX-affecting work:

- `resources/ux-guidebook.md` — the canonical 10-section guidebook
- `resources/ux-stress-test.md` — the runnable 12-question rubric, 15 red flags, mobile checklist, Mac-native checklist

## Procedure

### Step 1: Load the guidebook
Read `.skills/ux-context/resources/ux-guidebook.md` in full. This is the canonical, opinionated UX standard for this stable of projects. It is anchored in the durable canon (Norman, Rams, Nielsen, Tognazzini, Shneiderman, Cooper, Tufte, Krug) and validated against modern execution (Apple HIG, Refactoring UI, Linear, Vercel Geist, Rauno).

The book's central reconciling rule:

> **Visual chrome should be restrained. Task content should be as dense as the task earns. Density without grouping is noise; minimalism without signifiers is mystery.**

### Step 2: Load the stress-test rubric
Read `.skills/ux-context/resources/ux-stress-test.md`. This is the 12-question rubric (signifier, feedback, mental model, consistency, error prevention, reversibility, recognition, Fitts, defaults, honesty, density-vs-chrome, scan test), the 15-point red flags diagnostic, the 20-point mobile-feel checklist, and the 15-point Mac-native checklist.

### Step 3: Apply to your role

**If you are a planner:**
- Shape the plan so it answers the 12 stress-test questions explicitly. Don't leave signifier, empty-state, mobile divergence, or feedback decisions implicit.
- For any UI change, name the primary action, the empty state copy, and the loading/error states in the plan — not later.
- If the work touches mobile, include the desktop ↔ mobile divergence call-out (independent toolbars sharing state, not a responsive-shrunk desktop).
- If the work touches macOS-native, list which of the 15 Mac-native checklist items apply.

**If you are a builder / implementer:**
- Honor §4 of the guidebook ("The discipline") as you write code. Use the design-token recommendations: 4/8pt grid, one accent + one warning color, 8–10 tinted grays, three type sizes, three shadow tokens, one transition timing.
- Don't strip `:focus-visible`. Don't ship a 16px-everywhere chrome. Don't hand-roll per-component `box-shadow`. Don't use `100vh` on a mobile layout — use `100dvh`. Pad `env(safe-area-inset-*)` on every fixed surface.
- For copy: short verbs on buttons, plain-language errors that state what happened and what to do, preserve form input on validation failure.
- For motion: ≤200ms direct response, ≤400ms transitions, honor `prefers-reduced-motion`.

**If you are a fixer:**
- Cite the principle being fixed by section ID from the guidebook in your commit message and PR comment. Example: `Fix: empty layer panel had no instruction (ux-guidebook §4.7 #1 — empty states are first-onboarding).`
- Apply the smallest fix that resolves the principle violation; resist redesigning.

### Step 4: Cite when you decide
Any UX-affecting decision in your plan, code, or commit should cite the principle: `(ux-guidebook §4.2 #3 — color is semantic, not decorative)`. This makes the design rationale auditable downstream.

## Key Principles (excerpt — see guidebook for full set)

1. **Visual chrome restrained; content density task-appropriate.** Not minimalism — restraint. Not "less is more" — "as little as the task allows."
2. **A button must look pressable before it can look beautiful** (Norman). Flatness only when signifiers survive.
3. **Every action confirms within ~100ms; every commit has closure.** Quiet does not mean silent.
4. **Don't fake instant when you mean pending** (Rams #6). Honest progress, honest depth.
5. **Don't paste one OS's chrome into another.** Same icon, native behavior is fine; same chrome across platforms is broken.

## Companion Skill

For *reviewing* existing UI (your own or someone else's), see `.skills/ux-review/SKILL.md`. This skill is for *producing* work; ux-review is for critiquing it. Both consume the same guidebook in `.skills/ux-context/resources/`.

## Bundled Resources

- `resources/ux-guidebook.md` — canonical guidebook, ~530 lines
- `resources/ux-stress-test.md` — runnable rubric and checklists, ~150 lines

## Related Skills

- `.skills/ux-review/SKILL.md` — invokes the stress test against a target
- `.skills/plan-maker/SKILL.md` — the planner consumes both during plan creation
- `.skills/implementer/SKILL.md` — the builder consumes ux-context during implementation
- `.skills/code-reviewer/SKILL.md` — code reviewers cross-reference ux-review findings
