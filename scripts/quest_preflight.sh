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

# Resolve THIS script's real directory so helper scripts are found regardless of
# the caller's cwd. Quest may be installed outside the target repo and invoked by
# absolute path; helper paths must not resolve under the project's (often absent)
# scripts/ dir. Symlink-safe: macOS lacks `readlink -f`, so prefer python3
# (already a hard dependency) and fall back to `pwd -P`.
if ! SCRIPT_DIR="$(python3 -c 'import os,sys; print(os.path.dirname(os.path.realpath(sys.argv[1])))' "${BASH_SOURCE[0]}" 2>/dev/null)"; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
fi

# Helper scripts: default next to this script (env overrides win). Absolute.
CLAUDE_BRIDGE_SCRIPT="${QUEST_CLAUDE_BRIDGE_SCRIPT:-$SCRIPT_DIR/quest_claude_bridge.py}"
CLAUDE_BG_RUNNER_SCRIPT="${QUEST_CLAUDE_BG_RUNNER_SCRIPT:-$SCRIPT_DIR/claude_bg_run.py}"
CLAUDE_PROBE_SCRIPT="${QUEST_CLAUDE_PROBE_SCRIPT:-$SCRIPT_DIR/quest_claude_probe.py}"
# Project state stays cwd-relative on purpose (it lives in the target repo).
CLAUDE_BRIDGE_CACHE_FILE="${QUEST_PREFLIGHT_CACHE_FILE:-.quest/cache/claude_bridge_codex.json}"
CLAUDE_BG_CACHE_FILE="${QUEST_PREFLIGHT_BG_CACHE_FILE:-.quest/cache/claude_bg_codex.json}"
ALLOWLIST_FILE="${QUEST_ALLOWLIST_FILE:-.ai/allowlist.json}"
CLAUDE_PROBE_MODEL="${QUEST_CLAUDE_PROBE_MODEL:-claude}"
CURRENT_BG_PROBE_NAME=""

cleanup_bg_probes() {
  [ -f "$CLAUDE_BG_RUNNER_SCRIPT" ] || return 0
  # Sweep ONLY this preflight's own probe: a broad quest-bg-probe- sweep here
  # would kill a concurrent preflight's active probe and falsely fail its
  # transport check. The broad stale-probe sweep is owned by quest
  # start/resume (workflow.md), not by every preflight exit.
  if [ -n "$CURRENT_BG_PROBE_NAME" ]; then
    # Our own probe session: include active rows (a mid-probe session is ours
    # to stop). Only an unrecognized-flag error (overridden older runner)
    # falls back to a plain sweep; any REAL failure is surfaced on stderr
    # (stdout carries the preflight JSON payload) with the manual command.
    # The manual command in warnings must match the variant this runner
    # actually supports — recommending --sweep-include-active to an older
    # runner that just rejected it would fail the operator too.
    local sweep_out manual_cmd
    manual_cmd="python3 \"$CLAUDE_BG_RUNNER_SCRIPT\" --sweep \"$CURRENT_BG_PROBE_NAME\" --sweep-include-active"
    if ! sweep_out=$(python3 "$CLAUDE_BG_RUNNER_SCRIPT" --sweep "$CURRENT_BG_PROBE_NAME" --sweep-include-active 2>&1); then
      if printf '%s' "$sweep_out" | grep -qi "unrecognized arguments"; then
        manual_cmd="python3 \"$CLAUDE_BG_RUNNER_SCRIPT\" --sweep \"$CURRENT_BG_PROBE_NAME\""
        sweep_out=$(python3 "$CLAUDE_BG_RUNNER_SCRIPT" --sweep "$CURRENT_BG_PROBE_NAME" 2>&1) \
          || echo "WARNING: preflight probe sweep failed; stop it manually: $manual_cmd" >&2
      else
        echo "WARNING: preflight probe sweep failed; stop it manually: $manual_cmd" >&2
      fi
    fi
    # Exit 0 with "sweep skipped:" (CLI/roster unavailable) is also
    # UNVERIFIED cleanup — same honesty rule as everywhere else.
    case "$sweep_out" in
      *"sweep skipped:"*)
        echo "WARNING: preflight probe sweep could not be verified; stop it manually: $manual_cmd" >&2 ;;
    esac
  fi
}

