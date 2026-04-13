# Claude CLI Login Context

Date: 2026-03-24
Observed from: `/Users/kjell/ws/ai-tools`
Status: `reference`

## Summary

A machine can have Claude Code installed and even have an interactive Claude Code session open, while external `claude` CLI calls from another shell context still report `loggedIn: false`.

For Quest and other automation, treat Claude CLI login as a property of the exact execution context that will invoke `claude`, not as a property inferred from "Claude Code is open."

## What was verified

### CLI exists and runs

```bash
command -v claude
claude --version
claude --help
```

Observed:
- `claude` resolved to `/Users/kjell/.local/bin/claude`
- version reported `2.1.81 (Claude Code)`
- help output succeeded

### Shell environment was not using an API key

```bash
env | rg '^(ANTHROPIC|CLAUDE)_'
```

Observed:
- no `ANTHROPIC_*` or `CLAUDE_*` variables were present

### CLI auth status for the external shell context was unauthenticated

```bash
claude auth status
```

Observed:

```json
{"loggedIn":false,"authMethod":"none","apiProvider":"firstParty"}
```

### A real non-interactive Claude call failed on login

```bash
claude -p "Reply with exactly: OK" --output-format text --permission-mode bypassPermissions --tools ""
```

Observed:

```text
Not logged in - Please run /login
```

## Interpretation

This failure mode is not "missing API key." It is "the CLI process context is not authenticated."

Practical causes can include:
- the external caller is running under a different `HOME`
- the external caller is not seeing the same Claude auth store as the interactive app
- the app session exists, but CLI login was never completed for that same shell/user context

## Recommended operator flow

Use login-based auth, not API-key fallback:

```bash
claude auth login --claudeai
claude auth status
```

Only treat Claude as externally callable after `claude auth status` reports `loggedIn: true` in the same execution context that will run the automation.

## Quest implication

Quest diagnostics and bridge checks should avoid guidance that implies an API key is expected when the intended mode is subscription login. Operational guidance should instead say:

```bash
claude auth login --claudeai
claude auth status
```

and should note that "Claude Code is open" is not sufficient proof that external CLI calls will authenticate.
