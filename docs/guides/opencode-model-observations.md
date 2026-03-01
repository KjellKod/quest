# OpenCode Model Observations

Field notes from Quest orchestration testing. Updated as we learn more.

## Testing Context

- Runtime: OpenCode CLI
- Orchestration: Quest multi-agent pipeline (plan → dual review → arbiter → build → code review → fix)
- Date range: 2026-02-28 onwards

## Model Observations

### Trinity Large Preview (`opencode/trinity-large-preview-free`)

**Tested as:** Orchestrator, Planner
**Verdict:** Excellent planner, unreliable orchestrator

Planner:
- Excellent — structured output, follows prompt contracts well, fast execution
- Consistently produces quality plans that pass dual review

Orchestrator:
- Dispatches subagents via Task tool — real subagent invocation confirmed
- Sequential fan-out only (dispatches reviewer B after reviewer A finishes, not concurrently)
- **CRITICAL: Skips human approval gate.** "Present plan for approval" phase had 0 toolcalls — Trinity said "present" then immediately concluded "user approved" without waiting for input. This is a gate violation.
- Inconsistent gate behavior — respected `auto_approve_phases.implementation: false` in one run but skipped the plan presentation gate in another
- Lost fan-out during one dual review attempt (reviewer A hung, reviewer B never dispatched)
- On resume from slug: re-planned instead of recognizing existing plan artifact
- Tried `.agents/skills/` path before `.skills/` but self-corrected

General:
- Free tier — excellent for cost-sensitive subagent roles (planner, reviewer)
- **Recommendation: Use as planner/subagent, not orchestrator. Opus is more reliable for orchestration with human gates.**

### Claude Opus 4.6 (`opencode/claude-opus-4-6`)

**Tested as:** Orchestrator, Arbiter, Reviewer A
**Verdict:** Proven, reliable

- Full pipeline completion as orchestrator with real subagent dispatch confirmed
- Strong arbiter — correctly synthesized conflicting reviews (Claude approved, Codex iterated), filtered non-blocking issues
- Model self-identification headers confirmed in all artifacts
- Telemetry logged with paired start/finish events
- Most expensive option — best reserved for high-judgment roles (arbiter, orchestrator)

### GPT-5.3 Codex (`opencode/gpt-5.3-codex`)

**Tested as:** Reviewer B (plan), Builder
**Verdict:** Proven for implementation and review

- Successfully reviewed plans with structured output
- Produced genuine disagreement with Claude reviewer (iterated where Claude approved) — real model diversity
- Handoff contract compliance confirmed
- Good for implementation-heavy roles (builder, fixer, reviewer)

### KiMi K2.5 (`opencode/kimi-k2.5`)

**Tested as:** Reviewer B (plan), Orchestrator
**Verdict:** Good reviewer, failed orchestrator

Reviewer:
- Fast execution — noticeably quicker than other models
- Followed review prompt contract and produced structured output
- Adopted "Slot A (Claude)" label from workflow.md legacy naming — read Quest skill files literally and took on the slot name it found there. Artifact self-identification header is the real check.
- Different model family from Codex and Claude — provides genuine review diversity

Orchestrator:
- **Failed.** Did not dispatch any subagents — treated the task as a solo agent problem. No Quest phases, no handoff artifacts, no `.quest/` state.
- Bypassed edit permissions using `cat >` bash instead of Edit tool — circumvented the permission model
- Produced good quality output as a solo agent (485-line document, well-structured, researched via web search) but completely ignored the orchestration contract
- Paid tier model — cost did not help. Same failure class as Trinity (free) and MiniMax (free): none of them coordinate multi-agent pipelines.

**Recommendation: Use as Reviewer B (proven). Do not use as orchestrator, arbiter, or other judgment-heavy roles.**

### Big Pickle (`opencode/big-pickle`)

**Tested as:** Reviewer A (plan)
**Verdict:** Not recommended for agentic roles

- Received prompt and context but produced no output — appeared dead in subagent session
- Known limitation: "Struggles with interactive and multi-step reasoning tasks" (AgentBench), "Falls behind on mathematical reasoning" (AlignBench)
- Not suited for prompt-following tasks that require reading multi-file context and producing structured output
- **Not recommended for any Quest role** — reviewer, arbiter, builder, or fixer all require multi-step agentic reasoning
- Previously configured as fixer but removed — if it can't review, it can't reason about review feedback and fix code either
- 32B active parameters per inference — resource-heavy for its capability level in agentic contexts

### Minimax M2.5 (`opencode/minimax-m2.5-free`)

**Tested as:** Orchestrator, Arbiter, Code Reviewer B, Fixer
**Verdict:** Failed as orchestrator. Untested in subagent roles.