# EXIT handles the normal path; INT/TERM must actually terminate (a bare
# function trap can let bash resume after cleanup, swallowing Ctrl-C/CI kill).
trap cleanup_bg_probes EXIT
trap 'cleanup_bg_probes; trap - EXIT; exit 130' INT
trap 'cleanup_bg_probes; trap - EXIT; exit 143' TERM

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
# Codex-led session: probe for the Claude transports
#
# Policy (consumed from .ai/allowlist.json claude_role_transport, default auto;
# config drives scripts — agent prose never picks the transport):
#   auto             → probe background-agent; if it fails, block and prompt
#   background-agent → forced: bg probe only, no silent bridge fallback
#   bridge           → explicit legacy/API path, bg probe skipped
###############################################################################

configured_claude_transport() {
  # Echo the raw configured value (empty when the key is absent). Validation —
  # including failing closed on a present-but-invalid value — happens in
  # probe_claude_transport so a typo can never be silently coerced to a default.
  local value=""
  if [ -n "${QUEST_CLAUDE_ROLE_TRANSPORT:-}" ]; then
    value="$QUEST_CLAUDE_ROLE_TRANSPORT"
  elif [ -f "$ALLOWLIST_FILE" ]; then
    value=$(json_get "claude_role_transport" < "$ALLOWLIST_FILE" 2>/dev/null || true)
  fi
  printf '%s' "$value"
}

# Emit an available:false payload for a present-but-invalid claude_role_transport
# (config error). Fails closed with a diagnostic instead of probing/downgrading.
emit_invalid_transport_payload() {
  local configured="$1"
  # Build the warning sentences (with the raw value embedded) as plain strings,
  # then JSON-encode each via json_quote_or_null so a value containing a quote,
  # backslash, or newline cannot break the payload the fail-closed path emits.
  local warn1 warn2
  warn1="Invalid claude_role_transport '${configured}' in .ai/allowlist.json -- expected auto, background-agent, or bridge."
  warn2="Fix or remove the key; preflight will not coerce an invalid transport to a default (it could resume under a different billing path)."
  cat <<EOJSON
{
  "orchestrator": "codex",
  "second_model": "claude",
  "transport": $(json_quote_or_null "$configured"),
  "transport_downgraded": false,
  "source": "config",
  "runtime_requirement": null,
  "available": false,
  "checks": {
    "config_valid": false
  },
  "diagnostic": {
    "probe_result_kind": "invalid_transport_config",
    "probe_message": $(json_quote_or_null "claude_role_transport='${configured}' is not one of auto|background-agent|bridge")
  },
  "warning": [
    $(json_quote_or_null "$warn1"),
    $(json_quote_or_null "$warn2")
  ]
}
EOJSON
}

# Sets CLAUDE_CLI_INSTALLED / CLAUDE_AUTH_LOGGED_IN globals (shared by probes).
detect_claude_cli() {
  CLAUDE_CLI_INSTALLED="false"
  CLAUDE_AUTH_LOGGED_IN="false"
  if has_cmd claude; then
    CLAUDE_CLI_INSTALLED="true"
    local auth_status
    auth_status=$(claude auth status 2>/dev/null || true)
    if [ -n "$auth_status" ]; then
      if [ "$(printf '%s' "$auth_status" | json_get "loggedIn" 2>/dev/null || echo "false")" = "true" ]; then
        CLAUDE_AUTH_LOGGED_IN="true"
      fi
    fi
  fi
}

