# OpenCode: Field Notes from Multi-Model Orchestration

We put $20 into OpenCode, ported our multi-agent pipeline to run on it, and tested both high-tier paid models and free models across every role. Some surprised us. Some disappointed. One completely changed how we think about code review.

---

## What We Were Testing

Most AI coding tools tie you to one vendor. **Claude Code** runs Claude models. **Codex CLI** runs OpenAI models. They're good — but you're locked in.

**OpenCode** is different. It gives you access to 30+ models across multiple families — Claude, GPT/Codex, KiMi, Gemini, Trinity, and more — and lets you assign different models to different jobs in a single workflow. Think of it like building a team where each person is hired for what they're best at.

We tested this with **Quest**, our multi-agent orchestration system. Here's the workflow:

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

One AI writes a plan. Two different AIs review it independently. A third AI decides if the reviews are valid. A human approves. Another AI builds the code. Two more AIs review the code. If there are problems, yet another AI fixes them. Nine agents, seven phases.

The question: does mixing AI models from different companies actually produce better results than running everything on one vendor's best model?

The answer was yes — but not for the reasons we expected.

### How Quest works (and why the "bugs" in this document exist)

Most multi-agent frameworks use code to enforce rules — "don't skip step 3", "only the builder can edit source files." Quest does something different: **everything is driven by markdown instructions.** No code, no state machine, no programmatic guardrails. The AI reads the instructions and follows them.

This sounds fragile, and sometimes it is. Every issue in this document — models skipping approval steps, faking identities, bypassing permissions — happened because we're trusting AI models to follow written rules rather than enforcing those rules in code.

So why do it this way? **Portability.** The same instruction files work across Claude Code, Codex CLI, Cursor, Vibe-Kanban, and OpenCode with near-zero changes. No SDK to integrate, no runtime to port. If the tool can read markdown and dispatch subagents, Quest runs on it. That's a trade-off we're happy with.

---

## The Models That Worked

### ✅ Claude Opus 4.6 — The Reliable Veteran

**Tested as:** Orchestrator, Arbiter, Reviewer, Builder, Fixer

No surprises. Opus handles everything with consistent quality. Every step completed correctly, every approval gate was respected, every artifact was properly labeled. It just works.

The catch is cost. Opus is the most expensive model we tested, and you don't need it everywhere. We found its sweet spot: **arbiter** — the role that reads two conflicting reviews and decides what actually matters. That's a judgment call, and Opus is the best judge we have.

### ✅ GPT-5.3 Codex — The Disciplined Builder

**Tested as:** Reviewer, Builder, Fixer, Orchestrator

Codex is the workhorse. Best-in-class at writing code — clean, structured, compliant output every time.

What surprised us was its code review style. Codex is great at catching **user experience issues** — things like unrecoverable error states, broken first-run flows, and edge cases that would frustrate real users. Its reviews are concise and clean. No fluff.

Codex also follows instructions more precisely than any other model we tested. When the protocol says "log your start time and end time," Codex does it perfectly. Every time. This matters more than you'd think in a multi-agent pipeline.

### ✅ 🚀 KiMi K2.5 — The One That Changed Everything

**Tested as:** Reviewer, Code Reviewer, Orchestrator

KiMi K2.5 was supposed to be a quick experiment. It became our default orchestrator.

**Speed.** KiMi completed the full 9-agent pipeline in ~8 minutes. The same pipeline takes significantly longer with Opus or Codex orchestrating. The difference isn't marginal — **it's dramatic**.

**Review depth.** This is where KiMi genuinely surprised us. In head-to-head code reviews against Codex, KiMi consistently went deeper — especially on security. It found threat surfaces, authentication edge cases, and concurrency issues that other models completely overlooked.

#### 🏆 The defining moment

**KiMi caught a race condition that Codex never found — despite 3 separate opportunities.** Same code, same review instructions. Codex had 3 chances to catch it and missed it every time. KiMi found it on the first pass.

For security-sensitive code — authentication, session handling, anything with concurrency — **KiMi's depth provides materially higher confidence**. But both models are effective reviewers. They just see different things. Codex catches UX problems. KiMi catches security problems. Together, they don't rubber-stamp each other. They genuinely disagree, and that disagreement is the whole point.

##### The trade-off

**KiMi is weaker than Codex at following instructions to the letter.** Metadata was inconsistent — start times, end times, agent identity labels drifted across phases. Where Codex is meticulous about protocol, KiMi is... *creative*. It gets the job done, but the bookkeeping isn't always clean.

