# Quest: Stop blaming the model. Fix the process.

## Quest Philosophy

Unlocking agentic engineering leverage is not driven by massive models, endless swarms, or magical autonomy. It comes from discipline, process, and constraints.

Quest is not about prompt tricks, cute `skill.md` files, or model specific hacks. It is about building engineering agentic systems that reliably produce correct outcomes.

Humans set direction, constraints, and intent.  
Systems execute, verify, and enforce correctness.

We do not trust single outputs, human or machine.  
We trust repeatable processes backed by evidence.

Models generate artifacts.  
Pipelines validate artifacts and decide what is acceptable.

Autonomy is earned through constraints, not granted by capability.  
More autonomy without rigor increases risk, not leverage.

Clean context and focus are mandatory.  
Context contamination is a system failure, not a user habit.

Artifacts must be explicit, reviewable, traceable, and reproducible.  
Nothing important should live only in a model’s head or a chat window.

Verification must be continuous and automated wherever possible.  
Humans review intent, evidence, and anomalies, not every line of output.

The system should make correct behavior easy.  
The system should make incorrect behavior hard.

Scaling output without scaling engineering discipline is a dead end.  
Speed without rigor only accelerates failure.

Humans remain in the loop at the system level.  
Requiring humans to advance every step does not scale and increases error.

We are not replacing human judgment.  
We are amplifying it by removing avoidable toil and preventing avoidable mistakes.


### Where We Are vs Where We're Going

The philosophy above is our north star. We are not there yet. Here is where we stand:

**What Quest delivers today:**
- A prompt-orchestrated pipeline built within Claude Code's skill system
- Clear phase boundaries (plan → review → build → review → fix)
- Explicit, auditable artifacts in `.quest/<id>/`
- Dual-model verification (Claude + Codex reviewing independently)
- Human gates at phase boundaries
- Resumable state via `state.json`
- A thin orchestrator that passes paths, not content (Context Retention Rule)

**What Quest does not yet deliver:**
- System-enforced correctness (state transitions are checked by prompts, not scripts)
- Clean skill/role separation (some roles duplicate what skills already say)
- A structured exploration/research capability (no `/explore` skill yet)

**The philosophy is right. The architecture is pragmatically correct. The gap between them is the roadmap.**

See [ideas/quest-architecture-evolution.md](ideas/quest-architecture-evolution.md) for the phased plan to close these gaps.

# Quest: A Multi-Agent Orchestration Blueprint

