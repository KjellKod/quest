# Quest Memory Evaluation Loop

## Status: proposed

## Why this note exists

If Quest adds structured memory and retrieval, the next question is unavoidable:

- does it actually help?

Without an evaluation loop, Quest can easily build something that is:

- elegant
- local
- queryable
- well-documented

and still not materially improve agent behavior.

This note proposes a concrete, low-theater evaluation loop based on Quest's own archived runs.

## Decision

This note does **not** need a separate quest just to exist.

The design can and should be written directly now.

Implementation should only start after the memory/retrieval MVP is in place, because evaluating retrieval before retrieval exists is mostly measuring filesystem luck.

## Relationship to existing ideas

This note depends directly on:

- `ideas/2026-04-13-quest-memory-architecture.md`

It also complements:

- `ideas/archive/2026-04-13-review-intelligence-canonical.md`

The memory note defines what gets indexed and queried.
This evaluation note defines how to prove that the resulting memory is useful.

## Core position

Quest should evaluate memory the same way it evaluates other meaningful workflow improvements:

- against real artifacts
- against repeatable tasks
- with explicit scoring
- with baseline comparison

The test is not:

- "did the query tool return something?"

The test is:

- "did the memory layer help an agent choose better prior context, faster, with less guesswork?"

## MVP decision

The first implementation must be retrieval-only.

That means Phase A scores only:

- returned quest ids
- returned artifacts
- ranking quality

It does **not** score:

- final answer prose
- hallucination judgments
- downstream workflow quality

Those belong to a later phase after retrieval quality is proven.

## What should be evaluated

Quest memory should be evaluated on four dimensions:

1. **retrieval relevance**
2. **answer usefulness**
3. **workflow efficiency**
4. **hallucination reduction**

### 1. Retrieval relevance

Did the system surface the right prior quests/artifacts?

### 2. Answer usefulness

Did the retrieved memory actually help produce a better answer or decision?

### 3. Workflow efficiency

Did the memory reduce file exploration and wasted turns?

### 4. Hallucination reduction

Did the memory help the agent make fewer invented claims about prior Quest behavior?

## Design constraints

This proposal should be judged through:

- **KISS**: local fixtures, local scripts, no remote eval platform
- **evidence-first**: use archived Quest runs as the corpus
- **baseline required**: compare against plain filesystem exploration
- **incremental rollout**: start with retrieval-only eval before end-to-end workflow eval

## Benchmark design

### Corpus

Use archived and active Quest runs already present in:

- `.quest/archive/`
- `.quest/`

### Case structure

Store benchmark cases under:

`tests/fixtures/quest_memory_eval/`

Example layout:

```text
tests/fixtures/quest_memory_eval/
+-- cases/
|   +-- worktree-startup.json
|   +-- bridge-timeout.json
|   +-- review-severity.json
|   +-- runtime-fallback.json
+-- gold/
    +-- worktree-startup.json
    +-- bridge-timeout.json
    +-- review-severity.json
    +-- runtime-fallback.json
```

### Case file

Example:

```json
{
  "case_id": "bridge-timeout",
  "prompt": "Find the most relevant prior quest history for diagnosing false-negative bridge availability caused by execution context.",
  "query_tags": ["bridge", "timeout", "preflight", "sandbox"],
  "expected_modes": ["retrieval", "summary"],
  "notes": "This should strongly surface the preflight bugfix and related runtime dispatch work."
}
```

### Gold file

Example:

```json
{
  "case_id": "bridge-timeout",
  "expected_quest_ids": [
    "claude-runtime-dispatch_2026-03-09__1236",
    "codex-led-claude-bridge-runtime-hardening_2026-03-09__1039"
  ],
  "expected_artifacts": [
    ".quest/archive/claude-runtime-dispatch_2026-03-09__1236/quest_brief.md",
    ".quest/archive/codex-led-claude-bridge-runtime-hardening_2026-03-09__1039/quest_brief.md"
  ],
  "required_topics": [
    "host-visible context",
    "sandbox false negative",
    "bridge probe"
  ]
}
```

## Two evaluation modes

### Mode A: retrieval-only

Goal:

- test whether the memory layer returns the right prior quests/artifacts

This should be the first mode implemented.

Inputs:

- case prompt
- memory query tool

Outputs scored:

- returned quest ids
- returned artifacts
- match ordering

### Mode B: task-assisted

Goal:

- test whether memory improves a downstream answer

Inputs:

- case prompt
- either raw filesystem exploration or memory-assisted retrieval

Outputs scored:

