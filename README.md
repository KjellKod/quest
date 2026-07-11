# Quest: Multi-Agent AI Orchestration with Human Oversight

*Stop blaming the model. Fix the process.*

Quest is a portable framework that coordinates specialized AI agents (planner, reviewers, builder) in isolated contexts with human approval gates. Two different models (Claude + GPT) review independently, an arbiter filters noise, and you approve before anything gets built.

Copy it into any repo. Tear it apart and study it. It's built for learning, experimentation, and real work.

**Part of the [Candid Talent Edge](https://candidtalentedge.com) initiative by KjellKod**

> Watch the [Quest Demo](docs/media/quest-demo.mov) | Read the [Honest Analysis](docs/guides/quest_analysis.md) | View the [Portfolio Dashboard](https://kjellkod.github.io/quest/)

![Adventurers in our quest](docs/media/quest_v0.14.png)

## How It Works

```
You → Planner → Reviewers → Arbiter ──→ Builder → Reviewers → Arbiter → Done
               (Claude)       │    ▲                (Claude)      │         ▲
               (Codex)        │    │                (Codex)       ▼         │
               iterate ───────┘    │                Fixer ────────┘         │
                                   │                                        │
                          GATE: you approve                        GATE: you approve
```

**Where you spend your time:** The beginning and the end. You shape the plan, approve it, then validate the built result. Before build starts, Quest now presents a concise plan summary and can work with you to sharpen it diligently: challenging assumptions, walking tradeoffs, and locking down what will actually be built. That improves the plan and, as a useful side effect, gives the orchestrator a sharper understanding of the implementation before it hands work to the builder. Quest handles the middle.

For lighter tasks, **solo mode** uses a single reviewer, same pipeline, fewer stages, faster turnaround.

## Quick Start
Make sure you have claude and/or codex [installed](https://github.com/KjellKod/quest/blob/main/docs/guides/quest_setup.md). Ideally you have both, but you'll do fine with one of them.

Download the installer
```bash
curl -fsSL https://raw.githubusercontent.com/KjellKod/quest/main/scripts/quest_installer.sh -o quest_installer.sh
```
Give it permission to execute
```bash
chmod +x quest_installer.sh
```

Run the installer, you can preview without changes if you add `--check`
```bash
./quest_installer.sh       
```

### Then start a quest. 

In claude code/cli:
```bash
/quest "Add a loading skeleton to the user list"
```

In codex cli:
```bash
$quest "Add a loading skeleton to the user list"
```



That's it. Quest evaluates complexity, asks clarifying questions if needed, and routes to solo or full workflow. Before implementation, you get a plan summary menu: walk through the phases, sharpen the plan with adversarial Q&A, or proceed to build. You approve at each gate.

**Recommended:** Add both [Codex CLI](https://developers.openai.com/codex/cli/) and [Claude CLI](https://code.claude.com/docs/en/quickstart) for dual-model reviews. See the [Setup Guide](docs/guides/quest_setup.md) for full instructions, which include using either Codex or Claude as the orchestrator.

> **⚠️ Don't skip the one-time machine setup.** When Codex orchestrates, Claude roles default to the background-agent transport (`claude --bg`), which bills to your **Claude subscription**. Quest sends the initial bg prompt over stdin (required since Claude Code 2.1.191). Without the [one-time setup](docs/guides/quest_setup.md#one-time-machine-setup-for-the-background-agent-transport) — `claude login`, accept bypass mode once, CLI ≥ 2.1.143 — Quest stops and asks you to fix bg or explicitly choose the `claude --print` bridge, which bills to the **metered API pool after June 15, 2026**.

## Writing a Good Brief

Quest enforces **spec → plan → build**. You can start rough, Quest asks clarifying questions to fill gaps.

| Input level | What you provide | What happens |
|------------|-----------------|-------------|
| **Rough idea** | `"add dark mode"` | Quest asks questions (max 10), then plans |
| **Idea with context** | `"add dark mode, persist in localStorage, respect OS preference, toggle in header"` | Plans with clear direction |
| **Structured spec** | Doc with intent, constraints, acceptance criteria | Tight plan on first pass |

Say **"just go with it"** anytime to skip questions and proceed with assumptions. See the [Input Routing Guide](docs/guides/quest_input_routing.md) for details.

## What You Can Do

```bash
# Scale from simple to complex
/quest "Add a loading spinner to the save button"
/quest "Implement user preferences with localStorage, follow idea document <path> and our RFC ..."
/quest "Build a real-time collaboration system, plan phases first, don't implement yet"

# Resume, redirect, swap models
/quest feature-x_2026-02-04__1430
/quest feature-x_2026-02-04__1430 "re-plan using only claude"
/quest feature-x_2026-02-04__1430 "re-plan using gpt-5.2"
/quest 2026-02-04_1430__feature-x "Don't resume from building-phase, read <doc> and let's re-plan with this insight"

# Point to specs, tickets, or docs
/quest "implement docs/specs/notifications.md"
/quest "implement PROJ-1234"                      # with Jira MCP

# Generate competing plans and pick the best
/quest "migrate to SQLite, zero-downtime, dual-write pattern"
/quest "migrate to SQLite, minimal changes, feature-flag cutover"
```

Quest IDs default to `feature-x_2026-02-04__1430`; set `quest_id_format` to `date-first` in `.ai/allowlist.json` to create new IDs like `2026-02-04_1430__feature-x`. Resume accepts both formats.

Abort anytime, resume later. State persists in `.quest/<id>/state.json`.

### Cross-vendor resume

Quest is artifact-driven, not chat-history driven. `state.json`, `handoff.json`, plans, reviews, and logs are the durable contract, so a run can recover after an outage, token/session exhaustion, crash, or context loss. If Claude is unavailable, start Codex and run `$quest <quest-id>`; if Codex is unavailable, start Claude Code and run `/quest <quest-id>`. Quest resumes from `.quest/<id>/state.json` and the existing phase artifacts instead of depending on the original transcript.

Resume applies to **in-flight** quests (directories under `.quest/<id>/`). A completed quest is archived to `.quest/archive/<id>/` with its journal entry in `docs/quest-journal/` — archived quests are finished history, not resumable runs; start a new quest to build on their outcome.

For advanced patterns (phased execution, plan comparison, model mixing), see the [Quest Presentation](docs/guides/quest_presentation.md). 

> _Kjell: My personal approach for things like [doc2md](https://kjellkod.github.io/doc2md/) or the multiple MCP and CLI tools I've built, is to collect references, ideas and start with an **analysis quest** with the stated goal of creating a roadmap that delivers the `functionality` or the whole feature or app. Then use each phase in the roamap as a new quest._

## The Agents

| Role | Default model | What it does |
|------|--------------|-------------|
| **Planner** | GPT-5.6 Sol | Explores the codebase and writes the implementation plan |
| **Plan Reviewer A** | Claude Opus 4.8 | Challenges the plan from a different model family |
| **Plan Reviewer B** | GPT-5.6 Terra | Adds a fast, independent second review |
| **Arbiter** | Claude Opus 4.8 | Synthesizes plan reviews and decides approve or iterate |
| **Builder** | GPT-5.6 Sol | Implements the approved plan and runs validation |
| **Code Reviewer A** | Claude Opus 4.8 | Reviews Sol-produced code across model families |
| **Code Reviewer B** | GPT-5.6 Terra | Adds a second code-review perspective |
| **Review Arbiter** | Claude Opus 4.8 | Converts review findings into canonical decisions |
| **Fixer** | GPT-5.6 Terra | Applies bounded fixes before the next review pass |

### Choosing and overriding models

The `models` block in `.ai/allowlist.json` is the persistent default for new quests. At startup, Quest copies it into the quest snapshot, shows the active role assignments, and writes the accepted selection to `.quest/<id>/orchestration.json`. That per-quest file is then the source of truth for the rest of the run, so changing the repo allowlist does not rewrite an in-flight quest.

Choose **Customize for this quest only** at startup to change one or more roles without editing repo defaults. The chooser accepts either format:

```text
planner=gpt-5.6-sol, builder=claude-opus-4-8
```

```json
{
  "models": {
    "planner": "gpt-5.6-sol",
    "builder": "claude-opus-4-8"
  }
}
```

A direct JSON role map and a copied `"models": {...}` fragment are accepted too. Omitted roles keep their defaults. Quest validates role names, runtime-family availability, and whether a role is used in the selected solo/full mode before saving the override. A concrete model ID can still be rejected later by its provider if that account or client does not support it.

Model IDs select the runtime family: `claude` and `claude-*` use Claude; other IDs use Codex. In Claude-led runs, Codex MCP receives the configured Codex model. In Codex-led runs, local Codex subagents currently inherit the active Codex model by default, so a per-role Sol/Terra distinction is recorded but may not be enforceable without explicit model-aware local dispatch. Concrete Claude model IDs are passed through by the Claude runner.

Quest currently overrides **models only**, not per-role reasoning effort. Codex supports `model_reasoning_effort` values such as `low`, `medium`, `high`, `xhigh`, `max`, and `ultra` when the selected model supports them, but the available levels and behavior vary by model and surface. Configure reasoning in Codex itself or in a Codex agent definition for now; it is not stored in Quest's `orchestration.json`. Ultra is not simply a stronger spelling of High: on supported accounts/models it can also enable proactive subagent delegation. See the [Codex subagent model and reasoning guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents#choosing-models-and-reasoning).

Solo mode skips Reviewer B and the Arbiter. Same pipeline, just faster.

## Key Features

- **Artifact-driven**, agents communicate through written artifacts, not conversation. No chat history, no accumulated drift, no hallucinated context. Each agent reads evidence and produces evidence
- **Clean context**, each agent starts fresh with only the artifacts it needs
- **Dual-model review**, different models catch different blind spots
- **Human gates**, you approve before anything gets built
- **Smart routing**, evaluates complexity/risk, routes to solo or full workflow
- **Smart intake**, asks structured questions when your input needs more detail
- **Full audit trail**, every artifact saved in `.quest/`
- **Multi-runtime**, runs from Claude Code (`/quest`), Codex (`$quest`), or [OpenCode](https://opencode.ai/)
- **Built-in UX rigor**, when the router sees UI work it auto-attaches a canonical UX guidebook to the planner/builder/fixer and runs a stress-test rubric in code review. Invoke `/ux-review` on any file, URL, or screenshot to get a P0–P3 critique with principle citations.

## Philosophy

> *Autonomy is earned through constraints, not granted by capability.*
> *Context contamination is a system failure, not a user habit.*
> *Speed without rigor only accelerates failure.*

**Engineering principles baked into every agent:**
- **KISS** — Prefer simple solutions over clever ones
- **DRY** — Extract common patterns, but not prematurely
- **YAGNI** — Don't add features until they're needed
- **SRP** — Each change, function or module should focusing on doing one thing

These aren't guidelines — they're the first thing every agent reads. `AGENTS.md` shapes how agents think, plan, review, and build. The process enforces the philosophy; the philosophy produces the quality.

Quest is built on a conviction: **scaling AI output without scaling engineering discipline is a dead end.** We don't trust single outputs, human or machine. We trust repeatable processes backed by evidence. The system makes correct behavior easy and incorrect behavior hard.

We're not replacing human judgment. We're amplifying it.

Read the [full philosophy](docs/guides/philosophy.md).

## Install Options

**Per repo (recommended):** Use the installer above.

**Workspace umbrella (multi-repo):** Install once in a parent directory, all repos underneath inherit Quest's config. See the [Setup Guide](docs/guides/quest_setup.md).

**Not recommended, but possible is also a manual copy:** Grab `.ai/`, `.skills/`, `.agents/`, `.claude/`, `.cursor/`, `.codex/`, `.opencode/`, `AGENTS.md`, and `DOCUMENTATION_STRUCTURE.md`. See the [Setup Guide](docs/guides/quest_setup.md).

## Documentation

- **[Setup Guide](docs/guides/quest_setup.md)**, prerequisites, Codex MCP, allowlist customization, one-time background-agent transport setup (subscription vs API billing)
- **[Quest Presentation](docs/guides/quest_presentation.md)**, how it works with diagrams
- **[Input Routing Guide](docs/guides/quest_input_routing.md)**, complexity/risk evaluation and solo vs full workflow
- **[Philosophy](docs/guides/philosophy.md)**, the full manifesto
- **[OpenCode Field Notes](docs/guides/opencode-model-observations.md)**, multi-model testing and architecture comparison
- **[Architecture](docs/architecture/)**, platform direction and runtime contracts
- **[Portfolio Dashboard](https://kjellkod.github.io/quest/)**, live quest outcomes and journal entries
- **[UX Guidebook](.skills/ux-context/resources/ux-guidebook.md)**, canonical UX standards bundled with the ux-context skill so they travel with the install; auto-loaded for UI work

## License

Public Domain (Unlicense). No warranty. See [LICENSE](LICENSE).
