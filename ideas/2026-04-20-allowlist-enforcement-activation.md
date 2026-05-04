# Idea: Allowlist Enforcement — Role Identification, Hook Activation, and Bypass Tests

> Superseded by `ideas/2026-05-04-ci-review-allowlist-quality-roadmap.md`.
> Keep this file as historical source material; do not implement directly.

## Status: proposed (follow-up quest)

## Origin

Surfaced during PR #94 review. The user asked whether `enforce-allowlist.sh` was being used (answer: no) and whether that was intentional (answer: likely yes, deferred). This doc lays out the specific blockers that need to land before the `PreToolUse` hook can responsibly be turned on.

Scope here is **activation**: wiring the hook, solving the role-identification gap, and proving the enforcement works. It does **not** cover allowlist content bugs (bare bash/python, prefix matcher) — those are tracked in `ideas/2026-04-20-allowlist-pattern-hygiene.md` and are a strict prerequisite.

## The current state

| Component | Status |
|---|---|
| `.claude/hooks/enforce-allowlist.sh` | Exists, written for PreToolUse, reads `$1` as role arg, reads stdin as tool-use JSON. |
| `.claude/settings.json` `hooks.PreToolUse` | **Not present.** Only `SessionStart` and `PostToolUse` (audit log) are wired. |
| `.ai/allowlist.json` `role_permissions` | Exists, populated per role. Content has known bugs (see sibling doc). |

## The three blockers

### Blocker 1 — Role identification

`enforce-allowlist.sh:10` starts with `ROLE="${1:-}"` — it expects the role as a positional CLI argument. Claude Code's `PreToolUse` hook interface provides **stdin only** (the tool-use JSON). There's no mechanism for the orchestrator to say *"this tool call is from the fixer"* via hook arguments.

Result today (if the hook were wired): every invocation would have `ROLE=""` → hit `[[ -z "$ROLE" ]] && exit 0` → silently allow everything. No enforcement actually happens.

**Fix candidates:**

- **Environment variable.** Orchestrator sets `QUEST_ROLE=builder_agent` (or similar) in the subprocess environment before triggering any tool call. Hook reads `ROLE="${QUEST_ROLE:-}"` instead of `$1`. Simplest. But: the orchestrator must have a well-defined "current role" and discipline to set it. Every role-change boundary must set/unset the env var. Nested orchestration gets awkward.

- **Sentinel file.** Orchestrator writes `.quest/current_role` with the role name at dispatch time. Hook reads the file. Survives across process boundaries. But: cleanup discipline required, stale files can cause stale enforcement.

- **Claude Code user context.** If the Claude Code API exposes session-scoped user context (a key-value the orchestrator can set and hooks can read), use that. Needs investigation of what `PreToolUse` stdin actually contains — maybe it already carries the subagent label.

**My lean:** investigate Claude Code hook stdin contents first. If the PreToolUse JSON already contains the subagent label (e.g. `subagent_type: "fixer"`), no new mechanism is needed — the hook just reads from the JSON. If it doesn't, environment-variable is the simplest reliable option, with orchestrator discipline encoded in `workflow.md`.

### Blocker 2 — Allowlist content bugs

Tracked in `ideas/2026-04-20-allowlist-pattern-hygiene.md`. Must land first. Otherwise activation would:

- Block legitimate commands (`gh pr view 123` because the entry is `gh pr view.*` literal).
- Permit compound commands (`git status && rm -rf /` because prefix matcher).
- Permit bare-bash escape (`bash -c 'anything'` because bare `"bash"` is in the list).

Turning the hook on with these bugs still present would simultaneously over-block and under-block. Strictly worse than no enforcement.

### Blocker 3 — No bypass tests

No test currently asserts that `enforce-allowlist.sh` actually blocks anything. Adding the hook to `settings.json` without tests means a regression in the matcher goes undetected indefinitely.

## Proposal

A small quest that, in order:

1. **Investigate PreToolUse stdin.** Read Claude Code hook docs / examples. Write a trivial diagnostic hook (`log stdin to a file`) and examine what Claude actually passes when a subagent invokes a tool. Confirm whether the subagent/role label is present.