**Part of the [Candid Talent Edge](https://candidtalentedge.com) initiative by KjellKod**

> *New here?* Watch the [Quest Demo](docs/media/quest-demo.mov), listen to the [Fellowship of the Code](docs/media/critique-fellowship-of-the-code.m4a) (AI-generated audio critique), or read Claude's [honest analysis](docs/guides/quest_analysis.md) of this tool. Take a [look at how a disciplined approach](docs/guides/quest_presentation.md) to software engineering is directly applicable to an agentic orchestration setup. 

Quest is a portable framework for running coordinated AI agents with human oversight.

Copy it into any repository to enable structured, auditable AI workflows, or tear it apart and study it. It’s built for learning, experimentation, and fun.

Quest is very useful, but it is not currently intended to be a long term maintained project. Still, I’d genuinely love to hear what you discover and what you think of it. Submit an issue with your thoughts, or fork the repo and point me to something cool you built. No guarantees on bug fixes or support, but I’m very interested in what comes out of it.

![Adventurers in our quest](docs/media/quest_v0.14.png)

## Dashboard

Track portfolio status in the static executive dashboard:

- [Quest Dashboard](docs/dashboard/index.html)
- [Dashboard deployment + regeneration guide](docs/dashboard/README.md)

## What is Quest?

Quest is a multi-agent workflow where specialized AI agents (planner, reviewers, builder) work in **isolated contexts** with **human approval gates**. Two different models (Claude + GPT) review independently, an arbiter filters nitpicks, and you approve before anything gets built.

**One sentence:** *"Structured AI teamwork with checks and balances."*

```
┌─────────────── PLAN PHASE ───────────────┐    ┌─────────── BUILD PHASE ─────────────┐
│                                          │    │                                     │
│  You → Planner → Reviewers → Arbiter  ───┼────→  Builder → Reviewers → Arbiter ──→ Done 
│            ▲      (Claude)      │        │    │              (Claude)  │            │ ▲
│            │      (Codex)       │        │    │              (Codex)   │            │ GATE: human approval
│            └───── iterate ──────┘        │    │                 │      │            │
│                                          │    │                 ▼      │            │
│                                          │    │              Fixer ────┘            │
│                                          │    │           (if issues)               │
└──────────────────────────────────────────┘    └─────────────────────────────────────┘
                                   ▲
                                GATE: human approval
```

**Where you spend your time:** The beginning and the end. During planning, you review the plan, the arbiter's trade-off discussions, and occasionally override decisions. During hardening, you validate the MVP against reality — because you don't fully understand a feature until you see it built. Most follow-up quests and v2 ideas come from this post-build validation, not from planning. Critical code paths deserve human eyes regardless — you don't need to review every line, but you choose where to look. This works when you and Quest drive with intention: good test coverage and quality as a first-class constraint, not an afterthought.

## Quick Start
Almost there [quick start instructions](https://github.com/KjellKod/quest?tab=readme-ov-file#quick-start)

## Prerequisites

### Required: Claude Code CLI

Install Claude Code (Anthropic's official CLI):

```bash
# Install via npm
npm install -g @anthropic-ai/claude-code

# Or download from:
# https://docs.anthropic.com/en/docs/claude-code
```

### Optional: Codex MCP (for dual-model reviews)

Quest uses GPT 5.2 or GPT5-3-codex via Codex as a second reviewer. If you want dual-model reviews:

```bash

# update to gpt-5.3 
npm i -g @openai/codex
# validate you have access to it
codex -m gpt-5.3-codex 
# change the default
vim ~/.codex/config.toml
```

```bash
# Add Codex MCP server to Claude Code
claude mcp add codex -- npx -y @anthropic/codex-mcp-server

# Requires OpenAI API key configured
# https://platform.openai.com/docs/quickstart
```

If you skip this, Quest will use Claude for all roles (still works, just single-model).

## Quick Start

### Option A: Use the Installer (Recommended)

```bash
# Download the installer
curl -fsSL https://raw.githubusercontent.com/KjellKod/quest/main/scripts/quest_installer.sh -o quest_installer.sh
chmod +x quest_installer.sh

# Preview what will be installed
./quest_installer.sh --check

# Install Quest
./quest_installer.sh
```

The installer:
- Handles fresh installs AND updates
- Tracks file checksums to detect your modifications
- Never overwrites your customizations (uses `.quest_updated` suffix)
- Supports `--force` for CI/automation

### Option B: Manual Copy

Copy these folders to your repository root:
- `.ai/` - Source of truth (permissions, roles, templates)
- `.skills/` - Skill procedures (plan-maker, code-reviewer, etc.)
- `.claude/` - Claude Code integration (agents, hooks)
- `.cursor/` - Cursor integration
- `.codex/` - Codex integration
- `docs/guides/quest_setup.md` - Setup documentation
- `AGENTS.md` - Coding rules (customize for your project)
- `DOCUMENTATION_STRUCTURE.md` - Navigation guide

### Customize allowlist

Edit `.ai/allowlist.json` to match your project:

```json
{
  "role_permissions": {
    "builder_agent": {
      "file_write": [".quest/**", "src/**", "tests/**"],
      "bash": ["npm test", "pytest"]
    }
  }
}
```

### Add to .gitignore

```
.quest/
```

### Use it

```bash
claude
/quest "Add a loading skeleton to the user list"
# or
/quest "use my specification <path>"
# or if you have mcp/jira or similar installed, with skills etc to retrieve them
/quest "lets work with <jira ticket>"
```

Quest scales from simple to complex — just describe what you want:

```bash
# Quick feature
/quest "Add a loading spinner to the save button"

# Multi-file change
/quest "Implement user preferences with localStorage"

# Large refactor
/quest "Add weekly update checking with opt-out config"

# Resume where you left off
/quest feature-x_2026-02-04__1430

# Resume with new direction
/quest feature-x_2026-02-04__1430 "only use claude, skip codex"
```

Abort anytime, resume later. State persists in `.quest/<id>/state.json`.

## Writing a Good Quest Brief

Quest enforces **spec → plan → implementation** — the whole point is to prevent skipping straight to coding. Your initial input is the spec. You can start with a rough idea, but the more you clarify upfront, the better the plan and implementation will be.

**If your input is thin**, Quest automatically detects this and enters a **structured questioning phase** before planning begins. You don't need to get it perfect on the first try — Quest will ask the right questions to fill the gaps.

### How Questioning Works

When Quest determines your input needs more detail, it asks **targeted, numbered questions** (Q1, Q2, Q3...) in batches of 1-3 at a time. After each batch of answers, Quest decides whether to ask more, rephrase, or move on to planning.

- **Hard cap of 10 questions** — Quest never asks more than 10, and usually needs far fewer
- **Flexible approach** - Quest is on top of Claude so at **any time** you can modify things. Did you want to add more details, have it ask more questions? Ask and Quest/Claude provides. 
- **Checkpoint around Q5-Q7** — Quest offers to start planning if it has enough context
- **"Just go with it"** — say this at any point to skip remaining questions and proceed with explicit assumptions
- **Detailed input skips questioning entirely** — if your input already has clear deliverables, scope, and acceptance criteria, Quest goes straight to planning

The questioning phase produces a structured summary (requirements, constraints, assumptions, unknowns) that becomes the foundation for the plan. For a deeper look at how Quest evaluates your input and routes between questioning and planning, see the [Input Routing Guide](docs/guides/quest_input_routing.md).

### Input Quality Ladder

| Input level | What you provide | What Quest produces |
|------------|-----------------|-------------------|
| **Rough idea** | `"add dark mode"` | Quest enters questioning phase (Q1, Q2...), then plans. Works, but expect more iteration. |
| **Idea with context** | `"add dark mode — should persist in localStorage, respect OS preference, toggle in header"` | Planner has clear direction. Fewer review iterations. |
| **Structured spec** | A doc with intent, constraints, acceptance criteria, and scope boundaries | Planner produces a tight plan on the first pass. Reviewers focus on real issues. Best results. |

### Examples at Each Level

**Rough idea** — Quest enters the questioning phase before planning:
```bash
/quest "add user notifications"
# Quest detects thin input, starts questioning:
#   Q1: What triggers a notification? (API events, user actions, scheduled?)
#   Q2: In-app only, or also email/push?
#   Q3: What does "done" look like — what should a reviewer check?
# After your answers:
#   Decision: STOP — enough context to produce an actionable plan.
# Quest produces a requirements summary, then proceeds to planning.
```

**Idea with context** — enough for a solid first plan:
```bash
/quest "Add in-app notifications: toast component in bottom-right,
auto-dismiss after 5s, support info/warning/error levels,
trigger from any API error response"
```

**Structured spec** — point to a doc, PRD, RFC, or Jira ticket:
```bash
# Local spec file
/quest "implement the feature described in docs/specs/notifications.md"

# Jira ticket (if you have Jira MCP installed)
/quest "implement PROJ-1234"

# Inline spec with acceptance criteria
/quest "Add toast notifications:
- Intent: surface API errors and system events to users
- Constraints: no external dependencies, must work with existing design system
- Acceptance criteria:
  1. Toast appears on API error with message from response
  2. Auto-dismisses after 5s, manual dismiss via X button
  3. Three levels: info (blue), warning (yellow), error (red)
  4. Multiple toasts stack vertically
  5. Accessible: role=alert, keyboard dismissible"
```

The sweet spot for most tasks is somewhere between level 2 and 3. You don't need a formal RFC — just **intent** (what and why), **constraints** (boundaries and limits), and **acceptance criteria** (how you'll know it's done).

## Advanced Workflows

Quest's pause/resume and human gates enable workflows beyond simple "describe → build."

### Do you have something else in mind, Quest/Claude is super charged

Consider you have just recieved the brief, you have three alternatives to choose from. You can't decide which. 

```bash

[ongoing quest/before implementation]
"For the planning, I want to do all 3 suggestions, create 3 different slugs for them and let gpt-5.2 be the planner for all three"

```

### Swap Models Mid-Quest

Start a quest, review the plan, then re-run planning with different model configuration:

```bash
# Start with default dual-model planning
/quest "redesign the authentication flow"

# After reviewing the plan, restart planning with only Claude
/quest auth-redesign_2026-02-04__1430 "re-plan this using only claude, skip codex reviews"

# Or re-plan with GPT-5.2 for a different perspective
/quest auth-redesign_2026-02-04__1430 "re-plan this using gpt-5.2"

# Or merge the best of multiple plans — GPT as planner and arbiter  
/quest auth-redesign_2026-02-04__1430 "Look at the previous plans, find the best way
forward and merge in must-haves from the losing plan into our new plan.
Use gpt as planner and arbiter" .quest/plan-a/phase_01_plan/plan.md .quest/plan-b/phase_01_plan/plan.md

```

### Compare Multiple Plans

Generate competing plans and pick the best one:

```bash
# Plan A: default approach
/quest "migrate database from Postgres to SQLite"
# Review the plan, note the quest ID (e.g., db-migrate_2026-02-04__1430)

# Plan B: start a fresh quest with a different constraint
/quest "migrate database from Postgres to SQLite —
prioritize zero-downtime, use a dual-write pattern during transition"

# Plan C: different model mix
/quest "migrate database from Postgres to SQLite —
plan with emphasis on minimal code changes, feature-flag the cutover"

# Compare plans side by side
# Pick the best, resume that quest into build phase
/quest db-migrate_2026-02-04__1430
```

### Phased Execution for Large Work

For big features, break the work into phases with a dedicated plan and PR per phase:

```bash
# Step 1: Create a high-level plan with phases
/quest "Build a real-time collaboration system.
Create a high-level plan with 3-4 phases.
Phase 1: WebSocket infrastructure
Phase 2: Presence and cursor tracking
Phase 3: Conflict resolution (OT or CRDT)
Phase 4: UI integration
Don't implement yet — just plan the phases."

# Step 2: Review the high-level plan, then quest each phase individually
/quest "Implement Phase 1 from the collaboration system plan
in .quest/collab-system_2026-02-04__1430/phase_01_plan/plan.md —
WebSocket infrastructure only. Create a PR when done."

# Step 3: After Phase 1 PR is merged, continue
/quest "Implement Phase 2: presence and cursor tracking.
Build on the WebSocket infrastructure from Phase 1."

# Each phase gets: detailed plan → review → build → code review → PR
# You validate and merge each phase before moving to the next
```

This pattern works well because:
- Each phase has **focused context** (no accumulated drift)
- You can **adjust direction** between phases based on what you learned
- Each PR is **reviewable** in isolation
- You can **switch models or strategies** between phases

## Key Features

- **Clean context** — each agent starts fresh (no drift)
- **Dual-model review** — Claude + Codex review plans AND code (different blind spots)
- **Arbiter** — filters nitpicks, decides "good enough", prevents spin
- **Human gates** — you approve before building
- **Artifacts saved** — full audit trail in `.quest/`
- **Scales up** — step-by-step approach shines on large tasks (context stays manageable)
- **Smart intake** — Quest evaluates your input and asks structured, numbered questions when it needs more detail (max 10, usually fewer). Say "just go with it" to skip ahead anytime

## How the Orchestrator Works

The Quest Orchestrator (main Claude running `/quest`) coordinates specialized agents. During review phases, it dispatches **both reviewers in parallel**:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      QUEST ORCHESTRATOR                             │
│                 (Main Claude executing /quest skill)                │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Review Phase (Plan or Code)
                                  │
                    ┌─────────────┴─────────────┐
                    │   SINGLE MESSAGE with     │
                    │   TWO...MANY TOOL CALLS   │
                    └─────────────┬─────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              ▼                   │                   ▼
┌─────────────────────────┐       │       ┌─────────────────────────┐
│   Tool Call 1:          │       │       │   Tool Call 2:          │
│   Task tool             │  PARALLEL     │   mcp__codex__codex     │
│   (Claude subagent)     │   EXECUTION   │   (Codex MCP server)    │
│                         │       │       │                         │
│  → plan-reviewer or     │       │       │  → GPT-5.2 reviews      │
│    code-reviewer agent  │       │       │    same artifacts       │
└───────────┬─────────────┘       │       └───────────┬─────────────┘
            │                     │                   │
            ▼                     │                   ▼
   review_claude.md               │          review_codex.md
                                  │
              └───────────────────┼───────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │   Runtime collects BOTH   │
                    │   results, then continues │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                          Arbiter synthesizes
```

**Why parallel?** Both reviewers are independent (write separate files, read same inputs). Claude's API executes multiple tool calls from the same message concurrently.

## File Structure

```
your-repo/
├── .ai/                          # Source of truth (AI-agnostic)
│   ├── allowlist.json            # Permissions (customize this!)
│   ├── quest.md                  # Quick reference
│   ├── context_digest.md         # Short context for Codex reviews
│   ├── roles/                    # Agent behavior definitions
│   ├── schemas/                  # Handoff contract
│   └── templates/                # Document templates
├── .skills/                      # Skill procedures (AI-agnostic)
│   ├── quest/SKILL.md            # Quest orchestration procedure
│   ├── plan-maker/SKILL.md       # Planning methodology
│   ├── plan-reviewer/SKILL.md    # Plan review checklist
│   ├── code-reviewer/SKILL.md    # Code review checklist
│   ├── implementer/SKILL.md      # Implementation methodology
│   └── git-commit-assistant/SKILL.md  # Commit message from staged diff + trailer
├── .claude/                      # Claude Code integration
│   ├── agents/                   # Thin wrappers → .ai/roles/
│   ├── hooks/                    # Permission enforcement
│   └── skills/quest/SKILL.md     # Thin wrapper → .skills/quest/
├── .cursor/                      # Cursor integration
├── .codex/                       # Codex integration
└── .quest/                       # Ephemeral run state (gitignored)
```

## Documentation

- **[Quest Setup Guide](docs/guides/quest_setup.md)** - Detailed setup instructions
- **[Quest Presentation](docs/guides/quest_presentation.md)** - How it works (with diagrams)
- **[Input Routing Guide](docs/guides/quest_input_routing.md)** - How Quest evaluates your input and routes between questioning and planning
- **[AGENTS.md](AGENTS.md)** - Coding rules to customize
- **[.ai/quest.md](.ai/quest.md)** - Quick reference

## The Quest Party: Agent Roles

### Planner
Creates the implementation plan from your quest brief. Explores the codebase, identifies files to change, and writes a detailed plan with acceptance criteria.

### Reviewers (Claude + Codex)
Two independent reviewers examine plans and code:
- **Claude reviewer**: Uses Claude's understanding of the codebase
- **Codex reviewer**: Uses GPT 5.2 for a different perspective

Having two different model families catches different blind spots.

### Arbiter
Synthesizes both reviews, filters nitpicks, and decides: **approve** (proceed) or **iterate** (revise). Prevents endless review cycles by focusing on what matters.

### Builder
Implements the approved plan. Writes code, runs tests, and produces a PR description. Works only after you approve the plan.

### Fixer
**The cleanup specialist.** When code reviewers find issues after the builder finishes:

1. Fixer receives the review feedback
2. Makes targeted fixes to address the issues
3. Re-runs tests to verify
4. Code is re-reviewed

The fix loop continues until reviewers approve (or max iterations reached). This keeps the builder's original work intact while addressing review feedback.

**Key difference from Builder:**
- **Builder**: Implements the full plan from scratch
- **Fixer**: Makes surgical fixes to existing implementation based on review feedback

## License

Public Domain (Unlicense). No warranty. See [LICENSE](LICENSE).
