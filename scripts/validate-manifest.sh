#!/usr/bin/env bash
#
# Validates that .quest-manifest includes all Quest files
# Fails if any tracked files are missing from the manifest
#

set -e

MANIFEST=".quest-manifest"
ERRORS=0

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
# These are the Quest framework files that the installer manages
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
  "scripts/validate-quest-config.sh"
)

# Find all files matching our patterns
FOUND_FILES=""
for pattern in "${EXPECTED_PATTERNS[@]}"; do
  # Use find with -path to handle glob patterns
  matches=$(find . -path "./$pattern" -type f 2>/dev/null | sed 's|^\./||' || true)
  if [ -n "$matches" ]; then
    FOUND_FILES="$FOUND_FILES"$'\n'"$matches"
  fi
done

# Clean up and sort
FOUND_FILES=$(echo "$FOUND_FILES" | grep -v '^$' | sort | uniq)

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
  echo "  [user-customized]  - Files never overwritten (allowlist, context_digest)"
  echo "  [merge-carefully]  - Files that prompt for merge (settings.json)"
  echo "  [directories]      - Directories to create"
  exit 1
fi

log_ok "All Quest files are listed in .quest-manifest"

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
