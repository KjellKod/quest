# Installer Codex Setup and Bridge Timeout

- PRs: #78, #80
- Merged: 2026-03-20 to 2026-03-21
- Outcome: Installer handles Codex MCP setup; bridge timeout raised to 30 minutes.

## What Shipped

- **Installer Codex support** (PR#78): `quest_installer.sh` now offers Codex CLI and MCP server setup as part of the install flow. When the Codex probe fails at quest startup, the error message includes actionable fix commands instead of a generic failure.
- **Bridge timeout** (PR#80): Default subprocess timeout for the Claude bridge raised from 90 seconds to 30 minutes. Cross-reference comments added in both files where the default is defined, so future changes stay in sync.

## Why It Matters

90 seconds was too short for any non-trivial Claude role execution through the bridge. Builder roles routinely take 5-15 minutes. The installer change means new users get Codex MCP working out of the box instead of hitting a cryptic probe failure after install.
