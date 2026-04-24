#!/usr/bin/env bash
# Quest Allowlist Enforcement Hook
# Called by Claude Code PreToolUse event
# Usage: enforce-allowlist.sh <role_name>
# Reads tool invocation JSON from stdin
# Exit 0 = allow, Exit 2 = block (message on stderr)

set -euo pipefail

ROLE="${1:-}"
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ALLOWLIST="$REPO_ROOT/.ai/allowlist.json"
MATCHER="$REPO_ROOT/scripts/quest_allowlist_matcher.py"

# No role specified = allow (hook misconfigured, don't block)
[[ -z "$ROLE" ]] && exit 0

# No allowlist = allow (not using quest system)
[[ ! -f "$ALLOWLIST" ]] && exit 0

# Read tool invocation from stdin
INPUT=$(cat)

# Extract tool name and relevant input fields
TOOL=$(echo "$INPUT" | jq -r '.tool // empty')
[[ -z "$TOOL" ]] && exit 0

# Get role permissions from allowlist
PERMS=$(jq -r ".role_permissions.\"$ROLE\" // empty" "$ALLOWLIST")
[[ -z "$PERMS" || "$PERMS" == "null" ]] && exit 0  # No permissions defined = allow

normalize_repo_path() {
  local file_path="$1"

  python3 - "$REPO_ROOT" "$file_path" <<'PY'
from pathlib import Path
import sys

repo_root = Path(sys.argv[1]).resolve()
candidate = Path(sys.argv[2])
if not candidate.is_absolute():
    candidate = repo_root / candidate

try:
    resolved = candidate.resolve(strict=False)
    relative = resolved.relative_to(repo_root)
except (OSError, ValueError):
    sys.exit(1)

print(relative.as_posix())
PY
}

# Check file write permissions for Write/Edit tools
check_file_write() {
  local file_path="$1"
  local allowed_patterns

  # Get allowed file_write patterns as array
  allowed_patterns=$(echo "$PERMS" | jq -r '.file_write // [] | .[]')
  [[ -z "$allowed_patterns" ]] && return 1  # No patterns = deny

  file_path=$(normalize_repo_path "$file_path") || return 1

  # Check each pattern
  while IFS= read -r pattern; do
    [[ -z "$pattern" ]] && continue

    local regex
    regex=$(glob_to_regex "$pattern")

    if [[ "$file_path" =~ $regex ]]; then
      return 0  # Match found, allow
    fi
  done <<< "$allowed_patterns"

  return 1  # No match, deny
}

glob_to_regex() {
  local pattern="$1"
  local regex="^"
  local i char next

  for ((i = 0; i < ${#pattern}; i++)); do
    char="${pattern:i:1}"

    if [[ "$char" == "*" ]]; then
      next="${pattern:i+1:1}"
      if [[ "$next" == "*" ]]; then
        if [[ "${pattern:i+2:1}" == "/" ]]; then
          regex+="(.*/)?"
          i=$((i + 2))
        else
          regex+=".*"
          i=$((i + 1))
        fi
      else
        regex+="[^/]*"
      fi
      continue
    fi

    case "$char" in
      [\\.\^\$\+\?\(\)\[\]\{\}\|])
        regex+="\\$char"
        ;;
      *)
        regex+="$char"
        ;;
    esac
  done

  regex+="$"
  printf '%s\n' "$regex"
}

# Check bash command permissions
check_bash() {
  local command="$1"
  local allowed_commands_json
  local matcher_output

  # Get allowed bash commands as JSON array
  allowed_commands_json=$(echo "$PERMS" | jq -c '.bash // []')
  [[ "$allowed_commands_json" == "[]" ]] && return 1

  matcher_output=$(python3 "$MATCHER" --command "$command" --allow "$allowed_commands_json" 2>&1) || {
    CHECK_BASH_REASON="$matcher_output"
    return 1
  }

  CHECK_BASH_REASON=""
  return 0
}

case "$TOOL" in
  Write|Edit)
    FILE_PATH=$(echo "$INPUT" | jq -r '.input.file_path // empty')
    [[ -z "$FILE_PATH" ]] && exit 0  # No file path = allow (malformed, let Claude handle)

    if ! check_file_write "$FILE_PATH"; then
      echo "BLOCKED: $ROLE cannot write to $FILE_PATH" >&2
      echo "Allowed patterns: $(echo "$PERMS" | jq -r '.file_write | join(", ")')" >&2
      exit 2
    fi
    ;;

  Bash)
    COMMAND=$(echo "$INPUT" | jq -r '.input.command // empty')
    [[ -z "$COMMAND" ]] && exit 0  # No command = allow (malformed)

    if ! check_bash "$COMMAND"; then
      echo "BLOCKED: $ROLE cannot run: $COMMAND" >&2
      if [[ -n "${CHECK_BASH_REASON:-}" ]]; then
        echo "Reason: $CHECK_BASH_REASON" >&2
      fi
      echo "Allowed commands: $(echo "$PERMS" | jq -r '.bash | join(", ")')" >&2
      exit 2
    fi
    ;;

  *)
    # Other tools (Read, Glob, Grep, etc.) = allow
    # file_read is always ** for all roles in our setup
    ;;
esac

exit 0
