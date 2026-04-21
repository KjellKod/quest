# Quest Memory Architecture

## Status: proposed

## Why this note exists

Quest already produces useful history under `.quest/`:

- `quest_brief.md`
- `plan.md`
- review artifacts
- `handoff*.json`
- `state.json`
- builder and fixer discussion files
- logs

The missing piece is not "more artifacts." The missing piece is a small, local, queryable memory layer built on top of those artifacts.

This note is the canonical memory proposal. It combines the memory-system design with the retrieval guardrails so Quest has one active memory document instead of overlapping sibling notes.

## Relationship to existing ideas

- `ideas/2026-04-13-quest-memory-evaluation-loop.md`
  - stays separate
  - proves whether the memory layer is actually useful
- `ideas/archive/2026-04-13-review-intelligence-canonical.md`
  - remains the schema authority for review findings
  - future memory finding and decision records must inherit that canonical finding structure

## Hard guardrails

Memory should be:

- self-directed
- query-driven
- optional
- small
- verified against code

That means:

1. Do not preload memory into every task by default.
2. Do not require the user to manually ask for memory.
3. Start with code, tests, findings, and the current repo state.
4. Retrieve memory only when there is concrete uncertainty.
5. Retrieve at most `1-3` targeted snippets at a time.
6. If memory and code disagree, trust code and mark the memory stale.

Kill or roll back this idea if:

- memory starts appearing in most tasks by default
- easy tasks get slower without better outcomes
- reviewers cite memory more often than code
- benchmarked accuracy on hard tasks does not improve
- hallucinations or stale-summary errors increase

## 1. Operational Memory

Operational memory is what happened:

- what the quest was about
- what plan was approved
- what findings were raised
- what decisions were made
- what got fixed
- what failed
- what branch, runtime, and path were used
- what the final outcome was

Quest already has most of this today in `.quest/` artifacts.

## 2. Reflective Memory

Reflective memory is what we learned:

- which pattern worked
- which approach was rejected and why
- what repeated across multiple quests
- what should be reused or avoided next time

Quest has much less of this today. That is fine. The right move is to start with operational memory because it already exists and is more reliable, then add reflective memory in a small explicit way.

## 3. Structured Storage and Records

Add a local generated store:

`.quest/memory/`

Proposed shape:

```text
.quest/memory/
+-- manifest.json
+-- quests.jsonl
+-- findings.jsonl
+-- decisions.jsonl
+-- resolutions.jsonl
+-- reflections.jsonl
+-- snapshots/
    +-- <quest_id>.json
```

Use JSONL for append-friendly records and one per-quest snapshot for direct lookup.

The first pass should stay small:

- required in MVP:
  - `quest`
  - `decision` when a clear structured source exists
- second pass:
  - `finding`
  - `resolution`
  - `reflection`

Example record types from the source design:

- `quest`
- `finding`
- `decision`
- `resolution`
- `reflection`

Important KISS rule:

- do best-effort extraction from existing quest artifacts first
- add small structured sidecars later only if rebuild-based extraction is too weak or too expensive

## 4. Retrieval Rules

Memory is for questions like:

- which boundary or ownership rule applies here?
- what invariant has caused repeated review issues in this area?
- what known footgun should be checked before changing this path?
- what prior accepted quest or review pattern is relevant?

Do not use memory as a substitute for:

- reading the changed code
- reading nearby unchanged code
- running tests or validators
- checking the current repo structure

Only retrieve memory if one of these is true:

1. the change crosses more than one meaningful module boundary
2. reviewer disagreement suggests a boundary or invariant question
3. the agent has searched several times and still has unresolved uncertainty
4. the task touches a critical workflow with known footguns
5. the same class of finding keeps recurring in the same area
6. the user explicitly asks for architecture or prior-learnings context

If none of those are true:

- do not load memory

Concrete retrieval policy:

1. Start with diff, findings, tests, and code.
2. Retrieve memory only when one of the trigger conditions is true.
3. Retrieve at most `1-3` targeted snippets.
4. Quote the source path in the artifact or summary.
5. Validate memory claims against actual code before acting.

## 5. Freshness and Update Model

Freshness is important, but should be a second-phase improvement rather than a day-one requirement.

Update points:

- quest creation
  - create initial quest record from `state.json` and `quest_brief.md`
- after planner output
  - update quest summary, plan artifact path, and tags
- after plan reviews
  - ingest review findings if a structured sidecar exists
- after arbiter or review-decision output
  - create or update decision records
- after build or fix discussions
  - create or update resolution records when issue-to-fix linkage is explicit
- on completion or archive
  - finalize quest status
  - write a reflection
  - update the snapshot file

Minimal implementation order:

- MVP:
  - full rebuild from archived and active quests
- later:
  - incremental update hooks if full rebuilds prove too slow or too stale

## 6. Narrow Retrieval Commands

Start with one small local CLI:

`python3 scripts/quest_memory_query.py ...`

Initial commands:

- `similar-quests`
- `quest-summary`
- `findings`
- `decisions`
- `resolutions`

Initial ranking should stay simple:

- exact tag or topic match
- title and summary token overlap
- path and topic overlap
- recency
- resolved and accepted outcomes ranked above blocked and incomplete ones

Do not build a more complex retrieval layer in the first pass.

## 7. Reflective Summaries

Do not start by trying to generate deep insight from every quest automatically.

Start with a short explicit closeout artifact:

- `.quest/<id>/quest_reflection.md`
- `.quest/<id>/quest_reflection.json`

Required reflection fields from the source design:

- `what_worked`
- `what_failed`
- `reusable_lessons`
- `reuse_when`
- `avoid_when`

This keeps reflective memory explicit, small, and reusable.

## 8. Cross-References

Evaluation and proof:

- `ideas/2026-04-13-quest-memory-evaluation-loop.md`

Finding-schema authority:

- `ideas/archive/2026-04-13-review-intelligence-canonical.md`

Future memory `finding` and `decision` records must inherit and conform to the canonical finding schema defined in the review-intelligence canonical proposal.

## 9. What Not To Do

Do not:

- build a hosted memory platform before proving local retrieval value
- treat memory as authoritative over code
- preload memory into every task
- build a large reflection system before operational memory is useful
- depend on parsing arbitrary prose forever
- replace source artifacts instead of layering on top of them

## 10. Success Metrics

The memory layer is successful if it:

- helps on hard cross-module tasks
- stays out of the way on easy tasks
- reduces file exploration and wasted turns
- improves retrieval relevance for prior quest history
- reduces repeated confusion about boundaries, invariants, or prior decisions

## 11. Kill Criteria

Abort or roll back if:

- easy tasks get slower without better outcomes
- memory is loaded by default in most runs
- stale summaries increase wrong conclusions
- hallucinations go up
- benchmarked retrieval quality is not materially better than plain filesystem exploration

## 12. Suggested Phasing

Phase A:

- build the local structured memory store
- support full rebuild from existing quest artifacts
- keep scope to operational memory first

Phase B:

- add narrow retrieval commands
- validate ranking quality on real quest history

Phase C:

- add selective freshness updates if needed

Phase D:

- add small explicit reflective summaries

The evaluation loop remains separate and should decide whether later phases are worth shipping.
