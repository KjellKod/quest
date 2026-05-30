---
title: Quest Hooks vs Instructions Boundary
purpose: Reduce instruction-heavy orchestration by moving deterministic guardrails into hooks, keeping policy canonical in docs, and extracting runtime mechanics into scripts.
audience:
  - quest-maintainers
  - quest-runtime-authors
status: proposed
date: 2026-04-24
related:
  - AGENTS.md
  - .skills/quest/SKILL.md
  - .skills/quest/delegation/workflow.md
  - .claude/settings.json
  - .claude/hooks/enforce-allowlist.sh
  - ideas/2026-04-13-instruction-architecture.md
  - ideas/quest-policy-canonicalization-and-enforcement-roadmap.md
---

# Summary

Quest is not overcomplicated because it has too many rules.
Quest is overcomplicated because too much runtime behavior is encoded in markdown instead of being enforced mechanically.

The current split is off:

- `AGENTS.md` and the quest skill files contain real policy and workflow value.
- `.skills/quest/delegation/workflow.md` also carries a large amount of control-plane behavior that should live in scripts or hooks.
- `.claude/settings.json` currently wires only `SessionStart` and a `PostToolUse` audit hook, while the workflow text claims stronger enforcement than the runtime actually provides.

This note proposes a cleaner boundary:

1. Keep policy and phase semantics in instruction files.
2. Move deterministic allow/deny and context surfacing into hooks.
3. Move runtime probe, fallback, and bookkeeping logic into scripts and validators.
4. Keep shared policy canonical in repo files, with thin hook adapters for Claude and Codex rather than two separate policy systems.

# Why This Matters

Today, Quest has a drift problem between "what the docs say" and "what the runtime guarantees."

Concrete examples in this repo:

- The workflow says role permissions are enforced by `.claude/hooks/enforce-allowlist.sh`, but there is no active `PreToolUse` wiring in `.claude/settings.json`.
- The allowlist hook expects a positional role argument, which the hook runtime does not currently supply in the way the script expects.
- The workflow document carries detailed probe, dispatch, fallback, and logging mechanics that are really runtime implementation, not durable policy.

That creates two kinds of cost:

1. Prompt bloat: too much orchestration detail is loaded as prose.
2. False confidence: some important protections are documented but not actually enforced.

# Official Hook Model: Claude and Codex

This proposal should align with the official hook models, not with blog folklore.

## Claude Code

Canonical docs:

- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/hooks-guide

Relevant constraints and affordances from the official docs:

- `PreToolUse` can decide `allow`, `deny`, `ask`, or `defer`, and can also modify tool input.
- `PreToolUse` matches tool names such as `Bash`, `Edit`, `Write`, MCP tool names, and others.
- When multiple matching hooks return different decisions, the most restrictive result wins.
- Command hooks run with the user's full system permissions, so they must be reviewed and kept narrow.
- The guide positions hooks as lifecycle automation for things like blocking protected edits, surfacing context, formatting after writes, and reactive environment loading.

Implication for Quest:

- Claude hooks are suitable for real local guardrails.
- They are not a replacement for architecture docs or phase policy.
- They should be thin, deterministic, and test-backed.

## OpenAI Codex

Canonical docs:

- https://developers.openai.com/codex/hooks

Relevant constraints and affordances from the official docs:

- `PreToolUse` can intercept `Bash`, `apply_patch`, and MCP tool calls.
- Current Codex `PreToolUse` is explicitly described as a guardrail, not a complete enforcement boundary.
- Project-local `.codex` hooks load only when the project layer is trusted.
- Matching hooks run concurrently; one matching hook cannot stop another from starting.
- Codex receives hook input as JSON on `stdin`.
- Repo-local hook commands should resolve from the git root rather than assuming the current working directory.
- Unsupported `PreToolUse` responses such as `allow`, `ask`, `updatedInput`, and some other richer shapes currently fail open.

Implication for Quest:

