#!/usr/bin/env bash
# Quest Preflight Check
# Probes second-model availability before quest routing.
# Called by SKILL.md Step 2b — output is JSON to stdout.
#
# Usage: scripts/quest_preflight.sh [--orchestrator claude|codex]
#
# Exit codes:
#   0 — probe completed (check JSON "available" field for result)
#   1 — probe runtime error (script itself failed)
#   2 — usage error

set -euo pipefail

###############################################################################
# Defaults
###############################################################################

ORCHESTRATOR=""
CACHE_TTL_SECONDS="${QUEST_PREFLIGHT_CACHE_TTL_SECONDS:-43200}"
case "$CACHE_TTL_SECONDS" in
  ''|*[!0-9]*) CACHE_TTL_SECONDS=43200 ;;  # fallback on non-integer input
esac
CLAUDE_BRIDGE_SCRIPT="${QUEST_CLAUDE_BRIDGE_SCRIPT:-scripts/quest_claude_bridge.py}"
CLAUDE_BRIDGE_CACHE_FILE="${QUEST_PREFLIGHT_CACHE_FILE:-.quest/cache/claude_bridge_codex.json}"

###############################################################################
# Argument Parsing
###############################################################################

while [ $# -gt 0 ]; do
  case "$1" in
    --orchestrator)
      if [ $# -lt 2 ] || [ -z "$2" ]; then
        echo "Usage: quest_preflight.sh --orchestrator claude|codex" >&2
        exit 2
      fi
      ORCHESTRATOR="$2"
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

json_get() {
  local field="$1"
  python3 -c '
import json
import sys

field = sys.argv[1]

try:
    value = json.load(sys.stdin)
except Exception:
    sys.exit(1)

for part in field.split("."):
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = None
        break

if isinstance(value, bool):
    print("true" if value else "false")
elif value is None:
    print("")
else:
    print(str(value))
' "$field"
}

json_quote_or_null() {
  local value="${1:-}"
  if [ -z "$value" ]; then
    echo "null"
    return 0
  fi
  python3 -c 'import json, sys; print(json.dumps(sys.argv[1], ensure_ascii=True))' "$value"
}

load_success_cache() {
  local cache_file="$1"
  local ttl_seconds="$2"
  python3 - "$cache_file" "$ttl_seconds" <<'PY'
import json
import sys
import time
from pathlib import Path

cache_file = Path(sys.argv[1])
ttl_seconds = int(sys.argv[2])
if ttl_seconds <= 0 or not cache_file.exists():
    raise SystemExit(1)

try:
    wrapper = json.loads(cache_file.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    raise SystemExit(1)

cached_at_epoch = wrapper.get("cached_at_epoch")
payload = wrapper.get("payload")
if not isinstance(cached_at_epoch, int) or not isinstance(payload, dict):
    raise SystemExit(1)
if payload.get("available") is not True:
    raise SystemExit(1)

if int(time.time()) > cached_at_epoch + ttl_seconds:
    raise SystemExit(1)

print(json.dumps(wrapper, ensure_ascii=True))
PY
}

write_success_cache() {
  local cache_file="$1"
  local ttl_seconds="$2"
  local payload_json="$3"
  [ "$ttl_seconds" -gt 0 ] || return 0
  python3 - "$cache_file" "$ttl_seconds" "$payload_json" <<'PY'
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

cache_file = Path(sys.argv[1])
ttl_seconds = int(sys.argv[2])
payload = json.loads(sys.argv[3])
now = int(time.time())
wrapper = {
    "cached_at": datetime.fromtimestamp(now, timezone.utc).isoformat().replace("+00:00", "Z"),
    "cached_at_epoch": now,
    "expires_at": datetime.fromtimestamp(now + ttl_seconds, timezone.utc).isoformat().replace("+00:00", "Z"),
    "ttl_seconds": ttl_seconds,
    "payload": payload,
}
cache_file.parent.mkdir(parents=True, exist_ok=True)
cache_file.write_text(json.dumps(wrapper, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
PY
}

cache_fallback_allowed() {
  local auth_logged_in="$1"
  local probe_result_kind="$2"
  local probe_message="$3"

  if [ "$auth_logged_in" = "false" ]; then
    return 0
  fi

  if [ -n "$probe_message" ] && printf '%s' "$probe_message" | grep -Fq "Not logged in"; then
    return 0
  fi

  if [ "$probe_result_kind" = "timeout" ]; then
    return 0
  fi

  return 1
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

  # Build warning lines if not available
  local warning_lines=""
  if [ "$available" = "false" ]; then
    warning_lines="    \"Codex MCP not available -- quest will run Claude-only (all roles).\",\n"
    warning_lines="${warning_lines}    \"To enable dual-model mode (Claude + Codex), run:\",\n"
    if [ "$codex_cli_installed" = "false" ]; then
      warning_lines="${warning_lines}    \"  npm i -g @openai/codex          # install Codex CLI\",\n"
    fi
    if [ "$openai_auth" = "false" ]; then
      warning_lines="${warning_lines}    \"  codex auth                       # login to OpenAI\",\n"
    fi
    if [ "$codex_mcp_registered" = "false" ]; then
      warning_lines="${warning_lines}    \"  claude mcp add --scope user codex-cli -- codex mcp-server\",\n"
    fi
    warning_lines="${warning_lines}    \"Then restart this Claude Code session.\""
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
  "warning": $(if [ -n "$warning_lines" ]; then printf '[\n%b\n  ]' "$warning_lines"; else echo 'null'; fi)
}
EOJSON

  return 0
}

###############################################################################
# Codex-led session: probe for Claude bridge
###############################################################################

probe_claude_bridge() {
  local claude_cli_installed="false"
  local claude_auth_logged_in="false"
  local bridge_script_exists="false"
  local bridge_reachable="false"
  local cache_hit="false"
  local available="false"
  local source="live_probe"
  local probe_result_kind=""
  local probe_message=""
  local cache_cached_at=""
  local cache_expires_at=""
  local runtime_requirement="host_context"

  # Check Claude CLI
  if has_cmd claude; then
    claude_cli_installed="true"
    local auth_status
    auth_status=$(claude auth status 2>/dev/null || true)
    if [ -n "$auth_status" ]; then
      if [ "$(printf '%s' "$auth_status" | json_get "loggedIn" 2>/dev/null || echo "false")" = "true" ]; then
        claude_auth_logged_in="true"
      fi
    fi
  fi

  # Check bridge script
  if [ -f "$CLAUDE_BRIDGE_SCRIPT" ]; then
    bridge_script_exists="true"
  fi

  # Run the real probe if both exist
  if [ "$claude_cli_installed" = "true" ] && [ "$bridge_script_exists" = "true" ]; then
    local probe_dir
    local probe_json=""
    local probe_exit_code=""
    local probe_stdout=""
    local probe_stderr=""
    probe_dir=$(mktemp -d 2>/dev/null || mktemp -d -t quest_preflight)
    probe_json=$(python3 scripts/quest_claude_probe.py --quest-dir "$probe_dir" --model opus --bridge-script "$CLAUDE_BRIDGE_SCRIPT" 2>/dev/null || true)
    if [ -n "$probe_json" ]; then
      probe_exit_code=$(printf '%s' "$probe_json" | json_get "exit_code" 2>/dev/null || true)
      probe_result_kind=$(printf '%s' "$probe_json" | json_get "result_kind" 2>/dev/null || true)
      probe_stdout=$(printf '%s' "$probe_json" | json_get "stdout" 2>/dev/null || true)
      probe_stderr=$(printf '%s' "$probe_json" | json_get "stderr" 2>/dev/null || true)
    fi
    if [ "${probe_exit_code:-1}" = "0" ]; then
      bridge_reachable="true"
      available="true"
    elif [ -n "$probe_stdout" ]; then
      probe_message="$probe_stdout"
    elif [ -n "$probe_stderr" ]; then
      probe_message="$probe_stderr"
    fi
    rm -rf "$probe_dir"
  fi

  if [ "$available" = "false" ] &&
     [ "$claude_cli_installed" = "true" ] &&
     [ "$bridge_script_exists" = "true" ] &&
     cache_fallback_allowed "$claude_auth_logged_in" "$probe_result_kind" "$probe_message"; then
    local cache_json=""
    cache_json=$(load_success_cache "$CLAUDE_BRIDGE_CACHE_FILE" "$CACHE_TTL_SECONDS" 2>/dev/null || true)
    if [ -n "$cache_json" ]; then
      cache_hit="true"
      source="success_cache"
      available="true"
      bridge_reachable="true"
      cache_cached_at=$(printf '%s' "$cache_json" | json_get "cached_at" 2>/dev/null || true)
      cache_expires_at=$(printf '%s' "$cache_json" | json_get "expires_at" 2>/dev/null || true)
    fi
  fi

  # Build warning lines if not available
  local warning_lines=""
  if [ "$available" = "false" ]; then
    warning_lines="    \"Claude bridge not available -- quest will run Codex-only (all roles).\",\n"
    warning_lines="${warning_lines}    \"Ensure Claude CLI is installed and authenticated in a normal shell:\",\n"
    if [ "$claude_cli_installed" = "false" ]; then
      warning_lines="${warning_lines}    \"  npm i -g @anthropic-ai/claude-code  # install Claude CLI\",\n"
    fi
    if [ "$claude_auth_logged_in" = "false" ]; then
      warning_lines="${warning_lines}    \"  claude auth login                    # opens browser sign-in\",\n"
      warning_lines="${warning_lines}    \"  claude auth status                   # verify the CLI sees your session\",\n"
    fi
    if [ -n "$probe_message" ] && printf '%s' "$probe_message" | grep -Fq "Not logged in"; then
      warning_lines="${warning_lines}    \"  Claude CLI reported that it is not logged in.\",\n"
    elif [ -n "$probe_result_kind" ]; then
      warning_lines="${warning_lines}    \"  Probe result: ${probe_result_kind}\",\n"
    fi
    warning_lines="${warning_lines}    \"  If browser login already succeeded, rerun this preflight outside a restricted sandbox to refresh the retained host probe cache; some sandboxes cannot read Claude CLI auth state.\""
  fi

  local payload
  payload=$(cat <<EOJSON
{
  "orchestrator": "codex",
  "second_model": "claude",
  "source": $(json_quote_or_null "$source"),
  "runtime_requirement": $(json_quote_or_null "$runtime_requirement"),
  "available": ${available},
  "checks": {
    "claude_cli_installed": ${claude_cli_installed},
    "claude_auth_logged_in": ${claude_auth_logged_in},
    "bridge_script_exists": ${bridge_script_exists},
    "bridge_reachable": ${bridge_reachable},
    "cache_hit": ${cache_hit}
  },
  "cache": {
    "path": $(json_quote_or_null "$CLAUDE_BRIDGE_CACHE_FILE"),
    "ttl_seconds": ${CACHE_TTL_SECONDS},
    "cached_at": $(json_quote_or_null "$cache_cached_at"),
    "expires_at": $(json_quote_or_null "$cache_expires_at")
  },
  "diagnostic": {
    "probe_result_kind": $(json_quote_or_null "$probe_result_kind"),
    "probe_message": $(json_quote_or_null "$probe_message")
  },
  "warning": $(if [ -n "$warning_lines" ]; then printf '[\n%b\n  ]' "$warning_lines"; else echo 'null'; fi)
}
EOJSON
)

  if [ "$source" = "live_probe" ] && [ "$available" = "true" ]; then
    write_success_cache "$CLAUDE_BRIDGE_CACHE_FILE" "$CACHE_TTL_SECONDS" "$payload"
  fi

  printf '%s\n' "$payload"

  return 0
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
