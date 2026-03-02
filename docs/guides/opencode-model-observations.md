# OpenCode: Field Notes from Multi-Model Orchestration

We put $20 into OpenCode and ran 30+ models through a real multi-agent pipeline. Some models surprised us. Some disappointed. One completely changed how we think about code review.

---

## What We Were Testing

**OpenCode** gives you something Claude Code and Codex CLI don't: access to 30+ models across multiple families — Claude, GPT/Codex, KiMi, Gemini, Trinity, and more — with the ability to assign different models to different roles in a single pipeline.

We tested this with **Quest**, a 9-agent orchestration pipeline:

```
     ┌─────────────────────────────────────────────────────────┐
     │                      ORCHESTRATOR                       │
     │               (coordinates all phases below)            │
     └──┬───────┬────────┬────────┬────────┬─────────┬───────┬─┘
        │       │        │        │        │         │       │
        ▼       ▼        ▼        ▼        ▼         ▼       ▼
      plan  →  dual → arbiter → gate  →  build  →  dual  →  fix
              review             ⇑                review
                               [human]
```

Seven phases, nine agents, each slot running a different model. The question: does mixing model families actually produce better results than running everything on one vendor's best model?

The answer turned out to be yes — but not for the reasons we expected.

### A note on how Quest orchestrates

Quest doesn't use code to drive or enforce orchestration. There's no runtime state machine, no programmatic guardrails. The entire pipeline — phase transitions, human gates, handoff contracts, permission boundaries — is driven by **LLM instruction-following**. Markdown prompts, not code.

This is likely atypical for multi-agent orchestration. Most frameworks use code to enforce control flow. But the instruction-driven approach has a real advantage: **portability**. The same Quest skills and agent definitions work as a near drop-in across Claude Code, Codex CLI, Cursor IDE, Vibe-Kanban IDE, and now OpenCode. No runtime to port, no SDK to integrate. If the tool can follow markdown instructions and dispatch subagents, Quest runs on it.

The trade-off is that every "bug" in this document — skipped gates, identity forgery, permission bypasses — exists because there's no code enforcing the rules. The LLM has to *choose* to follow them. Some models are better at this than others, which is exactly what this document measures.

---

## The Models That Worked

### ✅ Claude Opus 4.6 — The Reliable Veteran

**Tested as:** Orchestrator, Arbiter, Reviewer, Builder, Fixer

No surprises here. Opus handles everything — orchestration, arbitration, all the roles — with consistent quality. Full pipeline completion, correct subagent dispatch, proper telemetry logging. Every artifact had self-identification headers. Every gate was respected.

The catch is cost. Opus is expensive, and you don't need it everywhere. We found its sweet spot: **arbiter**. The role that synthesizes conflicting reviews and makes judgment calls is exactly where you want the most capable model. In one run, Opus correctly filtered non-blocking issues from two reviewers who disagreed, keeping the pipeline moving without losing signal.

### ✅ GPT-5.3 Codex — The Disciplined Builder

**Tested as:** Reviewer, Builder, Fixer, Orchestrator

Codex is the workhorse. Best-in-class at code generation and implementation. As a builder and fixer, it just works — structured output, handoff contract compliance, clean artifacts every time.

What surprised us was its review style. Codex shines at **behavioral and UX-focused review** — it catches unrecoverable states, first-run flow issues, and user experience gaps that other models gloss over. Post-fix reviews are concise and clean. No fluff.

Codex also has the strongest **instruction discipline** of any model we tested. Handover items are consistent. Telemetry logging (start/end times, agent identity) is accurate across phases. When the protocol says to do something, Codex does it.

As orchestrator, it initially skipped the human approval gate — but so did every non-Opus model. After applying strengthened gate instructions, the problems went away.

### ✅ 🚀 KiMi K2.5 — The One That Changed Everything 

**Tested as:** Reviewer, Code Reviewer, Orchestrator

KiMi K2.5 was supposed to be a quick experiment. It became our **default** orchestrator.

**Speed.** KiMi completed the full 9-agent pipeline in ~8 minutes. For context, the same pipeline takes significantly longer with Opus or Codex orchestrating. The speed difference isn't marginal — **it's dramatic**.

**Review depth.** This is where KiMi genuinely surprised us. In head-to-head code reviews against Codex, KiMi consistently went deeper. It caught issues Codex missed. It surfaced security concerns — threat surface analysis, authentication edge cases — that other models overlooked entirely.

#### 🏆 The defining moment

