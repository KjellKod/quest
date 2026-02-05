# Quest: An Honest Analysis

**By Claude (Opus 4.5) — February 2026**

> This is an AI-generated analysis of the Quest framework, written after thorough exploration of the codebase. For an audio version, listen to [Fellowship of the Code](../media/critique-fellowship-of-the-code.m4a).

---

## Quick Start: How Flexible Is It?

Quest scales from simple to complex:

```bash
# Simple: one-liner feature request
/quest "Add a loading spinner to the save button"

# Medium: multi-file change with clear scope
/quest "Implement user preferences with localStorage persistence"

# Large: architectural change spanning multiple systems
/quest "Add weekly update checking with opt-out config and graceful network handling"
```

**No boilerplate required.** You describe what you want in natural language. The planner figures out the files, the reviewers check the approach, and you approve before anything gets built.

### Pause, Resume, and Direct

Quest isn't a black box you kick off and hope for the best:

```bash
# Resume a quest from where you left off
/quest feature-x_2026-02-04__1430

# Resume and give new direction
/quest feature-x_2026-02-04__1430 "skip codex, only use claude for reviews"

# Check status of all quests
/quest status
```

**Abort anytime.** Close the terminal, come back tomorrow, resume from the last completed phase. State is persisted in `.quest/<id>/state.json`.

**Give directions mid-flight.** Want to skip dual-model review for a quick iteration? Tell it. Want to focus the planner on specific files? Tell it. The orchestrator adapts.

---

## What Is Quest?

Quest is a **portable multi-agent orchestration framework** for AI-assisted software development. It coordinates specialized AI agents (planner, reviewers, builder, fixer) through structured phases with human approval gates.

**Key numbers:**
- 7 agent role definitions
- 5 reusable skills
- 44 documentation files (excluding ephemeral runtime state)
- 1,392-line installer script with checksum-based update detection

---

## The Good: What Works Well

### 1. Thoughtful Architecture

The separation of concerns is clean:
- `.ai/` — Source of truth (AI-agnostic configuration)
- `.claude/`, `.cursor/`, `.codex/` — Thin wrappers for specific tools
- `.skills/` — Reusable procedures that work across AI tools

This means you can switch between Claude Code, Cursor, or Codex without rewriting your workflow definitions.

### 2. Dual-Model Review

Quest runs **two different AI models in parallel** (Claude + GPT 5.2) to review both plans and code. This is genuinely clever:

- Different model families have different blind spots
- Claude might miss what GPT catches, and vice versa
- Reviews run concurrently (same API call, two tool invocations)

The Arbiter then synthesizes both reviews and filters nitpicks, preventing endless "one more thing" cycles.

### 3. The Installer Is Sophisticated

The `quest_installer.sh` is not a crude copy script. It implements:

- **Checksum tracking**: Detects if you've modified files locally
- **Smart updates**: Never overwrites your customizations
- **Suffix management**: Creates `.quest_updated` files when upstream changes conflict with your edits
- **Manifest-driven**: `.quest-manifest` categorizes files into `copy-as-is`, `user-customized`, and `merge-carefully`
- **Preview mode**: `--check` shows what would happen without changing anything
- **CI-friendly**: `--force` for automation

This is exactly how a portable framework installer should work.

### 4. Human Gates

Quest doesn't blindly execute. Critical transitions require human approval:

- Before implementation starts (you approve the plan)
- Before commits and pushes
- Before destructive operations

The `allowlist.json` controls which phases auto-approve and which wait for you.

### 5. Full Audit Trail

Every quest run creates artifacts in `.quest/<quest_id>/`:
- Quest brief (what you asked for)
- Implementation plan
- Both reviews (Claude + Codex)
- Arbiter verdict
- PR description

This is gitignored (ephemeral), but available for debugging and learning.

---

## The Honest Criticisms

### 1. Not a Marketplace Fit

Quest is **not** a simple plugin. It's an orchestration framework with 7 agents, 5 skills, and structured phases. Marketplaces (VS Code extensions, npm packages) are designed for self-contained tools with UI-based setup. Quest's distribution model (installer script + copy folders) is the right fit for what it is.