- final answer quality
- citations to prior artifacts
- file exploration cost

Mode B should come after Mode A is stable and only after the retrieval benchmark is already giving trustworthy signals.

## Baseline comparison

Every benchmark should compare at least:

1. **baseline**
   - raw filesystem exploration only
2. **memory-assisted**
   - use `quest_memory_query.py` first, then inspect returned artifacts

Optional later:

3. **memory-only constrained**
   - only returned artifacts allowed

That third mode is useful for stress-testing retrieval quality, but it should not be the main benchmark initially.

## Scoring

### Retrieval-only scoring

For each case, score:

- `top_1_hit`: whether the first result is in the gold set
- `top_3_recall`: how many gold quest ids appear in the top 3
- `artifact_recall`: how many gold artifacts appear
- `topic_coverage`: whether required topics are represented in returned summaries

### Task-assisted scoring

Later phase only.

For each answer, score:

- `relevance` 1-5
- `completeness` 1-5
- `hallucinations` count
- `useful_citations` count
- `tool_steps` count
- `files_opened` count

This phase should use an explicit human scoring rubric rather than loose model judgment.

## First benchmark cases

Start with 4-6 cases that clearly matter in this repo.

### Recommended initial cases

1. **Worktree startup selection**
   - find prior decisions around branch/worktree startup behavior

2. **Bridge timeout / false-negative readiness**
   - find prior evidence about host-visible vs sandbox-local execution context

3. **Review severity and finding handling**
   - find prior Quest work about review severity and triage

4. **Runtime fallback / handoff reliability**
   - find prior fixes and decisions around fallback ladders and artifact recovery

5. **Phase gate enforcement**
   - find prior work related to state transitions and pre-build safeguards

These are strong starter cases because:

- they have real history in this repo
- they cross multiple quests
- they are not trivial grep-only tasks

## Proposed scripts

Add:

- `scripts/quest_memory_eval_build_cases.py`
- `scripts/quest_memory_eval_run.py`
- `scripts/quest_memory_eval_report.py`

### `quest_memory_eval_build_cases.py`

Responsibilities:

- validate case files
- validate gold files
- ensure referenced quest ids/artifacts exist

### `quest_memory_eval_run.py`

Responsibilities:

- run baseline retrieval mode
- run memory-assisted retrieval mode
- record outputs and metrics

### `quest_memory_eval_report.py`

Responsibilities:

- aggregate per-case results
- compare baseline vs memory-assisted
- produce a readable markdown report

## Example result format

Store results under:

` .ws/quest-memory-eval/ `

Example file:

```json
{
  "case_id": "worktree-startup",
  "mode": "memory-assisted",
  "top_1_hit": true,
  "top_3_recall": 2,
  "artifact_recall": 3,
  "relevance": 5,
  "completeness": 4,
  "hallucinations": 0,
  "files_opened": 4,
  "tool_steps": 3
}
```

## Rollout plan

### Phase A: retrieval benchmark only

Build:

- case fixtures
- gold fixtures
- retrieval scoring

Acceptance:

- can compare baseline filesystem search vs memory-assisted retrieval

### Phase B: reporting

Build:

- markdown report generator
- per-case deltas

Acceptance:

- results are readable and comparable over time

### Phase C: task-assisted benchmark

Build:

- answer-quality scoring harness
- useful citation counting

Acceptance:

- can show whether memory improved the final answer, not just the returned ids

## What not to do

Do not:

- build a flashy benchmark system before the memory query MVP exists
- use vague "seems better" scoring
- rely on one giant benchmark task
- try to evaluate everything at once

Also do not benchmark memory in a way that rewards verbosity over usefulness.

## Phase A success thresholds

The retrieval-only MVP should define hard thresholds on a fixed starter case set.

Initial thresholds:

- `top_1_hit >= 0.60`
- `top_3_recall >= 0.80`
- `artifact_recall >= 0.70`

These numbers can be adjusted later, but the point is to have an actual bar.

## Success criteria

This idea is successful if Quest can answer:

1. does the memory layer retrieve the right prior quests more often than plain exploration?
2. does it reduce search effort?
3. does it reduce hallucinated prior-history claims?
4. which cases benefit from memory and which do not?

## Bottom line

A memory system without an evaluation loop is easy to overestimate.

Quest already has the perfect raw material for a meaningful local benchmark:

- archived quests
- phase artifacts
- real review/fix history

The right move is:

- benchmark retrieval first
- compare against raw filesystem exploration
- keep the scoring concrete
- only expand the evaluation loop after the memory MVP proves useful
