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

**Where you spend your time:** The beginning and the end. You shape the plan, approve it, then validate the built result. Most follow-up quests and v2 ideas come from this post-build validation, not from planning, because you don't fully understand a feature until you see it built. Quest handles the middle.

For lighter tasks, **solo mode** uses a single reviewer, same pipeline, fewer stages, faster turnaround.

## Quick Start

```bash
# Download and run the installer
curl -fsSL https://raw.githubusercontent.com/KjellKod/quest/main/scripts/quest_installer.sh -o quest_installer.sh
chmod +x quest_installer.sh
./quest_installer.sh          # preview first with --check
```

Then start a quest:

```bash
claude
/quest "Add a loading skeleton to the user list"
```

That's it. Quest evaluates complexity, asks clarifying questions if needed, and routes to solo or full workflow. You approve at each gate.

**Recommended:** Add [Codex CLI](https://developers.openai.com/codex/cli/) for dual-model reviews. See the [Setup Guide](docs/guides/quest_setup.md) for full instructions including Codex as orchestrator (BETA). To use Quest as a global Codex skill outside a specific repo, see [Installing Quest for Codex](docs/guides/codex-quest-install.md).

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

# Point to specs, tickets, or docs
/quest "implement docs/specs/notifications.md"
/quest "implement PROJ-1234"                      # with Jira MCP

# Generate competing plans and pick the best
/quest "migrate to SQLite, zero-downtime, dual-write pattern"
/quest "migrate to SQLite, minimal changes, feature-flag cutover"
```

Abort anytime, resume later. State persists in `.quest/<id>/state.json`.

For advanced patterns (phased execution, plan comparison, model mixing), see the [Quest Presentation](docs/guides/quest_presentation.md).

## The Agents

| Role | Default model | What it does |
|------|--------------|-------------|
| **Planner** | Opus 4.6 | Explores the codebase and writes the implementation plan |
| **Reviewer A** | Opus 4.6 | Reviews plans and code from one perspective |
| **Reviewer B** | GPT-5.4 | Reviews independently, different model, different blind spots |
| **Arbiter** | Opus 4.6 | Synthesizes reviews, filters nitpicks, decides approve or iterate |
| **Builder** | GPT-5.4 | Implements the approved plan, runs tests, produces PR description |
| **Fixer** | GPT-5.4 | Surgical fixes from review feedback without rebuilding |

These defaults work with Claude (Sonnet or Opus) or GPT-5.x (5.2 or later) as the orchestrator, and across runtimes: Claude Code, Codex CLI, or Cursor IDE.

Every role is swappable. Update `model_overrides` in `.ai/allowlist.json` to reassign roles, or just ask the orchestrator mid-quest to swap models. Want GPT as your planner and Claude as reviewer? KiMi as arbiter? Try it. With the installer setup you can mix and match any models you prefer. See the [OpenCode Field Notes](docs/guides/opencode-model-observations.md) for tested configurations across 30+ models.

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

## Philosophy

> *Autonomy is earned through constraints, not granted by capability.*
> *Context contamination is a system failure, not a user habit.*
> *Speed without rigor only accelerates failure.*

Quest is built on a conviction: **scaling AI output without scaling engineering discipline is a dead end.** We don't trust single outputs, human or machine. We trust repeatable processes backed by evidence. The system makes correct behavior easy and incorrect behavior hard.

We're not replacing human judgment. We're amplifying it.

Read the [full philosophy](docs/guides/philosophy.md).

## Install Options

**Per repo (recommended):** Use the installer above.

**Workspace umbrella (multi-repo):** Install once in a parent directory, all repos underneath inherit Quest's config. See the [Setup Guide](docs/guides/quest_setup.md).

**Manual copy:** Grab `.ai/`, `.skills/`, `.agents/`, `.claude/`, `.cursor/`, `.codex/`, `.opencode/`, `AGENTS.md`, and `DOCUMENTATION_STRUCTURE.md`. See the [Setup Guide](docs/guides/quest_setup.md).

## Documentation

- **[Setup Guide](docs/guides/quest_setup.md)**, prerequisites, Codex MCP, allowlist customization
- **[Quest Presentation](docs/guides/quest_presentation.md)**, how it works with diagrams
- **[Input Routing Guide](docs/guides/quest_input_routing.md)**, complexity/risk evaluation and solo vs full workflow
- **[Philosophy](docs/guides/philosophy.md)**, the full manifesto
- **[OpenCode Field Notes](docs/guides/opencode-model-observations.md)**, multi-model testing and architecture comparison
- **[Architecture](docs/architecture/)**, platform direction and runtime contracts
- **[Portfolio Dashboard](https://kjellkod.github.io/quest/)**, live quest outcomes and journal entries

## License

Public Domain (Unlicense). No warranty. See [LICENSE](LICENSE).
