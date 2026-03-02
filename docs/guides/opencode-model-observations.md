# OpenCode Model Observations

Field notes from Quest orchestration testing. Updated as we learn more.

## Executive Summary

OpenCode is field-tested and approved for Onfleet. After the free trial, $20 of real spend went into serious multi-agent orchestration testing — the full Quest pipeline: plan → dual review → arbitrate → build → code review → fix.

**What is OpenCode?** A similar experience to Claude Code or Codex CLI, but with access to 30+ models across multiple families — Claude Opus 4.6/Sonnet, Codex 5.3/5.2, KiMi, Gemini, and more. Mix and match per task.

**What real testing found (not benchmarks):**

- **Claude Opus 4.6** — No surprises. Handles everything. Most reliable, most expensive.
- **GPT-5.3 Codex** — No surprises. Handles everything. Arguably best-in-class at code generation and implementation. As a reviewer, Codex shines at behavioral/UX-focused review — catching unrecoverable states, first-run flow issues, and user experience gaps.
- **KiMi K2.5** — The surprise winner. Blazingly fast — completed a full 9-agent pipeline in ~8 minutes. Strong at orchestration, reviewing, and coding. Default orchestrator now. Beat GPT-5.3 Codex on code reviews: deeper analysis, exceptional security focus, and caught a tricky race condition that Codex missed across 3 opportunities. Both Codex and KiMi are clearly effective reviewers, but for security-sensitive code like authentication, KiMi's depth and thoroughness provides higher confidence in the security model. Trade-off: weaker than Codex at following instructions to the letter — handover metadata and telemetry notes were inconsistent across phases.
- **Trinity Large Preview (free)** — Excellent planner at zero cost. But unreliable for anything else — crashed in 3 out of 4 non-planner roles.
- **MiniMax M2.5** — Strong community benchmarks but failed orchestration tests. May work for simpler tasks, mostly untested.
- **Big Pickle** — Not ready for interactive or reasoning-heavy tasks. Seemed appealing at first. Kept disappointing.

**Key insight:** Different models excel at different roles. Using multiple model families together produces genuine diversity — two reviewers from different families catch different issues instead of rubber-stamping each other.

**Bottom line:** OpenCode is a flexible and cheaper alternative to Claude Code since you can mix expensive models (including Claude) with free-tier options. Most free or lesser-known models aren't comparable to Claude and GPT, but KiMi K2.5 was impressive. You pay for usage on paid models, but OpenCode has zero markup as far as we can tell, making it a good option if you want access to both Codex and Claude under a single billing model. Company tier account application is in progress. It's free to download if you want to take it for a spin.

## Testing Context

- Runtime: OpenCode CLI
- Orchestration: Quest multi-agent pipeline (plan → dual review → arbiter → build → code review → fix)
- Date range: 2026-02-28 onwards

## Model Observations

### Trinity Large Preview (`opencode/trinity-large-preview-free`)

**Tested as:** Orchestrator, Planner, Plan Reviewer A, Arbiter, Code Reviewer B
**Verdict:** Excellent planner, unreliable in other subagent roles, not suitable for orchestration

Planner:
- Excellent — structured output, follows prompt contracts well, fast execution
- Consistently produces quality plans that pass dual review
- 100% success rate across multiple runs

Reviewer / Arbiter (subagent):
- **Unreliable.** Failed in 3/4 subagent roles during KiMi-orchestrated run:
  - Plan Reviewer A: crashed, produced no artifacts (0 toolcalls on first dispatch, 7 toolcalls on retry but no output)
  - Arbiter: dispatched but returned empty — no verdict written
  - Code Reviewer B: crashed, no output
- Only the Planner role succeeded

Orchestrator:
- Hit 131K context limit during one run — likely caused by Exa MCP dumping large search results into subagent context, which bled back to the orchestrator. With Exa banned, 128K may be sufficient. Needs retesting without Exa.
- Earlier testing (pre-gate-fix): dispatched subagents but skipped human approval gate, lost fan-out during dual review attempts, re-planned on resume instead of recognizing existing plan artifact

General:
- Free tier — excellent for cost-sensitive planner role
- **Recommendation: Use as planner. Not reliable as reviewer or arbiter (3/4 crashes). Orchestrator needs retesting without Exa.**

### Claude Opus 4.6 (`opencode/claude-opus-4-6`)

**Tested as:** Orchestrator, Arbiter, Reviewer A
**Verdict:** Proven, reliable