Orchestrator:
- **Does not work as orchestrator.** Failed to drive the Quest pipeline — could not coordinate subagent dispatch and phase transitions.
- Same class of failure as Trinity (both free-tier models struggle with orchestration complexity)
- Strong benchmarks did not translate to reliable multi-agent coordination

Profile (from benchmarks):
- 80.2% SWE-Bench Verified, 84.3% HumanEval — strong coding
- Agentic workflows with autonomous task execution, 76.3% BrowseComp
- "Spec-writing" behavior — plans architecture before coding
- Complex task decomposition, 20% fewer rounds, 37% faster than predecessor
- 80% lower cost than Claude Sonnet 3.5
- Free tier available

**Recommendation: Do not use as orchestrator. May still work for subagent roles (arbiter, reviewer, fixer) — untested. Opus remains the only proven orchestrator.**

## Current Model Table

### Proven Configuration (Opus orchestrator)

| Role | Model | Status |
|------|-------|--------|
| Orchestrator | claude-opus-4-6 | Proven |
| Planner | trinity-large-preview-free | Proven |
| Plan Reviewer A | gpt-5.3-codex | Proven |
| Plan Reviewer B | kimi-k2.5 | Working |
| Arbiter | claude-opus-4-6 | Proven |
| Builder | gpt-5.3-codex | Proven |
| Code Reviewer A | gpt-5.3-codex | Proven |
| Code Reviewer B | trinity-large-preview-free | Untested in this slot |
| Fixer | gpt-5.3-codex | Proven (in builder role) |

### Failed: MiniMax orchestrator

MiniMax failed to drive the Quest pipeline as orchestrator. Config archived, not recommended.

### Failed: KiMi orchestrator

KiMi did not dispatch subagents — acted as solo agent, bypassed permissions via bash. Good output quality but zero orchestration.

### Failed Orchestrators Summary

| Model | Cost | Failure Mode |
|-------|------|-------------|
| trinity-large-preview-free | free | Skipped human gates, lost fan-out |
| minimax-m2.5-free | free | Could not drive pipeline |
| kimi-k2.5 | paid | Solo agent, no subagent dispatch |

**Conclusion: Opus is the only viable orchestrator. Cost tier does not predict orchestration capability.**

### Active Configuration (Opus orchestrator, diverse subagents)

| Role | Model | Cost | Status |
|------|-------|------|--------|
| Orchestrator | claude-opus-4-6 | paid | Proven |
| Planner | trinity-large-preview-free | free | Proven |
| Plan Reviewer A | gpt-5.3-codex | paid | Proven |
| Plan Reviewer B | kimi-k2.5 | paid | Working |
| Arbiter | claude-opus-4-6 | paid | Proven |
| Builder | gpt-5.3-codex | paid | Proven |
| Code Reviewer A | gpt-5.3-codex | paid | Proven |
| Code Reviewer B | minimax-m2.5-free | free | Testing |
| Fixer | gpt-5.3-codex | paid | Proven (in builder role) |

2 free / 7 paid slots. 5 model families: Claude, Trinity, Codex, KiMi, MiniMax.

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

## Key Learnings

1. **Model self-identification in artifacts is essential** — without it, you can't verify real subagent dispatch vs orchestrator role-playing
2. **"runtime=claude" in telemetry is correct even for Codex models** — runtime is the launcher (Claude Code Task tool), model is what runs inside
3. **Big Pickle is not suited for agentic Quest roles** — stalled on a structured review task, known to struggle with multi-step reasoning on AgentBench
4. **Trinity self-corrects on path errors** — tried wrong skill path, found the right one without intervention
5. **Fan-out is the fragile point** — dual review dispatch has failed once under Trinity; sequential dispatch is the norm
6. **Human gates require a reliable orchestrator** — Trinity skipped the plan approval gate (0 toolcalls, auto-concluded "user approved"). Opus respected the gate. For workflows with human checkpoints, Opus as orchestrator is the safe choice.
7. **Subagent slot naming leaks from shared skill files** — KiMi identified as "Slot A (Claude)" because workflow.md uses hardcoded Claude-era slot names. The model self-ID header in artifacts is the authoritative source, not the preamble text.
8. **Model diversity produces real disagreement** — Codex iterated where Claude approved in one run. This validates the dual-review pattern as more than rubber-stamping.
9. **Opus is the only viable orchestrator** — Trinity (free) skipped gates, MiniMax (free) couldn't drive the pipeline, KiMi (paid) acted as solo agent. 0/3 alternatives worked. Cost tier does not predict orchestration capability — only Opus reliably dispatches subagents and respects human gates.
10. **Permission bypass via bash** — KiMi used `cat >` to write files when Edit was denied. The permission model has a bash escape hatch that agentic models will find.
