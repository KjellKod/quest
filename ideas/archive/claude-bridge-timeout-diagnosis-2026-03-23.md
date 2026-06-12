# Claude Bridge Timeout Diagnosis

Date: 2026-03-23
Status: `reference` (archived 2026-06-11 — incident encoded as the migration spec's dispatch false-positive finding and the preflight live-probe + host-context design)
Repo: `/Users/kjell/ws/extra/MCP_WORK`
Affected quest: `diff-sync-layer_2026-03-23__0529`

## Conclusion

The Claude bridge was **not actually unavailable**.

The quest preflight returned `available: false` because it was executed **inside the Codex sandbox**, where the Claude CLI call path did not complete. Outside the sandbox, both the direct Claude CLI call and the full quest bridge probe succeeded.

## What was verified

### 1. Claude CLI exists and auth is healthy

Command:

```bash
claude auth status
```

Result:
- `loggedIn: true`
- `authMethod: api_key`
- `apiProvider: firstParty`

### 2. Direct Claude CLI call fails in sandbox but succeeds outside it

Sandboxed command:

```bash
claude --print 'Reply with exactly: ok' --output-format text
```

Observed behavior in sandbox:
- no prompt response
- command hung until timed out during troubleshooting

Escalated/outside-sandbox command:

```bash
claude --print 'Reply with exactly: ok' --output-format text
```

Observed result:

```text
ok
```

### 3. Full quest bridge probe fails in sandbox but succeeds outside it

Sandboxed command:

```bash
python3 scripts/quest_claude_probe.py --quest-dir /Users/kjell/ws/extra/MCP_WORK/.quest/diff-sync-layer_2026-03-23__0529 --cwd /Users/kjell/ws/extra/MCP_WORK
```

Sandboxed result:

```json
{"exit_code": 1, "handoff_state": "unparsable", "result_kind": "timeout", "source": null, "stderr": "Timed out after 60.0s", "stdout": ""}
```

Escalated/outside-sandbox result:

```json
{"exit_code": 0, "handoff_state": "found", "result_kind": "handoff_json", "source": "handoff_json", "stderr": "", "stdout": "---HANDOFF---\nSTATUS: complete\nARTIFACTS: /Users/kjell/ws/extra/MCP_WORK/.quest/diff-sync-layer_2026-03-23__0529/logs/bridge_probe/probe_artifact.txt\nNEXT: null\nSUMMARY: probe ok"}
```

### 4. Quest preflight false-negative

Command:

```bash
./scripts/quest_preflight.sh --orchestrator codex
```

Sandboxed result:

```json
{
  "orchestrator": "codex",
  "second_model": "claude",
  "available": false,
  "checks": {
    "claude_cli_installed": true,
    "bridge_script_exists": true,
    "bridge_reachable": false
  },
  "warning": [
    "Claude bridge not available -- quest will run Codex-only (all roles).",
    "Ensure Claude CLI is installed and authenticated:",
    "  claude auth                          # authenticate"
  ]
}
```

This result was misleading because auth was already healthy and the real failure mode was sandboxed reachability, not missing installation/authentication.

## Root cause

The current quest preflight/probe path is sensitive to the execution environment.

- In the Codex sandbox, the Claude CLI bridge call path does not complete.
- Outside the sandbox, the same commands succeed.

So the failure mode is best described as:

> **sandbox-induced false negative in Claude bridge preflight**

not:

> Claude unavailable

## What this means for quest routing

The previous quest used Codex-only fallback based on a false-negative bridge probe.

If we want the intended balanced model mix (Claude + Codex), the quest preflight for Claude availability should be run in a context that is allowed to execute the Claude CLI bridge successfully, or the preflight logic should explicitly distinguish:
- CLI/auth missing
- bridge timeout in sandbox
- true bridge unavailability

## Recommended follow-up

1. Update the quest preflight path so Codex-led Claude bridge probing does not treat sandbox timeout as true model unavailability.
2. Update the warning text so it does not always blame auth.
3. Restart the blocked quest from a fresh branch/quest run using a verified Claude-available setup.