### 2. Zero Config, But There's Depth

**Getting started is dead simple:**
```bash
curl -fsSL https://raw.githubusercontent.com/KjellKod/quest/main/scripts/quest_installer.sh | bash
claude
/quest "Add a logout button"
```

That's it. No customization required. The `allowlist.json` ships with sensible defaults.

**But there's depth if you want it.** You *can* customize permissions, review modes, iteration limits, and agent behavior. Most users won't need to. The defaults work.

### 3. Dependency on External Tools

Quest requires:
- **Claude Code CLI** (required) — Anthropic's official CLI
- **Codex MCP** (optional) — For dual-model reviews with GPT 5.2

If you skip Codex, Quest still works but uses Claude for all roles (single-model).

---

## Should Quest Be in a Marketplace?

**No.** Here's why:

| Marketplace Model | Quest Model |
|-------------------|-------------|
| Install and use | Adopt and adapt |
| Self-contained | Requires external CLIs |
| Minimal config | Customization is core |
| UI-based setup | File-based configuration |

Quest's distribution model (copy folders + installer script) is the right fit. A marketplace install would still require the same customization steps afterward.

---

## Task Size: Small, Medium, or Large?

A common question: *"Is this overkill for small tasks? Does it work for large ones?"*

**The surprising answer: Quest works well at all sizes, but shines on larger tasks.**

### Why Large Tasks Work

The step-by-step approach that might seem like overhead for small tasks becomes essential for large ones:

1. **Context stays fresh** — Each agent starts clean. No accumulated confusion from long conversations.

2. **Dual review catches more** — On a 500-line change, having two different models review independently catches issues a single model might miss.

3. **The arbiter prevents scope creep** — When reviewers suggest "nice to have" changes on a large PR, the arbiter filters them out.

4. **Audit trail helps debugging** — When something goes wrong in a large change, you can trace back through the plan, reviews, and verdicts.

5. **Human gates at the right moments** — You approve the plan *before* the builder writes 20 files, not after.

### Live Example: Weekly Update Check

At the time of this analysis, Quest was implementing its own update-check feature. Here's what happened:

**Iteration 1**: Planner proposed checking `checksums.txt` from upstream.

**Arbiter caught it**: "The detection mechanism relies on `checksums.txt` which does not exist upstream."

**Iteration 2**: Plan revised to use `.quest-version` SHA comparison via `git ls-remote` — infrastructure that already exists.

This is exactly how it should work. The dual-model review caught a real issue, the arbiter made a clear decision, and the plan improved. One iteration, one fix, move forward.

### The Real Overhead

The honest truth: Quest adds ~2-5 minutes of planning/review overhead before implementation starts.

For a 10-minute fix, that might feel excessive.
For a 2-hour feature, that's nothing.
For a multi-day refactor, it's invaluable.

**Recommendation**: Use Quest for anything non-trivial. For quick fixes, just ask Claude directly.

---

## Who Should Use Quest?

**Good fit:**
- Teams wanting consistent, auditable AI workflows
- Projects where quality gates matter
- Developers who don't fully trust a single model's output
- Organizations needing audit trails of AI-assisted changes

**Not a fit:**
- Quick prototyping where speed beats process
- Solo developers comfortable with ad-hoc AI assistance
- Projects where the overhead isn't justified

---

## What Could Be Better

1. **Interactive setup** (optional): `quest_installer.sh --interactive` could walk through configuration for users who want guidance
2. **Example projects**: A directory showing Quest in action on small, complete codebases

---

## Bottom Line

Quest is **well-engineered for what it is** — a portable multi-agent orchestration framework with dual-model verification and human gates. The installation mechanism is appropriate. The architecture is clean.

The question isn't "is this ugly?" — the question is "does this fit your needs?"

If you want structured, auditable AI workflows with quality gates: Quest delivers.

If you want zero-config AI assistance: Look elsewhere.

---

*Analysis generated by Claude (Opus 4.5) after exploring the Quest codebase. This document reflects an honest assessment, including criticisms.*
