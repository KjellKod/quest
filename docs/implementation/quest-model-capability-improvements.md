---
title: Quest Model-Capability Improvements (May 2026)
purpose: Validated, backend-symmetric changes that let quest exploit capabilities now common to both Claude (Opus 4.8 / Sonnet 4.6) and OpenAI Codex (GPT-5.5).
audience: Quest maintainers and implementing agents.
scope: Orchestration changes that are model-agnostic — they hold no matter whether a role is filled by Claude or Codex.
status: active
owner: maintainers
last_updated: 2026-05-31
related:
  - .skills/quest/delegation/workflow.md
  - .ai/allowlist.json
  - .ai/schemas/handoff.schema.json
  - scripts/quest_runtime/review_intelligence.py
  - scripts/quest_runtime/orchestration.py
---

# Quest Model-Capability Improvements (May 2026)

## Why this matters

Quest assigns each role to either Claude or Codex (`.ai/allowlist.json` `models.*`).
A change is only safe to bake into the orchestrator if it improves outcomes
**regardless of which backend fills the role**. This document lists only such
backend-symmetric changes, and only ones anchored to a capability that **both**
families verifiably shipped as of May 2026. Claude-only or Codex-only levers are
listed at the bottom under "Deliberately excluded" so the filter is auditable.

Inclusion bar (per request): *every item below is something we know for a fact
improves things and know how to make happen.* Speculative items are quarantined
in the "Needs measurement" section and are **not** recommendations.

### Capability baseline (both families, May 2026)

| Capability | Claude (Opus 4.8 / Sonnet 4.6) | Codex (GPT-5.5) | Quest today |
|---|---|---|---|
| Strict schema-enforced output | `output_format` grammar-constrained decode + `strict` tool args | `json_schema` strict (default); CLI `codex exec --output-schema <file>` | Asks for JSON in prose, then validates after the fact |
| Per-call / per-agent reasoning effort | `effort` (low/med/high); CLI-exposed | `reasoning.effort` none/low/medium/high/xhigh; per-agent + CLI | Only a model *name* per role; no tuning |
| Prompt caching of a stable prefix | Yes (a forked subagent reuses the parent's prompt cache) | Yes (automatic for stable leading content) | No cache-awareness; core files re-read every call |

Sources: Anthropic models overview and structured-outputs / effort docs
(`platform.claude.com/docs/en/about-claude/models/overview`,
`/build-with-claude/structured-outputs`); OpenAI Codex non-interactive and
subagents docs (`developers.openai.com/codex/noninteractive`,
`/codex/subagents`, `/api/docs/models/gpt-5.5`). Retrieved 2026-05-31.

---

## Improvement 1 — Enforce structured output at generation; retire malformed-JSON recovery

**Status: validated. Highest leverage.**

### The fact it rests on
Both backends now *guarantee* schema-valid JSON at decode time:
- Claude: `output_format` compiles the schema into a decode-time grammar; the
  returned text is guaranteed to validate. `strict: true` does the same for
  tool-call arguments.
- Codex/GPT-5.5: strict `json_schema` is the default; the CLI exposes
  `codex exec --output-schema <file.json>` to force the final message to conform.

### What quest does today (and why)
Quest treats "the model might emit prose instead of JSON" as the normal case and
spends significant machinery recovering from it:
- The `---HANDOFF---` text fallback parser (`scripts/quest_runtime/claude_runner.py:170-174`).
- The contract validator that *requires* role files to use the text
  `---HANDOFF---` format rather than embedded JSON
  (`scripts/quest_validate-handoff-contracts.sh:51-58`).
- The three-tier fallback ladder for "missing/unparsable handoff"
  (`.skills/quest/delegation/workflow.md` Handoff File Polling §6).
- The per-slot findings gate's "structure the review you already wrote" retry
  (`.skills/quest/delegation/workflow.md`, findings-compliance section; vocabulary
  `found_retry`/`fallback`/`missing_block`).

The schemas already exist — `.ai/schemas/handoff.schema.json` and the findings
schema in `scripts/quest_runtime/review_intelligence.py:12-52` — they are simply
validated *after* generation, never *enforced during* it.

### The change
Pass the existing schema through the transport so the model is constrained at
generation:
- Codex roles: add `--output-schema <schema>` to the `codex exec` invocation for
  the artifact that must be JSON (`handoff.json`, findings JSON).
- Claude roles: use `output_format` with the same schema in the bridge/native call.

Then demote the malformed-JSON recovery paths to a **transport-error-only** safety
net:
- Keep cross-runtime fallback for genuine failures (timeout, auth, CLI-missing) —
  those are real and unrelated to JSON validity.
- Keep `validate-findings` / `validate-backlog` — schema-valid is not the same as
  semantically correct; the gate stays.
- Remove the "model returned prose, re-ask it to emit JSON" retry and treat the
  `---HANDOFF---` text parse as legacy compatibility only.

### Why it is a real improvement
It is a net **deletion** of code (KISS / YAGNI per `AGENTS.md`): the premise the
recovery machinery was built on — a capable model failing to produce valid JSON —
no longer holds on either backend. Fewer retries also means lower cost and
latency on every phase.

### Caveat
Roles still emit prose *commentary* around the JSON artifact; structured output
applies to the artifact files, not necessarily the whole turn. Confirm each
backend's flag constrains the file write quest relies on, and keep the validator.

---

## Improvement 2 — Add per-role reasoning effort to the model contract

**Status: validated.**

### The fact it rests on
Both backends expose reasoning effort per call / per sub-agent:
- Claude: `effort` (e.g. low / medium / high); Opus 4.8 defaults to high.
- Codex/GPT-5.5: `reasoning.effort` with none / low / medium (default) / high / xhigh,
  settable per agent (`model_reasoning_effort`) and per CLI call.

### What quest does today
The per-role config carries only a model *name* (`.ai/allowlist.json:22-31`;
`scripts/quest_runtime/orchestration.py` `DEFAULT_MODELS`). There is **no**
per-role effort, thinking budget, temperature, or token tuning anywhere in
`orchestration.json` or the bridge (`scripts/quest_claude_bridge.py` passes only
`--model`, prompts, and permission flags).

### The change
Allow each role entry to be either a string (back-compatible) or an object:

```jsonc
"planner":  { "model": "gpt-5.5", "effort": "high" },
"fixer":    { "model": "gpt-5.5", "effort": "low"  },
"plan-reviewer-a": "claude"        // string form still valid → backend default
```

Map `effort` to each backend's native flag at dispatch (Claude `effort`,
Codex `model_reasoning_effort` / `reasoning.effort`). Validate the value against
each backend's allowed set in the chooser, alongside the existing model
availability check.

