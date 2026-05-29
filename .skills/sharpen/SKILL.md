---
name: sharpen
description: Adversarial interview against a plan, design, or write-up - one question at a time, with a recommended answer attached to each - to surface contradictions, hidden assumptions, and unresolved tradeoffs before they ship. Use when the user invokes /sharpen or $sharpen, says "sharpen this", "stress-test this", "find the holes", "challenge my plan", or wants to confirm shared understanding before locking a decision.
user-invocable: true
---

# Skill: Sharpen

Pressure-test the artifact under discussion. Walk the decision tree branch by branch. Surface contradictions, hidden assumptions, orphaned design intent, and unresolved tradeoffs before they bite at month 3.

The point is shared understanding — agent and human aligned on what's actually settled, what's still soft, and what needs to change before this ships.

## On entry

Read the artifact (the path the user supplied, or the artifact already in context). Then:

1. Estimate how many decision branches it has. Commit to a question count. Hard cap at 12.
2. Announce: `Sharpening <artifact>. Estimated ~N questions.`
3. Ground before Q1 when local facts matter:
   - If the artifact references local implementation surface (repo/code/tests/scripts/workflows/tools/conventions), run a bounded grounding pass before asking Q1.
   - Default grounding budget per session: at most 5 targeted reads and 3 targeted searches, unless the user explicitly asks for deeper investigation.
   - Extract anchors from the artifact first: paths, commands, scripts, tests, modules, acceptance criteria.
   - Verify the highest-impact anchors in the current checkout.
   - Skip questions already answered by grounded facts and log those decisions in `Resolved`.
   - If no repo/local surface exists, ground on artifact-only evidence and do not claim local verification.
   - If a grounding search returns more than 50 hits, accept partial grounding and disclose that uncertainty in the next relevant question.

## Each question

- **One at a time.** Never batch. The user must answer fully before the next one lands.
- **Take a position.** Provide your own recommended answer with each question. When local facts support that recommendation, cite the grounding facts directly in the recommendation. The signal lives in whether the user agrees, corrects, or hesitates — not in "what do you think?".
- **Walk the tree, don't ping-pong.** Resolve one branch fully before moving to a sibling. If the user's answer changes a downstream decision, follow that branch to its leaves before backing up.
- **Adversarial, not flattering.** Try to break the artifact. Best questions are the ones the user doesn't want to answer.
- **Per-question grounding.** When local facts materially affect the question, prepend:
  - `Grounded on: <path:line, command output, or artifact excerpt>`
- **Footer every question** with `(Q<n> of ~<N>, <pct>% — <one-word topic>)` so the user sees progress and the current branch.
- **Revise the estimate at most once** if a deep branch opens up. Say so explicitly: `(Q5 of ~9 — revised, 56% — naming)`. Don't let the count drift quietly.
- **Track open vs locked.** When a sub-decision is resolved, name it as resolved out loud and move on. Don't re-litigate.
- **Handle contradictions explicitly.**
  - If grounding contradicts a plan claim and blocks the rest of the tree, make it Q1:
    - `The plan says X. I found Y in path:line. Which is correct?`
  - If a contradiction is fully resolved by local evidence, log it under `Resolved` and continue with the next highest-impact unresolved question.

## On exit

When the tree is walked, emit a structured summary:

1. **Resolved** — decisions locked, one-line rationale each.
2. **Open** — questions that surfaced but weren't settled, ranked by importance.
3. **Next** — one concrete action. Either `no changes needed` or `re-plan with these revisions: …` (list them).

Then ask once: `Anything I missed before we wrap?` If yes, address it and re-emit the summary. If no, done.

## When NOT to invoke

- The user wants you to *write* the artifact, not pressure-test one — use a planning skill instead.
- The artifact is too vague to challenge. Say so: `Not enough surface to sharpen yet — sketch the decision points first.`
- A quick yes/no question.
- The user asks primarily for implementation planning deliverables, code patches, or PR review findings instead of adversarial interview questions.

