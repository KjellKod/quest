---
title: OpenCode Quickstart Guide
description: How to install and run Quest from OpenCode runtime
---

# OpenCode Quickstart Guide

This guide explains how to run Quest from the OpenCode runtime. If you're using Claude Code instead, see [Quest Setup Guide](quest_setup.md).

## Prerequisites

### Required: OpenCode CLI

Install OpenCode following the official documentation:
- Visit [https://opencode.ai/docs](https://opencode.ai/docs) for installation instructions
- Verify installation:
  ```bash
  opencode --version
  ```

## Installation

### Step 1: Copy OpenCode Configuration

Copy the `.opencode/` directory to your repository root:

```bash
# From the Quest repository
cp -r .opencode/ /path/to/your-repo/
```

### Step 2: Verify Installation

```bash
# Start OpenCode in your repository
opencode

# Quest should be available via $quest command
$quest "your task description"
```

## Directory Structure

The `.opencode/` directory contains:

```
.opencode/
├── opencode.json      # OpenCode configuration (agents, commands, models)
├── agents/           # Portable role definitions
│   ├── planner.md
│   ├── plan-reviewer.md
│   ├── builder.md
│   ├── code-reviewer.md
│   ├── arbiter.md
│   └── fixer.md
├── skills/            # Skill procedures
│   └── quest/
│       └── SKILL.md  # Quest orchestration skill
└── commands/          # Command definitions
    └── quest.md       # $quest command definition
```

## Running Your First Quest

### Step 1: Start OpenCode

```bash
cd your-repo
opencode
```

### Step 2: Run a Quest

```bash
# Basic quest
$quest "Add a loading skeleton to the user list"

# With specific requirements
$quest "Add dark mode that persists in localStorage"

# Resume a previous quest
$quest feature-x_2026-02-27__1200
```

### Step 3: Human Approval Gates

Quest will pause at key points for your approval:
- **Plan Approval**: Review the implementation plan before building
- **Code Review Approval**: Review changes before they're finalized

Type `yes` to approve, `no` to request changes, or `abort` to cancel.

## Configuration

### Customize Agent Permissions

Edit `.opencode/opencode.json` to configure agent permissions:

```json
{
  "agent": {
    "quest": {
      "permission": {
        "task": {
          "builder": "allow"
        }
      }
    }
  }
}
```

### Allowed Directories

Quest validates file access through `.ai/allowlist.json`. See [Quest Setup Guide](quest_setup.md) for configuration details.

## Next Steps

- **[Quest Setup Guide](quest_setup.md)** - Full setup documentation for both runtimes
- **[Quest Presentation](quest_presentation.md)** - How Quest works (with diagrams)
- **[Input Routing Guide](quest_input_routing.md)** - How Quest evaluates your input
- **[AGENTS.md](../../AGENTS.md)** - Customize coding rules for your project
