---
title: UX Stress Test — Pre-Commit Checklist
purpose: The runnable 12-question rubric and 15-point red-flag list from the UX guidebook. Use before commit, in PR review, or to triage a clunky project.
audience: Engineers self-reviewing UI work; PR reviewers giving UX feedback.
scope: Project-agnostic. Pairs with ux-guidebook.md.
status: active
owner: maintainers
---

# UX Stress Test

*If you can't honestly tick all twelve, you have UX debt.*

This is the runnable companion to [ux-guidebook.md](./ux-guidebook.md). Walk it before commit. Use it as the rubric in PR review. Use it to diagnose a clunky existing project before deciding what to redesign.

Any "no" requires either a fix or an explicit, defensible exception logged in the PR description.

---

## The 12-question rubric

Run against each screen, component, or interaction you changed.

### 1. Signifier
- [ ] A first-time user can tell what's interactive **without hovering**.
- [ ] Icon-only buttons have a visible label, tooltip, or `aria-label`.
- [ ] No "is that clickable?" mystery boxes.

> *Rationale: Norman's first principle. A button must look pressable before it can look beautiful.*

### 2. Feedback
- [ ] Every action produces a visible system response within ~100ms.
- [ ] Every commit (save, send, submit) has explicit closure — a state change, a toast, a redirect, a checkmark.
- [ ] Destructive actions confirm or are undoable.

> *Rationale: Nielsen #1 (visible system status), Norman (gulf of evaluation), Shneiderman #3 (closure). "Quiet by default" must not mean silent on commit.*

### 3. Mental model
- [ ] The screen describes the user's task, not your data schema.
- [ ] Terms used match the user's vocabulary, not the implementation's.

> *Rationale: Cooper's represented-model rule. If you're explaining your schema in the UI, you've lost.*

### 4. Consistency
- [ ] The same word means the same thing throughout the product.
- [ ] The same color means the same thing throughout the product.
- [ ] The same component looks and behaves the same wherever it appears.
- [ ] Platform conventions are honored (⌘W closes, Esc cancels, Tab moves forward, etc.).

> *Rationale: Nielsen #4. Consistency beats cleverness.*

### 5. Error prevention
- [ ] The most destructive action on this screen is harder to hit than the constructive ones.
- [ ] Inputs are constrained at the source (type, min/max, pattern) rather than validated only after submit.
- [ ] Impossible options are disabled, not just shown-and-rejected.

> *Rationale: Nielsen #5. The best error message is the one the user never has to read.*

### 6. Reversibility
- [ ] The user can undo what they just did, or back out without consequence.
- [ ] Multi-step flows have a clear back path that preserves entered data.
- [ ] No traps: no flow that the user can enter but not exit.

> *Rationale: Shneiderman #7, Nielsen #3.*

### 7. Recognition
- [ ] No screen asks the user to remember information from a previous screen.
- [ ] Selections, filters, sort orders are visible, not implicit.

> *Rationale: Nielsen #6, Miller. Working memory is for the task, not for your UI.*

### 8. Reach (Fitts)
- [ ] The primary action is large (≥44pt touch / ≥24px pointer).
- [ ] Frequent actions are near where the eye and hand are.
- [ ] Common actions are edge- or corner-anchored where possible (screen edges are infinite-size targets).
- [ ] Adjacent touch targets have ≥8px between them.

> *Rationale: Fitts's Law (size + distance + edge advantage), Apple HIG, Material.*

### 9. Defaults
- [ ] The default value is what 80% of users want.
- [ ] If a setting has a "recommended" choice, it is the default.
- [ ] No required field has a value the user must change before submit succeeds.

> *Rationale: Tognazzini. Defaults are the most-used setting.*

### 10. Honesty
- [ ] Copy doesn't overstate what the system does.
- [ ] Progress indicators reflect real progress (not animated decoration).
- [ ] Shadows, glows, and gradients aren't faking depth that isn't there.
- [ ] Optimistic UI is used only where success is overwhelmingly likely; **never for money, irreversible destructive actions, or data loss.**

> *Rationale: Rams #6, Norman, Tognazzini. Don't fake instant when you mean pending. Honest progress, honest depth.*

### 11. Density vs chrome
- [ ] Every border, shadow, and divider is separating things the user actually needs separated.
- [ ] Gap between grouped elements > gap within an element.
- [ ] Task content matches frequency: expert at ≥10×/day → density wins; stranger at once a month → chrome restraint wins.
- [ ] Chrome is restrained; content is Tufte-dense where the task calls for it.

> *Rationale: Tufte (data-ink ratio), Rams #10, Gestalt (proximity). Density without grouping is noise; minimalism without signifiers is mystery.*

### 12. Scan test
- [ ] Reading only the headings, button labels, and first line of each paragraph, the user can still complete the task.
- [ ] Important information is not buried in the second sentence.

> *Rationale: Krug, Redish. Users scan, don't read.*

---

## Red flags (15-point diagnostic)

Use this to triage a clunky project before deciding what to fix. Each hit gets a screenshot or `file:line` reference in the report.