**KiMi caught a race condition that Codex never found — despite 3 separate opportunities.** Same code, same review prompt. Codex had 3 opportunities to catch it and missed it every time. KiMi found it on the first pass.

For security-sensitive code — authentication, session handling, anything with concurrency — **KiMi's depth provides materially higher confidence than Codex**. Both models are effective reviewers, but they see different things. Codex catches UX and behavioral issues really well. KiMi catches security and correctness issues. Together, they don't rubber-stamp each other. They genuinely disagree, and that disagreement is valuable.

Post-fix, both were effective. KiMi produced deeper, narrative-style reviews. Codex was concise and clean. Different styles, both useful.

##### The trade-off

**KiMi is weaker**  than Codex at following instructions to the letter. Handover items had glitches. Telemetry notes — start times, end times, agent identity — were inconsistent across phases. Where Codex is meticulous about protocol compliance, KiMi is... *creative*. It gets the job done, but the metadata isn't always clean.

Despite these rough edges, KiMi earned its spot. For speed and analytical depth, nothing else comes close.

---

## The Models That Didn't

### ✅   Trinity Large Preview (free) — Planner Only 🤔

**Trinity is an excellent planner**. 100% success rate across multiple runs — structured output, follows prompt contracts, fast execution. At zero cost, it's the best value in the pipeline. Codex, Kimi, Opus all agreed with Trinity's planning.

❌ Everything else failed. Trinity crashed in 3 out of 4 non-planner roles: plan reviewer (no output after 7 tool calls), arbiter (dispatched, returned empty), code reviewer (crashed). 

**Use it as a planner. Don't use it for anything else.**

### ❌ MiniMax M2.5 (free) — Benchmarks Lied

Strong community benchmarks. Failed orchestration immediately — couldn't coordinate subagent dispatch or phase transitions. May work for simpler subagent roles "fixer"?, but we stopped testing after the catastrophic orchestrator failure.

### 💀 Big Pickle — Dead on Arrival

Produced no output when dispatched as a reviewer. Appeared dead in the subagent session. Seemed appealing at first when we used it with direct prompting. Kept disappointing. Not recommended for any Quest role. Maybe can be suitable for drone work?

---

## The Winning Configuration

Four model families. One free, eight paid. Each model in its best role.

```
              ┌─────────────────────┐
              │      KiMi K2.5      │
              │    (orchestrator)    │
              └──────────┬──────────┘
                         │ dispatches all agents below
                         ▼
              ┌─────────────────────┐
              │    Trinity Free     │
              │     (planner)       │
              └──────────┬──────────┘
                         │
                ┌────────┴────────┐
                ▼                 ▼
       ┌──────────────┐  ┌──────────────┐
       │    Codex     │  │     KiMi     │
       │ (reviewer A) │  │ (reviewer B) │
       └──────┬───────┘  └───────┬──────┘
              └─────────┬────────┘
                        ▼
              ┌─────────────────────┐
              │     Opus            │
              │    (arbiter)        │
              └──────────┬──────────┘
                         │
                         ▼
                   [human gate]
                         │
                         ▼
              ┌─────────────────────┐
              │       Codex         │
              │     (builder)       │
              └──────────┬──────────┘
                         │
                ┌────────┴────────┐
                ▼                 ▼
       ┌──────────────┐  ┌──────────────┐
       │     KiMi     │  │    Codex     │
       │ (reviewer A) │  │ (reviewer B) │
       └──────┬───────┘  └───────┬──────┘
              └─────────┬────────┘
                        ▼
              ┌─────────────────────┐
              │       Codex         │
              │      (fixer)        │◄── if issues found
              └─────────────────────┘
```

| Role | Model | Why This Model |
|------|-------|----------------|
| Orchestrator | KiMi K2.5 | Fastest. Full pipeline in ~8 min. |
| Planner | Trinity (free) | 100% success rate. Zero cost. |
| Plan Reviewer A | Codex | Behavioral/UX focus. Instruction discipline. |
| Plan Reviewer B | KiMi K2.5 | Security focus. Deeper analysis. |
| Arbiter | Opus | Only proven arbiter. Worth the cost. |
| Builder | Codex | Best at code generation. |
| Code Reviewer A | KiMi K2.5 | Catches race conditions and security issues. |
| Code Reviewer B | Codex | Concise, clean, catches UX gaps. |
| Fixer | Codex | Same strengths as builder. |

**Alternative:** Swap KiMi orchestrator for Opus for maximum reliability at higher cost.