- Codex hooks are useful, but weaker and narrower than Claude hooks.
- We should not make Codex hooks the only source of truth for important policy.
- Shared policy logic should live in scripts/validators, with a Codex hook adapter calling that logic where useful.

## Design Consequence

Quest should not build three independent policy stacks:

- one in markdown
- one in Claude hooks
- one in Codex hooks

Instead:

1. Keep canonical policy in docs plus shared scripts.
2. Use Claude hooks as the first enforcement adapter where they fit well.
3. Add Codex hook parity only as thin adapters over the same policy logic.
4. Keep validators and artifact checks as the final backstop for cross-runtime correctness.

# Recommended Boundary

## Keep In Instruction Files

These are policy or architecture and should remain human-readable:

- Repo-wide engineering values and review rubric in `AGENTS.md`
- Quest gate sequence and approval semantics
- Phase responsibilities and artifact contracts
- Routing policy, including when to question, when to run solo, and when to run full workflow
- Human-facing explanation of why a rule exists
- Architecture ownership and selective-loading direction from `ideas/2026-04-13-instruction-architecture.md`

These are durable, cross-runtime, and not naturally expressed as a single tool interception.

## Move To Hooks

These are deterministic, repetitive, and naturally tied to lifecycle events:

1. Allowlist enforcement
   - Best fit: `PreToolUse`
   - Why: tool boundary, clear allow/deny outcome, existing script already present

