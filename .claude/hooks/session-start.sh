#!/bin/bash
set -uo pipefail

# Quest SessionStart hook for Claude Code on the web.
# Keep startup deterministic: persist env state and perform non-fatal checks only.

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo "=== Quest session-start: setting up web sandbox ==="

log() {
  echo "[session-start] $*"
}

warn() {
  echo "[session-start] WARNING: $*"
}

persist_openai_key() {
  local key="$1"
  local env_file="${CLAUDE_ENV_FILE:-}"

  if [ -z "$env_file" ]; then
    warn "CLAUDE_ENV_FILE is not set — OPENAI_API_KEY not persisted"
    return 0
  fi

  if ! touch "$env_file" 2>/dev/null; then
    warn "Cannot write $env_file — OPENAI_API_KEY not persisted"
    return 0
  fi

  printf "export OPENAI_API_KEY=%q\n" "$key" >> "$env_file" || warn "Failed to append OPENAI_API_KEY to $env_file"
}

read_openai_key_from_dotenv() {
  local env_path="$1"
  local line

  line=$(grep -m1 -E '^[[:space:]]*OPENAI_API_KEY=' "$env_path" 2>/dev/null || true)
  if [ -z "$line" ]; then
    return 1
  fi

  line="${line#*=}"
  line=$(printf '%s' "$line" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

  if [ "${line#\"}" != "$line" ] && [ "${line%\"}" != "$line" ]; then
    line="${line#\"}"
    line="${line%\"}"
  elif [ "${line#\'}" != "$line" ] && [ "${line%\'}" != "$line" ]; then
    line="${line#\'}"
    line="${line%\'}"
  fi

  if [ -z "$line" ]; then
    return 1
  fi

  printf '%s' "$line"
}

# --- OpenAI API Key ---
# If OPENAI_API_KEY is already set (e.g. from sandbox config), persist it for the session.
# Otherwise, check for a .env file at the project root.
if [ -n "${OPENAI_API_KEY:-}" ]; then
  persist_openai_key "${OPENAI_API_KEY}"
  log "OPENAI_API_KEY found in environment, persisted to session"
elif [ -f "${CLAUDE_PROJECT_DIR:-.}/.env" ]; then
  OPENAI_KEY=$(read_openai_key_from_dotenv "${CLAUDE_PROJECT_DIR:-.}/.env" || true)
  if [ -n "$OPENAI_KEY" ]; then
    persist_openai_key "${OPENAI_KEY}"
    log "OPENAI_API_KEY loaded from .env"
  else
    warn "No OPENAI_API_KEY in .env — Codex MCP reviews will be skipped"
  fi
else
  warn "No OPENAI_API_KEY found — Codex MCP reviews will be skipped"
  log "Set OPENAI_API_KEY in environment or create .env at project root"
fi

# --- Codex MCP server ---
if command -v codex >/dev/null 2>&1; then
  log "codex CLI available — Codex MCP server can be launched on demand"
else
  warn "codex CLI not found — Codex MCP server will be unavailable"
fi

# --- Shellcheck (linter for shell scripts) ---
if command -v shellcheck >/dev/null 2>&1; then
  log "shellcheck already available"
else
  warn "shellcheck not available (optional)"
fi

echo "=== Quest session-start: setup complete ==="