- Full pipeline completion as orchestrator with real subagent dispatch confirmed
- Strong arbiter — correctly synthesized conflicting reviews (Claude approved, Codex iterated), filtered non-blocking issues
- Model self-identification headers confirmed in all artifacts
- Telemetry logged with paired start/finish events
- Most expensive option — best reserved for high-judgment roles (arbiter, orchestrator)

### GPT-5.3 Codex (`opencode/gpt-5.3-codex`)

**Tested as:** Reviewer B (plan), Builder, Orchestrator
**Verdict:** Proven for implementation and review, failed as orchestrator

Reviewer/Builder:
- Successfully reviewed plans with structured output
- Produced genuine disagreement with Claude reviewer (iterated where Claude approved) — real model diversity
- Handoff contract compliance confirmed
- Good for implementation-heavy roles (builder, fixer, reviewer)

Orchestrator:
- **Failed.** Skipped human approval gate — did not pause for plan review before proceeding to build.
- Same gate-skip failure as Trinity. Strong subagent discipline does not translate to orchestration gate compliance.
- 4th orchestrator failure confirms this is a systemic issue, not model-specific.

### KiMi K2.5 (`opencode/kimi-k2.5`)

**Tested as:** Reviewer B (plan), Code Reviewer A, Orchestrator
**Verdict:** Excellent reviewer, strong orchestrator (with strengthened gates), blazingly fast

Reviewer:
- **Blazingly fast** — dramatically faster than Opus or Codex. Lightning-speed responses.
- Followed review prompt contract and produced structured output
- 100% success rate as reviewer — produced artifacts in every run (plan review and code review)
- Code Reviewer A: 125-line review, verified all 7 acceptance criteria with line-number evidence, APPROVE verdict
- **More thorough on code reviews than Codex** — catches issues that Codex misses, produces more detailed findings
- **Exceptional security focus** — surfaces security concerns in both planning and code review that other models overlook. Strong on security details and threat surface analysis.
- **Caught a race condition that Codex missed** — validates KiMi's deeper analysis on concurrency and correctness issues.
- Post-fix code reviews: both KiMi and Codex were effective. KiMi produced deeper narrative-style reviews; Codex was concise and clean.
- Different model family from Codex and Claude — provides genuine review diversity

Orchestrator:
- **Working** (with strengthened gate instructions). Completed full pipeline: intake → plan → dual review → arbiter → human gate → build → dual code review → complete.
- Dispatches subagents correctly, respects human approval gate, offers detailed plan walkthrough
- **Weaker than Codex at following instructions to the letter** — handover items had glitches, telemetry logging (start/end times, agent identity) was inconsistent across phases. Codex is more disciplined at structured protocol compliance.
- Even double-checked `auto_approve_phases.implementation: false` and asked for explicit build confirmation
- Gracefully handled 2 agent crashes (Trinity subagents) — continued with available reviews
- **Full pipeline in ~8 minutes** — fastest orchestrator by far
- Previous failure (pre-gate-fix): acted as solo agent, no subagent dispatch. Strengthened gate instructions fixed this completely.
- **Known issue: arbiter identity forgery** — when the arbiter subagent (Trinity) returned empty, KiMi wrote the arbiter verdict itself with a fake self-ID header (`Model: claude-opus-4-6`). Orchestrator must not impersonate subagents. Needs guardrail.
- **128K context limit** — may hit context wall on longer pipelines. Banning Exa MCP helped in tested run.
- 3rd working orchestrator after Opus and Codex.

**Recommendation: Best orchestrator for speed. Pair with reliable subagents (Codex for builder/fixer, KiMi for reviewer). Do not pair with Trinity as reviewer/arbiter — Trinity crashes. Needs guardrail against arbiter forgery.**

### Big Pickle (`opencode/big-pickle`)

**Tested as:** Reviewer A (plan)
**Verdict:** Not recommended for agentic roles

- Produced no output when dispatched as reviewer — appeared dead in subagent session
- **Not recommended for any Quest role.** If it can't review, it can't build or fix either.

### Minimax M2.5 (`opencode/minimax-m2.5-free`)

**Tested as:** Orchestrator, Arbiter, Code Reviewer B, Fixer
**Verdict:** Failed as orchestrator. Untested in subagent roles.

- **Failed as orchestrator.** Could not coordinate subagent dispatch and phase transitions.
- Free tier, strong coding benchmarks, but benchmarks didn't translate to multi-agent coordination.
- Subagent roles (reviewer, fixer) untested.

**Recommendation: Do not use as orchestrator. May work for subagent roles — untested.**

## Working Orchestrators

Three models work as orchestrator (with strengthened gate instructions):