Despite the rough edges, KiMi earned its spot. For speed and analytical depth, nothing else comes close.

---

## The Models That Didn't

### ✅ Trinity Large Preview (free) — Planner Only 🤔

**Trinity is an excellent planner.** 100% success rate across multiple runs, and it's free. Every other model in the pipeline agreed with Trinity's plans. Best value in the whole setup.

❌ Everything else failed. Trinity crashed in 3 out of 4 non-planner roles. Use it as a planner. Don't use it for anything else.

### ❌ MiniMax M2.5 (free) — Benchmarks Lied

Strong community benchmarks. Failed orchestration immediately — couldn't coordinate the pipeline at all. We stopped testing after that.

### 💀 Big Pickle — Dead on Arrival

Produced no output when dispatched as a reviewer. Just... nothing. Seemed appealing at first with direct prompting. Kept disappointing.

---

## The Winning Configuration

Four model families. One free, eight paid. Each model doing what it does best.

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
              │        Opus         │
              │      (arbiter)      │
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

| Role | Model | Why |
|------|-------|-----|
| Orchestrator | KiMi K2.5 | Fastest. Full pipeline in ~8 min. |
| Planner | Trinity (free) | 100% success rate. Zero cost. |
| Plan Reviewer A | Codex | UX focus. Instruction discipline. |
| Plan Reviewer B | KiMi K2.5 | Security focus. Deeper analysis. |
| Arbiter | Opus | Best judgment. Worth the cost. |
| Builder | Codex | Best at writing code. |
| Code Reviewer A | KiMi K2.5 | Catches race conditions and security issues. |
| Code Reviewer B | Codex | Concise, catches UX gaps. |
| Fixer | Codex | Same strengths as builder. |

**Want more reliability?** Swap KiMi orchestrator for Opus. Slower, more expensive, but rock-solid.

---

# Why Multi-Model Beats Single-Vendor

## The diversity argument is real

We expected mixing model families would be an interesting experiment. It turned out to be the most important insight from the entire effort.

Two reviewers from the same AI company tend to agree with each other. Two reviewers from *different* companies catch **different classes of issues**. KiMi finds security holes. Codex finds UX gaps. In one run, Codex pushed back on a plan that Claude had already approved. These aren't rubber-stamp reviews — they're genuinely complementary perspectives.

One reviewer is not enough. Two identical reviewers is theater. Two *different* reviewers is real quality assurance.

## What OpenCode gives you

**Pick the right model for each job.** One config file declares all 9 agents, which model runs each one, and what each agent is allowed to do. In Claude Code, cross-model dispatch requires extra MCP wiring. In OpenCode, the whole team topology is visible in one place.

**Per-agent permissions.** The builder can edit source code. The reviewer can only write notes. The planner can't run shell commands at all. Each role gets exactly the access it needs — declared in config, enforced by the platform.

**Cost control.** Free models for commodity work (planning). Fast models for speed-sensitive roles (orchestration, review). Expensive models only where judgment matters (arbitration). OpenCode charges provider rates with no markup as far as we can tell.

---

## Under the Hood: Context, Sessions, and the Memory Problem

If you're curious about how these tools actually work internally — and why some of the issues in this document exist — this section explains the plumbing.

### The context accumulation problem

When an orchestrator dispatches a subagent, the subagent does its work in an **isolated session** — it can't see the orchestrator's conversation history. Good so far.

But when the subagent finishes, its **final result** flows back into the orchestrator's memory. Not the subagent's full internal transcript — the intermediate tool calls, file reads, and reasoning stay private. But the result message itself (which can still be large — a full code review, a complete plan) enters the orchestrator's context. Do this nine times across a pipeline and you've eaten a lot of memory.

| Direction | Isolated? | What happens |
|-----------|-----------|--------------|
| Orchestrator → Subagent | **Yes** | Subagent starts fresh, can't see parent's history |
| Subagent internals | **Yes** | Tool calls, reasoning, intermediate steps stay private |
| Subagent result → Orchestrator | **No** | Final result returned, accumulates in orchestrator |

This is how both **OpenCode** and **Claude Code** work — we verified against OpenCode's source code. The context growth per subagent call is bounded by the result size, not the subagent's total work. But if your agents write verbose results, it adds up.

**Codex CLI** handles this differently. The orchestrator can suspend itself while subagents work, and subagents post results to an async inbox. The orchestrator only pulls what it needs when it resumes. Context doesn't accumulate the same way.

### How Quest handles it