2. **Implement role identification.** Based on the investigation:
   - If role is in stdin → update `enforce-allowlist.sh` to read it from JSON.
   - Else → add `QUEST_ROLE` env-var writing to orchestrator dispatch in `.skills/quest/delegation/workflow.md` (every role invocation), and update the hook to read `${QUEST_ROLE}`.

3. **Write bypass tests.** Scripts under `tests/` that invoke the hook with representative tool-use JSONs for each role and each decision (allow / block), asserting exit codes. Cover:
   - Allowed command for the right role → exit 0.
   - Allowed command for a DIFFERENT role whose allowlist excludes it → exit 2.
   - Disallowed metachar-compound command → exit 2.
   - Missing role → exit 0 (current safety fallback — keep this so a misconfigured hook doesn't wedge the entire tool stack).

4. **Wire the hook in settings.json.** Add `PreToolUse` entry pointing at `enforce-allowlist.sh`.

5. **Dogfood it on a real quest.** Run one small quest with the hook active. Observe behavior. Confirm nothing legitimate is blocked; confirm at least one synthetic bad command is blocked (e.g. manually try `bash -c 'rm -rf /tmp/nonexistent'` from a role that doesn't have bare `bash`).

## Files to change

- `.claude/hooks/enforce-allowlist.sh` — role source (stdin or env var).
- `.claude/settings.json` — add `PreToolUse` hook wiring.
- `.skills/quest/delegation/workflow.md` — document the role-identification contract; if env-var-based, add "set `QUEST_ROLE` before each role dispatch" to every Task/Codex invocation section.
- `tests/` — new hook bypass test suite (`tests/unit/test_enforce_allowlist.sh` or `.py`).

## Acceptance Criteria

1. The PR #2026-04-20-allowlist-pattern-hygiene has landed (prerequisite).
2. `PreToolUse` hook is wired in `.claude/settings.json`.
3. Role identification works: hook resolves the current role via a documented mechanism (stdin field or env var) and applies that role's allowlist.
4. Bypass test suite covers:
   - Allowed command for correct role → exit 0.
   - Allowed command for wrong role → exit 2.
   - Compound command with `&&` → exit 2.
   - Compound command with `;` → exit 2.
   - Missing role → exit 0 (safety).
5. One real quest runs cleanly with the hook active, documented in a journal entry.

## Out of Scope

- Expanding allowlist coverage beyond what roles already need.
- Building a graphical allowlist editor.
- Hook performance profiling (acceptable unless someone observes a real slowdown).

## Priority

Medium. Without hook activation, the allowlist is documentation. Fixing allowlist patterns (pattern-hygiene doc) is a prerequisite and is higher priority because it also tightens the documented intent for humans. Activation is the payoff step: it converts the documented intent into enforced behavior.

The sequencing matters: **do not activate before patterns are fixed.** Activating first would produce worse behavior than the current "documented but not enforced" state.

## Dependencies

**Blocked by:** `ideas/2026-04-20-allowlist-pattern-hygiene.md`.

## Follow-up Quest Prompt (Draft)

```text
/quest "Activate allowlist enforcement: role identification, hook wiring, bypass tests.

Reference: ideas/2026-04-20-allowlist-enforcement-activation.md
Prerequisite: ideas/2026-04-20-allowlist-pattern-hygiene.md must have landed.

DELIVERABLES

1. Investigate Claude Code PreToolUse stdin contents via a diagnostic hook.
   Confirm whether subagent/role label is present.

2. Implement role identification:
   - If role is in stdin -> update enforce-allowlist.sh to read it from JSON.
   - Else -> add QUEST_ROLE env-var dispatch to .skills/quest/delegation/workflow.md
     and update the hook to read env var.

3. Write a bypass test suite at tests/unit/test_enforce_allowlist.* covering:
   - allowed command + correct role = exit 0
   - allowed command + wrong role = exit 2
   - compound command with &&, ;, |, etc. = exit 2
   - missing role = exit 0 (safety)

4. Wire PreToolUse in .claude/settings.json.

5. Dogfood: run one real quest with the hook active, write a journal entry
   documenting what legitimate commands ran and at least one synthetic
   bad command that was correctly blocked.

OUT OF SCOPE

- Expanding allowlist coverage beyond what roles need.
- GUI/editor for the allowlist.
- Performance profiling unless a real slowdown is observed."
```
