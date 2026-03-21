# Codex MCP Docs and Model Dispatch Cleanup

- PRs: #70, #72, #73
- Merged: 2026-03-16 to 2026-03-17
- Outcome: Codex MCP setup docs overhauled, allowlist cleaned up, model dispatch reads from config instead of hardcoding.

## What Shipped

- **MCP server fix** (PR#70): Replaced `@anthropic/codex-mcp-server` npm package references with the correct `codex mcp-server` CLI invocation across docs, agent files, workflow, and runtime code.
- **Docs overhaul and allowlist cleanup** (PR#72): Rewrote Codex MCP setup documentation. Cleaned up allowlist config. Workflow now reads role models from `allowlist.json` instead of hardcoding them.
- **Installer alignment** (PR#73): Aligned model-dispatch docs with installer coverage. Codex-led Claude bridge assets documented, validated, and shipped by manifest.

## Why It Matters

The Codex MCP integration went through rapid iteration. These three PRs stabilized the setup docs, fixed a wrong package name that would break new installs, and made model dispatch config-driven rather than scattered across prose.
