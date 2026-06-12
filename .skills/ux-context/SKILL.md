# UX Context

Primer skill that loads the canonical UX guidebook and stress-test rubric, and owns the UX Defaults emission protocol that the planner follows for `ui_work: true` quests.

At activation, announce the skill name and scope in one line. Example: `[ux-context] UX guidebook loaded — principles and stress-test rubric in scope.`

**Not user-invocable.** Auto-attached by the orchestrator when the router classifies a quest as `ui_work: true`. For direct critique of existing UI, see `.skills/ux-review/SKILL.md`.

## When to Use

Loaded by orchestration when the planner, builder/implementer, or fixer is about to produce user-facing work. Supplies the principles the agent shapes its output against — it does not perform a review.

Agents reading this skill load resources progressively, by role and surface:

- `resources/ux-guidebook.md` — the canonical guidebook (single source of truth for principles, inference tables, and named defaults)
- `resources/ux-stress-test.md` — the runnable 12-question rubric, 15 red flags, mobile checklist, Mac-native checklist

## Procedure

### Step 0: Read the brief end-to-end (mandatory before anything else)
Before loading any UX context, read `.quest/<id>/quest_brief.md` fully and extract `ui_work` from the `## Router Classification` JSON block. Treat a missing field as `false` — do not load this skill for legacy briefs without the classification block. If `ui_work_evidence` is present, use it to scope your attention to the named files/areas.

### Step 1: Load only the guidebook sections your role needs
Do not read the whole guidebook by default. Find your row in the table and read those sections only:

| Role | Required guidebook sections | Stress-test? |
|---|---|---|
| Planner | §2 (14 principles), §3 (central rule), §4.9 (inference table) — then the UX Defaults emission protocol below | no |
| Builder / implementer | §2, §3, and the §4 subsections matching the file types being touched (4.1 typography for prose/labels, 4.2 color for tokens, 4.3 spacing/density for layout, 4.5 motion for transitions, 4.7 empty/loading/error states for state UI, 4.8 a11y for any interactive surface). Add §5 only for responsive, mobile, or native-platform work. | no |
| Fixer | The guidebook section(s) cited by each UX finding, plus nearby context if the fix is ambiguous | no — unless verifying the fix |
| Plan-reviewer | §2, §3, §4.9, plus the section cited by any finding the reviewer is interpreting | Not needed for the plan-phase UX intent pass unless the plan includes rendered evidence |
| Code-reviewer | Sections cited by the findings under review, plus §2 + §3 for principle anchoring | Yes — the full rubric in `resources/ux-stress-test.md` is the review tool |

Central reconciling rule (loaded by every role):

> **Visual chrome should be restrained. Task content should be as dense as the task earns. Density without grouping is noise; minimalism without signifiers is mystery.**

### Step 2: Load the stress-test rubric per the table above
The Step 1 table names exactly when each role reads `resources/ux-stress-test.md`. Planners and builders do not load the full rubric unless the prompt explicitly asks for a self-review checklist.

### Step 3: Apply to your role

**If you are a planner** — follow the UX Defaults emission protocol below.

**If you are a builder / implementer** — honor the relevant §4 guidebook sections as you write code. Use the design tokens from §4.2, the spacing rules from §4.3, the motion budgets from §4.5, and the mobile rules from §5.2 only when the change touches those concerns. If `ui_work_evidence` is non-empty, prioritize those files.

**If you are a fixer** — cite the principle being fixed by section ID in your commit message and PR comment. Example: `Fix: empty layer panel had no instruction (ux-guidebook §4.7 #1).` Smallest fix that resolves the violation; resist redesigning.

---

## UX Defaults Emission Protocol (planner)

When the brief has `ui_work: true`, the planner must emit a `## UX Defaults` section in the plan. This is how backend engineers and non-designers see what's being built without having to articulate it themselves.

### Render-layer guard (false-positive suppression)

The router biases toward `ui_work: true`. Before emitting `## UX Defaults`, verify the plan actually touches a render layer or visible styling surface (`*.tsx`, `*.jsx`, `*.vue`, `*.svelte`, `*.css`, `*.scss`, `*.html`, `*.swift`, `*.swiftui`, `*.kt`, `*.kts`, `tailwind.config.*`, `components.json`, `theme.ts`). If none, **omit the section** and append a one-line note in the plan:

> *Router flagged `ui_work: true`, but plan touches no render layer — UX Defaults section omitted.*

This prevents a backend task ("dump UI config to JSON") from triggering a defaults section it doesn't need.

### Required fields (six, plus state plan)

Pick the inference row from `resources/ux-guidebook.md §4.9` that matches the prompt's strongest signal. When in doubt, default to the last row (`slate / comfortable / content-forward / required` + accent `#2563eb`).

