---
title: Feedback-intent routing for Quest orchestration
purpose: Classify user feedback by intent so Quest routes clarification, replanning, second opinions, and escalation deliberately, with a small companion improvement for skill authoring
audience: Quest maintainers
status: proposed
date: 2026-04-13
supersedes:
  - 2026-04-13-feedback-aware-delegation-keywords.md
  - 2026-04-13-intent-anchored-example-prompts.md
related:
  - .skills/quest/delegation/workflow.md
  - .skills/gpt/SKILL.md
  - .skills/quest/agents/plan-reviewer.md
  - .skills/quest/SKILL.md
---

# Feedback-intent routing for Quest orchestration

## Why this note exists

Quest currently has two nearby ideas that are really one proposal:

- one note reframes inert `keywords:` metadata into a live feedback-routing feature
- one note proposes example prompts in skill files as a low-cost way to match real user phrasing better

These should not compete as separate top-level ideas.

The stronger proposal is:

- use user phrasing where it already matters during a quest
- route that feedback deliberately
- keep skill-authoring improvements as a small companion tactic, not the main solution

## Core position

The original `keywords:` idea should be dismissed as a primary direction.

The real opportunity is to use the same underlying insight in a place where it changes behavior today:

- inside Quest's feedback loop

Quest already receives plain-English user feedback during planning and walkthrough.
That feedback contains a strong signal about what the user actually wants next.
Right now the workflow mostly treats all such feedback the same and loops it back into planning.

That is too blunt.

## 1. The problem with inert keyword metadata

A recurring suggestion for larger skill libraries is to add a `keywords:` array to frontmatter so the router sees literal trigger phrases such as:

- "second opinion"
- "ask codex"
- "review my plan"

The problem is simple:

- Claude Code matches skills on the `description` line, not custom frontmatter
- Quest does not consume a `keywords:` field either
- therefore `keywords:` is inert metadata today

That means the field is not a live improvement. It is speculative structure that looks useful without changing runtime behavior.

That is exactly the kind of thing Quest should resist:

- it invites keyword stuffing
- it weakens authoring discipline
- it gives the appearance of better routing without producing it

So the recommendation is:

- do not standardize `keywords:` as a Quest idea by itself

What should be preserved from that discarded idea is the real principle behind it:

- user-facing phrasing matters more than abstract description language

That principle is valid. It just belongs in a live routing path instead of dead metadata.

## 2. Feedback-intent classification inside Quest loops

The real register mismatch in Quest is not just skill selection.
It happens during live quest execution.

Current pattern:

1. the user gives feedback on a plan or walkthrough
2. Quest records it under `.quest/<id>/phase_01_plan/user_feedback.md`
3. the workflow forwards it back into another planning iteration

That works for real replanning requests, but it is wrong for several common cases.

Examples:

- "I don't understand this part" means clarify, not replan
- "this is wrong, rethink it" means replan
- "what does codex think before we commit?" means second opinion
- "we keep looping here" means escalate

So the proposal is to add a small intent-classification step inside the Quest orchestrator before feedback is routed onward.

Important scope constraint:

- this should live inline in the existing workflow logic
- it should not become a new general-purpose router system
- it should not require an LLM classifier to get started

The first version should be a cheap deterministic classifier based on a short intent table.

## 3. Supported intents and routing behavior

The initial intent set should stay intentionally small.

| Intent | Example triggers | Routing behavior |
|---|---|---|
| `clarify` | "explain", "expand", "what do you mean", "I don't understand" | Route to a clarify-only response. Do not generate a fresh plan revision. Write the answer to a feedback response artifact for the user. |
| `replan` | "this is wrong", "try again", "rethink this", "that's not right" | Route back into the normal planner iteration with verdict plus feedback. |
| `second_opinion` | "second opinion", "ask codex", "what does gpt think", "other model" | Dispatch a narrow second-opinion review using the existing `gpt` skill and feed that result into the next arbiter decision. |
| `escalate` | "we're stuck", "still wrong", "we've been here before", "stop looping" | Stop the silent loop and bring the issue back to the user explicitly. |
| `unknown` | anything ambiguous or weakly matched | Fall back to current behavior. Do not invent a new route. |

