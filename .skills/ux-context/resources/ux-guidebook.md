---
title: The UX Guidebook for Engineers
purpose: A canonical, opinionated standard for clean, intuitive, restrained UX across web, mobile-web, and macOS-native software. Used to self-review work and to critique clunky projects.
audience: Engineers reviewing their own UI work; reviewers giving UX feedback on PRs; teams onboarding a new repo to this standard.
scope: Repo-wide and project-agnostic. Travels to any future repo.
status: active
owner: maintainers
---

# The UX Guidebook for Engineers

> Great UX is the minimum friction between user intent and outcome, expressed through **restrained visual chrome**, **task-appropriate content density**, **durable affordances**, **honest feedback**, and **respect for the user's attention and time**.

This is a guidebook for engineers, not designers. Its job is to help you review your own UI in five minutes and improve it in one. It is anchored in the canon ([Norman](https://jnd.org/books/the-design-of-everyday-things-revised-and-expanded-edition/), [Rams](https://www.vitsoe.com/us/about/good-design), [Nielsen](https://www.nngroup.com/articles/ten-usability-heuristics/), [Tognazzini](https://asktog.com/atc/principles-of-interaction-design/), [Shneiderman](https://www.cs.umd.edu/users/ben/goldenrules.html), [Cooper](https://www.gregbulla.com/TechStuff/Docs/NotesFromAboutFace3.htm), [Tufte](https://faculty.cc.gatech.edu/~stasko/7450/16/Notes/tufte.pdf), [Krug](https://blas.com/dont-make-me-think/)) and validated against modern execution ([Apple HIG](https://developer.apple.com/design/human-interface-guidelines/), [Refactoring UI](https://refactoringui.com/), [Linear Method](https://linear.app/method), [Vercel Geist](https://vercel.com/geist/introduction), [Rauno on interaction](https://rauno.me/craft/interaction-design)).

The companion file [ux-stress-test.md](./ux-stress-test.md) is the runnable checklist you pull up before commit.

---

## 1. Thesis

The word doing the most work in the opening line is *restrained*, not *minimal*. Minimalism fails when it removes signifiers along with chrome (Norman). Restraint succeeds when chrome recedes and the user's task takes the center of the screen.

The word doing the second most work is *task-appropriate*. Density is not the enemy. IDEs, Linear, Bloomberg Terminal, Figma, and Notion are all visually dense and canonically tasteful. **Visual chrome gets minimalism; task content gets [Tufte](https://faculty.cc.gatech.edu/~stasko/7450/16/Notes/tufte.pdf)** — high data-ink ratio, layered separation, no chartjunk. Telling an engineer to "remove things" without this distinction produces anemic empty-screen design.

---

## 2. The 14 durable principles

The spine. Every recommendation in the rest of this book derives from these; none contradicts them.

1. **Match the user's mental model, not your implementation.** ([Norman](https://jnd.org/books/the-design-of-everyday-things-revised-and-expanded-edition/); [Cooper](https://www.gregbulla.com/TechStuff/Docs/NotesFromAboutFace3.htm))
2. **Make the possible visible: every affordance needs a signifier.** A button must look pressable before it can look beautiful. ([Norman](https://jnd.org/books/the-design-of-everyday-things-revised-and-expanded-edition/); [Tognazzini](https://asktog.com/atc/principles-of-interaction-design/))
3. **Confirm every action with timely, proportional feedback.** ([Norman](https://jnd.org/books/the-design-of-everyday-things-revised-and-expanded-edition/); [Nielsen #1](https://www.nngroup.com/articles/ten-usability-heuristics/); Shneiderman #3)
4. **Stay consistent — within the product, with the platform, with conventions.** Conventions exist for reasons. ([Nielsen #4](https://www.nngroup.com/articles/ten-usability-heuristics/); [Krug](https://blas.com/dont-make-me-think/))
5. **Prevent errors before designing recovery. When recovery is needed, make it cheap and reversible.** ([Nielsen #5, #9](https://www.nngroup.com/articles/ten-usability-heuristics/); Shneiderman #5, #6)
6. **Prefer recognition over recall. Never make users carry state between screens.** ([Nielsen #6](https://www.nngroup.com/articles/ten-usability-heuristics/); [Miller](https://lawsofux.com/millers-law/))
7. **Honor [Fitts's Law](https://lawsofux.com/fittss-law/): size, place, and edge-anchor in proportion to frequency and importance.** Screen edges and corners are infinite targets. ([Tognazzini](https://asktog.com/atc/principles-of-interaction-design/))
8. **Choose defaults with surgical care — they are the most-used setting.** ([Tognazzini](https://asktog.com/atc/principles-of-interaction-design/))
9. **Be honest: don't fake capability, don't fake progress, don't fake depth.** ([Rams #6](https://www.vitsoe.com/us/about/good-design); Norman)
10. **Be as little design as possible — but no less than the task requires.** Complexity is conserved ([Tesler](https://lawsofux.com/teslers-law/)); you can only relocate it. ([Rams #10](https://www.vitsoe.com/us/about/good-design); [Nielsen #8](https://www.nngroup.com/articles/ten-usability-heuristics/); [Tufte](https://faculty.cc.gatech.edu/~stasko/7450/16/Notes/tufte.pdf))
11. **Keep the user in control: explorable, reversible, never trapped.** (Shneiderman #7; Nielsen #3)
12. **Respect the user's attention and time: anticipate needs, stay within perf budgets, get out of the way.** *Performance is a UX feature — perceived latency is real latency. Ship perf budgets in the design system alongside colors and spacings.* ([Tognazzini](https://asktog.com/atc/principles-of-interaction-design/); [Krug](https://blas.com/dont-make-me-think/))
13. **Design for the perpetual intermediate, not the novice or expert.** Most users are neither — they're learning but not learners; productive but not power-users. Learnable but not condescending, efficient but not opaque. ([Cooper](https://www.gregbulla.com/TechStuff/Docs/NotesFromAboutFace3.htm))
14. **Heuristics catch ~75% of issues. Watch one real user before shipping.** Heuristic evaluation is a complement to user testing, not a replacement. One user, one task, observed end-to-end will find what 14 rubric items can't. ([Nielsen](https://www.nngroup.com/articles/ten-usability-heuristics/))

---

## 3. The central reconciling rule

> **Visual chrome should be restrained. Task content should be as dense as the task earns. Density without grouping is noise; minimalism without signifiers is mystery.**

**Deciding test for task-appropriate density:** if an expert uses this screen ≥10×/day, density wins; if a stranger uses it once a month, chrome restraint wins. The middle case is "restraint as floor, density as opt-in" — e.g. Stripe Dashboard ships chrome-restrained by default with dense table views the user can toggle. Earn density as you earn frequency; don't impose it upfront.

Two flanking pitfalls:

- **Anemic minimalism** — chrome removed *and* signifiers removed. The "is that clickable?" UI. Tesler's Law says you didn't remove the complexity — you moved it onto the user's mental load.
- **Cluttered density** — content added without [Gestalt](https://www.figma.com/resource-library/gestalt-principles/) grouping. Jira and Linear ship comparable information density; one feels noisy, the other calm. The difference is grouping discipline, not pixel count.

---

## 4. The discipline

Concrete, prescriptive rules. Each subsection is independently usable as a pre-commit checklist for that domain.

### 4.1 Typography

1. **Two typefaces max.** One sans for UI, one mono for code/numerics. Three is a tell; four is broken.
2. **Modular scale, not arbitrary px.** Use Apple's [system text styles](https://developer.apple.com/design/human-interface-guidelines/typography) or Tailwind's `text-xs / sm / base / lg / xl / 2xl / 3xl`. Never `font-size: 13px` next to `font-size: 14px` — pick one.
3. **App chrome 13–15px; prose 16–18px.** **Default to chrome at 13–15** — modal bodies, empty-state copy, toast text, error explanations, settings descriptions all count as chrome even when the text is long. **Only the user's actual content** (an article, a doc, the editor body) gets prose at 16+. 16px-everywhere is a children's-tutorial smell. On Mac native, system body is 13pt.
4. **Line-height inversely with size.** Body 1.5–1.6. UI labels 1.2. Display headings 1.1–1.25.
5. **Cap measure at 60–75 ch.** `max-width: 65ch` on prose.
6. **Weight is hierarchy. Use it before size.** Semibold (600) next to Regular (400) creates hierarchy without layout shift.
7. **Soften pure black.** `#0f172a` to `#1a1a1a` reads cleaner than `#000` on emissive screens. Pure black cannot cast a shadow in dark mode.
8. **`font-variant-numeric: tabular-nums` on any column of numbers.** Money, timestamps, counters.
9. **Mobile inputs: `font-size: 16px` minimum.** Anything smaller triggers iOS Safari auto-zoom. Do *not* fix this with `maximum-scale=1` — it breaks accessibility zoom.

### 4.2 Color

1. **You need more grays than you think.** Plan 8–10 grays before designing. Almost every pixel in a UI is gray.

2. **Tint your grays — pick from this menu, don't roll your own.** Pure `#888` looks dead. Five aesthetics, five Tailwind ramps:

   | Brand color / aesthetic | Recommended ramp | Examples that ship this |
   |---|---|---|
   | No brand yet / cool brand (blue/purple/teal/green) | `slate` (cool blue-gray) | Linear, Vercel, Stripe, modern SaaS defaults |
   | Warm brand (orange/amber/red/yellow) | `stone` (warm beige-gray) | Things, Day One, Substack |
   | Utilitarian / explicitly monochrome | `neutral` (true gray) | Bloomberg, terminal UIs |
   | Tech/scientific (high-contrast, blue-heavy) | `zinc` (slightly bluer than slate) | GitHub dark, Linear-dark |
   | Content-forward / paper feel (white-dominant, generous whitespace) | `gray` (true gray, light usage — surfaces mostly `#fff`, borders at `gray-200`, body at `gray-900`, middle steps rare) | Google, GitHub light, mockdown.design |

   **Two decisions, not one:** the *ramp* (slate / stone / neutral / zinc / gray) sets the temperature; the *white-to-gray ratio* sets the feel. Linear and Vercel use slate at high gray density (chrome dense). Google and GitHub use cool-grays at low density (white dominant). Pick both.

3. **Color is semantic, not decorative.** Red destructive, green positive, yellow warning, accent brand for primary action. **Once each per screen, max.** ([Refactoring UI: building your palette](https://refactoringui.com/previews/building-your-color-palette))
4. **9-shade ramps per hue.** Tailwind's `50 / 100 / ... / 900` is the de-facto standard. 50 for tinted backgrounds, 500 for primary action, 700 for hover, 900 for emphasized text.
5. **Never rely on color alone to convey meaning.** Pair red errors with an icon and a label. ~8% of men have color-vision deficiency.
6. **Contrast minimums (WCAG AA):** 4.5:1 body text, 3:1 large text and UI components.
7. **Dark mode = layered tinted grays, not inverted black.** Pure `#000` flattens depth.
8. **Desaturate brand colors 10–30% in dark mode.** Saturated brand vibrates painfully on near-black.

### 4.3 Spacing & density

1. **4pt or 8pt grid, no exceptions.** Every margin, padding, and gap snaps to multiples.
2. **Gap between cards > inner padding.** If a card has 16px inner padding, the gap *between* cards must exceed 16px (try 24–32px). Most common density mistake.
3. **Whitespace groups before borders do.** Two related fields with 8px gap need no surrounding box.
4. **Dense ≠ cluttered.** Linear, Things, Notion are dense yet calm because density is achieved through *tighter spacing within consistent typographic rhythm*, not by stuffing more elements in. Test: can you draw a clean column-line through every list row's left edge?
5. **Touch targets ≥44pt (iOS) / 48dp (Material); pointer targets ≥24px (WCAG 2.5.8), ideally ≥32px.** ([Apple HIG layout](https://developer.apple.com/design/human-interface-guidelines/layout))
6. **8px minimum between adjacent touch targets.** ([Material](https://m2.material.io/develop/web/supporting/touch-target))

### 4.4 Depth & elevation

1. **Reach order: tint < border < shadow.** Tinted background is the cheapest separator. Shadow only when the element is meant to feel detachable.
2. **One shadow style per elevation level.** Define `shadow-sm`, `shadow-md`, `shadow-lg` once. Stripe and Linear ship maybe 3 shadow tokens total.
3. **Soft and large, not hard and tight.** `box-shadow: 0 8px 24px rgba(0,0,0,0.08)` reads expensive. `box-shadow: 2px 2px 0 #000` reads like a 2003 CSS demo.
4. **"Flat but not flat."** Modern tasteful UI is mostly tonal flat layers with subtle elevation only where interaction demands it.
5. **Depth is hierarchy.** A sheet over a dimmed parent reads as "this is happening on top of, against, that."

### 4.5 Motion

1. **Ease-out for entrances, ease-in for exits.** Things appearing decelerate; things leaving accelerate away.
2. **Timing budget:** ≤100ms feels instantaneous. 100–200ms for direct response. 200–400ms for transitions. **>500ms requires a justification.**
3. **High-frequency actions don't animate.** Command palettes, context menus, every-keystroke updates open instantly. ([Rauno](https://rauno.me/craft/interaction-design))
4. **Motion communicates causality and spatial origin.** A modal that scales up from the button that opened it tells the user *this is that button's surface*.
5. **Interactions must be interruptible.** A drag that can't be cancelled mid-flight feels broken.
6. **Feedback at touch-down, not at click.** A button that responds when the finger lands feels alive.
7. **Honor `prefers-reduced-motion`.** Replace transforms with opacity fades; cut durations to ~0. Accessibility, not optional.
8. **Spring physics > linear timing for organic moves.** Drag-and-drop, pull-to-refresh, dismiss gestures.

### 4.6 Copy & voice

1. **Write like a person, not a system.** "Sign in" over "Authenticate". "Couldn't load your messages" over "Error 4032".
2. **Remove every word you can.** "Click here to delete this item" → "Delete." Button labels are verbs or verb phrases under 3 words.
3. **Errors state what happened, why, and what to do.** "Invalid input" is wrong. "Email needs an @ symbol" is right. (Nielsen #9.)
4. **Never wipe form input on validation failure.** Show the error next to the field, leave the values, focus the offending input.
5. **Don't shout. Don't grovel.** No "Oops!", no "Whoops!", no "Something went wrong, please try again." Both extremes are signs of a writer who didn't know what to say.
6. **Match the user's vocabulary** ([Nielsen #2](https://www.nngroup.com/articles/ten-usability-heuristics/)). "Tickets" not "Records." "Folders" not "Hierarchical containers."
7. **Pick a register and lock it. Default is sentence case** ("How it works"). Lowercase ("how it works") is a brand statement — earn it before adopting it. Mixing is never defensible. (Nielsen #4.)
8. **Personality budget.** If your product needs a voice, concentrate it in one ignorable corner (a mascot, a hero ASCII block, a 404 page). Spending zero personality is also correct — Stripe, Linear, Things ship with none. Do not sprinkle.

### 4.7 Empty, loading, and error states

1. **An empty state is the first onboarding screen.** Show *what should be here*, *why it isn't*, and *the exact action that fills it*. Linear's empty issue list says "No issues — press C to create one," teaching the keyboard shortcut at the moment it's relevant.
2. **Skeleton beats spinner when shape is known.** Use skeletons for content lists, cards, profiles. Reserve spinners for genuinely unknown durations.
3. **Show nothing under 300ms.** A spinner that flashes for 80ms is worse than no spinner.
4. **Three thresholds:** <100ms feels instant; 100ms–1s no spinner needed; 1–10s requires a progress indicator; >10s requires progress bar with cancel and estimate. ([Nielsen response-time limits](https://www.nngroup.com/articles/response-times-3-important-limits/))
5. **Optimistic UI for confident operations.** Like, favorite, send-message, mark-read, rename — update locally first, reconcile on response, animate a recovery on failure. **Never for money, irreversible destructive actions, or data loss.** UI must reflect actual state when reverting is impossible.
6. **First-run states deserve the most design care, not the least.** The empty inbox is when a user decides if your app is worth keeping.

### 4.8 Keyboard & accessibility

1. **Every primary action gets a keyboard shortcut.** `Cmd-K` command palette is now table stakes (Linear, Notion, Figma, Raycast, GitHub).
2. **Tab order follows visual order.** Test by tabbing through the whole screen. Fix the DOM, not `tabindex`.
3. **`:focus-visible` rings are a feature.** A 2px ring matching the brand color, offset by 2px. Stripping `outline: none` without a replacement is the most common a11y crime in modern CSS.
4. **Semantic HTML first; ARIA last.** `<button>` not `<div onclick>`. `<label for>` not floating text. First rule of ARIA: don't use ARIA.
5. **WCAG 2.5.8: interactive elements ≥24×24 CSS px minimum, ≥44×44 preferred on touch.**
6. **Trap focus only in modals, and trap it well.** Modal close must be Tab-reachable and Esc-dismissable.
7. **Test with VoiceOver / NVDA once per project.** Headings (`<h1>`–`<h6>`) form the screen-reader table of contents.

### 4.9 Defaults for new UI work

When a quest is classified as `ui_work: true`, the planner emits a `## UX Defaults` section in the plan with inferred values. This table is the canonical inference rubric: prompt signal → defaults. The planner picks the row whose signal best matches; sharpen's `ux-defaults` mode walks the same six fields one at a time.

| Prompt signal | Gray ramp (§4.2 #2) | Density (§3) | Ratio (§4.2 #2) | Mobile (§5.2) |
|---|---|---|---|---|
| "modern SaaS", "dashboard", "admin panel" | `slate` | comfortable | content-forward | optional |
| "developer tool", "IDE", "terminal", "CLI ui" | `zinc` | compact | chrome-dense | no |
| "consumer mobile app", "iOS", "Android" | `slate` | comfortable | content-forward | required |
| "marketing site", "landing page", "blog" | `gray` | comfortable | content-forward | required |
| "consumer settings", "account settings", "profile settings" | `slate` | comfortable | content-forward | required |
| "admin settings", "developer settings", "internal preferences" | `slate` | comfortable | content-forward | optional unless the prompt names mobile |
| "data table", "analytics" | `zinc` | compact | chrome-dense | no |
| "Bloomberg-style" (warm dense) | `stone` | compact | chrome-dense | no |
| "warm consumer brand", "food", "hospitality" | `stone` | comfortable | content-forward | required |
| "utilitarian", "monochrome" | `neutral` | varies | varies | varies |
| no signal / generic UI request | `slate` | comfortable | content-forward | required |

**Brand accent:** default `#2563eb` (Tailwind `blue-600`) unless the prompt or brief names a hex. **Six fields** the planner must emit, in order: mobile, gray ramp, density, ratio, accent, destructive actions — plus exactly one sentence each for empty/loading/error states. Anything else (primary action placement, mobile divergence pattern) is decided at implementation time, citing the relevant §.

---

## 5. Platform layers

### 5.1 Web responsive

Adopt Tailwind's default breakpoints (`sm 640 / md 768 / lg 1024 / xl 1280 / 2xl 1536`) unless you have a specific reason. Cap content at ~75ch at `2xl`. **Use container queries (`@container`) for components inside layouts that may collapse below their viewport** — sidebars, iPad split view, embedded panes — because viewport breakpoints alone break in those cases.

### 5.2 Mobile-feel (web AND native)

Non-negotiable rules. Pull these in on Day 1.

1. **Viewport meta** with `viewport-fit=cover` (paint to edge, past notch) and `interactive-widget=resizes-content` (layout reflows above keyboard).
2. **`100dvh`, not `100vh`.** On iOS Safari, `100vh` returns the largest viewport. Use `dvh` for adaptive, `svh` when content must always be visible, `lvh` to fill maximum. ([web.dev viewport units](https://web.dev/blog/viewport-units))
3. **`env(safe-area-inset-*)` on every fixed surface.** Bottom, top, plus left/right in landscape.
4. **Inputs at `font-size: 16px` minimum** to avoid iOS auto-zoom.
5. **Correct `inputmode` and `autocomplete`.** `inputmode="numeric"` for OTP, `autocomplete="one-time-code"` for SMS codes.
6. **Touch targets ≥44pt with ≥8px gaps.**
7. **Primary CTA in the thumb zone** — bottom-center third. Destructive actions go to top corners. ([Smashing — Thumb Zone](https://www.smashingmagazine.com/2016/09/the-thumb-zone-designing-for-mobile-users/))
8. **Tab bar = navigation only, 3–5 items, anchored bottom, always visible.** Items never trigger actions or sheets. ([Apple HIG tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars))
9. **No hover-only affordances on touch.** Gate hover-revealed UI with `@media (hover: none) and (pointer: coarse)`.
10. **`touch-action: manipulation`** on tappable elements.
11. **`overscroll-behavior: contain`** on chat, editors, infinite-scroll feeds.
12. **Don't fight iOS edge-swipe-back.** Custom horizontal swipes stay >20px from the left edge.

### 5.3 The desktop ↔ mobile divergence rule

> **Don't responsive-shrink a desktop toolbar. Write a mobile UI that shares state and nothing else.**

Concrete pattern, tested in real products:

- **Independent components, shared store.** A `Toolbar` and `MobileToolbar` that both call the same state — never a single component branching on viewport.
- **Move the status bar inside the mobile overflow sheet,** not pinned to the screen edge.
- **Selection actions float and replace primary chrome** at the same Y position. The screen never shows both.
- **Promote two primary actions** (AI/Generate, Copy/Export) to persistent top-right buttons for thumb reach.
- **Bottom bar = two-row N-column grid.** Icon stacked over `text-[10px]` label; row 2 ends with a `More` button into a bottom sheet.
- **Bottom sheets need: drag handle, backdrop tap-to-close, slide-in animation.**
- **`active:` replaces `hover:` everywhere on mobile.**
- **Drop features that touch-degrade rather than touch-port them.**

### 5.4 Native platforms (one rule)

**Same icon across platforms is fine; same chrome is broken.** Don't paste a macOS menu bar into a web app. For platform-specific checklists (Mac-native pass/fail, iOS thumb zone, etc.) use [ux-stress-test.md](./ux-stress-test.md). The cross-platform stack decision (Native / Tauri / Electron / PWA) is shipping/architecture, not UX — it lives in `docs/guides/` if anywhere.

---

## 6. The stress test

The runnable 12-question pre-commit checklist. Full version with checkable items in [ux-stress-test.md](./ux-stress-test.md).

1. **Signifier** — Can a first-time user tell what's interactive without hovering?
2. **Feedback** — Does every action produce a visible response within ~100ms? Does every commit have closure?
3. **Mental model** — Does the screen describe the user's task, or your schema?
4. **Consistency** — Do the same words, colors, and components mean the same here as elsewhere?
5. **Error prevention** — What is the most destructive action on this screen, and what stops a user from doing it by accident?
6. **Reversibility** — Can the user undo what they just did, or back out without consequence?
7. **Recognition** — Am I asking the user to remember anything from a previous screen?
8. **Reach (Fitts)** — Is the primary action big enough, near enough, and ideally edge- or corner-anchored?
9. **Defaults** — What's the default, and is it the answer 80% of users want?
10. **Honesty** — Does anything on this screen overstate what the system actually does?
11. **Density vs chrome** — Is every border, shadow, and divider separating things the user needs separated? Is content density matched to the user's expertise level?
12. **Scan test** — If a user reads only the headings, button labels, and first line of each paragraph, can they still complete the task?

Any "no" requires either a fix or an explicit, defensible exception.

---

## 7. Red flags

Fifteen telltale signs of "built without UX care." Use this list to triage a clunky project before deciding what to redesign.

1. Two or more buttons of equal weight on the same screen — no primary.
2. Pure `#000` text on `#FFF`, or pure `#000` background in dark mode.
3. Pixel-arbitrary spacing (`padding: 13px 17px`, `margin-top: 7px`) — no grid.
4. Three+ typefaces, or four+ font sizes off any scale.
5. `outline: none` on focus with no `:focus-visible` replacement.
6. Body text 16px+ in a dense app — the children's-tutorial smell.
7. Decorative color (rainbow tags, gradient on every card) with no semantic meaning.
8. Per-component hand-rolled `box-shadow` values — no shared elevation tokens.
9. Spinners that flash for <300ms, or full-page spinners when a skeleton would do.
10. Error messages reading "Something went wrong" or showing raw stack traces / error codes.
11. Empty states that are literally empty — no copy, no CTA, no teaching moment.
12. Buttons without hover or active states.
13. Modal dialogs for trivial operations (rename, toggle a setting).
14. On Mac: stub menu bar, custom traffic lights, iOS-sized touch targets.
15. Animations on every keystroke / list update / navigation — death by 250ms.

---

## 8. Bootstrapping a new repo (Day 1)

1. **Design system:** 4pt or 8pt grid, one accent color, one warning color, 8–10 tinted grays (pick the ramp from §4.2), three type sizes, three shadow tokens, one transition timing. Lock it.
2. **Pick a voice register** (default: sentence case). Lock it.
3. **Ship a populated empty state and a working error state before the happy path.** They are not polish — they are the first onboarding.
4. **Wire `:focus-visible`, `prefers-reduced-motion`, and `env(safe-area-inset-*)`** before you ship a single screen.
5. **Run the stress test on the first three screens.** Any "no" is a Day-1 bug.

---

## Appendix A — Canon reminders

The canon insists on these even when the design discourse looks away. Re-read when you feel a clever-but-novel pattern coming on.

1. **Users do not read. They scan.** ([Krug](https://blas.com/dont-make-me-think/); [Redish](https://redish.net/books/letting-go-of-the-words/)) Hierarchy carries meaning. If the most important information is in your second sentence, it is invisible.
2. **Consistency beats cleverness, always.** A novel bespoke pattern that users must learn is a tax. Charge it only when the value clears the curve.
3. **Affordances precede aesthetics.** A button must look pressable before it can look beautiful (Norman). Flatness is allowed only insofar as it preserves a signifier.
4. **Error prevention beats good error messages.** The best error message is the one the user never has to read (Nielsen #5).
5. **Defaults are the most-used setting.** Treat the default as a product decision, not a placeholder.
6. **The user's mental model wins over your data model.** If you find yourself explaining your schema in the UI, you have already lost (Norman, Cooper).
7. **Complexity is conserved.** You did not remove the step; you moved it. Decide whose step it is now (Tesler).
8. **Feedback is non-negotiable, even when "quiet by default" is the aesthetic.** Quiet means unobtrusive (good); it cannot mean silent on commit (bad).
9. **Honesty includes performance honesty.** Don't fake instant when you mean pending. A spinner that finishes in 50ms is worse than no spinner. A spinner that runs forever without progress is worst.
---

## Appendix B — Source map

### Canon
- [Norman — *The Design of Everyday Things*](https://jnd.org/books/the-design-of-everyday-things-revised-and-expanded-edition/)
- [Rams — Ten Principles of Good Design](https://www.vitsoe.com/us/about/good-design)
- [Tognazzini — First Principles of Interaction Design](https://asktog.com/atc/principles-of-interaction-design/)
- [Nielsen — 10 Usability Heuristics](https://www.nngroup.com/articles/ten-usability-heuristics/)
- [Shneiderman — Eight Golden Rules](https://www.cs.umd.edu/users/ben/goldenrules.html)
- [Cooper — *About Face* (notes)](https://www.gregbulla.com/TechStuff/Docs/NotesFromAboutFace3.htm)
- [Tufte — *Visual Display of Quantitative Information* (summary)](https://faculty.cc.gatech.edu/~stasko/7450/16/Notes/tufte.pdf)
- [Krug — *Don't Make Me Think* (summary)](https://blas.com/dont-make-me-think/)
- [Redish — *Letting Go of the Words*](https://redish.net/books/letting-go-of-the-words/)
- [Laws of UX](https://lawsofux.com/) — Fitts, Hick, Miller, Tesler, Postel, Gestalt

### Modern execution
- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [Refactoring UI](https://refactoringui.com/) — [Building a color palette](https://refactoringui.com/previews/building-your-color-palette)
- [Linear Method](https://linear.app/method)
- [Vercel Geist](https://vercel.com/geist/introduction)
- [Rauno — Invisible Details of Interaction Design](https://rauno.me/craft/interaction-design)
- [Nielsen Norman — Response Time Limits](https://www.nngroup.com/articles/response-times-3-important-limits/)
- [Smashing — Thumb Zone](https://www.smashingmagazine.com/2016/09/the-thumb-zone-designing-for-mobile-users/)

### Web platform
- [web.dev — Viewport units](https://web.dev/blog/viewport-units)
- [web.dev — viewport-fit and safe area insets](https://web.dev/blog/viewport-fit-and-safe-area-insets)
- [Tailwind — Responsive design](https://tailwindcss.com/docs/responsive-design)
- [Material Design — Touch target](https://m2.material.io/develop/web/supporting/touch-target)