## Special mode: `/sharpen ux-defaults`

Invoke this when the user wants to lock in UX defaults for a UI project — typically right before plan approval on a quest where the router set `ui_work: true`, or any time a backend engineer has built something that "needs to look right" but can't articulate the design choices.

**Invocation:** `/sharpen ux-defaults` is the explicit invocation. When an orchestration workflow invokes sharpen on a `ui_work: true` plan, it should pass `ux-defaults` as the argument so this mode runs automatically. Outside a workflow, the user types `/sharpen ux-defaults` directly. If a user types `/sharpen` with no argument and you cannot resolve an active artifact, prompt them once: "Did you mean `/sharpen ux-defaults` on the current plan, or `/sharpen <path>` for a specific artifact?"

**The six questions** — same one-at-a-time, recommended-answer-attached rhythm as standard sharpen. Skip any question whose answer is already visible in the prompt or plan.

1. **Mobile relevance** (asked first because it gates downstream choices). "Will this be used on phone-class viewports? Recommended: required for any consumer or web-public surface; no for internal admin / desktop-only tools. If required, the plan must address desktop ↔ mobile divergence (see guidebook §5.3)."
2. **Temperature.** "What's the brand color, if any? Recommended: no brand yet → cool (Tailwind `slate`). Linear, Stripe, Vercel, and many modern SaaS defaults use this family. Override: warm brand → `stone`; utilitarian / explicitly monochrome → `neutral`; tech/scientific → `zinc`; content-forward / paper feel (Google/GitHub) → `gray`."
3. **Density.** "How dense is the UI? Recommended: comfortable for consumer / settings / marketing; compact for IDE / data table / power-user. Override: pick the other."
4. **Content-vs-chrome ratio.** "Does the user spend more time looking at the toolbars and panels (chrome-dense — Linear, Figma, VS Code sidebar, the GitHub Actions UI) or at the content inside them (content-forward — GitHub READMEs, Google search, a settings form)? Recommended: content-forward for almost everything except dedicated creator/developer tools."
5. **Brand accent.** "Have a brand accent color? Recommended: `#2563eb` (Tailwind `blue-600`) if no other answer — reads as 'modern web'. Override: any hex."
6. **Destructive actions on this surface?** "Anything that loses money, deletes data, or is otherwise irreversible? Recommended: if yes, separate it visually (red text, far from primary action), require explicit confirmation, and log for undo where possible. If no, mark `none` and move on. This is the failure mode the rest of the rubric won't catch — `Delete account` next to `Save` is the canonical example."

**On exit**, emit a fenced `## UX Defaults` block that can be pasted into the plan or used to update the plan in place:

```markdown
## UX Defaults (locked via /sharpen ux-defaults)

- Mobile: <required | optional | no>
- Gray ramp: <slate | stone | neutral | zinc | gray>
- Density: <comfortable | compact>
- Ratio: <content-forward | chrome-dense>
- Accent: <hex>
- Destructive actions: <none | listed with confirmation/undo plan>

Principle citations: ux-guidebook§4.2, §4.3, §4.7, §5.2, §5.3.
```

If the user only wants to adjust some of the six, walk only those branches and emit a partial block. Skip questions where the answer is already visible in the prompt or plan.

## Style

Direct. Opinionated. No hedging. Short questions, short follow-ups. Restate the tree state periodically so the user can see what's locked and what's open.

## Example: Grounding Smoke Runner (Portable)

Before (ungrounded):
- Q1: "Should we keep the smoke-runner?"
- Recommended: "Yes, keep it."

After (grounded):
- Grounded on: `<smoke-runner script path>`, `<smoke-runner test path>`, artifact acceptance criteria
- Q1: "The artifact keeps the smoke runner, but the referenced acceptance criteria do not say who owns failures. Should CI failures block merge, or should the runner warn only?"
- Recommended: "Block merge only if the acceptance criteria define smoke failures as release-blocking; otherwise keep CI warn-only until ownership is explicit."
