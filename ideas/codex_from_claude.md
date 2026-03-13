in a memory filr from claude

⏺ ---
  name: Codex CLI for cross-model reviews
  description: How to call OpenAI Codex (GPT-5.4) from Claude Code via codex exec CLI for multi-model PR reviews
  type: reference
  ---

  ## Calling Codex from Claude Code

  Codex CLI is installed at `/Users/kjell/.nvm/versions/node/v22.17.0/bin/codex` (v0.112.0+).

  ### MCP Server
  Configured in `.claude/mcp.json` as `codex` → `codex mcp-server`. However, the MCP tools may not always be discoverable via
  ToolSearch. Fallback to CLI.

  ### CLI Usage (preferred for reviews)
  ```bash
  codex exec --sandbox read-only -o /tmp/output.txt "Your prompt here"

  - --sandbox read-only for review tasks (no writes needed)
  - -o <file> captures the last agent message to a file
  - Default model is gpt-5.4
  - Use -m <model> to override
  - Timeout may need to be generous (300s+) for thorough reviews
  - Codex will use its own MCP servers (datadog, google sheets) if configured in ~/.codex/

  Multi-model PR review pattern

  Launch Claude sub-agents (via Agent tool) in parallel for different review angles, then call codex exec for a GPT-5.4 perspective.
   Synthesize all findings before presenting to user.
  ```


