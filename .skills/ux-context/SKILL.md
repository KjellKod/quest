# UX Context

Primer skill that loads the canonical UX guidebook and stress-test rubric, and owns the UX Defaults emission protocol that the planner follows for `ui_work: true` quests.

At activation, announce the skill name and scope in one line. Example: `[ux-context] UX guidebook loaded — principles and stress-test rubric in scope.`

**Not user-invocable.** Auto-attached by the orchestrator when the router classifies a quest as `ui_work: true`. For direct critique of existing UI, see `.skills/ux-review/SKILL.md`.

## When to Use

Loaded by orchestration when the planner, builder/implementer, or fixer is about to produce user-facing work. Supplies the principles the agent shapes its output against — it does not perform a review.

Agents reading this skill should also read its resources:

- `resources/ux-guidebook.md` — the canonical 10-section guidebook (single source of truth for principles, inference tables, and all named defaults)
- `resources/ux-stress-test.md` — the runnable 12-question rubric, 15 red flags, mobile checklist, Mac-native checklist

## Procedure

### Step 0: Read the brief end-to-end (mandatory before anything else)
Before loading any UX context, read `.quest/<id>/quest_brief.md` fully and extract `ui_work` from the `## Router Classification` JSON block. Treat a missing field as `false` — do not load this skill for legacy briefs without the classification block. If `ui_work_evidence` is present, use it to scope your attention to the named files/areas.

### Step 1: Load the guidebook
Read `resources/ux-guidebook.md` in full. Central reconciling rule:

> **Visual chrome should be restrained. Task content should be as dense as the task earns. Density without grouping is noise; minimalism without signifiers is mystery.**

### Step 2: Load the stress-test rubric
Read `resources/ux-stress-test.md`.

### Step 3: Apply to your role

**If you are a planner** — follow the UX Defaults emission protocol below.

**If you are a builder / implementer** — honor §4 of the guidebook as you write code. Use the design tokens from §4.2, the spacing rules from §4.3, the motion budgets from §4.5, the mobile rules from §5.2. If `ui_work_evidence` is non-empty, prioritize those files.

**If you are a fixer** — cite the principle being fixed by section ID in your commit message and PR comment. Example: `Fix: empty layer panel had no instruction (ux-guidebook §4.7 #1).` Smallest fix that resolves the violation; resist redesigning.

---

## UX Defaults Emission Protocol (planner)

When the brief has `ui_work: true`, the planner must emit a `## UX Defaults` section in the plan. This is how backend engineers and non-designers see what's being built without having to articulate it themselves.

### Render-layer guard (false-positive suppression)

The router biases toward `ui_work: true`. Before emitting `## UX Defaults`, verify the plan actually touches a render layer (`*.tsx`, `*.jsx`, `*.vue`, `*.svelte`, `*.css`, `*.scss`, `*.swift`, `*.html`). If none, **omit the section** and append a one-line note in the plan:

> *Router flagged `ui_work: true`, but plan touches no render layer — UX Defaults section omitted.*

This prevents a backend task ("dump UI config to JSON") from triggering a defaults section it doesn't need.

### Required fields (five, plus state plan)

Pick the inference row from `resources/ux-guidebook.md §4.9` that matches the prompt's strongest signal. When in doubt, default to the last row (`slate / comfortable / content-forward / required` + accent `#2563eb`).

1. **Gray ramp:** one of `slate / stone / neutral / zinc / gray`. One-line rationale.
2. **Density:** `comfortable` or `compact`. One-line rationale.
3. **Content-vs-chrome ratio:** `content-forward` or `chrome-dense`. One-line rationale.
4. **Mobile relevance:** `required / optional / no`. If `required`, name the desktop ↔ mobile divergence approach (independent toolbars / responsive shrink / drawer).
5. **Brand accent:** hex value, defaulting to `#2563eb` (Tailwind `blue-600`) if not specified.

Plus a **one-sentence plan for empty, loading, and error states** — three sentences, total. Concrete copy, not "TBD."

### Opt-out for UX-savvy prompts

If the user prompt or quest brief already names **≥3 of the five defaults** (ramp, density, ratio, mobile, accent), emit a shortened block listing only the unspecified fields, plus a one-line acknowledgement of the ones the user did specify. Skip the closing sharpen pointer — the user signaled they don't need it.

Example shortened block:

```markdown
## UX Defaults

User specified: gray ramp `slate`, density `compact`, accent `#0f172a` text. Inferred:

- Ratio: chrome-dense — implied by Vercel-like reference.
- Mobile: optional — internal dashboard.
- Empty / loading / error: skeleton rows, inline form-error preservation, plain-language messages.
```

### Closing pointer (when emitting the full block)

End the `## UX Defaults` section with one line so the user knows the interview path exists:

> *To refine these, run `/sharpen ux-defaults` at the plan-approval gate. It walks each decision with a recommended answer attached — useful when you can see good UX but can't articulate it.*

This line is omitted when the opt-out short form is used.

---

## Step 4: Cite when you decide

Any UX-affecting decision in your plan, code, or commit should cite the principle: `(ux-guidebook §4.2 #3)`. Canonical format is `ux-guidebook§<section_number>` — no spaces, no sub-bullet numbers, no `#` suffix. This makes the design rationale auditable and greppable downstream.

## Key Principles (excerpt — see guidebook for full set)

1. **Visual chrome restrained; content density task-appropriate.** Not minimalism — restraint.
2. **A button must look pressable before it can look beautiful** (Norman).
3. **Every action confirms within ~100ms; every commit has closure.** Quiet does not mean silent.
4. **Don't fake instant when you mean pending** (Rams #6). Performance is UX.
5. **Don't paste one OS's chrome into another.** Same icon, native behavior is fine; same chrome across platforms is broken.

## Companion Skill

For *reviewing* existing UI, see `.skills/ux-review/SKILL.md`. This skill is for *producing* work; ux-review is for critiquing it. Both consume the same guidebook resources.

## Bundled Resources

- `resources/ux-guidebook.md` — canonical guidebook (10 sections + appendices, inference table at §4.9)
- `resources/ux-stress-test.md` — runnable rubric and checklists

## Related Skills

- `.skills/ux-review/SKILL.md` — invokes the stress test against a target
- `.skills/sharpen/SKILL.md` — `ux-defaults` mode walks the same five fields one at a time as a refinement interview
- `.skills/plan-maker/SKILL.md` — the planner consumes both during plan creation
- `.skills/implementer/SKILL.md` — the builder consumes ux-context during implementation
- `.skills/code-reviewer/SKILL.md` — code reviewers cross-reference ux-review findings