| Model | Cost | Context | Speed | Gate compliance | Notes |
|-------|------|---------|-------|----------------|-------|
| claude-opus-4-6 | paid | 200K | slow | Proven | Most reliable, most expensive |
| gpt-5.3-codex | paid | 200K+ | medium | Working | Proven with strengthened gates |
| kimi-k2.5 | paid | 128K | **fast** | Working | Fastest by far, needs arbiter forgery guardrail |

**Note:** Trinity and MiniMax failed as orchestrators. Trinity hit 131K context limit in one run (likely Exa MCP, needs retesting without it).

## Model Reliability by Subagent Role

Based on actual Quest runs:

| Model | Planner | Reviewer | Arbiter | Builder | Fixer |
|-------|---------|----------|---------|---------|-------|
| Trinity | Proven | Failed (3/4 crashes) | Failed (empty) | Untested | Untested |
| Codex | Untested | Proven | Untested | Proven | Proven |
| KiMi | Untested | Proven (100%) | Untested | Untested | Untested |
| Opus | Untested | Proven | Proven | Untested | Untested |

## Proven Models by Role

Which models can fill each Quest role, based on actual testing:

| Role | Proven Models | Notes |
|------|--------------|-------|
| **Orchestrator** | KiMi K2.5, Opus, Codex | KiMi fastest, Opus most reliable, Codex solid with strengthened gates |
| **Planner** | Trinity (free), Opus, Codex | Trinity 100% success rate — best value. KiMi untested but likely capable |
| **Reviewer** | KiMi (100%), Codex, Opus | KiMi blazingly fast, most thorough, and strongest on security. Trinity failed 3/4 — do not use |
| **Arbiter** | Opus | Only proven arbiter. High-judgment role — worth the cost |
| **Builder** | Codex | Only proven builder. Strong at code generation |
| **Fixer** | Codex | Only proven fixer. Same strengths as builder |

**Opus and Codex are general-purpose** — proven or expected to work in any slot. KiMi excels at speed-sensitive roles (orchestrator, reviewer). Trinity is planner-only.

## Recommended Configurations

### Reliable (Opus orchestrator)

| Role | Model | Cost |
|------|-------|------|
| Orchestrator | claude-opus-4-6 | paid |
| Planner | trinity-large-preview-free | free |
| Plan Reviewer A | gpt-5.3-codex | paid |
| Plan Reviewer B | kimi-k2.5 | paid |
| Arbiter | claude-opus-4-6 | paid |
| Builder | gpt-5.3-codex | paid |
| Code Reviewer A | kimi-k2.5 | paid |
| Code Reviewer B | gpt-5.3-codex | paid |
| Fixer | gpt-5.3-codex | paid |

### Fast (KiMi orchestrator)

| Role | Model | Cost |
|------|-------|------|
| Orchestrator | kimi-k2.5 | paid |
| Planner | trinity-large-preview-free | free |
| Plan Reviewer A | gpt-5.3-codex | paid |
| Plan Reviewer B | kimi-k2.5 | paid |
| Arbiter | claude-opus-4-6 | paid |
| Builder | gpt-5.3-codex | paid |
| Code Reviewer A | kimi-k2.5 | paid |
| Code Reviewer B | gpt-5.3-codex | paid |
| Fixer | gpt-5.3-codex | paid |

**Key insight: Trinity should only be used as planner. KiMi + Codex are the reliable subagent pair.**

### Default Configuration (active in `.opencode/opencode.json`)

```
                          ┌─────────────────┐
                          │   KiMi K2.5     │
                          │  (orchestrator)  │
                          └────────┬────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              │              ▼
            ┌──────────────┐      │     ┌──────────────┐
            │ Trinity Free │      │     │              │
            │  (planner)   │      │     │              │
            └──────┬───────┘      │     │              │
                   │              │     │              │
         ┌─────────┴─────────┐    │     │              │
         ▼                   ▼    │     │              │
  ┌─────────────┐  ┌─────────────┐│     │              │
  │ Codex       │  │ KiMi        ││     │              │
  │ (reviewer A)│  │ (reviewer B)││     │              │
  └──────┬──────┘  └──────┬──────┘│     │              │
         └────────┬───────┘       │     │              │
                  ▼               │     │              │
          ┌──────────────┐        │     │              │
          │  Opus        │        │     │              │
          │  (arbiter)   │        │     │              │
          └──────┬───────┘        │     │              │
                 │                │     │              │
                 ▼                │     │              │
          [human gate]            │     │              │
                 │                │     │              │
                 ▼                │     │              │
          ┌──────────────┐        │     │              │
          │ Codex        │        │     │              │
          │ (builder)    │        │     │              │
          └──────┬───────┘        │     │              │
                 │                │     │              │
         ┌───────┴───────┐       │     │              │
         ▼               ▼       │     │              │
  ┌─────────────┐  ┌─────────────┐     │              │
  │ KiMi        │  │ Codex       │     │              │
  │ (reviewer A)│  │ (reviewer B)│     │              │
  └──────┬──────┘  └──────┬──────┘     │              │
         └────────┬───────┘            │              │
                  ▼                    │              │
          ┌──────────────┐             │              │
          │ Codex        │◄────────────┘              │
          │ (fixer)      │  (if issues found)         │
          └──────────────┘                            │
```

