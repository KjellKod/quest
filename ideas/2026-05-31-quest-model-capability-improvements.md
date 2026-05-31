---
title: Quest Model-Capability Improvements
purpose: Fact-checked proposal for using newer Claude and Codex capabilities only where they create measurable Quest value.
audience: Quest maintainers and implementing agents.
scope: Orchestration changes around structured artifacts, reasoning effort, and prompt caching.
status: proposed
owner: maintainers
last_updated: 2026-05-31
related:
  - .skills/quest/delegation/workflow.md
  - .ai/allowlist.json
  - .ai/schemas/handoff.schema.json
  - scripts/quest_claude_bridge.py
  - scripts/quest_claude_runner.py
  - scripts/quest_runtime/claude_runner.py
  - scripts/quest_runtime/orchestration.py
  - scripts/quest_runtime/review_intelligence.py
---

# Quest Model-Capability Improvements

## Bottom line

Do not implement the earlier version of this idea as written. It mixed real
model/runtime capabilities with conclusions that are not yet proven for Quest.

The value path is narrower:

1. Measure how often malformed or missing artifact recovery actually fires in
   real Quest runs.
2. Prove Claude and Codex structured-output flags against Quest's real schemas,
   not toy JSON.
3. Only if those checks justify it, build a transport-owned structured artifact
   path where the model returns schema-valid final JSON and the Quest runner
   writes `handoff.json` or findings files itself.
4. Add prompt-cache telemetry before changing prompt assembly. Reorder stable
   prefixes only if telemetry shows the prefix is cacheable and reused.

The non-goal is important: do not delete malformed-output recovery just because
new models are stronger. Delete it only after Quest no longer depends on agents
writing their own JSON files correctly.

## Evidence checked

### Claude Opus 4.7 / 4.8

Official Anthropic docs support these facts:

- Claude Opus 4.8 exists, is positioned for complex reasoning and long-horizon
  agentic coding, has a 1M-token context window on the first-party API, and has
  a 128k max synchronous output limit.
- Claude Opus 4.8 `effort` defaults to `high`; the docs explicitly say to set
  effort to use a different level.
- The Claude Code CLI supports `--effort` and `--json-schema`. The JSON-schema
  flag is documented as validated JSON output after the agent completes its
  workflow.
- Prompt caching is real. Anthropic guidance says static content should be at
  the beginning of the prompt. Cacheable minimums differ: Opus 4.8 is listed at
  1,024 tokens, while Opus 4.7 is listed at 4,096 tokens.

Sources:

- https://platform.claude.com/docs/en/about-claude/models/overview
- https://code.claude.com/docs/en/cli-usage
- https://platform.claude.com/docs/en/build-with-claude/prompt-caching

Local check:

- `claude --version` returned `2.1.159 (Claude Code)`.
- `claude --help` lists `--effort`, `--json-schema`, and
  `--model claude-opus-4-8`.
- A tiny Opus 4.8 structured-output smoke was attempted twice with explicit
  budget caps. Both invocations reached the cap before returning the final JSON,
  so this branch should not claim a successful local Opus schema smoke.

### Codex / GPT-5.5

Official OpenAI docs and local CLI checks support these facts:

- GPT-5.5 is listed as a current frontier model for coding and professional
  work, with reasoning levels `none`, `low`, `medium`, `high`, and `xhigh`.
- GPT-5.5 supports structured outputs.
- Prompt caching is automatic for recent OpenAI models. OpenAI guidance says
  cache hits require exact prefix matches and recommends static instructions and
  examples first, variable content last.
- Codex CLI supports `codex exec --output-schema <file>`.
- Codex config supports `model_reasoning_effort` with
  `minimal | low | medium | high | xhigh`.

Sources:

- https://developers.openai.com/api/docs/models/gpt-5.5
- https://developers.openai.com/api/docs/guides/prompt-caching
- https://developers.openai.com/codex/cli/reference
- https://developers.openai.com/codex/config-reference

Local check:

- `codex --version` returned `codex-cli 0.135.0`.
- `codex exec --help` lists `--output-schema`.
- A local smoke with `codex exec -m gpt-5.5 -c model_reasoning_effort=low
  --output-schema <schema>` exited 0 and wrote this trivial object:

```json
{"ok":true,"runtime":"codex"}
```

That smoke proves the local CLI path can enforce a tiny final-response schema.
It does not prove the path works with Quest's actual handoff schema.

## What is not proven

### Schema flags do not automatically fix Quest handoff files

Claude `--json-schema` and Codex `--output-schema` constrain the final response
shape. Quest currently asks agents to create artifact files such as
`handoff.json`, plan reviews, and findings files. A schema-valid final response
does not prove that a tool-written artifact file is valid.

This invalidates the earlier recommendation to retire malformed-JSON recovery as
a first step. That would be theatre: it would remove the safety net without
moving JSON ownership out of the model's file-writing behavior.

### Per-role effort exists, but the value curve is unmeasured

The effort knobs are real on both sides. What is not proven is which Quest roles
benefit from higher effort and which roles get cheaper without quality loss at
lower effort. Defaults should come from Quest telemetry, not intuition.

### Prompt caching is real, but Quest cache hit rates are unmeasured

Both providers reward stable leading prompt content. Quest likely has a good
shape for caching because role instructions, `AGENTS.md`, `BOOTSTRAP.md`, and
the quest brief repeat across plan and review loops. The magnitude is still a
measurement question. The win only appears if the prefix is byte-stable, large
enough, and used repeatedly within each provider's caching behavior.

