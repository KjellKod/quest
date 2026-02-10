#!/bin/bash
set -euo pipefail

# Quest SessionStart hook for Claude Code on the web
# Installs dependencies needed for Quest's dual-model review workflow
# Only runs in remote/web sandbox environments

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "=== Quest session-start: setting up web sandbox ==="

# --- OpenAI API Key ---
# If OPENAI_API_KEY is already set (e.g. from sandbox config), persist it for the session.
# Otherwise, check for a .env file at the project root.
if [ -n "${OPENAI_API_KEY:-}" ]; then
  echo "export OPENAI_API_KEY='${OPENAI_API_KEY}'" >> "$CLAUDE_ENV_FILE"
  echo "[session-start] OPENAI_API_KEY found in environment, persisted to session"
elif [ -f "${CLAUDE_PROJECT_DIR:-.}/.env" ]; then
  # Source .env and export OPENAI_API_KEY if present
  OPENAI_KEY=$(grep -E '^OPENAI_API_KEY=' "${CLAUDE_PROJECT_DIR:-.}/.env" 2>/dev/null | head -1 | cut -d'=' -f2- | tr -d "'\"" || true)
  if [ -n "$OPENAI_KEY" ]; then
    echo "export OPENAI_API_KEY='${OPENAI_KEY}'" >> "$CLAUDE_ENV_FILE"
    echo "[session-start] OPENAI_API_KEY loaded from .env"
  else
    echo "[session-start] WARNING: No OPENAI_API_KEY in .env — Codex MCP reviews will be skipped"
  fi
else
  echo "[session-start] WARNING: No OPENAI_API_KEY found — Codex MCP reviews will be skipped"
  echo "[session-start] Set OPENAI_API_KEY in environment or create .env at project root"
fi

# --- Python: openai package ---
if ! python3 -c "import openai" 2>/dev/null; then
  echo "[session-start] Installing openai Python package..."
  pip install --quiet openai 2>&1 | tail -1
  echo "[session-start] openai package installed"
else
  echo "[session-start] openai package already available"
fi

# --- Node.js: Codex MCP server ---
# Quest uses @anthropic/codex-mcp-server for dual-model (Claude + GPT) reviews
if ! command -v npx &>/dev/null; then
  echo "[session-start] WARNING: npx not available — cannot set up Codex MCP server"
  echo "[session-start] Install Node.js to enable dual-model reviews"
else
  echo "[session-start] npx available — Codex MCP server can be launched on demand"
fi

# --- Shellcheck (linter for shell scripts) ---
if ! command -v shellcheck &>/dev/null; then
  echo "[session-start] Installing shellcheck..."
  apt-get update -qq 2>/dev/null && apt-get install -y -qq shellcheck 2>/dev/null | tail -1 || echo "[session-start] WARNING: shellcheck install failed (non-fatal)"
  echo "[session-start] shellcheck installed"
else
  echo "[session-start] shellcheck already available"
fi

echo "=== Quest session-start: setup complete ==="