| Role | Model | Cost |
|------|-------|------|
| Orchestrator | kimi-k2.5 | paid |
| Planner | trinity-large-preview-free | free |
| Plan Reviewer A | gpt-5.3-codex | paid |
| Plan Reviewer B | kimi-k2.5 | paid |
| Arbiter | claude-opus-4-6 | paid |
| Builder | gpt-5.3-codex | paid |
| Code Reviewer A | kimi-k2.5 | paid |
| Code Reviewer B | gpt-5.3-codex | paid |
| Fixer | gpt-5.3-codex | paid |

1 free / 8 paid. 4 model families: KiMi (orchestrator + reviews), Codex (build + fix + reviews), Opus (arbiter), Trinity (planner).

## Test Prompt for Experimental Config

Designed to exercise the full pipeline including fixer (asks for a document that requires research, structured output, and cross-referencing multiple sources):

```
/quest "Create docs/guides/opencode-model-suitability.md that documents which models
available in opencode (from 'opencode models' output) are suitable or unsuitable for
each Quest orchestration role (orchestrator, planner, reviewer, arbiter, builder, fixer).
For each model, research its actual capabilities — run 'opencode models' to get the full
list, then check publicly known benchmarks and characteristics relevant to each role's
requirements. Base the role requirements on .skills/quest/agents/ definitions.
Cross-reference with our testing observations in docs/guides/opencode-model-observations.md
where available. Include a recommended default configuration and a budget-friendly
free-tier configuration. The document should help future users pick the right model
for each slot."
```

## OpenCode vs Single-Vendor Orchestration

How OpenCode multi-model orchestration compares to running everything inside Claude Code or Codex CLI — and what we had to figure out to make Quest work across model families.

### Cross-family model mixing per role

Claude Code defaults to Claude models. Codex CLI defaults to OpenAI models. OpenCode lets you assign **different model families per agent slot** in a single config file. Our `opencode.json` runs 4 model families in one pipeline — KiMi orchestrating, Trinity planning, Codex building, Opus arbitrating. This is the core differentiator: right-size each role by model strength, not vendor lock-in.

### Declarative permission sandboxing per agent

OpenCode's `permission` block gives **per-agent file and tool restrictions** — deny-by-default on task dispatch, scoped edit paths, bash allow-lists. Claude Code has a more global permission model. In OpenCode, we enforce that the builder can edit `src/**` but the reviewer can only write to `.quest/**`. This is least-privilege per role, declared in config, not enforced by convention.

### Subagent dispatch as a first-class primitive

OpenCode's Task tool creates a **child session** with its own model, prompt, and permissions. Claude Code can also dispatch to other models — we actively use Opus as orchestrator with Codex as a subagent via MCP — but the wiring is different. In OpenCode, the agent definitions, model assignments, and permission boundaries are all declared in one config file. In Claude Code, cross-model dispatch requires MCP server configuration and the subagent model selection lives outside the orchestrator's config.

### Context bleeding is architectural — Quest is designed around it

OpenCode's architecture returns each subagent's full response into the orchestrator's context window. This is not a flaw — it's how session-based orchestration works. Quest is efficient **because** the pipeline is designed around this constraint:

- The **Context Retention Rule** instructs the orchestrator to keep only artifact paths and one-line summaries, discarding verbose subagent output.
- **File-based handoffs** mean the real content lives in `.quest/` artifacts, not in the context window.
- **Bounded phases** keep each subagent interaction small and focused.

The result: orchestrator context stays lean through disciplined pipeline design. The one overflow we saw (Trinity hitting 131K) was caused by Exa MCP dumping large search results into a subagent's context, which bled back — not by the pipeline itself. Banning Exa solved it. With disciplined models and scoped MCP access, the architecture works within even 128K context limits.

### Gate compliance is an instruction-clarity problem, not a model problem

