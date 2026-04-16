---
title: PreToolUse Branch/Directory Verification Hook
purpose: Add a safe, additive hook pattern that surfaces branch and directory context before edits.
audience:
  - quest-developers
  - quest-users
scope: Hook-level observability guardrails for Edit/Write actions.
status: proposed
owner: kjell
---

## Problem
The evaluation identifies wrong-location edits as the top friction pattern (`Wrong Approach` = 55), with repeated incidents where changes landed in the wrong branch, wrong directory, or wrong nested Quest path. The report explicitly calls out that Codex sub-agents wrote to incorrect directories and forced recovery cycles.

## Proposal
Use the exact hook command from the evaluation before `Edit|Write` tool calls so branch/directory context is always visible:

```json
{
  "matcher": "Edit|Write",
  "hooks": [
    {
      "type": "command",
      "command": "echo '📍 Branch:' $(git branch --show-current) '| Dir:' $(pwd)"
    }
  ]
}
```

Quest-specific adaptation: merge this additively into existing hooks and add non-git fallback behavior for outside-in runs where repository VCS is unavailable.

## Dual-Mode Sanity Check
### Inside-repo use (Quest developed here)
Inside this repo, branch and path are almost always available; printing both before writes directly targets the most frequent error class with minimal behavior change.

### Outside-in use (Quest invoked from another repo)
Outside-in sessions can run with `vcs_available == false` in `.skills/quest/delegation/workflow.md`, so `git branch --show-current` may fail. The hook should degrade safely (for example, `git branch --show-current 2>/dev/null || echo 'no git'`) while still printing `pwd`.

### Conflicts and Required Adaptations
`.claude/settings.json` already has `SessionStart` and a `PostToolUse` `Write|Edit` audit hook. This proposal must be an additive merge, not a replacement, to avoid stomping existing audit behavior.

## Actionable Steps
1. Inspect current hooks with `jq '.hooks' .claude/settings.json`.
2. Add a `PreToolUse` entry for `Edit|Write` containing the evaluation command.
3. Adapt the command to tolerate non-git workspaces using `2>/dev/null` fallback.
4. Validate in two contexts: a git repo and a temporary non-git directory.
5. Document the hook intent in `AGENTS.md` or a canonical policy pointer file so the rule is discoverable.

## Cross-References
- `ideas/2026-04-15-claude-rule-confirm-pwd-branch-before-edits.md`
- `ideas/2026-04-15-subagent-path-constraints-hardening.md`
- `ideas/2026-04-13-instruction-architecture.md`
- `ideas/quest-policy-canonicalization-and-enforcement-roadmap.md`

## Risks / Non-Goals
- Non-goal: this does not guarantee correctness; it only improves context visibility.
- Risk: noisy output can be ignored if overused, so the message should stay short and consistent.
- Risk: overwriting `.claude/settings.json` hooks would regress existing audit logging.

## Success Signal
During edits, every `Edit|Write` action logs branch+directory context (or explicit `no git` fallback), and wrong-directory edits decrease in subsequent Quest sessions.