### Stronger models do not justify lower gates

There is no branch-local evidence that Opus 4.7/4.8 or GPT-5.5 should reduce
Quest's plan or fix iteration caps. Gate changes need Quest outcome data.

### The fallback base rate is unknown

The current draft does not show how often malformed JSON, missing handoffs, or
text fallback recovery fire in real Quest runs. Without that base rate,
transport-owned artifacts are plausible but not yet proven high-value.

## Measurement-first proposal

### 1. Measure current fallback and artifact health

Status: first step.

Instrument the existing paths before adding new transport code:

- Count `handoff_json`, `handoff_missing`, `handoff_unparsable`,
  `text_fallback`, `transport_error`, and `permission/write_boundary` outcomes
  per role and phase.
- Record whether a recovery retry was needed and whether it changed the final
  transition decision.
- Summarize counts in a per-quest artifact so maintainers can see whether this
  is a frequent operational cost or a rare edge case.

Value:

- Establishes whether structured artifacts solve a real Quest problem.
- Prevents building a new code path for a failure mode that may be rare.

### 2. Prove real-schema structured output

Status: required before runner integration.

Run provider-specific smoke tests against the actual Quest schemas:

- Codex: `codex exec -m gpt-5.5 -c model_reasoning_effort=low --output-schema
  .ai/schemas/handoff.schema.json ...`
- Claude: `claude --print --model claude-opus-4-8 --effort low --json-schema
  '<handoff schema>' ...`

Acceptance criteria:

- The final response validates against `.ai/schemas/handoff.schema.json`.
- The generated object passes Quest's existing handoff validator.
- The smoke uses representative field shape, not a toy `{ "ok": true }` schema.
- The Claude smoke completes without hitting a budget cap.

Value:

- Proves the transport capability is usable for Quest's real contract before
  any orchestration changes are made.
- Separates model/schema viability from runner design.

### 3. Transport-owned structured artifacts

Status: candidate implementation only after steps 1 and 2.

Change the handoff path so the role returns schema-valid final JSON, and the
Quest runner writes the canonical artifact file. For example:

- Claude bridge role returns final JSON via `--json-schema`.
- Codex role returns final JSON via `codex exec --output-schema`.
- The runner validates the returned object and writes `handoff.json` or findings
  JSON atomically.
- Existing validators remain authoritative.
- Existing text/file fallback remains until real runs show it is unused except
  for transport or auth failures.

Acceptance criteria:

- One Claude-designated role and one Codex-designated role can produce the same
  schema-valid handoff through the new path.
- The runner, not the model, writes the canonical JSON artifact.
- Existing `validate-findings`, `validate-backlog`, and handoff validators still
  run.
- Logs distinguish `structured_final_response`, `file_artifact`, `transport_error`,
  and `fallback_used`.
- At least one forced malformed-file test proves the new path does not read a
  stale or invalid agent-written JSON file.

Value:

- Converts a fragile prose instruction into a runtime contract.
- Creates a real reason to simplify recovery later.
- Keeps KISS discipline because the first slice proves deletion is safe before
  deleting anything.

### 4. Stable-prefix prompt assembly with cache telemetry

Status: low semantic risk, value still to be measured.

If usage logs show cacheable, repeated prompt prefixes, build role prompts in
this order:

```text
[stable prefix]
role instructions
AGENTS.md
BOOTSTRAP.md
quest brief

[variable suffix]
iteration feedback
arbiter verdict
git diff
attempt-specific reminders
```

Add lightweight logs for:

- stable prefix byte hash,
- approximate prefix token count,
- provider usage fields for cache creation/read when available,
- latency per role attempt.

Value:

- Lower cost and latency without changing role contracts.
- Gives data to decide whether "fast review" context stripping is still worth
  its complexity.

Do not remove fast-mode behavior in this slice. Measure first.

## Deferred

### Per-role effort as an explicit config knob

Status: real capability, but YAGNI until a specific cost or quality problem is
shown.

Keep the current string model form working:

```json
"planner": "gpt-5.5"
```

Allow an object form:

```json
"planner": { "model": "gpt-5.5", "effort": "high" }
```

Map effort at dispatch:

- Claude CLI: `--effort <level>`.
- Codex CLI: `-c model_reasoning_effort=<level>`.

Initial rollout should not change default effort globally. It should only permit
explicit overrides and record outcome/cost metrics. After enough quests, tune
defaults from data.

Value:

- Enables controlled experiments per quest or per role.
- Avoids hard-coding cost/quality folklore into the default workflow.

## Drop or keep deferred

- Drop: "retire malformed-JSON recovery" as an immediate change.
- Defer: lowering plan/fix iteration caps.
- Defer: removing fast-review context stripping before prompt-cache data exists.
- Defer: per-role effort defaults or schema expansion before a measured need
  exists.
- Drop: backend-specific ideas that force Quest to behave differently per model
  unless the proposal explicitly scopes them as backend-specific.

## Suggested next quest

Run only the measurement and real-schema proof slice:

> Measure current Quest handoff/fallback outcomes and run real-schema structured
> output smokes for Codex GPT-5.5 and Claude Opus 4.8 using
> `.ai/schemas/handoff.schema.json`. Do not add transport-owned artifact writing,
> do not change iteration caps, do not change fast-review behavior, and do not
> add per-role effort config. The output should be a factual go/no-go report for
> whether transport-owned structured artifacts are worth implementing.

That would create facts. The rest can follow from measured evidence.
