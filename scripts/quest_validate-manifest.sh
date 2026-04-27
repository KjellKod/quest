#!/usr/bin/env bash
#
# Validates that .quest-manifest includes all installer-managed Quest files
# Fails if shipped Quest files are missing from the manifest
#

set -e

MANIFEST=".quest-manifest"
ERRORS=0
STRICT_MODE="${QUEST_MANIFEST_STRICT:-auto}"

case "${1:-}" in
  "")
    ;;
  --strict)
    STRICT_MODE=1
    ;;
  --installed)
    STRICT_MODE=0
    ;;
  --help|-h)
    cat <<'EOF'
Usage: scripts/quest_validate-manifest.sh [--strict|--installed]

Validates .quest-manifest.

Modes:
  --strict     Also scan Quest source paths for files missing from the manifest.
  --installed  Validate only manifest entries; allow repo-local custom files.

Default mode is auto: strict when scripts/quest_installer.sh exists, installed
otherwise. Set QUEST_MANIFEST_STRICT=1 or 0 to override auto mode.
EOF
    exit 0
    ;;
  *)
    echo "Unknown option: $1" >&2
    echo "Usage: scripts/quest_validate-manifest.sh [--strict|--installed]" >&2
    exit 2
    ;;
esac

if [ "$STRICT_MODE" = "auto" ]; then
  if [ -f "scripts/quest_installer.sh" ]; then
    STRICT_MODE=1
  else
    STRICT_MODE=0
  fi
fi

# Colors
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[0;33m'
NC=$'\033[0m'

log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }

# Check manifest exists
if [ ! -f "$MANIFEST" ]; then
  log_error ".quest-manifest not found"
  exit 1
fi

# Extract all file paths from manifest (skip comments, section headers, empty lines)
get_manifest_files() {
  grep -v '^#' "$MANIFEST" | grep -v '^\[' | grep -v '^[[:space:]]*$' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'
}

MANIFEST_FILES=$(get_manifest_files | sort)

# Define which directories/patterns should be in the manifest
# These are the Quest framework files that the installer ships
EXPECTED_PATTERNS=(
  ".ai/*.md"
  ".ai/*.json"
  ".ai/roles/*.md"
  ".ai/schemas/*.json"
  ".ai/templates/*.md"
  ".skills/*.md"
  ".skills/*/*.md"
  ".skills/*/*/*.md"
  ".agents/*/*/*.md"
  ".claude/*.md"
  ".claude/agents/*.md"
  ".claude/hooks/*.sh"
  ".claude/skills/*/*.md"
  "scripts/quest_allowlist_matcher.py"
  "scripts/quest_claude_bridge.py"
  "scripts/quest_claude_probe.py"
  "scripts/quest_claude_runner.py"
  "scripts/quest_backfill_journal.py"
  "scripts/quest_complete.py"
  "scripts/quest_preflight.sh"
  "scripts/quest_review_intelligence.py"
  "scripts/quest_select_tests.py"
  "scripts/quest_startup_branch.py"
  "scripts/quest_state.py"
  "scripts/quest_celebrate/*.py"
  "scripts/quest_celebrate/*.sh"
  "scripts/quest_validate-handoff-contracts.sh"
  "scripts/quest_validate-manifest.sh"
  "scripts/quest_validate-quest-config.sh"
  "scripts/quest_validate-quest-state.sh"
  "scripts/quest_checks/*.py"
  "scripts/quest_runtime/*.py"
  "tests/integration/test-enforce-allowlist.sh"
  "tests/test-quest-preflight.sh"
  "tests/test-quest-runtime.sh"
  "tests/test-validate-handoff-contracts.sh"
  "tests/test-validate-quest-state.sh"
)

# Find all files matching our patterns
# Prune nested git worktrees so their files do not masquerade as repo content.
FOUND_FILES=""
for pattern in "${EXPECTED_PATTERNS[@]}"; do
  # Use find with -path to handle glob patterns
  matches=$(find . \
    -type d \( -path './.claude/worktrees' -o -path './.worktrees' -o -path './.git' \) -prune -o \
    -path "./$pattern" -type f -print 2>/dev/null | sed 's|^\./||' || true)
  if [ -n "$matches" ]; then
    FOUND_FILES="$FOUND_FILES"$'\n'"$matches"
  fi
done

# Clean up and sort
FOUND_FILES=$(echo "$FOUND_FILES" | grep -v '^$' | sort | uniq)

if [ "$STRICT_MODE" = "1" ]; then
  # Check each found file is in the manifest
  echo "Checking Quest files are listed in $MANIFEST..."
  echo ""

  MISSING_FILES=""
  while IFS= read -r file; do
    [ -z "$file" ] && continue

    if ! echo "$MANIFEST_FILES" | grep -q "^${file}$"; then
      MISSING_FILES="$MISSING_FILES$file"$'\n'
      ((ERRORS++)) || true
    fi
  done <<< "$FOUND_FILES"

  # Report results
  if [ $ERRORS -gt 0 ]; then
    log_error "Found $ERRORS file(s) missing from .quest-manifest:"
    echo ""
    echo "$MISSING_FILES" | grep -v '^$' | while read -r f; do
      echo "  - $f"
    done
    echo ""
    echo "Please add these files to the appropriate section in .quest-manifest"
    echo ""
    echo "Sections:"
    echo "  [copy-as-is]       - Files replaced with upstream (most files)"
    echo "  [user-customized]  - Files that preserve local edits (AGENTS.md may auto-update if pristine)"
    echo "  [merge-carefully]  - Files that prompt for merge (settings.json)"
    echo "  [directories]      - Directories to create"
    exit 1
  fi

  log_ok "All Quest files are listed in .quest-manifest"
else
  log_ok "Installed repo mode: allowing repo-local files outside .quest-manifest"
fi

# Also check for stale entries (files in manifest that don't exist)
echo ""
echo "Checking for stale manifest entries..."

# Get only files (not directories) from manifest
get_manifest_files_only() {
  awk '/^\[copy-as-is\]/,/^\[/' "$MANIFEST" | grep -v '^\[' | grep -v '^#' | grep -v '^[[:space:]]*$'
  awk '/^\[user-customized\]/,/^\[/' "$MANIFEST" | grep -v '^\[' | grep -v '^#' | grep -v '^[[:space:]]*$'
  awk '/^\[merge-carefully\]/,/^\[/' "$MANIFEST" | grep -v '^\[' | grep -v '^#' | grep -v '^[[:space:]]*$'
}

STALE_COUNT=0
while IFS= read -r file; do
  file=$(echo "$file" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  [ -z "$file" ] && continue

  if [ ! -f "$file" ]; then
    log_warn "Stale entry (file not found): $file"
    ((STALE_COUNT++)) || true
  fi
done <<< "$(get_manifest_files_only)"

if [ "$STALE_COUNT" -eq 0 ]; then
  log_ok "No stale entries in manifest"
fi

echo ""
echo "Manifest validation complete."
