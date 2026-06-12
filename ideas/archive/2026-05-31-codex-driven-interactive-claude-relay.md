# Codex-Driven Background-Agent Claude Relay

Date: 2026-05-31 (revised 2026-05-31 after verifying official surfaces)
Status: `done` — implemented as the Step-1 standalone runner (`scripts/claude_bg_run.py`, PR #136) and the Step-2 Quest wiring (`docs/implementation/claude-bg-transport-step2-wiring.md`); background-agent transport is the Codex-led default (`claude_role_transport: auto`).
Related: `claude-cli-login-context.md`, `codex_calls_claude.sh`,
`2026-05-26-native-runtime-dispatch.md`, `2026-04-13-codex-companion-runtime.md`,
`scripts/quest_claude_bridge.py`, `scripts/quest_claude_runner.py`,
`scripts/quest_preflight.sh`

## Problem

Effective **June 15, 2026**, Anthropic moves `claude -p` (non-interactive /
headless) and the Agent SDK off the subscription usage pool and onto a separate
monthly **Agent SDK credit** metered at full API rates (Pro $20 / Max5x $100 /
Max20x $200, no rollover, then spills to API rates). **Interactive Claude Code in
the terminal stays on the normal subscription pool, unaffected.**

Quest's Codex-led Claude roles run through `scripts/quest_claude_bridge.py`, which
shells out to `claude --print` (`quest_claude_bridge.py:132`). After June 15 that
path is API-priced. We want Codex-orchestrated quests to keep using Claude roles
**on the subscription pool**, without API cost.

Source: Anthropic Help Center, "Use the Claude Agent SDK with your Claude plan"
(support.claude.com/en/articles/15036540...). Retrieved 2026-05-31.

## Key finding: background agents are an official, subscription-billed surface

Claude Code ships **background agents** + a **per-user supervisor** — full Claude
Code sessions (not `-p`, not the Agent SDK) that run detached from any terminal and
are dispatched and managed from the shell. Verified against the installed CLI
(v2.1.159) and the canonical doc `code.claude.com/docs/en/agent-view.md`.

**Billing (verbatim, agent-view.md → Limitations):**
> "Rate limits apply: background sessions consume your subscription usage the same
> as interactive sessions, so running ten agents in parallel uses quota roughly ten
> times as fast as running one."

**Supervisor auth (verbatim):**
> "The supervisor and its sessions authenticate with the same credentials as your
> interactive sessions and make no additional network connections beyond the model
> API."

So background agents draw from the **subscription pool**, not the Agent-SDK credit
pool. This is the cheap, sanctioned path — it replaces the earlier tmux + `/loop`
prototype this note originally proposed.

### Verified shell surface (Claude Code v2.1.159)

```bash
claude --bg "<prompt>"                       # dispatch a background session
claude --bg --agent <name> --name <label> \  # role + display name
       --model <m> --effort <e> --permission-mode <mode> --add-dir <dir> "<prompt>"
# prints: "backgrounded · <shortID> · <name>" plus the management commands:
claude agents --json     # live sessions as JSON (pid, cwd, kind, startedAt, sessionId, name, status); no TTY
claude attach <id>       # open in this terminal
claude logs <id>         # print recent output
claude stop <id>         # stop (alias: kill); claude respawn <id>; claude rm <id>
claude daemon status     # per-user supervisor health
```
State: `~/.claude/jobs/<id>/state.json`, roster `~/.claude/daemon/roster.json`.

## Approach: a background-agent transport behind a hard switch

Add a hard transport switch (a config value consumed by the runner/preflight,
**not** a prose rule in `workflow.md`), in `.ai/allowlist.json`, copied into
`.quest/<id>/orchestration.json` at startup:

```jsonc
"claude_role_transport": "bridge"            // default: existing claude --print path (API-metered after Jun 15)
// or
"claude_role_transport": "background-agent"  // this proposal: subscription-pool path
```

`bridge` stays the honest, headless, API-metered default (works in CI / locked
sandboxes with an API key). `background-agent` is the opt-in subscription-pool path
for Codex-led quests on a host with a logged-in Claude subscription.

### Mechanism (self-bootstrapping; no tmux, no keystroke injection)

Auth persists on disk after a one-time `claude login` / `claude setup-token`, so a
fresh background session is already authenticated — **Codex dispatches and manages
sessions itself**; no human is required per dispatch. (Per
`claude-cli-login-context.md`: auth is a property of the *execution context* — the
dispatch must run under the same HOME/user that completed login, with
`claude auth status` reporting `loggedIn: true` in that context.)

```
# one-time, ever, per machine (human): the only steps Codex cannot do
claude login                                    # creds persisted to ~/.claude
claude --permission-mode bypassPermissions ...  # one interactive acceptance of bypass mode

# per Claude role (Codex orchestrator, via its exec tool):
1. dispatch:
   claude --bg --name "<quest>-<role>" --model <m> --effort <e> \
          --permission-mode bypassPermissions --add-dir <quest_dir> \
          "Read <files>. Write <artifact> + handoff.json. Non-interactive contract."
   # capture printed <shortID>
2. detect completion: poll .quest/<id>/.../handoff_<role>.json   (EXISTING contract, reused verbatim)
   #   and/or `claude agents --json` for state (working / needs input / completed / failed)
3. on "needs input": route to the human gate (maps to quest's needs_human)
4. teardown: claude rm <shortID>
```

- Sessions run as full Claude Code sessions (not `-p`) → subscription pool.
- Result detection reuses `quest_claude_runner.py` handoff polling unchanged.
- `claude logs <id>` gives diagnostics; `claude agents --json` gives structured state.

### Preflight + fallback (keeps the switch honest)

`scripts/quest_preflight.sh` for `background-agent`:
1. `claude auth status` → require `loggedIn: true` in the execution context; if not,
   instruct the user to run `claude login` once.
2. `claude daemon status` → confirm the supervisor is reachable (it autostarts on
   first dispatch).
3. If auth is missing, or the CLI/version lacks agent view, **fall back to `bridge`**
   and record the downgrade — never silently block.

## Reused vs. net-new

- **Reused:** `quest_claude_runner.py` handoff polling; `prepare_artifact_files` /
  `expected_artifacts_for_role`; preflight's cache/availability pattern. **No tmux,
  no `/loop`, no relay skill, no keystroke injection** — those were dropped.
- **Net-new:** the `claude_role_transport` key + a `background-agent` dispatch branch
  in the runner (`claude --bg` + ID capture + `claude rm` teardown); the preflight
  `auth status` / `daemon status` probes; a `needs input` → `needs_human` mapping.

## Constraints (do not paper over) — from agent-view.md

1. **One-time human setup** per machine: `claude login`, plus one interactive
   acceptance of `bypassPermissions`/`auto` before background sessions may use it.
2. **Worktree auto-isolation for write roles.** Background sessions move into
   `.claude/worktrees/<id>/` before editing, and `claude rm` can delete that worktree
   (with uncommitted changes). Read-only Claude roles (planner, plan/code reviewers,
   arbiter, review-arbiter) are unaffected. A Claude **builder/fixer** would need
   `worktree.bgIsolation: "none"` or path reconciliation — but quest's builder/fixer
   default to Codex, so this rarely applies.
3. **Research preview.** Agent view requires v2.1.139+ and "the interface and
   keyboard shortcuts may change." Pin automation to `claude agents --json` and the
   printed management commands, not the TUI.
4. **Quota burns at interactive rates.** N parallel Claude roles ≈ N× subscription
   quota. Fine for quest (1–2 Claude roles per phase).
5. **`kind` values.** A running interactive session reports `kind: "interactive"`;
   the doc lists `kind` in the JSON but does not enumerate the background value.
   Treat `claude agents --json` `status` as authoritative for state.

## ToS posture

Stronger than the original tmux idea: this uses an **officially documented,
subscription-billed** feature for its intended purpose ("dispatch tasks you don't
watch every step, from your shell"). The only stretch is that *Codex* plays the
supervisor role the docs frame as a human; billing is explicitly subscription, so
the cost goal is met on sanctioned surfaces. Offered behind an opt-in switch; the
default remains `bridge`.

## Why pursue it

For a Pro/Max user it keeps Codex-led Claude roles on the subscription pool (no API
spend) after June 15, reuses quest's existing file-handoff contract untouched, is
self-bootstrapping once login is done, and rides official CLI surfaces
(`claude --bg`, `claude agents --json`, `claude logs`, the per-user supervisor)
instead of a bespoke harness.

## Resolved / no longer open

- **stream-json over interactive?** No — `--input-format`/`--output-format
  stream-json` are `--print`-only (confirmed in `claude --help`). Background agents
  make this moot.

## Open questions

- Liveness/health: how should preflight detect a *wedged* (vs. merely working)
  background session, and recover (`claude respawn` vs. fall back to `bridge`)?
- Confirm the exact `kind` string for background sessions for a tighter
  `agents --json` filter.
