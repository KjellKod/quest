---
name: sharpen
description: Adversarial interview against a plan, design, or write-up — one question at a time, with a recommended answer attached to each — to surface contradictions, hidden assumptions, and unresolved tradeoffs before they ship. Use when the user types /sharpen, says "sharpen this", "stress-test this", "find the holes", "challenge my plan", or wants to confirm shared understanding before locking a decision. Also invoked by Quest's plan presentation menu.
user-invocable: true
---

# Skill: Sharpen

Pressure-test the artifact under discussion. Walk the decision tree branch by branch. Surface contradictions, hidden assumptions, orphaned design intent, and unresolved tradeoffs before they bite at month 3.

The point is shared understanding — agent and human aligned on what's actually settled, what's still soft, and what needs to change before this ships.

## On entry

Read the artifact (the path the user supplied, or the artifact already in context). Then:

1. Estimate how many decision branches it has. Commit to a question count. Hard cap at 12.
2. Announce: `Sharpening <artifact>. Estimated ~N questions.`
3. Skip questions you can answer by reading the file or any other source. Don't waste the user's attention on facts already on disk.

## Each question

- **One at a time.** Never batch. The user must answer fully before the next one lands.
- **Take a position.** Provide your own recommended answer with each question. The signal lives in whether the user agrees, corrects, or hesitates — not in "what do you think?".
- **Walk the tree, don't ping-pong.** Resolve one branch fully before moving to a sibling. If the user's answer changes a downstream decision, follow that branch to its leaves before backing up.
- **Adversarial, not flattering.** Try to break the artifact. Best questions are the ones the user doesn't want to answer.
- **Footer every question** with `(Q<n> of ~<N>, <pct>% — <one-word topic>)` so the user sees progress and the current branch.
- **Revise the estimate at most once** if a deep branch opens up. Say so explicitly: `(Q5 of ~9 — revised, 56% — naming)`. Don't let the count drift quietly.
- **Track open vs locked.** When a sub-decision is resolved, name it as resolved out loud and move on. Don't re-litigate.

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

## Style

Direct. Opinionated. No hedging. Short questions, short follow-ups. Restate the tree state periodically so the user can see what's locked and what's open.