2. ~~Branch and directory visibility before file edits~~ — **RETIRED (won't-do, PR #116).**
   - A `PreToolUse` `Edit|Write` hook was tried and closed: its stdout on exit 0 is debug-log-only (invisible to user and model), it reports the orchestrator's `pwd`/branch rather than the edit target, and it never fires under Codex/MCP. Statusline already covers this visibility on the Claude side. Do not re-propose. See [`archive/2026-04-15-pretooluse-branch-dir-verification-hook.md`](archive/2026-04-15-pretooluse-branch-dir-verification-hook.md). The portable lesson — put cross-runtime guardrails in the Quest Python seam (state machine / validators), not in Claude-only hooks — is reflected in the "Move To Scripts And Validators" section below.

3. Pre-build write blocking for non-`.quest/**` edits
   - Best fit: `PreToolUse` on `Edit|Write`
   - Why: current rule is deterministic and based on quest state plus target path

4. Lightweight write audit
   - Already a hook
   - Keep it small and append-only

## Move To Scripts And Validators

These are too procedural or stateful for hook bodies and too detailed for instruction files:

1. Runtime preflight and second-model probing
2. Claude bridge readiness and runtime dispatch
3. Handoff polling and artifact preparation
4. Fallback ladders and retry classification
5. Context-health logging format and runtime attribution bookkeeping
6. Commit-readiness checks such as staged diff review and branch cleanliness
7. Post-run path validation for subagent outputs

These belong in scripts because they are orchestration mechanics, not policy text.

## Do Not Move To Hooks

These are not good hook candidates:

- The full quest phase recipe
- Planner/reviewer/fixer role instructions
- Questioner limits and interaction style
- Review philosophy
- Human approval gates
- Anything requiring long-lived state reasoning across multiple steps

If a rule cannot be answered by "given this one event, should the runtime allow, deny, warn, or annotate?", it likely does not belong in a hook.

# Concrete Recommendations

## Recommendation 1: Thin `workflow.md`

Reduce `.skills/quest/delegation/workflow.md` to:

- phase sequence
- role entry/exit conditions
- artifact contract
- high-level invariant rules

Move detailed dispatch, probe, retry, and logging mechanics into scripts or validators, then reference those scripts from the workflow.

## Recommendation 2: Activate Real Claude `PreToolUse` Enforcement

Quest already has the beginnings of this in `.claude/hooks/enforce-allowlist.sh`, but it is not wired as active policy yet.

Recommended scope:

1. Solve role identification cleanly.
2. Wire `PreToolUse` in `.claude/settings.json`.
3. Add test coverage for both allow and deny paths.
4. Dogfood on a real quest before treating it as canonical enforcement.

## Recommendation 3: Add A Separate Branch/Directory Visibility Hook

Keep this hook additive and narrow:

- print branch and working directory before `Edit|Write`
- degrade safely outside git
- do not bundle policy decisions into this hook

This is a high-value, low-risk context aid.

## Recommendation 4: Enforce Pre-Build Path Rules Mechanically

The rule "no source edits before Build" is currently important enough that it should not remain instruction-only.

Recommended implementation:

- shared script reads `.quest/<id>/state.json`
- shared script evaluates the target file path
- hook blocks non-`.quest/**` writes before Build
- validator also checks the workspace afterward, so the rule has a backstop beyond hook execution

This should be implemented once as shared policy logic, then exposed through a Claude hook first and a Codex hook adapter later if needed.

## Recommendation 5: Do Not Build Full Hook Parity First

Do not start by trying to mirror every Claude hook in Codex.

Why:

- Codex `PreToolUse` is explicitly a guardrail rather than a full enforcement boundary.
- Some Codex decision shapes currently fail open.
- Codex project-local hooks require trusted `.codex` project configuration.

Better sequence:

1. define shared policy logic in scripts
2. wire Claude hooks first where the repo already has `.claude/` structure
3. add Codex adapters only for the narrow policies that benefit from parity

## Recommendation 6: Keep Validators As The Final Backstop

Hooks improve live behavior.
Validators prove correctness after the fact.

Quest should keep both.

Examples:

- hook blocks a bad pre-build write attempt
- validator proves no illegal pre-build writes slipped through
- hook blocks an out-of-policy bash command
- validator proves artifacts and state transitions are still consistent

# Suggested Implementation Sequence

## Phase A: Hook The Low-Risk, High-Signal Guards

1. Branch/directory visibility hook for `Edit|Write`
2. Allowlist enforcement activation, once role identification and tests are ready

## Phase B: Hook The Strong Path Guard

3. Pre-build non-`.quest/**` write blocker

This requires a shared policy script rather than embedding the logic directly in the hook command.

## Phase C: Thin The Workflow Docs

4. Move probe, runtime dispatch, retry ladder, and logging details out of `workflow.md`
5. Replace long procedural prose with short references to scripts and validation contracts

## Phase D: Optional Codex Adapter Layer

6. If Codex local hook usage becomes important for Quest development, add `.codex` hook adapters that call the same shared scripts
7. Keep behavior intentionally narrower than Claude where Codex semantics are weaker

# Validation Strategy

The validation needs to go beyond unit tests.
We need to prove the boundary works during real quest execution, during interruption, and during resume.

## 1. Script-Level Tests

Add targeted tests for the shared policy scripts and hook wrappers:

- allowlist allow case
- allowlist deny case
- wrong role case
- missing role case
- branch/directory hook in a git repo
- branch/directory hook in a non-git directory
- pre-build write to `.quest/**` allowed
- pre-build write to source path denied
- post-Build source write allowed

## 2. Hook-Level Dry Runs

Drive the hook scripts with synthetic JSON payloads that match the official hook inputs:

- Claude `PreToolUse` payloads for `Bash`, `Edit`, and `Write`
- Codex `PreToolUse` payloads for `Bash` and `apply_patch`

Success criteria:

- expected exit codes
- expected stderr / JSON messages
- no malformed-output failures

## 3. Real Quest Dogfood: Plan-Phase Write Guard

Run a small quest and intentionally pressure the bad path.

Scenario:

1. start a small `/quest`
2. stop during plan or plan review
3. try to force an implementation edit before Build
4. verify the hook blocks the write
5. verify the user-facing message tells the operator to proceed through Build first

Success criteria:

- no non-`.quest/**` edits land before Build
- quest state remains valid
- the block message is actionable rather than vague

## 4. Real Quest Dogfood: Interrupt And Resume

Validate that hook-based guardrails do not break resume behavior.

Scenario:

1. start a quest
2. interrupt after planning artifacts exist
3. resume by quest id
4. continue to Build
5. confirm the guardrails are still active and not duplicated or stale

Success criteria:

- `SessionStart` and resume behavior do not corrupt env or state
- no duplicate side effects from startup hooks
- plan-phase protections still apply before Build

## 5. Outside-In Validation

Run Quest from another repo and, separately, from a non-git temp directory where practical.

Validate:

- branch/dir hook prints a safe fallback when git metadata is unavailable
- repo-local assumptions do not crash the hook
- git-root resolution is used where required for Codex-style adapters

## 6. Codex Compatibility Check

If and when a `.codex` adapter is added, validate against Codex's actual hook semantics:

- trusted project layer required
- repo-root hook path resolution
- deny path works for `Bash` / `apply_patch`
- no dependence on unsupported `allow`, `ask`, or `updatedInput` behaviors
- no assumption that Codex hook interception is complete

## 7. Regression Gate

Before declaring success, rerun:

- Quest smoke flow
- interrupted quest resume
- one blocked-policy scenario
- one allowed-policy scenario

The acceptance bar should be "the runtime now enforces what the docs claim" for the chosen scope.

# Acceptance Criteria

This proposal is successful when:

1. Quest policy is clearly split across docs, hooks, and scripts.
2. `workflow.md` becomes shorter and less procedural.
3. Claude hook enforcement exists for at least the highest-value deterministic guards.
4. Shared policy logic is test-backed and not duplicated in hook commands.
5. Codex compatibility is handled intentionally rather than assumed.
6. Quest dogfood runs show that real lifecycle behavior matches the documented policy.

# Non-Goals

- Replacing quest architecture docs with hooks
- Full Claude/Codex feature parity in one pass
- Moving review philosophy or routing logic into hooks
- Building a giant hook framework before the first few protections prove value

# Proposed Follow-Up Quest

```text
/quest "Implement the first hooks-vs-instructions boundary cleanup for Quest.

Reference:
- ideas/2026-04-24-quest-hooks-vs-instructions-boundary.md
- ideas/2026-04-20-allowlist-enforcement-activation.md
- ideas/archive/2026-04-15-pretooluse-branch-dir-verification-hook.md (RETIRED won't-do — do NOT implement the branch/dir hook; included only so it is not re-proposed)
- ideas/quest-policy-canonicalization-and-enforcement-roadmap.md

Goal:
Move the highest-value deterministic Quest guardrails out of prose and into
mechanical enforcement, while reducing procedural runtime detail in workflow.md.

Deliverables:
1. Activate a real Claude PreToolUse path for one or more narrow policy guards.
2. Keep shared policy logic in scripts, not inline hook shell fragments.
3. Add focused tests for hook allow/deny behavior and non-git fallback.
4. Dogfood with:
   - one normal quest run
   - one interrupted and resumed quest run
   - one pre-build write-block scenario
5. Trim workflow.md so runtime mechanics point to scripts instead of carrying
   the full implementation detail inline.

Out of scope:
- full Codex hook parity
- broad review-policy changes
- redesigning Quest orchestration end to end"
```

# References

Official docs:

- OpenAI Codex hooks: https://developers.openai.com/codex/hooks
- Claude hooks reference: https://code.claude.com/docs/en/hooks
- Claude hooks guide: https://code.claude.com/docs/en/hooks-guide

Repo context:

- [AGENTS.md](../AGENTS.md)
- [.skills/quest/SKILL.md](../.skills/quest/SKILL.md)
- [.skills/quest/delegation/workflow.md](../.skills/quest/delegation/workflow.md)
- [.claude/settings.json](../.claude/settings.json)
- [.claude/hooks/enforce-allowlist.sh](../.claude/hooks/enforce-allowlist.sh)
- [ideas/2026-04-13-instruction-architecture.md](2026-04-13-instruction-architecture.md)
- [ideas/quest-policy-canonicalization-and-enforcement-roadmap.md](quest-policy-canonicalization-and-enforcement-roadmap.md)
