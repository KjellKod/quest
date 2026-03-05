#!/usr/bin/env bash
# Shell wrapper for quest celebration
# Delegates to Python script, with simple fallback if Python unavailable

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Try Python first
if command -v python3 &>/dev/null; then
    exec python3 "${SCRIPT_DIR}/celebrate.py" "$@"
elif command -v python &>/dev/null; then
    exec python "${SCRIPT_DIR}/celebrate.py" "$@"
fi

# Fallback: extract quest name from --quest-dir argument
QUEST_NAME="quest"
for ((i=1; i<=$#; i++)); do
    arg="${!i}"
    if [[ "$arg" == "--quest-dir" ]]; then
        next=$((i+1))
        if [[ $next -le $# ]]; then
            quest_path="${!next}"
            # Extract last directory component and parse quest name
            quest_dir=$(basename "$quest_path")
            # Format: quest-name_YYYY-MM-DD__HHMM
            QUEST_NAME=$(echo "$quest_dir" | sed 's/_.*//' | tr '-' ' ')
        fi
        break
    fi
done

# Simple fallback message
echo "Quest complete: ${QUEST_NAME}"
exit 0