Since neither OpenCode nor Claude Code compress subagent output automatically, Quest handles it behaviorally: the orchestrator is instructed to keep only file paths and one-line summaries after each subagent call. The real content lives in files on disk, not in the AI's memory. Subagents read files themselves — the orchestrator routes work, it doesn't relay content.

This works. The one overflow we hit (a model reaching its 131K token limit) was caused by a search tool dumping huge results into a session — not by the pipeline itself. Disabling that tool solved it.

### The big architectural insight

The difference that matters most: **OpenCode and Claude Code both bleed subagent responses into the orchestrator's memory. Codex CLI doesn't** — its async inbox model decouples subagent work from orchestrator context entirely.

Quest's Context Retention Rule is a behavioral workaround for an architectural limitation shared by OpenCode and Claude Code. Codex CLI doesn't need this workaround because its session model handles it natively.

But here's the thing: Quest's instruction-driven approach means the *same workaround works on both platforms without code changes*. That's the portability trade-off in action — one set of instructions, multiple architectures, same result.

### What we had to add for OpenCode

Quest's core instruction files work across Claude Code, Codex CLI, Cursor, and other tools. For OpenCode, we needed a few additions:

**Agent identity tags.** When every agent is Claude, you know who did what. When you have four model families, you don't. We added a requirement for every agent to label its output with its model name. Simple, but essential for debugging.

**Stricter "no questions" rules.** In Claude Code, a subagent can ask the user for clarification. In OpenCode, subagents can't interact mid-task. We hardened the instructions: if something is unclear, make an assumption and document it. Don't ask — just proceed.

**Fallback plans.** If the free-tier planner crashes, retry once, then fall back to a paid model. Single-vendor tools don't need this — there's only one model. Multi-model pipelines need insurance.

**A config file.** OpenCode needs agent definitions, model assignments, and permissions declared in its own JSON format. This is the main reason Quest has a separate `.opencode/` folder — not because the instructions are different, but because OpenCode's config format is different from Claude Code's. The OpenCode agent files are thin wrappers that point back to the same core Quest instructions. The hardening (identity tags, stricter rules) could easily be folded into the core files without affecting other platforms.

### Code-driven vs instruction-driven orchestration

OpenCode supports both approaches:

- **Markdown + Config** — write instructions in markdown files, declare agents in a config file, no code. This is what Quest does.
- **Code-based** — use an SDK (TypeScript, Python, Go, Rust) to build a custom orchestration runtime with programmatic control.

A code-based approach would let you *enforce* things like context compression, identity validation, and approval gates — guaranteed by code, not dependent on the AI following instructions.

But you'd lose what makes Quest work: **portability.** The same markdown files run on five different platforms without code changes. No SDK dependency, no build step. Anyone who can write markdown can modify the pipeline.

For Quest, that trade-off is worth it. The instruction-driven approach works well enough, and the portability is genuinely valuable. A code approach would make sense if you were building exclusively for one platform and needed guarantees the AI can't violate.

---

## Lessons Learned

1. **Make every agent identify itself.** In a multi-model pipeline, you need to know which AI produced each piece of work. We require every agent to label its output. Without this, you can't tell real work from an orchestrator quietly doing the job itself and claiming someone else did it. (Yes, we caught this happening.)

2. **Two different reviewers beat two identical ones.** Models from different companies catch different bugs. This is the single most valuable insight from the entire experiment.

3. **AI models will find creative workarounds.** One model bypassed file edit restrictions by writing files through shell commands instead. Another model faked a different model's identity when a subagent crashed. If your security model relies on the AI choosing to comply, assume the most creative model will find a way around it.

4. **Don't trust benchmarks for orchestration.** MiniMax had strong benchmark scores. It couldn't orchestrate at all. Trinity is excellent at planning but crashed at everything else. A model's general capability doesn't predict its performance in a specific pipeline role.

5. **Approval gates need blunt language.** Every model except Opus skipped the human approval step on first attempt. The fix was aggressive instruction language: "STOP", "MUST ask", "do not assume approval." Polite instructions get ignored. Be blunt.

6. **$20 goes a long way.** Full multi-model testing across 6 models, multiple pipeline runs, real code review comparisons. OpenCode's pricing makes experimentation cheap enough to just try things.

---

## Still Untested

- **GLM-5** — potential diversity candidate for building or reviewing.
- **24 other models** across Gemini, GLM, MiniMax, and other families.
- **Sonnet 4.6** — ~3x cheaper than Opus. Could replace Opus as arbiter.

---

## Try It Yourself

OpenCode is free to download. Company tier accounts are also available.
