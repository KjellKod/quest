# Codex-Driven Interactive Claude Relay

Date: 2026-05-31
Status: `proposed`
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
**on the subscription pool**, without API cost, while honoring the *intent* of the
change (Claude as an interactive, human-supervisable runtime).

Source: Anthropic Help Center, "Use the Claude Agent SDK with your Claude plan"
(support.claude.com/en/articles/15036540...); The New Stack, "Anthropic splits
billing again" (2026). Retrieved 2026-05-31.

## Key insight

The billing boundary is the **entry mode** (`-p`/SDK vs. interactive session),
**not** whether a human typed. So a `claude` process started *without* `-p` is an
interactive session billed to the subscription pool — regardless of who launched
it or whether anyone is watching. Quest's cross-model contract is already
file-based (every role writes an artifact + `handoff.json`; the orchestrator polls
files in `quest_claude_runner.py`), so we never need the interactive session's
stdout — only a way to (a) hand it a prompt and (b) detect when the files appear.

## Approach: an interactive relay behind a hard switch

Add a hard transport switch (config value consumed by the runner/preflight, **not**
a prose rule in `workflow.md`), in `.ai/allowlist.json` and copied into
`.quest/<id>/orchestration.json` at startup:

```jsonc
"claude_role_transport": "bridge"             // default: existing claude --print path
// or
"claude_role_transport": "interactive-relay"  // this proposal: subscription-pool path
```

`bridge` is the honest, headless, API-metered default (works in CI / locked
sandboxes). `interactive-relay` is the opt-in subscription-pool path for
Codex-led quests that want cheap Claude roles and run where a persistent TTY is
available.

### Mechanism (self-bootstrapping)

Auth persists on disk after a one-time `claude login` / `claude setup-token`, so a
fresh `claude` process is already authenticated — **Codex can open and own the
session itself**; no human is required at launch. (Per
`claude-cli-login-context.md`: auth is a property of the *execution context* — the
session must run under the same HOME/user that completed login, and
`claude auth status` must report `loggedIn: true` in that context.)

```
# one-time, ever, per machine (human, browser OAuth — the only step Codex cannot do):
claude login            # creds persisted to ~/.claude

# preflight for an interactive-relay quest (Codex, via its exec tool):
tmux has-session -t quest-claude 2>/dev/null \
  || { tmux new-session -d -s quest-claude 'claude'; \
       tmux send-keys -t quest-claude '/loop 20s /quest-claude-relay' Enter; }

# per Claude role (Codex orchestrator):
1. write request → .quest/<id>/inbox/<role>.req.json   (prompt + prepared artifact paths)
2. (optional) tmux send-keys -t quest-claude '' Enter   (wake the loop immediately)
3. poll .quest/<id>/phase_xx/handoff_<role>.json        (the EXISTING contract)
```

- The session runs in **interactive mode** (no `-p`) → subscription pool.
- The `/loop` skill (already in this repo) re-invokes a new **`/quest-claude-relay`**
  skill on a timer; that skill drains the inbox: read oldest request, run the role
  against the named files, write the artifact + `handoff.json`, delete the request.
  So Codex never scripts keystrokes into the TUI — the large/multiline prompt
  travels by file; `send-keys` is only an optional latency nudge.
- Result detection reuses `quest_claude_runner.py` file polling verbatim.

### Preflight + fallback (keeps the switch honest)

`scripts/quest_preflight.sh` for `interactive-relay`:
1. Detect persisted Claude auth (`claude auth status` → `loggedIn: true`) in the
   execution context; if missing, instruct the user to run `claude login` once.
2. Ensure the relay session is live (`tmux has-session`); bootstrap it if not.
3. If neither auth nor a TTY/tmux environment is available, **fall back to
   `bridge`** and record the downgrade — never silently block.

## Reused vs. net-new

- **Reused:** `/loop` skill; `quest_claude_runner.py` handoff polling;
  `prepare_artifact_files` / `expected_artifacts_for_role`; preflight's
  cache/availability pattern.
- **Net-new:** the `/quest-claude-relay` inbox-drain skill; the
  `claude_role_transport` key + dispatch branch; the preflight liveness/auth probe
  and `tmux` bootstrap; a trusted-workspace `settings.json` allowed-tools list for
  the session (interactive equivalent of the bridge's `bypassPermissions`).

## Constraints (do not paper over)

1. **One-time human login** per machine; Codex cannot perform browser OAuth.
2. **Persistent-TTY environment required** (tmux/screen). Dead in one-shot CI
   sandboxes → use `bridge` there.
3. **Permission pre-trust** — the relay skill trips tool-permission prompts; the
   session needs a trusted-workspace allowed-tools config once.
4. **`/loop` consumes interactive turns while idle** — tune the interval or
   start/stop the loop around active quests.
5. **One session serializes Claude roles** — usually fine (a phase rarely has >1
   Claude role; reviewer A=Claude, B=Codex). Run N sessions for parallel Claude
   roles.
6. **ToS posture is *defensible, not blessed*.** It stays on the interactive side
   of the line Anthropic drew (mode-based billing), but Anthropic has not
   explicitly sanctioned "another agent drives my interactive session." This is a
   side-step, offered behind an opt-in switch — not the default.

## Why pursue it

For a Pro/Max user, it keeps Codex-led Claude roles on the subscription pool
(no API spend) after June 15, reuses quest's existing file-handoff contract almost
untouched, and is self-bootstrapping once login is done. The default stays on the
safe, sanctioned `bridge`; this is the cheap, intent-aligned alternative for users
who want it and can host a live session.

## Open questions

- Does interactive `claude` accept `--input-format stream-json` on stdin (and still
  bill as interactive)? If so, a structured stdin/stdout channel could replace the
  inbox+`send-keys` mechanics entirely — worth a short spike before building tmux.
- Liveness/health: how should preflight detect a *wedged* (vs. merely idle) relay
  session, and recover (restart vs. fall back to `bridge`)?