probe_claude_bg() {
  local claude_cli_installed="false"
  local claude_auth_logged_in="false"
  local bg_runner_script_exists="false"
  local agents_json_ok="false"
  local bg_reachable="false"
  local cache_hit="false"
  local available="false"
  local source="live_probe"
  local probe_result_kind=""
  local probe_message=""
  local cache_cached_at=""
  local cache_expires_at=""
  local runtime_requirement="host_context"

  detect_claude_cli
  claude_cli_installed="$CLAUDE_CLI_INSTALLED"
  claude_auth_logged_in="$CLAUDE_AUTH_LOGGED_IN"

  if [ -f "$CLAUDE_BG_RUNNER_SCRIPT" ]; then
    bg_runner_script_exists="true"
  fi

  # Background sessions need a CLI whose `agents --json` speaks JSON (older
  # CLIs print a non-JSON subagent listing — bg transport unsupported there).
  if [ "$claude_cli_installed" = "true" ]; then
    if claude agents --json 2>/dev/null | python3 -c '
import json, sys
data = json.load(sys.stdin)
raise SystemExit(0 if isinstance(data, list) else 1)
' 2>/dev/null; then
      agents_json_ok="true"
    fi
  fi

  if [ "$claude_cli_installed" = "true" ] &&
     [ "$bg_runner_script_exists" = "true" ] &&
     [ "$agents_json_ok" = "true" ]; then
    local probe_dir
    local probe_json=""
    local probe_exit_code=""
    local probe_stdout=""
    local probe_stderr=""
    probe_dir=$(mktemp -d 2>/dev/null || mktemp -d -t quest_preflight)
    if [ ! -f "$CLAUDE_PROBE_SCRIPT" ]; then
      probe_result_kind="preflight_invocation_error"
      probe_message="quest_claude_probe.py not found at $CLAUDE_PROBE_SCRIPT"
      probe_json=""
    else
      CURRENT_BG_PROBE_NAME="quest-bg-probe-$(basename "$probe_dir")"
      cleanup_bg_probes
      probe_json=$(python3 "$CLAUDE_PROBE_SCRIPT" --quest-dir "$probe_dir" --model "$CLAUDE_PROBE_MODEL" --transport background-agent --bg-runner-script "$CLAUDE_BG_RUNNER_SCRIPT" 2>/dev/null || true)
    fi
    if [ -n "$probe_json" ]; then
      probe_exit_code=$(printf '%s' "$probe_json" | json_get "exit_code" 2>/dev/null || true)
      probe_result_kind=$(printf '%s' "$probe_json" | json_get "result_kind" 2>/dev/null || true)
      probe_stdout=$(printf '%s' "$probe_json" | json_get "stdout" 2>/dev/null || true)
      probe_stderr=$(printf '%s' "$probe_json" | json_get "stderr" 2>/dev/null || true)
    fi
    if [ "${probe_exit_code:-1}" = "0" ]; then
      bg_reachable="true"
      available="true"
    elif [ -n "$probe_stderr" ]; then
      probe_message="$probe_stderr"
    elif [ -n "$probe_stdout" ]; then
      probe_message="$probe_stdout"
    fi
    rm -rf "$probe_dir"
  fi

  if [ "$available" = "false" ] &&
     [ "$claude_cli_installed" = "true" ] &&
     [ "$bg_runner_script_exists" = "true" ] &&
     [ "$agents_json_ok" = "true" ] &&
     cache_fallback_allowed "$claude_auth_logged_in" "$probe_result_kind" "$probe_message"; then
    local cache_json=""
    cache_json=$(load_success_cache "$CLAUDE_BG_CACHE_FILE" "$CACHE_TTL_SECONDS" 2>/dev/null || true)
    if [ -n "$cache_json" ]; then
      cache_hit="true"
      source="success_cache"
      available="true"
      bg_reachable="true"
      cache_cached_at=$(printf '%s' "$cache_json" | json_get "cached_at" 2>/dev/null || true)
      cache_expires_at=$(printf '%s' "$cache_json" | json_get "expires_at" 2>/dev/null || true)
    fi
  fi

  local warning_lines=""
  if [ "$available" = "false" ]; then
    warning_lines="    \"Background-agent transport not available for Claude roles.\",\n"
    if [ "$claude_cli_installed" = "false" ]; then
      warning_lines="${warning_lines}    \"  npm i -g @anthropic-ai/claude-code  # install Claude CLI\",\n"
    fi
    if [ "$claude_auth_logged_in" = "false" ]; then
      warning_lines="${warning_lines}    \"  claude login                         # subscription sign-in\",\n"
    fi
    if [ "$agents_json_ok" = "false" ] && [ "$claude_cli_installed" = "true" ]; then
      warning_lines="${warning_lines}    \"  claude agents --json did not return JSON — update the Claude CLI (>= 2.1.143).\",\n"
    fi
    if [ "$probe_result_kind" = "bypass_not_accepted" ]; then
      warning_lines="${warning_lines}    \"  Background running of Claude failed because bypassPermissions has not been accepted for background sessions.\",\n"
      warning_lines="${warning_lines}    \"  Run: claude --dangerously-skip-permissions\",\n"
      warning_lines="${warning_lines}    \"  Accept the prompt, exit Claude, then return here and rerun Quest; Quest will retry the bg probe.\",\n"
    elif [ "$probe_result_kind" = "startup_dialog" ]; then
      warning_lines="${warning_lines}    \"  Claude background session blocked on a startup trust/bypass dialog before consuming the prompt.\",\n"
      warning_lines="${warning_lines}    \"  Open Claude interactively in the target cwd, accept trust/bypass prompts, exit Claude, then rerun Quest.\",\n"
    elif [ "$probe_result_kind" = "rate_limited" ]; then
      warning_lines="${warning_lines}    \"  Claude reported a session/rate limit. This is transient, NOT a setup problem: wait for the reset time shown by Claude, then rerun Quest — or ask whether to choose another configured Claude model.\",\n"
    elif [ "$probe_result_kind" = "model_rejected" ]; then
      warning_lines="${warning_lines}    \"  Claude rejected the configured probe model. Set the model to the literal value claude (account default) or a concrete supported model, in .ai/allowlist.json models.* or the per-quest chooser.\",\n"
    elif [ "$probe_result_kind" = "bg_initial_prompt_not_consumed" ]; then
      warning_lines="${warning_lines}    \"  Claude background session registered but did not consume the initial prompt (Claude CLI reported: send a prompt to start).\",\n"
      warning_lines="${warning_lines}    \"  Quest sends bg prompts on stdin (required since Claude Code 2.1.191); this indicates a remaining bg prompt-delivery regression.\",\n"
      warning_lines="${warning_lines}    \"  Use claude_role_transport=bridge only if you explicitly accept API-metered bridge billing for this run.\",\n"
    elif [ "$probe_result_kind" = "hook_startup_failed" ]; then
      warning_lines="${warning_lines}    \"  Claude startup hook failed. Check .claude/hooks permissions, especially executable bits, then rerun Quest.\",\n"
    elif [ "$probe_result_kind" = "invocation_error" ]; then
      warning_lines="${warning_lines}    \"  Background dispatch failed. If bypass mode has never been accepted, run claude --dangerously-skip-permissions once interactively and accept.\",\n"
    elif [ -n "$probe_result_kind" ]; then
      warning_lines="${warning_lines}    \"  Probe result: ${probe_result_kind}\",\n"
    fi
    if [ "$probe_result_kind" = "rate_limited" ]; then
      # A transient limit is not a setup/config problem: appending machine-setup
      # and switch-to-bridge boilerplate here misdirects the human toward
      # API-metered billing for something that clears on its own.
      warning_lines="${warning_lines}    \"  (Switching to the API-metered bridge is NOT needed for a rate limit; it clears at the reset time.)\""
    else
      warning_lines="${warning_lines}    \"  To use the API-metered bridge instead, make it explicit: set claude_role_transport to bridge for this run.\",\n"
      warning_lines="${warning_lines}    \"  See docs/guides/quest_setup.md for the one-time machine setup.\""
    fi
  fi

  local payload
  payload=$(cat <<EOJSON
{
  "orchestrator": "codex",
  "second_model": "claude",
  "transport": "background-agent",
  "transport_downgraded": false,
  "source": $(json_quote_or_null "$source"),
  "runtime_requirement": $(json_quote_or_null "$runtime_requirement"),
  "available": ${available},
  "checks": {
    "claude_cli_installed": ${claude_cli_installed},
    "claude_auth_logged_in": ${claude_auth_logged_in},
    "bg_runner_script_exists": ${bg_runner_script_exists},
    "agents_json_ok": ${agents_json_ok},
    "bg_reachable": ${bg_reachable},
    "cache_hit": ${cache_hit}
  },
  "cache": {
    "path": $(json_quote_or_null "$CLAUDE_BG_CACHE_FILE"),
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
    write_success_cache "$CLAUDE_BG_CACHE_FILE" "$CACHE_TTL_SECONDS" "$payload"
  fi

  printf '%s\n' "$payload"

  return 0
}

probe_claude_bridge() {
  # Explicit bridge probe. Auto-mode bg failures no longer call this path.
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

  detect_claude_cli
  claude_cli_installed="$CLAUDE_CLI_INSTALLED"
  claude_auth_logged_in="$CLAUDE_AUTH_LOGGED_IN"

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
    if [ ! -f "$CLAUDE_PROBE_SCRIPT" ]; then
      probe_result_kind="preflight_invocation_error"
      probe_message="quest_claude_probe.py not found at $CLAUDE_PROBE_SCRIPT"
      probe_json=""
    else
      probe_json=$(python3 "$CLAUDE_PROBE_SCRIPT" --quest-dir "$probe_dir" --model "$CLAUDE_PROBE_MODEL" --bridge-script "$CLAUDE_BRIDGE_SCRIPT" 2>/dev/null || true)
    fi
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

  # Build warning lines for the explicit bridge path.
  local warning_lines=""
  if [ "$available" = "false" ]; then
    warning_lines="${warning_lines}    \"Claude bridge not available -- quest will run Codex-only (all roles).\",\n"
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
    elif [ "$probe_result_kind" = "artifact_missing" ]; then
      warning_lines="${warning_lines}    \"  Claude responded (probe handoff written) but the probe ARTIFACT was not written — the transport is reachable; the failure is a filesystem write.\",\n"
      warning_lines="${warning_lines}    \"  Check write permissions/sandbox access for the quest logs probe directory, then rerun preflight.\",\n"
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
  "transport": "bridge",
  "transport_downgraded": false,
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

probe_claude_transport() {
  local configured
  configured=$(configured_claude_transport)

  case "$configured" in
    ""|auto)
      : # absent/empty or explicit auto → the auto path below
      ;;
    bridge)
      probe_claude_bridge
      return 0
      ;;
    background-agent)
      # Forced: no silent bridge fallback — an unavailable bg transport blocks
      # with remediation in the payload warning.
      probe_claude_bg
      return 0
      ;;
    *)
      # Present but invalid: fail closed with a config diagnostic. Never coerce a
      # typo to auto — that could silently pick a different billing path.
      emit_invalid_transport_payload "$configured"
      return 0
      ;;
  esac

  # auto: background-agent first. A failed bg probe is a user-visible decision
  # point, not implicit consent to the API-metered bridge.
  local bg_payload
  bg_payload=$(probe_claude_bg)
  if [ "$(printf '%s' "$bg_payload" | json_get "available" 2>/dev/null || echo "false")" = "true" ]; then
    printf '%s\n' "$bg_payload"
    return 0
  fi
  printf '%s\n' "$bg_payload"
}

###############################################################################
# Main
###############################################################################

case "$ORCHESTRATOR" in
  claude)
    probe_codex
    ;;
  codex)
    probe_claude_transport
    ;;
  *)
    echo "Unknown orchestrator: $ORCHESTRATOR (expected: claude or codex)" >&2
    exit 2
    ;;
esac
