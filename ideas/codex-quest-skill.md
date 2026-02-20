# Codex `$quest` (GPT-5.2-only) Skill + Runner

## What
Add a Codex-invocable quest entrypoint (ideally `$quest ...`) that runs the same quest workflow as Claude `/quest`, but using **only GPT‑5.2** for every role (planner/reviewers/arbiter/builder/fixer).

## Why
- Make the Quest blueprint runnable from **Codex CLI** without requiring Claude Code.
- Keep the existing Claude `/quest` workflow intact.
- Reuse the existing “source of truth” files (`.ai/` roles/templates/allowlist + `.quest/` artifact layout).

## Approach

### Design goals / invariants
- **Do not break Claude `/quest`**: no changes required to `.claude/skills/quest/SKILL.md` or `.skills/quest/SKILL.md`.
- **Reuse artifacts + layout**: write the same files into `.quest/<id>/...` so either tool can resume/review the same quest.
- **Reuse the same policy**: enforce `.ai/allowlist.json` gates/permissions from the Codex runner.
- **Clean-context roles**: each role runs with isolated context (no “planner drift” leaking into “reviewer”).

### What “multiple instances” means here
In the Claude flow, “multiple instances” = separate Task subagents and separate MCP calls, each with a fresh context.

For Codex-only quest, “multiple instances” means:
- **Planner run** is one fresh Codex conversation context
- **Plan reviewer A** is another fresh context
- **Plan reviewer B** is another fresh context (still GPT‑5.2, but independently seeded)
- **Arbiter**, **Builder**, **Code reviewer**, **Fixer** are each their own fresh contexts

This isolation is the core guardrail: reviewers/arbiter should not inherit the planner’s chain of thought or intermediate assumptions, only the artifacts.

### Architecture (Codex side)
Add a Codex skill named `quest` that delegates to a local runner:
- Skill: minimal wrapper that parses the user’s `$quest ...` input and calls the runner.
- Runner: a deterministic state machine that:
  - creates/resumes `.quest/<id>/state.json`
  - writes/reads `.quest/<id>/quest_brief.md`, phase artifacts
  - enforces `.ai/allowlist.json`
  - invokes GPT‑5.2 “role runs” in isolated contexts

The runner should treat `.skills/quest/SKILL.md` as the *behavioral spec* (phases, artifacts, gating), but does not need to literally execute that markdown.

### Codex backend choices: SDK vs `codex exec`

#### Option A — Codex SDK (Node): `@openai/codex-sdk`
Use a local Node runner that:
- creates **one Codex thread per role** (planner/reviewer/arbiter/builder/etc)
- calls `thread.run(prompt)` for each role step
- persists thread IDs into `.quest/<id>/logs/` (optional) for debugging/retries

**Strengths**
- Strong programmatic control (structured orchestration, retries, timeouts).
- Natural “multiple instances” model: **thread-per-role** is explicit.
- Easier to implement “resume” semantics (store/reuse thread IDs if desired).
- Can standardize outputs (e.g., force JSON handoffs matching `.ai/schemas/handoff.schema.json`).

**Weaknesses**
- Adds a Node dependency surface (runner script + pinned `@openai/codex-sdk` version).
- More “moving parts” when copying to another repo (install deps, keep versions aligned).
- You need to decide how the runner is distributed (committed JS, TS+build step, or `npx`).

**When it’s the better fit**
- You want reliable orchestration and clean separation (thread-per-role).
- You expect to evolve the workflow (more phases/roles) and need maintainability.

#### Option B — Shell out to `codex exec` (CLI)
Use a runner (bash/python/node) that spawns a new process for each role:
- `codex exec "prompt..."` (plus any non-interactive flags/settings you standardize)
- parse stdout for the handoff marker and/or emitted events
- write artifacts to disk

**Strengths**
- Fewer SDK-level dependencies: requires “Codex CLI installed” but no SDK library.
- Easy to run in CI and simple environments (just a binary + a script).
- Very explicit clean-context isolation: **each role = fresh process**.

**Weaknesses**
- Output parsing can be brittle if you rely on free-form text.
- Less control over streaming/events unless you fully adopt the JSONL event format.
- Potentially slower (process startup overhead per role run).

**When it’s the better fit**
- You want the simplest “portable blueprint” story: copy repo files + run one script.
- You want to keep the runner language-agnostic (Python stdlib, bash).

### “More portable” — what that means
Portability here means “how easy is it to copy this Quest blueprint to a brand-new repo and have it work”.

`codex exec` tends to be more portable because:
- the new repo only needs the **Codex CLI** + a small runner script committed with the blueprint
- you don’t need to add a Node package dependency and lockfile to the target repo

SDK tends to be less portable because:
- the new repo must install `@openai/codex-sdk` (and often a TS toolchain if written in TS)
- dependency/version drift becomes part of the setup story

Note: both options still assume “Codex is installed and authenticated”; they differ mainly in “extra dependencies inside the repo”.

### Reuse strategy (keep Claude `/quest` working)
Reuse these as-is:
- `.ai/allowlist.json` (policy + gates)
- `.skills/quest/agents/*.md` and `.ai/roles/quest_agent.md` (role instructions)
- `.ai/templates/*.md` (artifact templates)
- `.ai/context_digest.md` (stable review context)
- `.ai/schemas/handoff.schema.json` (handoff contract)
- `.quest/` folder structure + artifact naming

Add Codex-only files without touching Claude integration:
- a Codex skill wrapper (so `$quest ...` works in Codex)
- a runner script (the orchestrator)
- optional: a Codex config file to ensure the skill is discoverable in that repo

### Minimal feature set for v1
Support:
- `$quest "<instruction>"` (new quest)
- `$quest <quest-id>` (resume)
- `$quest status`
- `$quest allowlist`

Keep gates:
- honor `.ai/allowlist.json` → `auto_approve_phases.*` and `gates.*`

Plan phase (v1):
- single planner run → single reviewer run → single arbiter run (even though Claude does dual reviews)
  - (Reason: GPT‑5.2-only makes dual-review less valuable; keep v1 simpler.)

Then iterate toward parity:
- add “dual review” by spawning two independent reviewer threads/processes
- add build/review/fix phases

### Acceptance criteria (for the eventual implementation quest)
1. In Codex CLI, user can run `$quest "..."` and it creates `.quest/<id>/...` artifacts.
2. The runner never writes outside `.quest/**` unless the active role is permitted by `.ai/allowlist.json`.
3. Implementation and fix phases respect the configured human gates in `.ai/allowlist.json`.
4. Claude `/quest` continues to work unchanged in the same repo.

## Status
idea
