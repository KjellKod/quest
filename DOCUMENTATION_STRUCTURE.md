---
title: Documentation Structure & Navigation
purpose: Explain the documentation layers and how to navigate between them.
audience: Contributors and AI agents.
scope: Repo-wide documentation map and navigation rules.
status: active
owner: maintainers
---

# Documentation Structure & Navigation

This document explains how documentation is organized in this repository and how to navigate it effectively. The structure is designed to support both human contributors and AI coding agents.

## Philosophy: Layered Context Management

Instead of dumping all context into a single document, this repository uses **layered context**:

| Layer | Purpose | Stability | When to Read |
|-------|---------|-----------|--------------|
| **1. Principles** | Coding rules, product intent, boundaries | Very stable | Always (entry point) |
| **2. Architecture** | System design, data flows, component relationships | Stable | When understanding how things work |
| **3. Implementation Plans** | Feature roadmaps, step-by-step plans | Active/changing | When building features |
| **4. Historical Reference** | Completed work, lessons learned | Archived | When investigating past decisions |
| **5. Guides** | How-to documentation, configuration | Reference | When doing specific tasks |

### Architecture vs Guides

These two layers serve different purposes:

| Aspect | `docs/architecture/` | `docs/guides/` |
|--------|---------------------|----------------|
| **Answers** | *How does it work?* | *How do I use it?* |
| **Audience** | Engineers, AI agents, contributors | End users, new contributors |
| **Content** | Diagrams, data flows, component boundaries, design decisions | Step-by-step instructions, CLI commands, examples |
| **Changes when** | Major refactors, new subsystems | UX changes, new features users interact with |

Each layer links to others. This keeps the AI sharp, grounded, and less likely to invent things just to be helpful.

---

## YAML Headers (Frontmatter)

Selected docs include a short YAML header at the top to enable **header-first reading**. Agents should read headers first and only load full documents when needed.

**Minimal schema:**
```yaml
---
title: <short title>
purpose: <1–2 sentences>
audience: <who should read>
scope: <what this doc covers>
status: <draft | active | complete | deprecated>
owner: <team or role>
last_updated: <YYYY-MM-DD>
related:
  - <path>
---
```

Use this schema for high-signal entry points (AGENTS, BOOTSTRAP, architecture summaries). Do not add headers to every historical or archival doc unless needed.

---

## Documentation Map

```
Repository Root
├── AGENTS.md                    ← START HERE (coding rules & boundaries)
├── .skills
│   ├── BOOTSTRAP.md             ← How to discover and use skills
│   └── SKILLS.md                ← Available skills index
├── README.md                    ← Product overview & setup
├── DOCUMENTATION_STRUCTURE.md   ← You are here (navigation guide)
│
├── docs/
│   ├── architecture/            ← Layer 2: System design (optional)
│   │
│   ├── implementation/          ← Layer 3: Active plans
│   │   ├── README.md                (navigation hub for plans)
│   │   ├── [active plans...]
│   │   ├── backlog/                 (future work)
│   │   └── history/             ← Layer 4: Completed work
│   │
│   └── guides/                  ← Layer 5: Reference docs
│       ├── quest_setup.md
│       └── quest_presentation.md
│
├── .ai/                         ← Quest orchestration config
│   ├── allowlist.json
│   ├── quest.md
│   └── roles/
│
├── .claude/                     ← Claude Code integration
│   └── AGENTS.md                ← Claude entry point (points here)
│
├── .cursor/                     ← Cursor integration
│   └── rules                    ← Cursor entry point (points here)
│
└── .codex/                      ← Codex integration
    └── AGENTS.md                ← Codex entry point (points here)
```

---

## How AI Agents Should Navigate

### Starting a Task

1. **Read `AGENTS.md`** - Understand coding rules and architecture boundaries
2. **Check `docs/implementation/README.md`** - Find relevant active plans (if exists)
3. **Read the specific plan** - Understand approach before coding

### Understanding the System

1. **Start with `docs/architecture/`** - Get the big picture (if present)
2. **Dive into specific architecture docs** as needed
3. **Reference `docs/guides/`** for specific subsystems

### Building a Feature

1. **Check for existing plan** in `docs/implementation/`
2. **Review related history** in `docs/implementation/history/` if plan references past work
3. **Follow the plan** - Don't invent new approaches without discussion

### Investigating Past Decisions

1. **Search `docs/implementation/history/`** - Most decisions are documented
2. **Check git blame/log** for context on specific changes
3. **Look for "lessons learned"** sections in historical docs

---

## Key Entry Points by Role

| Role | Start Here | Then Navigate To |
|------|------------|------------------|
| **AI Agent (general)** | `AGENTS.md` | Architecture → Implementation plans |
| **New contributor** | `README.md` → `docs/guides/quest_setup.md` | `AGENTS.md` |
| **Using quest** | `.ai/quest.md` | `docs/guides/quest_setup.md` |
| **Debugging an issue** | `docs/architecture/` | Relevant component docs |
| **Adding a feature** | `docs/implementation/README.md` | Specific feature plan |

---

## Why This Structure Works

1. **Reduces hallucination** - AI has clear authoritative sources, not scattered context
2. **Scales with project growth** - History is archived, active docs stay manageable
3. **Supports context windows** - Each layer is self-contained, load only what's needed
4. **Maintains consistency** - Principles layer rarely changes, provides stable grounding
5. **Enables verification** - AI can cross-reference architecture against implementation

---

## Maintaining This Structure

### When Adding New Docs

- **New feature plan?** → `docs/implementation/` + update `README.md` index
- **Completed feature?** → Move to `docs/implementation/history/`
- **Architecture change?** → Update `docs/architecture/`
- **New guide?** → `docs/guides/`

### When Updating AGENTS.md

- Keep it focused on **rules and boundaries**
- Link to detailed docs rather than duplicating content
- Update "Where to Learn More" if navigation changes

---

## Related Documents

- [AGENTS.md](AGENTS.md) - Coding rules and architecture boundaries
- [README.md](README.md) - Product overview
- [.ai/quest.md](.ai/quest.md) - Quest orchestration guide
- [.skills/SKILLS.md](.skills/SKILLS.md) - Available skills
