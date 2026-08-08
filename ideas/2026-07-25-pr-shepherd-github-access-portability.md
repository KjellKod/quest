# pr-shepherd GitHub-Access Portability

Date: 2026-07-25
Status: `proposed`
Origin: surfaced while running `pr-shepherd` on PR #157 in a Claude-Code-on-web
session where `gh` is absent. The skill "worked" only because there were no
inline review threads to process; the script-backed review pipeline would have
failed. Adjacent to `ideas/2026-07-25-codex-claude-transport-hardening.md`
(same theme: make Quest work across execution contexts). Analysis only — no
code changed.

## Problem

`pr-shepherd` and its supporting scripts are hard-wired to the `gh` CLI. In
`gh`-less environments (Claude Code on web/remote, some CI, non-GitHub-CLI
platforms) the skill silently degrades. This is not hypothetical: the
session-start hook already warns `gh CLI not available — PR shepherd will be
limited`, and the shepherd run on PR #157 only succeeded because the
`gh`-dependent Step 4 / 4.4 pipeline was never exercised (no review comments).

The `gh` dependency lives in **two layers**:

- **Layer A — prose commands in `.skills/pr-shepherd/SKILL.md`:**
  `gh pr checks`, `gh run view --log-failed`, `gh pr ready`, `gh pr view`. An
  agent can hand-substitute GitHub MCP calls for these (as was done manually on
  PR #157).
- **Layer B — the Python scripts in `scripts/`** (not in the skill directory;
  the skill orchestrates repo-shared scripts):
  - `quest_pr_shepherd_checkout.py` → `gh pr view` / `gh pr checkout`
  - `quest_pr_shepherd_collect_intake.py` → `gh api user`, `gh …`
  - `quest_pr_shepherd_annotate_scope.py` → `gh pr diff --patch`
  - `quest_pr_shepherd_post_reply.py` → `gh api`, `gh pr comment`
  - `quest_pr_shepherd_fetch_failed_logs.py` → `gh run view --log-failed`
  - `quest_pr_sync_default_branch.py` → `gh` (this one already has a `git ls-remote`
    fallback)

## Key architectural constraint

"Detect `gh` or the GitHub MCP, prefer `gh`" is coherent **only at the agent /
instruction layer**. MCP tools are agent-only — **a Python subprocess cannot
call the GitHub MCP.** So at the script layer the real alternative to `gh` is
the **GitHub REST API with a token**, not MCP. Both `GH_TOKEN` and
`GITHUB_TOKEN` are present in the web/remote environment, so a REST fallback is
feasible.

Accurate model:
- **Agent layer:** `gh` ↔ GitHub MCP.
- **Script layer:** `gh` ↔ REST-with-token (MCP not reachable).

## Proposal

Make GitHub access **`gh`-preferred with an explicit fallback**, and resolve
the choice **once**, mirroring the existing `claude_role_transport: "auto"`
pattern (preflight resolves background-agent vs bridge once; everyone consumes
the result). Analogously, resolve `github_access: gh | rest` once — via
preflight or a small `scripts/quest_gh.py` helper — instead of sprinkling
`command -v gh` through every script and prose step.

Detection is cheap and reliable: `command -v gh` plus `gh auth status`. Default
order: prefer `gh` when present and authenticated; otherwise fall back
(MCP at the agent layer, REST at the script layer).

## Increments

1. **Instruction-layer branch (quick win).** Add to `SKILL.md`: "if `gh` is
   available use it; otherwise use the GitHub MCP equivalents
   (`pull_request_read`, `update_pull_request`, `add_issue_comment`,
   `add_reply_to_pull_request_comment`, …)." Formalizes what was done by hand on
   PR #157. Fixes Layer A; leaves Layer B unaddressed.
2. **Shared script helper (substantive).** Give the `pr_shepherd_*` scripts a
   common GitHub-access helper that uses `gh` when present and REST-with-token
   otherwise. This is the load-bearing change — it makes the Step 4 / 4.4
   review pipeline survive without `gh`. Real code across ~6 scripts plus tests.
3. **Non-goal.** Do not attempt to make scripts "call the MCP" — architecturally
   impossible; the REST-token path is the script-layer answer.

## Scope and relationship

- Orthogonal to the Opus 5 model upgrade; do not bundle.
- Thematically adjacent to the codex→Claude transport-hardening backlog (both
  are "make Quest robust across execution contexts").
- `pr-assistant` shares the same `gh` assumption for PR creation/body updates;
  a portability fix should consider covering it under the same helper so the
  two PR skills stay consistent.

## Suggested sequencing

1. Increment 1 (instruction branch) as a standalone quick win — low risk, high
   coverage for the common web/remote case's read/ready path.
2. Increment 2 (script helper + REST fallback) as its own quest, with tests
   that exercise both the `gh` and REST paths.
