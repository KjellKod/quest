#!/usr/bin/env bash
# Quest Preflight Check
# Probes second-model availability before quest routing.
# Called by SKILL.md Step 2b — output is JSON to stdout.
#
# Usage: scripts/quest_preflight.sh [--orchestrator claude|codex]
#
# Exit codes:
#   0 — second model available
#   1 — second model unavailable (warning in JSON output)
#   2 — usage error

set -euo pipefail

###############################################################################
# Defaults
###############################################################################

ORCHESTRATOR=""

###############################################################################
# Argument Parsing
###############################################################################

while [ $# -gt 0 ]; do
  case "$1" in
    --orchestrator)
      ORCHESTRATOR="${2:-}"
      shift 2
      ;;
    *)
      echo "Usage: quest_preflight.sh --orchestrator claude|codex" >&2
      exit 2
      ;;
  esac
done

if [ -z "$ORCHESTRATOR" ]; then
  echo "Usage: quest_preflight.sh --orchestrator claude|codex" >&2
  exit 2
fi

###############################################################################
# Auto-detect helpers
###############################################################################

json_bool() {
  if "$@" >/dev/null 2>&1; then echo "true"; else echo "false"; fi
}

has_cmd() {
  command -v "$1" >/dev/null 2>&1
}

###############################################################################
# Claude-led session: probe for Codex
###############################################################################

probe_codex() {
  local codex_cli_installed="false"
  local codex_mcp_registered="false"
  local openai_auth="false"
  local available="false"
  local warning=""

  # Check Codex CLI
  if has_cmd codex; then
    codex_cli_installed="true"
  fi

  # Check MCP registration (requires claude CLI)
  if has_cmd claude; then
    if claude mcp list 2>/dev/null | grep -q "codex-cli"; then
      codex_mcp_registered="true"
    fi
  fi

  # Check OpenAI auth
  if [ -n "${OPENAI_API_KEY:-}" ]; then
    openai_auth="true"
  elif [ -f ".env" ] && grep -q "OPENAI_API_KEY" ".env" 2>/dev/null; then
    openai_auth="true"
  fi

  # Determine overall availability
  if [ "$codex_cli_installed" = "true" ] && [ "$codex_mcp_registered" = "true" ]; then
    available="true"
  fi

  # Build warning if not available
  if [ "$available" = "false" ]; then
    local steps=""
    if [ "$codex_cli_installed" = "false" ]; then
      steps="npm i -g @openai/codex          # install Codex CLI\n"
    fi
    if [ "$openai_auth" = "false" ]; then
      steps="${steps}codex auth                       # login to OpenAI\n"
    fi
    if [ "$codex_mcp_registered" = "false" ]; then
      steps="${steps}claude mcp add --scope user codex-cli -- codex mcp-server\n"
    fi
    warning="Codex MCP not available — quest will run Claude-only (all roles).\nTo enable dual-model mode (Claude + Codex), run:\n  ${steps}Then restart this Claude Code session."
  fi

  cat <<EOJSON
{
  "orchestrator": "claude",
  "second_model": "codex",
  "available": ${available},
  "checks": {
    "codex_cli_installed": ${codex_cli_installed},
    "codex_mcp_registered": ${codex_mcp_registered},
    "openai_auth": ${openai_auth}
  },
  "warning": $(if [ -n "$warning" ]; then printf '%s' "$warning" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))'; else echo 'null'; fi)
}
EOJSON

  if [ "$available" = "true" ]; then
    return 0
  else
    return 1
  fi
}

###############################################################################
# Codex-led session: probe for Claude bridge
###############################################################################

probe_claude_bridge() {
  local claude_cli_installed="false"
  local bridge_script_exists="false"
  local bridge_reachable="false"
  local available="false"
  local warning=""

  # Check Claude CLI
  if has_cmd claude; then
    claude_cli_installed="true"
  fi

  # Check bridge script
  if [ -f "scripts/claude_cli_bridge.py" ]; then
    bridge_script_exists="true"
  fi

  # Run the real probe if both exist
  if [ "$claude_cli_installed" = "true" ] && [ "$bridge_script_exists" = "true" ]; then
    local probe_dir=".quest/_preflight_probe"
    mkdir -p "$probe_dir"
    if python3 scripts/quest_claude_probe.py --quest-dir "$probe_dir" --model opus >/dev/null 2>&1; then
      bridge_reachable="true"
      available="true"
    fi
    rm -rf "$probe_dir"
  fi

  # Build warning if not available
  if [ "$available" = "false" ]; then
    local steps=""
    if [ "$claude_cli_installed" = "false" ]; then
      steps="Install Claude CLI: npm i -g @anthropic-ai/claude-code\n  "
    fi
    steps="${steps}Authenticate: claude auth"
    warning="Claude bridge not available — quest will run Codex-only (all roles).\nEnsure Claude CLI is installed and authenticated:\n  ${steps}"
  fi

  cat <<EOJSON
{
  "orchestrator": "codex",
  "second_model": "claude",
  "available": ${available},
  "checks": {
    "claude_cli_installed": ${claude_cli_installed},
    "bridge_script_exists": ${bridge_script_exists},
    "bridge_reachable": ${bridge_reachable}
  },
  "warning": $(if [ -n "$warning" ]; then printf '%s' "$warning" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))'; else echo 'null'; fi)
}
EOJSON

  if [ "$available" = "true" ]; then
    return 0
  else
    return 1
  fi
}

###############################################################################
# Main
###############################################################################

case "$ORCHESTRATOR" in
  claude)
    probe_codex
    ;;
  codex)
    probe_claude_bridge
    ;;
  *)
    echo "Unknown orchestrator: $ORCHESTRATOR (expected: claude or codex)" >&2
    exit 2
    ;;
esac
