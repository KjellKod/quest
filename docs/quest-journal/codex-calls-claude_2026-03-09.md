# Codex -> Claude Shell-Out Prototypes

Status: complete

Retired from `ideas/` on 2026-03-09. The supported bridge implementation now lives at `scripts/claude_cli_bridge.py`, while the Quest-owned Codex-led runtime path uses `scripts/quest_claude_runner.py` and `scripts/quest_claude_probe.py`.

- Supported bridge script: `scripts/claude_cli_bridge.py`
- Prototype wrapper: `ideas/codex_calls_claude.sh`

> Footnote: This note supersedes the older cross-model bridge write-up. The supported implementation now lives at `scripts/claude_cli_bridge.py`. The Bash wrapper remains a prototype in `ideas/`.

This repo now contains one supported bridge and one quick experiment for triggering Claude from a Codex-driven shell flow:

- `scripts/claude_cli_bridge.py` (supported Python bridge with optional JSON envelope)
- `ideas/codex_calls_claude.sh` (minimal Bash wrapper)

## How this fits Quest

Use this pattern only for **Codex-orchestrated** Quest experiments where Codex needs to call Claude directly for a specific step (for example: arbitration-style reasoning, second-opinion review, or narrative synthesis).

Guidance:

- **Primary target:** Codex as orchestrator.
- **Not needed for OpenCode normal flow:** OpenCode already routes through its configured agents/subagents and MCP tools.
- **Do not replace existing Quest orchestration defaults** for Claude/OpenCode paths.
- **Treat as optional fallback/bridge** when a Codex-led run specifically needs Claude CLI access.

In short: this is an additive prototype bridge for Codex-led flows, not a change to the standard Quest runtime behavior.

## Why this may or may not be better

Compared with direct API bridge (Anthropic SDK/HTTP):

- **Potentially better:**
  - Less setup when `claude` CLI is already installed/authenticated.
  - Mirrors `codex exec` workflow (simple shell one-shot).
  - Easy to test quickly inside existing terminal-driven loops.
- **Potentially worse:**
  - Depends on local CLI availability/auth/session state.
  - Output contract can be less stable than owning the API payload end-to-end.
  - Harder to guarantee identical behavior across environments.

Compared with MCP/subagent-native routing:

- **Potentially better:**
  - Useful as a lightweight emergency bridge in Codex-led experiments.
- **Potentially worse:**
  - Bypasses normal orchestration abstractions and policy surfaces.
  - Adds another execution path to maintain and reason about.

Recommendation: keep this as a prototype bridge for Codex-orchestrated experiments; prefer native OpenCode/Quest subagent routing where already available.

## 1) Bash wrapper

```bash
./ideas/codex_calls_claude.sh --prompt "Hello world from Codex" --output-format json
```

From file:

```bash
./ideas/codex_calls_claude.sh --prompt-file prompt.txt --output-format text
```

From stdin:

```bash
echo "Review this diff" | ./ideas/codex_calls_claude.sh --output-format json
```

## 2) Python wrapper

Plain passthrough output:

```bash
python3 scripts/claude_cli_bridge.py --prompt "Hello world from Codex"
```

Stable JSON envelope (good for scripts):

```bash
python3 scripts/claude_cli_bridge.py \
  --prompt "Review this patch" \
  --output-format json \
  --json-wrap
```

## Notes

- These scripts assume `claude` CLI is installed and authenticated.
- If `claude` is missing, scripts fail with a clear error.
- These are intentionally lightweight prototypes; production routing should move to an official script path later.