- [ ] **RF-1** Two or more buttons styled with equal weight on the same screen — no clear primary.
- [ ] **RF-2** Pure `#000` text on `#FFF` background, or pure `#000` background in dark mode.
- [ ] **RF-3** Pixel-arbitrary spacing (`padding: 13px 17px`, `margin-top: 7px`) — no grid.
- [ ] **RF-4** Three+ typefaces, or four+ font sizes that don't follow a scale.
- [ ] **RF-5** `outline: none` on focus with no `:focus-visible` replacement.
- [ ] **RF-6** Body text 16px+ in a dense app — children's-tutorial smell.
- [ ] **RF-7** Decorative color (rainbow tags, gradient on every card) with no semantic meaning.
- [ ] **RF-8** Per-component hand-rolled `box-shadow` — no shared elevation tokens.
- [ ] **RF-9** Spinners that flash for <300ms, or full-page spinner when a skeleton would do.
- [ ] **RF-10** Error message reading "Something went wrong" or showing a raw stack trace / error code.
- [ ] **RF-11** Empty states that are literally empty — no copy, no CTA, no teaching moment.
- [ ] **RF-12** Buttons without hover or active states.
- [ ] **RF-13** Modal dialogs for trivial operations (rename, toggle a setting).
- [ ] **RF-14** On Mac: stub menu bar, custom traffic lights, or iOS-sized touch targets.
- [ ] **RF-15** Animations on every keystroke, every list update, every navigation — death by 250ms.

---

## Mobile-feel pass/fail (web apps)

Run when a web app is expected to feel right on a phone.

- [ ] **MF-1** `<meta viewport>` includes `viewport-fit=cover` and `interactive-widget=resizes-content`.
- [ ] **MF-2** All tappable elements ≥44×44px, with ≥8px gap between adjacent targets.
- [ ] **MF-3** No interaction depends solely on hover; `@media (hover: none)` paths tested.
- [ ] **MF-4** Inputs have `font-size: ≥16px` and correct `inputmode` / `autocomplete`.
- [ ] **MF-5** Full-height containers use `100dvh` (with `100vh` fallback), not raw `100vh`.
- [ ] **MF-6** Bottom toolbars/CTAs add `padding-bottom: env(safe-area-inset-bottom)`.
- [ ] **MF-7** Top app bar respects `env(safe-area-inset-top)`; landscape respects left/right insets.
- [ ] **MF-8** Primary CTA lives in the bottom-center thumb zone on phone widths.
- [ ] **MF-9** Tab bar has 3–5 items, anchored bottom, items navigate (never trigger actions or sheets).
- [ ] **MF-10** Pull-to-refresh disabled where it conflicts (`overscroll-behavior: contain`).
- [ ] **MF-11** Long-press, swipe-to-delete, and any gesture-only action have a visible alternative.
- [ ] **MF-12** Destructive list-row actions either confirm or are undoable.
- [ ] **MF-13** Body text ≥16px in `rem`, line-height 1.4–1.5, line length ≤75ch.
- [ ] **MF-14** Waits <300ms show nothing; 0.3–1s show skeleton; >1s show progress; >10s have cancel + estimate.
- [ ] **MF-15** Optimistic UI on like/favorite/send; never on payment/upload.
- [ ] **MF-16** App shell renders meaningful content within ~1s on a mid-tier Android over 4G.
- [ ] **MF-17** Scroll is 60fps on a 2-year-old phone at production list lengths.
- [ ] **MF-18** Custom horizontal swipes stay >20px from the left edge (don't fight iOS back-swipe).
- [ ] **MF-19** Layout survives iPad Split View at 320px width without horizontal scroll.
- [ ] **MF-20** Keyboard appearing doesn't cover the focused input or the primary action.

---

## Mac-native feel pass/fail (macOS apps)

Run when shipping a macOS-native app or a desktop Electron/Tauri shell that wants to feel native.

- [ ] **MN-1** Menu bar is fully populated; every command reachable from a menu.
- [ ] **MN-2** `⌘W`, `⌘Q`, `⌘,`, `⌘N`, `⌘S`, `⌘Z`, `⌘⇧Z`, `⌘F` all behave as expected.
- [ ] **MN-3** Traffic lights top-left; all three buttons do something sensible.
- [ ] **MN-4** Top-level navigation lives in a sidebar (`NavigationSplitView`), not a top tab bar.
- [ ] **MN-5** Sidebar, toolbar, popovers, sheets use system materials / vibrancy.
- [ ] **MN-6** Light and Dark Mode both render correctly; no hardcoded colors.
- [ ] **MN-7** System accent color tints buttons, selection, and focus rings.
- [ ] **MN-8** Every icon-only toolbar button has a `.help()` tooltip.
- [ ] **MN-9** Settings opens via `⌘,` as a separate window scene (not a sheet).
- [ ] **MN-10** Every selectable item supports a context menu via right-click / two-finger tap.
- [ ] **MN-11** Scrollbars are system-native (auto-hiding overlay), not custom.
- [ ] **MN-12** Focus rings visible on keyboard navigation; full-keyboard-access works.
- [ ] **MN-13** Drag-and-drop works for the obvious cases (files in/out, reordering).
- [ ] **MN-14** Sheets attach to their parent window; alerts reserved for genuine alerts.
- [ ] **MN-15** App responds to Hide, Hide Others, ⌘-Tab, full-screen, multiple windows.

---

## Output format when reviewing a clunky project

When using this as a critique tool on someone else's UI, produce findings in this shape per item:

```
### [Severity] [Principle ID] — Brief description

**Where:** path/to/file.tsx:42 (or screenshot.png region)
**Symptom:** what's visible
**Principle violated:** which canonical principle (link to ux-guidebook.md section)
**Smallest fix:** the minimum change that resolves it
**Why this matters:** one sentence on the user impact
```

Severity rubric:
- **P0** — Signifier loss (user can't tell what's clickable). Block ship.
- **P1** — Feedback loss (action commits silently) or destructive trap (no undo). Block ship.
- **P2** — Consistency violation (same thing means two different things). Fix this sprint.
- **P3** — Chrome bloat (decorative borders/shadows/colors). Fix when free.

Resist the urge to redesign. Tesler's Law: you'd just move the complexity.