### Suggested defaults (judgment-heavy = high, mechanical = low)
- **high:** planner, arbiter, review-arbiter, plan/code reviewers.
- **low / medium:** fixer (backlog-driven, mechanical), and the router
  classification (`.skills/quest/delegation/router.md`) which already emits a
  small fixed JSON.

### Why it is a real improvement
It is purely additive (string form keeps working) and symmetric across backends.
It raises quality where judgment matters and cuts cost/latency on the mechanical
roles — the same dial, on either family.

---

## Improvement 3 — Order prompts for prompt-cache hits (stable prefix first)

**Status: validated mechanism; magnitude to be measured.**

### The fact it rests on
Both backends cache a stable leading prompt prefix and bill/serve repeats of it
cheaply: Claude reuses a forked sub-agent's prompt cache from the parent; Codex
automatically caches stable leading content. Both vendors' guidance is the same:
keep invariant content at the front.

### What quest does today
Every role re-reads its instruction `.md` + `AGENTS.md` + `BOOTSTRAP.md` + the
brief (+ plan, + diff) on each invocation, with no cache-awareness. The
"full vs fast" prompt split (`.skills/quest/delegation/workflow.md`,
Plan Reviewers section) exists largely to *avoid paying* for re-reading
`BOOTSTRAP.md` / `AGENTS.md`.

### The change
Construct every role prompt as:

```
[ STABLE PREFIX — byte-identical across calls ]
  role instructions + AGENTS.md + BOOTSTRAP.md + quest_brief.md
[ VARIABLE SUFFIX ]
  iteration feedback, arbiter verdict, git diff, per-attempt reminders
```

The planner → review → arbiter loop re-runs the same prefix many times per quest,
so the cacheable surface is large.

### Why it is a real improvement
The same shared context, read by many sub-agents across many iterations, is
exactly the workload prompt caching is designed for, on both families. It lowers
fan-out cost and latency without changing any contract.

### Knock-on simplification (optional, follow-up)
Once the shared prefix is cached, the cost rationale for stripping
`BOOTSTRAP.md` / `AGENTS.md` in "fast mode" weakens. `fast_review_thresholds`
(`.ai/allowlist.json:40-42`) can be kept as a *review-depth* signal while the
context-stripping behavior is dropped — fewer prompt variants to maintain. Treat
this as a separate change gated on measured cache hit rates.

---

## Needs measurement — NOT yet a recommendation

- **Lowering iteration caps.** `gates.max_plan_iterations: 4` and
  `max_fix_iterations: 3` (`.ai/allowlist.json:252-253`) are plausibly generous
  given stronger 2026 models, but no dated, quantified autonomy benchmark was
  confirmed from a primary source. Decide from the data quest already collects
  (`.quest/<id>/logs/context_health.log`, `parallelism.log`) — do **not** change
  blind.

## Deliberately excluded — not backend-symmetric

These are real 2026 capabilities but favor one backend, so they do **not** belong
in a backend-neutral orchestrator contract:
- **1M context exploited in-CLI.** Claude Code exposes 1M; the Codex CLI is
  product-capped (~400k effective) as of May 2026. A role told to rely on 1M
  would behave differently per backend.
- **`CLAUDE_CODE_SUBAGENT_MODEL` / fork-cache.** Claude-specific sub-agent
  plumbing; no Codex equivalent in the same form.

---

## Rollout order

1. **Improvement 1** (strict output + recovery slimming) — biggest win, and it
   reduces surface area before other changes touch it.
2. **Improvement 2** (per-role effort) — additive config + dispatch mapping.
3. **Improvement 3** (cache-friendly prompt ordering) — prompt construction only;
   measure hit rate before the fast-mode simplification.

Each is independently shippable and independently testable.