### Example: `second_opinion`

For a comment like:

> before we commit, what does codex think of this plan?

Quest should do something explicit and narrow:

1. classify the feedback as `second_opinion`
2. announce the routing decision to the user
3. run the `gpt` skill against:
   - the quest brief
   - the current plan
   - the existing plan reviews
4. write a third review artifact for the next verdict

That is a materially better outcome than:

- sending the same plan back through another replanning cycle
- or making the user leave Quest and run a separate command manually

### Where this logic lives

Keep the mechanism simple:

- the intent table lives in one Quest-owned place
- the orchestrator checks it before choosing the next action
- ambiguous matches use `unknown`
- `unknown` means current behavior

This is not the place to build:

- a generalized semantic routing engine
- dynamic prompt retrieval
- a large taxonomy of conversational intents

## 4. Low-risk companion improvements in skill authoring

The companion idea from the example-prompts note is still worth keeping, but in the right place in the hierarchy.

It should be treated as:

- a low-risk skill-authoring improvement
- not the main runtime solution

### Proposal

Add a short `## Example prompts` block to selected skill files with 2-4 realistic user utterances.

Example:

```md
## Example prompts

- "get a second opinion from codex"
- "have gpt review this plan"
- "what does the other model think?"
- "cross-check this with codex"
```

### Why this is still useful

- it improves phrasing coverage in the current skill surface
- it is extremely cheap to roll out
- it acts as a sanity check on whether a skill is described in natural terms

### Why this is not the primary solution

It does not change Quest's mid-quest routing behavior.

At best it helps the model connect user phrasing to existing skill descriptions.
It does not decide whether live quest feedback should:

- clarify
- replan
- seek a second opinion
- escalate

So it belongs as a companion authoring convention, not as the core routing feature.

### Authoring rules for example prompts

If Quest adopts this convention, keep it disciplined:

1. use real user phrasing, not polished product language
2. include a little register variation
3. include the direct tool/skill name once when it is natural
4. avoid fake placeholders like `PR #123`
5. cap the block at 4 examples

### Candidate first-pass skills

- `.skills/gpt/SKILL.md`
- `.skills/quest/SKILL.md`
- `.skills/pr-assistant/SKILL.md`
- `.skills/pr-shepherd/SKILL.md`
- `.skills/code-reviewer/SKILL.md`
- `.skills/git-commit-assistant/SKILL.md`

## 5. Rollout and guardrails

### Guardrails

These rules should remain explicit in the canonical proposal:

1. Start with cheap deterministic matching.
2. Keep the intent set small.
3. Default ambiguous cases to current behavior.
4. Announce surprising routing decisions to the user.
5. Treat example prompts as a companion authoring aid, not the primary runtime solution.

### Additional operating rules

- Do not silently route feedback to a different model without telling the user.
- Do not add a sixth intent casually. If the set wants to grow, first check whether the existing intent definitions are too narrow.
- Do not preload broader router logic into every Quest path. This is a targeted improvement to the feedback loop.
- Do not let the example-prompts convention expand into exhaustive skill documentation. Its value is signal, not volume.

### Rollout order

1. Adopt this canonical proposal as the single active idea doc for the theme.
2. Add a small Quest-owned intent table for feedback routing.
3. Patch the workflow's feedback-handling path to classify before rerouting.
4. Ship `second_opinion` first because it has the clearest user value and a natural existing tool path.
5. Ship `clarify` second because it reduces needless replanning churn.
6. Ship `escalate` third because it breaks silent loops.
7. Keep `replan` as the normal default.
8. Log intent classifications so Quest can audit whether the classifier is helping or misfiring.
9. Roll out example-prompt blocks to a small set of skills as a separate low-risk follow-up.

## Decision

Quest should:

- reject inert `keywords:` metadata as the main idea
- keep the core insight that user phrasing matters
- apply that insight to live feedback routing inside Quest
- keep example prompts as a companion authoring improvement

That gives Quest one canonical routing proposal with:

- a clear runtime behavior change
- a narrow scope
- explicit guardrails
- a cheap supporting improvement that does not pretend to solve the whole problem