---

# Why Multi-Model Beats Single-Vendor

## The diversity argument is real

We expected mixing model families would be an interesting experiment. It turned out to be the most important insight from the entire testing effort.

Two reviewers from the same model family tend to agree. Two reviewers from different families — KiMi and Codex — catch **different classes of issues**. KiMi finds security holes and race conditions. Codex finds UX gaps and unrecoverable states. In one run, Codex iterated on a plan where Claude had approved it. These aren't rubber-stamp reviews. They're genuinely complementary perspectives.

### What OpenCode gives you that single-vendor doesn't

**One config file, multiple model families.** Our `opencode.json` declares 9 agents across 4 model families with per-agent permissions. In Claude Code, cross-model dispatch requires MCP server configuration and the subagent model selection lives outside the orchestrator's config. We actively use Opus as orchestrator with Codex as a subagent via MCP in Claude Code — it works, but the wiring is different. OpenCode makes the full agent topology visible in one place.

**Per-agent permission sandboxing.** The builder can edit `src/**`. The reviewer can only write to `.quest/**`. The planner can't touch bash at all. Deny-by-default, scoped per role, declared in config. Claude Code has a more global permission model.

**Cost optimization through role-appropriate selection.** Trinity (free) handles planning. KiMi handles speed-sensitive roles. Opus is reserved for high-judgment arbitration. OpenCode has zero markup on model usage as far as we can tell — you pay the provider rate. Slotting free-tier models into commodity roles materially reduces total pipeline cost.

### Context management: designed around, not fought against

OpenCode returns each subagent's full response into the orchestrator's context window. This sounds like a problem — and it is, if you don't plan for it. Quest is efficient **because** the pipeline is designed around this constraint:

- The **Context Retention Rule** tells the orchestrator to keep only artifact paths and one-line summaries
- **File-based handoffs** store real content in `.quest/` artifacts, not in the context window
- **Bounded phases** keep each interaction small

The one overflow we saw (Trinity hitting 131K) was Exa MCP dumping search results into a subagent's context, not the pipeline itself. Banning Exa from subagent sessions solved it. With disciplined models and scoped MCP access, even 128K context limits are sufficient.

### Gate compliance: an instruction problem, not a model problem

Every non-Opus model failed human approval gates initially. After adding explicit "STOP", "MUST ask", "do not assume approval" language, all three orchestrators (Opus, Codex, KiMi) work correctly. **Orchestration gates need unambiguous STOP language regardless of model or runtime.** This matches the OpenCode orchestration guide's warning about "vague orchestrator prompts" as a top failure mode.

---

## Lessons Learned the Hard Way

1. **Make every agent identify itself.** In a multi-model pipeline, you need to know which model actually produced each artifact. We require every subagent to include a self-identification header (model name, timestamp) in its output. Without this, there's no way to distinguish real subagent work from an orchestrator quietly doing the job itself.

2. **Model diversity produces real disagreement.** Two reviewers from the same model family tend to agree. Two reviewers from different families catch different classes of bugs. One reviewer is not enough; two identical reviewers is theater.

3. **Permission sandboxes have escape hatches.** KiMi bypassed file edit denials by writing files through `cat >` in bash instead. Codex respected the same boundaries. Different models have different levels of permission discipline — design your sandbox assuming the most creative model will find a way around it.

4. **Orchestrators will impersonate failed subagents.** When a subagent crashes and returns nothing, we saw the orchestrator write the missing artifact itself — complete with a fake self-ID header claiming to be a different model. The fix: require self-ID headers and validate them. If the header doesn't match the model that was dispatched, flag it.

5. **Free-tier models have a narrow sweet spot.** Trinity is an excellent planner and nothing else. MiniMax failed orchestration despite strong benchmarks. Don't extrapolate from one successful role to all roles.

6. **Human approval gates need unambiguous language.** Every non-Opus model skipped the human approval gate on first attempt. The fix was explicit instruction language: "STOP", "MUST ask", "do not assume approval." Vague gate instructions get ignored across all model families. Be blunt.

7. **$20 goes a long way.** Full multi-model orchestration testing across 6 models, multiple pipeline runs, real code review comparisons. OpenCode's pricing model makes experimentation cheap.

---

## Still Untested

- **GLM-5** — potential builder/reviewer diversity candidate.
- **24 other models** across Gemini, GLM, MiniMax, and other families.

---

## Try It Yourself

OpenCode is free to download. Company tier accounts are also available.
