#!/bin/bash
set -uo pipefail

# Quest SessionStart hook for Claude Code on the web.
# Keep startup deterministic: perform non-fatal checks only.

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

# Codex authentication is selected by Quest preflight, never inferred from a key.
# Do not scrape .env or persist credentials during startup.
if command -v codex >/dev/null 2>&1; then
  log "Codex CLI found. Quest uses scripts/quest_codex_runner.py for Claude-to-Codex tasks."
  log "Prefer codex login (ChatGPT). Preflight verifies the selected cached or explicit api-key mode."
else
  warn "Codex CLI not found. Install Codex CLI before selecting Codex-backed roles."
fi

# --- GitHub CLI (gh) ---
if command -v gh >/dev/null 2>&1; then
  log "gh CLI already available"
else
  warn "gh CLI not available — PR shepherd will be limited"
fi

# --- Shellcheck (linter for shell scripts) ---
if command -v shellcheck >/dev/null 2>&1; then
  log "shellcheck already available"
else
  warn "shellcheck not available (optional)"
fi

echo "=== Quest session-start: setup complete ==="