1. **Mobile:** `required / optional / no`. If `required`, name the desktop ↔ mobile divergence approach (independent toolbars / responsive shrink / drawer).
2. **Gray ramp:** one of `slate / stone / neutral / zinc / gray`. One-line rationale.
3. **Density:** `comfortable` or `compact`. One-line rationale.
4. **Ratio:** `content-forward` or `chrome-dense`. One-line rationale.
5. **Accent:** hex value, defaulting to `#2563eb` (Tailwind `blue-600`) if not specified.
6. **Destructive actions:** `none` if the prompt names no deletion / revocation / billing / data-loss surfaces; otherwise list each one with the confirmation + undo plan. Default to `none — none identified in prompt`; sharpen Q6 catches anything the planner missed at refinement time.

Plus **exactly one sentence each for empty, loading, and error states** — three sentences total. Concrete copy, not "TBD."

The plan-presentation menu in `workflow.md` discloses to the user that `/sharpen ux-defaults` is available on UX quests (the menu wording branches on the presence of this section in the plan). **Do not append a `/sharpen ux-defaults` pointer at the end of the emitted block** — the menu carries that disclosure, and duplicating it inside the plan body buries it where the executive summary doesn't reach.

### Opt-out for UX-savvy prompts

If the user prompt or quest brief already **explicitly names ≥3 of the six defaults** (mobile, gray ramp, density, ratio, accent, destructive actions), emit a shortened block listing only the unspecified fields, plus a one-line acknowledgement of the ones the user did specify.

**"Explicitly named" means a token that directly maps to one of the six field values:** `slate`/`stone`/`neutral`/`zinc`/`gray` for ramp; `comfortable`/`compact`/`dense` (and synonyms `tight`/`spacious`) for density; `content-forward`/`chrome-dense` for ratio; `mobile`/`mobile-first`/`desktop-only`/`responsive` for mobile relevance; a literal hex (`#0070f3`) or named brand color for accent; an explicit mention of deletion/revocation/billing/data-loss surfaces for destructive. **Brand references like "Vercel-like" or "Linear-style" do NOT count as named defaults** — even when they imply a default, the protocol uses literal naming for trigger consistency. If the user wants the shortened block, they must say it.

**Why brand references are excluded — and what to use instead.** Brand-implied defaults drift over time (one company's "Vercel-like" today is not the same as next year), so the opt-out predicate stays on literal tokens for stability rather than a maintenance-heavy brand-mapping layer. The planner can still use a brand reference as a *signal* for picking an inferred row from the §4.9 table (e.g. "Linear-style" → the `slate / comfortable / content-forward` row), and the resulting `## UX Defaults` block is still surfaced to the user at the plan-approval gate. If the inferred row needs refinement, `/sharpen ux-defaults` walks the six fields one at a time — that is the user's lightweight path when literal tokens were missing from the prompt.

Example shortened block:

```markdown
## UX Defaults

User specified: gray ramp `slate`, density `compact`, accent `#0f172a` text. Inferred:

- Ratio: chrome-dense — implied by Vercel-like reference.
- Mobile: optional — internal dashboard.
- Destructive actions: none — none identified in prompt.
- Empty / loading / error: skeleton rows, inline form-error preservation, plain-language messages.
```

---

## Step 4: Cite when you decide

Any UX-affecting decision in your plan, code, or commit should cite the principle: `(ux-guidebook §4.2 #3)`. Canonical format is `ux-guidebook §<section>[ #<bullet>]` — the section number always, the `#<bullet>` suffix when a specific sub-bullet applies (matching the guidebook's own numbering and `.skills/ux-review/SKILL.md`). This makes the design rationale auditable and greppable downstream (`grep -rn "ux-guidebook"`).

## Key Principles (excerpt — see guidebook for full set)

1. **Visual chrome restrained; content density task-appropriate.** Not minimalism — restraint.
2. **A button must look pressable before it can look beautiful** (Norman).
3. **Every action confirms within ~100ms; every commit has closure.** Quiet does not mean silent.
4. **Don't fake instant when you mean pending** (Rams #6). Performance is UX.
5. **Don't paste one OS's chrome into another.** Same icon, native behavior is fine; same chrome across platforms is broken.

## Companion Skill

For *reviewing* existing UI, see `.skills/ux-review/SKILL.md`. This skill is for *producing* work; ux-review is for critiquing it. Both consume the same guidebook resources.

## Bundled Resources

- `resources/ux-guidebook.md` — canonical guidebook (inference table at §4.9)
- `resources/ux-stress-test.md` — runnable rubric and checklists

## Related Skills

- `.skills/ux-review/SKILL.md` — invokes the stress test against a target
- `.skills/sharpen/SKILL.md` — `ux-defaults` mode walks the same six fields one at a time as a refinement interview
- `.skills/plan-maker/SKILL.md` — the planner consumes both during plan creation
- `.skills/implementer/SKILL.md` — the builder consumes ux-context during implementation
- `.skills/code-reviewer/SKILL.md` — code reviewers cross-reference ux-review findings
