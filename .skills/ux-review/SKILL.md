# UX Review

Run the canonical UX stress-test rubric against a target (file, directory, URL, screenshot, or git diff) and produce a structured critique report. Used by reviewer agents during the quest pipeline, and directly invokable by users with `/ux-review` or `$ux-review`.

At activation, announce the skill name and scope in one line. Example: `[ux-review] reviewing src/components/SettingsPanel.tsx against ux-guidebook`.

## When to Use

- **Direct user invocation:** `/ux-review <path|url|image>` or `$ux-review <path|url|image>`. The developer is asking for a UX critique of a specific surface.
- **Quest pipeline:** Plan-reviewer and code-reviewer agents invoke this skill when the router classified the quest as `ui_work: true`. The review findings flow into the arbiter alongside other review signals.
- **Triaging a clunky existing project:** Walk the red-flags and stress-test against the codebase or a deployed app to produce a prioritized punch list.

Do **not** use this skill for taste-only preferences (lowercase vs sentence case, font selection, accent hue). Flag inconsistency, never preference.

## Knowledge Source

This skill sources its rubric and principles from the canonical UX guidebook bundled with the companion `ux-context` skill:

- **Guidebook:** `.skills/ux-context/resources/ux-guidebook.md`
- **Stress-test rubric:** `.skills/ux-context/resources/ux-stress-test.md`

Load these before reviewing. They are the single source of truth — do not improvise principles.

## Procedure

### Step 1: Identify the target

Determine what is being reviewed:

| Target type | How to gather evidence |
|---|---|
| File path | Read the file. If it's a component, also read its CSS / Tailwind classes and any related design tokens. |
| Directory | Walk the directory; identify component files, design tokens (`globals.css`, `tailwind.config.*`, `theme.ts`), and any screenshot in the repo. |
| URL | Fetch with WebFetch (and request a screenshot if available). Note: WebFetch may fail on authenticated URLs. |
| Screenshot/image | Read the image. Visual-only review — no DOM heuristics. |
| Git diff | Run `git diff --name-only` and review only the UI-relevant changed files. |
| No target | Review the staged and locally-uncommitted UI changes in the current repo. |

### Visual evidence path (URL / local app targets)

When the target is a URL, local dev server, or rendered app surface and browser automation is available, collect visual evidence before filing findings:

1. Capture screenshots at `375px`, `768px`, `1280px`, and `1920px` widths when practical.
2. Retrieve the DOM / accessibility snapshot if the tool supports it.
3. Check keyboard focus visibility, obvious contrast failures, overflow, overlap, clipping, and touch-target problems at the relevant viewports.
4. Include viewport or screenshot-region evidence in each finding.
5. If a standalone user explicitly asks you to fix issues, fix one issue at a time and re-capture the affected viewport before reporting it resolved.

Quest-pipeline invocations are review-only: produce findings and evidence, but leave source edits to the builder/fixer phases.

### Step 2: Load the rubric

Read `.skills/ux-context/resources/ux-stress-test.md` in full. The rubric has four sections:

1. **12-question stress test** (universal, every UI)
2. **15-point red flags** (telltale signs of carelessness)
3. **20-point mobile-feel checklist** (when the target is mobile-relevant)
4. **15-point Mac-native checklist** (when the target is a macOS app)

If unsure whether the target is mobile-relevant, check for: viewport meta tags, `dvh`/`vh` units, `env(safe-area-inset-*)` usage, mobile-specific component files, or breakpoint usage at `sm`/`md`.

### Step 3: Walk the rubric against the target

For each rubric item, classify as:
- **PASS** — the principle is honored
- **FAIL** — the principle is violated; record evidence
- **N/A** — the principle doesn't apply to this surface (justify briefly)

For each FAIL, gather:
- `file:line` reference or screenshot region
- The visible symptom
- The canonical principle violated (section ID from the guidebook, e.g. `§4.2 #3` or `RF-7`)
- The smallest fix that resolves it
- One sentence on user impact