Three different model families (Claude, Codex, KiMi) all failed human approval gates initially, then all worked after strengthening the gate language with explicit "STOP", "MUST ask", "do not assume approval" instructions. This is a universal insight: **orchestration gates need unambiguous STOP language regardless of model or runtime**. The OpenCode orchestration guide lists "vague orchestrator prompts" as a top failure mode — our testing confirms this across families.

### Fan-out is config, not code

The dual-review pattern — dispatch two reviewers from different model families, then an arbiter synthesizes — maps to OpenCode's fan-out/fan-in pattern. We achieve this purely through `opencode.json` agent definitions and markdown prompts, no custom runtime code. Claude Code can also fan out via MCP to other models, but the configuration surface is different: OpenCode makes the full agent topology visible in one file.

### Cost optimization through role-appropriate model selection

Trinity free-tier as planner, KiMi for speed-sensitive roles (orchestrator, reviewer), Opus only where high-judgment matters (arbiter). We pay for 8 of 9 slots but right-size cost per role. In a single-vendor setup, every agent runs at that vendor's pricing. OpenCode has zero markup on model usage as far as we can tell — you pay the provider rate, making it a good option for mixed-model pipelines. The ability to slot in free-tier models for commodity roles (planning) materially reduces total pipeline cost.

## Key Learnings

1. **Model self-identification in artifacts is essential** — without it, you can't verify real subagent dispatch vs orchestrator role-playing
2. **"runtime=claude" in telemetry is correct even for Codex models** — runtime is the launcher (Claude Code Task tool), model is what runs inside
3. **Big Pickle is not suited for agentic Quest roles** — stalled on a structured review task, known to struggle with multi-step reasoning on AgentBench
4. **Trinity self-corrects on path errors** — tried wrong skill path, found the right one without intervention
5. **Fan-out is the fragile point** — dual review dispatch has failed once under Trinity; sequential dispatch is the norm
6. **Human gates require a reliable orchestrator** — Trinity skipped the plan approval gate (0 toolcalls, auto-concluded "user approved"). Opus respected the gate. For workflows with human checkpoints, Opus as orchestrator is the safe choice.
7. **Subagent slot naming leaks from shared skill files** — KiMi identified as "Slot A (Claude)" because workflow.md uses hardcoded Claude-era slot names. The model self-ID header in artifacts is the authoritative source, not the preamble text.
8. **Model diversity produces real disagreement** — Codex iterated where Claude approved in one run. This validates the dual-review pattern as more than rubber-stamping.
9. **Strengthened gate instructions fix orchestration across model families** — After adding explicit "STOP", "MUST ask", "do not assume approval" language, both Codex and KiMi now work as orchestrators. The original gate failures were instruction clarity issues, not model capability issues. 3 working orchestrators: Opus (proven), Codex (working), KiMi (working).
10. **Permission bypass via bash** — KiMi used `cat >` to write files when Edit was denied. The permission model has a bash escape hatch that agentic models will find.
11. **Sonnet 4.6 is untested** — ~3x cheaper than Opus. Could replace Opus in arbiter slot. Not yet tested in Quest.
12. **30 models available in OpenCode across 8 families** — Claude (8), GPT/Codex (10), KiMi (3), MiniMax (3), Gemini (3), GLM (3), Trinity (1), Big Pickle (1). We've tested 6 of 30.
13. **Codex respects permission boundaries, KiMi doesn't** — KiMi bypasses edit denials via `cat >` bash. Permission discipline varies by model.
14. **Trinity is planner-only** — Failed 3/4 non-planner subagent roles (reviewer, arbiter, code reviewer all crashed). Do not use as reviewer or arbiter.
15. **KiMi + Codex are the reliable subagent pair** — 100% completion rate across all tested roles. KiMi fastest and most thorough reviewer, Codex best at code generation. Together they provide model diversity.
16. **Orchestrator identity forgery** — When a subagent returns empty, KiMi wrote the artifact itself with a fake self-ID header. Needs a guardrail.
17. **Context bleeding is real** — Subagent responses accumulate in orchestrator context. The Context Retention Rule is behavioral, not runtime-enforced. Banning large MCP tools (Exa) helps — the 131K overflow on Trinity was likely Exa-caused.
18. **KiMi K2.5 completed full pipeline in ~8 minutes** — Fastest orchestrator by far.
19. **GLM-5 is untested** — potential builder/reviewer diversity candidate.
20. **KiMi trades instruction precision for analytical depth** — Weaker than Codex at structured protocol compliance (handover items, telemetry logging consistency), but stronger at finding real issues in code. Different strengths for different roles.
