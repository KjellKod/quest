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

# Check file write permissions for Write/Edit tools
check_file_write() {
  local file_path="$1"
  local allowed_patterns

  # Get allowed file_write patterns as array
  allowed_patterns=$(echo "$PERMS" | jq -r '.file_write // [] | .[]')
  [[ -z "$allowed_patterns" ]] && return 1  # No patterns = deny

  # Make path relative to repo root if absolute
  if [[ "$file_path" == "$REPO_ROOT"* ]]; then
    file_path="${file_path#$REPO_ROOT/}"
  fi

  # Check each pattern
  while IFS= read -r pattern; do
    [[ -z "$pattern" ]] && continue

    # Convert glob pattern to regex for matching
    # ** matches any path, * matches within a directory
    local regex="^${pattern//\*\*/.*}$"
    regex="${regex//\*/[^/]*}"

    if [[ "$file_path" =~ $regex ]]; then
      return 0  # Match found, allow
    fi
  done <<< "$allowed_patterns"

  return 1  # No match, deny
}

# Check bash command permissions
check_bash() {
  local command="$1"
  local allowed_commands

  # Get allowed bash commands as array
  allowed_commands=$(echo "$PERMS" | jq -r '.bash // [] | .[]')

  # Empty bash list = no bash allowed
  [[ -z "$allowed_commands" ]] && return 1

  # Check if command starts with any allowed prefix
  while IFS= read -r allowed; do
    [[ -z "$allowed" ]] && continue

    # Check if command starts with the allowed prefix
    if [[ "$command" == "$allowed"* ]]; then
      return 0  # Match found, allow
    fi
  done <<< "$allowed_commands"

  return 1  # No match, deny
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