### Step 4: Triage by severity

Group findings using the severity rubric from `ux-stress-test.md`:

- **P0 — Signifier loss.** User cannot tell what is clickable. Block ship.
- **P1 — Feedback loss or destructive trap.** Action commits silently, or no undo. Block ship.
- **P2 — Consistency violation.** Same thing means two different things in the product. Fix this sprint.
- **P3 — Chrome bloat.** Decorative borders/shadows/colors that don't earn their ink. Fix when free.

### Step 5: Produce the report

Output a markdown report in this exact shape:

```markdown
## /ux-review report

**Target:** <path | url | screenshot description>
**Surface area:** <which screens/components/states>
**Reviewed against:** ux-guidebook (.skills/ux-context/resources/ux-guidebook.md)
**Score:** N findings (P0: x, P1: y, P2: z, P3: w)

### P0 findings (block ship)

#### [P0] [§<section>] <one-line description>

- **Where:** path/to/file.tsx:42 (or screenshot region)
- **Symptom:** what's visible
- **Principle violated:** [§4.2 #3 — color is semantic, not decorative](.skills/ux-context/resources/ux-guidebook.md#42-color)
- **Smallest fix:** the minimum change that resolves it
- **User impact:** one sentence

### P1 findings (block ship)
... same shape ...

### P2 findings (fix this sprint)
... same shape ...

### P3 findings (fix when free)
... same shape ...

### Bright spots
<3-5 specific things the target does well, with file:line evidence. The punch list needs a counterbalance — agents and humans alike review better when good is named alongside bad.>

### Methodology
- Rubric: ux-stress-test.md (12-Q + 15 red flags + 20-point mobile + 15-point Mac-native)
- Items walked: <count>
- N/A items: <count>
```

### Step 6: Phase-specific output routing

**Step 6 only applies to quest-pipeline invocations.** Standalone runs (a developer typing `/ux-review path/to/file.tsx`) end at Step 5 with the markdown report — skip this section.

**`principle_id` format:** `ux-guidebook§<section_number>` — e.g. `ux-guidebook§4.2`. No spaces, no sub-bullet numbers, no `#` suffix. This format is greppable for audit and enforcement.

**Plan-review phase (plan-reviewer-a / plan-reviewer-b):**
Run a plan-phase UX intent pass instead of the rendered-UI stress test. Check whether the plan makes the UX decisions explicit enough to build and review:

- `## UX Defaults` is present when the plan touches a render layer and the brief has `ui_work: true`.
- The defaults cover the six required fields from `ux-context`, in canonical order: **mobile, gray ramp, density, ratio, accent, destructive actions**.
- Empty, loading, and error states have **exactly one sentence each** of concrete copy/behavior — not `TBD`, not multi-sentence paragraphs. Three sentences total.
- Mobile is justified; if mobile is `required`, the plan names a divergence approach.
- Destructive actions have confirmation and undo/recovery treatment, or are explicitly marked `none`.

Embed UX findings inline in the markdown review using the standard `[N]` format with the principle citation appended. The arbiter synthesizes findings from the two markdown plan reviews; plan-reviewers do **not** write a separate findings JSON.

Example markdown finding:
```markdown
[N] Must fix - plan.md:Acceptance Criteria - the settings page plan lists "Save" and "Cancel" buttons styled identically; no primary action is named (ux-guidebook§2 — make the possible visible: every affordance needs a signifier).
```

**Code-review phase (code-reviewer-a / code-reviewer-b):**
Write canonical findings JSON to the reviewer's slot path under `.quest/<id>/phase_03_review/`. Use the canonical schema from `.skills/code-reviewer/SKILL.md`. All list fields must be `list[str]`, never scalar:

```json
{
  "finding_id": "ux-button-no-hover-7",
  "source": "ux-review",
  "kind": "ux",
  "severity": "high",
  "confidence": "high",
  "path": "src/components/Settings.tsx",
  "line": 87,
  "summary": "Primary Save button has no hover or active state",
  "why_it_matters": "Users cannot tell the button is interactive without clicking; keyboard users have no focus indicator.",
  "evidence": ["<button className=\"bg-blue-600 text-white px-4 py-2\">Save</button>"],
  "action": "Add hover:bg-blue-700 active:bg-blue-800 focus-visible:ring-2 focus-visible:ring-blue-400",
  "needs_test": false,
  "write_scope": ["src/components/"],
  "related_acceptance_criteria": [],
  "principle_id": "ux-guidebook§4.8",
  "principle_ref": ".skills/ux-context/resources/ux-guidebook.md#48-keyboard--accessibility"
}
```

**Severity mapping:**
- P0 → `critical` (block ship — signifier loss)
- P1 → `high` (block ship — feedback loss, destructive trap)
- P2 → `medium` (consistency violation — fix this sprint)
- P3 → `low` (chrome bloat — rides the existing `select_decision` rules: `drop` at high confidence, `defer` at low confidence; no UX-specific override)

## Key Principles

- **Cite the principle by section ID on every finding.** Audit trail beats authority.
- **Smallest fix, not redesign.** Tesler's Law: you'd just move complexity.
- **Never flag preference as a finding.** Lowercase headings, accent hue, font choice — these are taste. Only flag inconsistency (same product, two registers; same product, two accent colors).
- **Bright spots are required.** A review without named strengths reads as nitpicking. Name three to five things the target does well.
- **One severity per finding.** If a finding spans two severities, split it.

## Output Format Examples

### Example: a failing button

```markdown
#### [P0] [§4.1 — typography / §RF-12] Button has no hover or active state

- **Where:** src/components/Settings.tsx:87 — `<button className="bg-blue-600 text-white px-4 py-2">Save</button>`
- **Symptom:** No `hover:`, `active:`, or `focus-visible:` styling. The button looks the same before, during, and after the cursor lands on it.
- **Principle violated:** [§RF-12 — buttons without hover or active states](.skills/ux-context/resources/ux-stress-test.md#red-flags-15-point-diagnostic) and Norman's signifier rule from `ux-guidebook§2`.
- **Smallest fix:** Add `hover:bg-blue-700 active:bg-blue-800 focus-visible:ring-2 focus-visible:ring-blue-400`.
- **User impact:** User cannot tell the button is interactive without clicking it; keyboard users have no focus indicator.
```

### Example: a bright spot

```markdown
### Bright spots

- **`src/app/globals.css:14`** — `--radius: 0rem` enforced globally via `* { border-radius: 0 !important; }`. One radius token, one enforcement point. Honors §4.4 #2 (one elevation style per level) and the broader restraint principle.
- **`src/components/EmptyHint.tsx:7`** — Empty state copy *names the action that fills it*: "Draw or insert something and it will appear here." Honors §4.7 #1.
- **`src/app/globals.css:42`** — `button:active { transform: scale(0.96); }` global rule gives every button a satisfying press without per-component animation. Honors §4.5 #6.
```

## Command Invocation

Run `gh` and `git` commands directly — not through `bash -lc`, `sh -c`, or other shell wrappers. Permission prefixes only match when the binary is the top-level command. Use shell wrappers only when you need pipes, redirects, or multi-command composition.

## Related Skills

- `.skills/ux-context/SKILL.md` — the primer; loaded by planners/builders/fixers when `ui_work: true`. Owns the guidebook and stress-test resources.
- `.skills/code-reviewer/SKILL.md` — code reviewers run this alongside ux-review on `ui_work: true` quests.
- `.skills/plan-reviewer/SKILL.md` — plan reviewers run this against the plan to verify UX intent is explicit before build.
- `.skills/pre-commit-review/SKILL.md` — local pre-commit reviewers can include ux-review for UI changes.
