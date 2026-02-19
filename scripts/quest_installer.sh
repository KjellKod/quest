#!/usr/bin/env bash
# Quest Installer Script
# Installs and updates Quest in any repository
# Usage: quest_installer.sh [--branch <name>] [--check|--force|--help]
#
# Copyright (c) 2026 Quest Authors
# License: MIT

set -e

###############################################################################
# Configuration Constants
###############################################################################

UPSTREAM_REPO="KjellKod/quest"
UPSTREAM_BRANCH="main"
RAW_BASE="https://raw.githubusercontent.com/${UPSTREAM_REPO}"
SCRIPT_NAME="$(basename "$0")"

# Resolve script path reliably (handles both direct execution and sourcing)
# Uses BASH_SOURCE[0] instead of $0 to handle "bash script.sh" invocation
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

# Mode flags (set by argument parsing)
DRY_RUN=false
FORCE_MODE=false
SKIP_SELF_UPDATE=false
SOURCE_EXPLICIT=false

# State variables (set during execution)
IS_GIT_REPO=false
HAS_QUEST=false
LOCAL_VERSION=""
UPSTREAM_SHA=""
LATEST_RELEASE=""

# Dry-run summary counters
DRY_RUN_WOULD_CREATE=0
DRY_RUN_WOULD_UPDATE=0
DRY_RUN_WOULD_SKIP=0
DRY_RUN_UP_TO_DATE=0
DRY_RUN_MODIFIED=0

###############################################################################
# Cleanup Trap
###############################################################################

cleanup() {
  rm -f ".quest-checksums.tmp.$$" ".quest-temp.$$" 2>/dev/null
}
trap cleanup EXIT

###############################################################################
# File Category Arrays (populated dynamically from .quest-manifest)
###############################################################################

# These arrays are populated by load_manifest()
COPY_AS_IS=()
USER_CUSTOMIZED=()
MERGE_CAREFULLY=()
CREATE_DIRS=()

###############################################################################
# Manifest Loading
###############################################################################

# Fetch and parse .quest-manifest from upstream
load_manifest() {
  log_info "Fetching file manifest..."

  local manifest_content
  if ! manifest_content=$(fetch_file ".quest-manifest" 2>/dev/null); then
    log_error "Could not fetch .quest-manifest from upstream"
    log_error "The Quest repository may be misconfigured"
    exit 1
  fi

  local current_section=""

  while IFS= read -r line; do
    # Skip empty lines and comments
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue

    # Check for section headers
    if [[ "$line" =~ ^\[([a-z-]+)\]$ ]]; then
      current_section="${BASH_REMATCH[1]}"
      continue
    fi

    # Trim whitespace
    line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [[ -z "$line" ]] && continue

    # Add to appropriate array based on current section
    case "$current_section" in
      copy-as-is)
        COPY_AS_IS+=("$line")
        ;;
      user-customized)
        USER_CUSTOMIZED+=("$line")
        ;;
      merge-carefully)
        MERGE_CAREFULLY+=("$line")
        ;;
      directories)
        CREATE_DIRS+=("$line")
        ;;
    esac
  done <<< "$manifest_content"

  # Always include the installer itself in copy-as-is
  COPY_AS_IS+=("scripts/quest_installer.sh")

  log_info "Loaded ${#COPY_AS_IS[@]} copy-as-is, ${#USER_CUSTOMIZED[@]} user-customized, ${#MERGE_CAREFULLY[@]} merge-carefully files"
}

# Files that need executable bit set
EXECUTABLE_FILES=(
  ".claude/hooks/enforce-allowlist.sh"
  "scripts/validate-quest-config.sh"
  "scripts/quest_installer.sh"
)

###############################################################################
# Checksum Storage (parallel arrays for bash 3.2 compatibility)
###############################################################################

# Local checksums (from .quest-checksums)
LOCAL_CHECKSUM_FILES=()
LOCAL_CHECKSUM_VALUES=()

# Upstream checksums (from checksums.txt)
UPSTREAM_CHECKSUM_FILES=()
UPSTREAM_CHECKSUM_VALUES=()

# Updated checksums (to be saved at end)
UPDATED_CHECKSUM_FILES=()
UPDATED_CHECKSUM_VALUES=()

###############################################################################
# Color Output
###############################################################################

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  RED=$'\033[0;31m'
  GREEN=$'\033[0;32m'
  YELLOW=$'\033[0;33m'
  BLUE=$'\033[0;34m'
  BOLD=$'\033[1m'
  NC=$'\033[0m'
else
  RED='' GREEN='' YELLOW='' BLUE='' BOLD='' NC=''
fi

###############################################################################
# Utility Functions
###############################################################################

# Clear any progress line before logging (progress is on stderr)
clear_progress() {
  printf "\r%-80s\r" "" >&2
}

log_info() {
  clear_progress
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  clear_progress
  echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
  clear_progress
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

log_action() {
  clear_progress
  if $DRY_RUN; then
    echo -e "${YELLOW}[DRY-RUN]${NC} Would: $1"
  else
    echo -e "${GREEN}[ACTION]${NC} $1"
  fi
}

# Show a markdown file with best available local renderer.
show_markdown_file() {
  local filepath="$1"

  if [ ! -f "$filepath" ]; then
    log_warn "Cannot open missing file: $filepath"
    return 1
  fi

  # Prefer a markdown renderer if installed.
  if command -v glow &>/dev/null; then
    glow "$filepath"
    return 0
  fi

  # Fall back to pager/plain text.
  if command -v less &>/dev/null; then
    less "$filepath"
  else
    cat "$filepath"
  fi
}

# Optional post-install prompt to view quest documentation.
prompt_view_docs() {
  # Skip in non-interactive or automation modes.
  if $DRY_RUN || $FORCE_MODE || [ ! -t 0 ] || [ ! -t 1 ]; then
    return 0
  fi

  echo ""
  local prompt="Would you like to view .ai/quest.md now?"
  if ! command -v glow &>/dev/null; then
    prompt="${prompt} (for best viewing experience, install glow: brew install glow)"
  fi

  if prompt_yn "$prompt" "y"; then
    echo ""
    show_markdown_file ".ai/quest.md" || true
  else
    echo "Installer finished. You can open .ai/quest.md any time."
  fi
}

# Confirm install source when defaulting to main with no explicit source flag.
confirm_install_source() {
  # Non-main branch was explicitly chosen or set.
  if [ "$UPSTREAM_BRANCH" != "main" ]; then
    return 0
  fi

  # --branch was provided explicitly (including --branch main).
  if $SOURCE_EXPLICIT; then
    return 0
  fi

  # Skip prompt for automation/dry-run/non-interactive runs.
  if $FORCE_MODE || $DRY_RUN || [ ! -t 0 ]; then
    return 0
  fi

  echo ""
  log_warn "Install source not specified. Default source is branch: main."
  if prompt_yn "Install from main?" "y"; then
    return 0
  fi

  echo ""
  log_info "Installation cancelled."
  echo "Re-run with an explicit source/option:"
  echo "  --branch <name>   Install from a specific branch"
  echo "  --check           Dry run (preview only)"
  echo "  --force           Non-interactive mode"
  echo "  --help            Show all options"
  echo ""
  echo "Examples:"
  echo "  ./$SCRIPT_NAME --branch main"
  echo "  ./$SCRIPT_NAME --branch phase4_architecture_evolution_codex"
  echo "  ./$SCRIPT_NAME --check --branch main"
  exit 0
}

# Prompt user for yes/no (defaults to yes)
# Returns 0 for yes, 1 for no
prompt_yn() {
  local prompt="$1"
  local default="${2:-y}"

  if $FORCE_MODE; then
    # In force mode, accept default
    if [ "$default" = "y" ]; then
      return 0
    else
      return 1
    fi
  fi

  local yn_hint
  if [ "$default" = "y" ]; then
    yn_hint="[Y/n]"
  else
    yn_hint="[y/N]"
  fi

  echo -n -e "${prompt} ${yn_hint} "
  read -r response

  case "$response" in
    [yY]|[yY][eE][sS])
      return 0
      ;;
    [nN]|[nN][oO])
      return 1
      ;;
    "")
      if [ "$default" = "y" ]; then
        return 0
      else
        return 1
      fi
      ;;
    *)
      return 1
      ;;
  esac
}

# Prompt user for action on modified file
# Returns: o=overwrite, s=skip, d=diff
prompt_file_action() {
  local filepath="$1"

  if $DRY_RUN; then
    # In dry-run mode, don't prompt - just indicate it would ask
    echo "s"
    return
  fi

  if $FORCE_MODE; then
    # In force mode, skip modified files
    echo "s"
    return
  fi

  while true; do
    echo -n -e "${YELLOW}${filepath}${NC} has local modifications. [O]verwrite / [S]kip / [D]iff? "
    read -r response

    case "$response" in
      [oO])
        echo "o"
        return
        ;;
      [sS]|"")
        echo "s"
        return
        ;;
      [dD])
        echo "d"
        return
        ;;
      *)
        echo "Please enter O, S, or D"
        ;;
    esac
  done
}

###############################################################################
# Help
###############################################################################

show_help() {
  fetch_latest_release
  cat <<EOF
${BOLD}Quest Installer${NC} (latest release: ${LATEST_RELEASE}, branch: ${UPSTREAM_BRANCH})

Installs and updates Quest in any repository.
Run this script from the root of your target repository.

${BOLD}Usage:${NC}
  cd /path/to/your/repo
  $SCRIPT_NAME [OPTIONS]

${BOLD}Options:${NC}
  --branch <name>  Use a specific upstream branch (default: main)
  --check          Dry-run mode: show what would change without modifying files
  --force          Non-interactive mode: accept safe defaults, skip modified files
  --help           Show this help message

${BOLD}Examples:${NC}
  $SCRIPT_NAME                          # Interactive install/update from main
  $SCRIPT_NAME --branch feature/xyz     # Install from a specific branch
  $SCRIPT_NAME --check                  # Preview changes
  $SCRIPT_NAME --force                  # CI/automation mode

${BOLD}File Categories:${NC}
  - Copy as-is:      Replaced with upstream (if unmodified)
  - User-customized: Never overwritten (.quest_updated suffix for upstream changes)
  - Merge carefully: Manual merge offered for settings files

${BOLD}Troubleshooting:${NC}
  Run with debug output:
    bash -x $SCRIPT_NAME --check 2>&1 | tee debug.log

${BOLD}More Info:${NC}
  https://github.com/${UPSTREAM_REPO}
EOF
  exit 0
}

###############################################################################
# Prerequisites Check
###############################################################################

check_prerequisites() {
  local missing=false

  if ! command -v curl &>/dev/null; then
    log_error "curl is required but not installed"
    missing=true
  fi

  if ! command -v git &>/dev/null; then
    log_error "git is required but not installed"
    missing=true
  fi

  if ! command -v jq &>/dev/null; then
    log_warn "jq is not installed - JSON merge features will be limited"
  fi

  if $missing; then
    exit 1
  fi
}

###############################################################################
# Checksum Functions
###############################################################################

# Detect platform-appropriate checksum command
get_checksum_cmd() {
  if command -v sha256sum &>/dev/null; then
    echo "sha256sum"
  elif command -v shasum &>/dev/null; then
    echo "shasum -a 256"
  else
    log_error "No SHA256 checksum utility found (need sha256sum or shasum)"
    exit 1
  fi
}

# Calculate SHA256 checksum of a file
get_file_checksum() {
  local file="$1"
  local cmd
  cmd=$(get_checksum_cmd)
  $cmd "$file" 2>/dev/null | cut -d' ' -f1
}

# Calculate SHA256 checksum of content from stdin
get_content_checksum() {
  local cmd
  cmd=$(get_checksum_cmd)
  $cmd | cut -d' ' -f1
}

# Load checksums from .quest-checksums file
load_local_checksums() {
  LOCAL_CHECKSUM_FILES=()
  LOCAL_CHECKSUM_VALUES=()

  if [ -f ".quest-checksums" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
      # Skip comments and empty lines
      case "$line" in
        \#*|"") continue ;;
      esac

      # Parse: checksum  filepath (two spaces between)
      local checksum filepath
      checksum=$(echo "$line" | cut -d' ' -f1)
      filepath=$(echo "$line" | sed 's/^[^ ]*  //')

      # Validate checksum format (SHA256 = 64 hex chars) and filepath is non-empty
      if [ ${#checksum} -ne 64 ] || [ -z "$filepath" ]; then
        log_warn "Malformed checksum entry, skipping: $line"
        continue
      fi

      LOCAL_CHECKSUM_FILES+=("$filepath")
      LOCAL_CHECKSUM_VALUES+=("$checksum")
    done < ".quest-checksums"
  fi
}

# Get stored checksum for a file
get_stored_checksum() {
  local target="$1"
  local i
  for i in "${!LOCAL_CHECKSUM_FILES[@]}"; do
    if [ "${LOCAL_CHECKSUM_FILES[$i]}" = "$target" ]; then
      echo "${LOCAL_CHECKSUM_VALUES[$i]}"
      return 0
    fi
  done
  return 1
}

# Update or add checksum in updated arrays
set_updated_checksum() {
  local target="$1"
  local checksum="$2"
  local i
  for i in "${!UPDATED_CHECKSUM_FILES[@]}"; do
    if [ "${UPDATED_CHECKSUM_FILES[$i]}" = "$target" ]; then
      UPDATED_CHECKSUM_VALUES[$i]="$checksum"
      return
    fi
  done
  # Not found, append
  UPDATED_CHECKSUM_FILES+=("$target")
  UPDATED_CHECKSUM_VALUES+=("$checksum")
}

# Initialize updated checksums from local checksums
init_updated_checksums() {
  UPDATED_CHECKSUM_FILES=("${LOCAL_CHECKSUM_FILES[@]}")
  UPDATED_CHECKSUM_VALUES=("${LOCAL_CHECKSUM_VALUES[@]}")
}

# Save checksums to .quest-checksums file (atomic write, sorted)
save_checksums() {
  if $DRY_RUN; then
    log_action "Update .quest-checksums with ${#UPDATED_CHECKSUM_FILES[@]} entries"
    return
  fi

  local tmp_file=".quest-checksums.tmp.$$"

  {
    echo "# Quest Installer Checksums"
    echo "# Do not edit manually - managed by quest_installer.sh"
    echo "# Format: SHA256  filepath"
    echo ""

    # Sort by filepath for stable diffs
    # Create temp file with "filepath|checksum" entries, sort, then output
    local i
    for i in "${!UPDATED_CHECKSUM_FILES[@]}"; do
      echo "${UPDATED_CHECKSUM_FILES[$i]}|${UPDATED_CHECKSUM_VALUES[$i]}"
    done | sort | while IFS='|' read -r fp cs; do
      echo "${cs}  ${fp}"
    done
  } > "$tmp_file"

  mv "$tmp_file" ".quest-checksums"
  log_success "Updated .quest-checksums"
}

# Load upstream checksums from checksums.txt
load_upstream_checksums() {
  UPSTREAM_CHECKSUM_FILES=()
  UPSTREAM_CHECKSUM_VALUES=()

  local content
  if ! content=$(fetch_file "checksums.txt" 2>/dev/null); then
    # This is expected - checksums are calculated on-the-fly
    return 1
  fi

  while IFS= read -r line || [ -n "$line" ]; do
    # Skip comments and empty lines
    case "$line" in
      \#*|"") continue ;;
    esac

    # Parse: checksum  filepath (two spaces between)
    local checksum filepath
    checksum=$(echo "$line" | cut -d' ' -f1)
    filepath=$(echo "$line" | sed 's/^[^ ]*  //')

    # Validate checksum format (SHA256 = 64 hex chars) and filepath is non-empty
    if [ ${#checksum} -ne 64 ] || [ -z "$filepath" ]; then
      log_warn "Malformed checksum entry, skipping: $line"
      continue
    fi

    UPSTREAM_CHECKSUM_FILES+=("$filepath")
    UPSTREAM_CHECKSUM_VALUES+=("$checksum")
  done <<< "$content"

  return 0
}

# Get upstream checksum for a file
get_upstream_checksum() {
  local target="$1"
  local i
  for i in "${!UPSTREAM_CHECKSUM_FILES[@]}"; do
    if [ "${UPSTREAM_CHECKSUM_FILES[$i]}" = "$target" ]; then
      echo "${UPSTREAM_CHECKSUM_VALUES[$i]}"
      return 0
    fi
  done
  return 1
}

# Check if a local file is pristine (matches stored checksum)
is_file_pristine() {
  local filepath="$1"

  if [ ! -f "$filepath" ]; then
    return 1
  fi

  local stored_checksum
  if ! stored_checksum=$(get_stored_checksum "$filepath"); then
    # No stored checksum - treat as potentially modified
    return 1
  fi

  local current_checksum
  current_checksum=$(get_file_checksum "$filepath")

  if [ "$current_checksum" = "$stored_checksum" ]; then
    return 0  # Pristine
  else
    return 1  # Modified
  fi
}

###############################################################################
# Version Functions
###############################################################################

detect_repo_state() {
  # Check if in git repo (we've already cd'd to root if needed)
  if git rev-parse --show-toplevel &>/dev/null; then
    IS_GIT_REPO=true
  else
    IS_GIT_REPO=false
    log_warn "Not in a git repository. Quest will still be installed but some features may not work."
  fi

  # Check if Quest is already installed
  if [ -f ".quest-version" ]; then
    HAS_QUEST=true
    LOCAL_VERSION=$(cat ".quest-version" 2>/dev/null || echo "")
  else
    HAS_QUEST=false
    LOCAL_VERSION=""
  fi
}

fetch_latest_release() {
  # Get the latest release tag from GitHub
  local tags
  tags=$(git ls-remote --tags "https://github.com/${UPSTREAM_REPO}.git" 2>/dev/null | grep -v '\^{}' | awk '{print $2}' | sed 's|refs/tags/||' | sort -V | tail -1)

  if [ -n "$tags" ]; then
    LATEST_RELEASE="$tags"
  else
    LATEST_RELEASE="unreleased"
  fi
}

fetch_upstream_version() {
  # Use git ls-remote to get the SHA of the main branch
  # This is simpler and more reliable than parsing GitHub API JSON
  local remote_info
  if ! remote_info=$(git ls-remote "https://github.com/${UPSTREAM_REPO}.git" "refs/heads/${UPSTREAM_BRANCH}" 2>/dev/null); then
    log_error "Could not fetch upstream version from GitHub"
    log_error "Check your network connection and try again"
    exit 1
  fi

  UPSTREAM_SHA=$(echo "$remote_info" | cut -f1)

  if [ -z "$UPSTREAM_SHA" ]; then
    log_error "Could not determine upstream version"
    exit 1
  fi

  log_info "Upstream version: ${UPSTREAM_SHA:0:8}"
}

update_version_marker() {
  if $DRY_RUN; then
    log_action "Update .quest-version to ${UPSTREAM_SHA:0:8}"
    return
  fi

  echo "$UPSTREAM_SHA" > ".quest-version"
  log_success "Updated .quest-version"
}

###############################################################################
# File Operations
###############################################################################

# Fetch a file from upstream (pinned to UPSTREAM_SHA)
fetch_file() {
  local remote_path="$1"

  if [ -z "$UPSTREAM_SHA" ]; then
    log_error "Internal error: UPSTREAM_SHA not set"
    return 1
  fi

  local url="${RAW_BASE}/${UPSTREAM_SHA}/${remote_path}"

  curl -fsSL "$url"
}

# Fetch file to a temp file (preserves trailing newlines for accurate checksums)
fetch_file_to_temp() {
  local remote_path="$1"
  local temp_file="$2"

  if [ -z "$UPSTREAM_SHA" ]; then
    log_error "Internal error: UPSTREAM_SHA not set"
    return 1
  fi

  local url="${RAW_BASE}/${UPSTREAM_SHA}/${remote_path}"

  curl -fsSL "$url" -o "$temp_file"
}

# Create parent directories for a file path
ensure_parent_dir() {
  local filepath="$1"
  local parent_dir
  parent_dir=$(dirname "$filepath")

  if [ ! -d "$parent_dir" ]; then
    if $DRY_RUN; then
      log_action "Create directory: $parent_dir"
    else
      mkdir -p "$parent_dir"
    fi
  fi
}

# Write content to a file
write_file() {
  local filepath="$1"
  local content="$2"

  ensure_parent_dir "$filepath"

  if $DRY_RUN; then
    log_action "Write: $filepath"
    return
  fi

  printf '%s\n' "$content" > "$filepath"
}

# Set executable bit on a file
set_executable() {
  local filepath="$1"

  if $DRY_RUN; then
    log_action "Set executable: $filepath"
    return
  fi

  chmod +x "$filepath"
}

# Show diff between local and upstream file
show_diff() {
  local filepath="$1"
  local upstream_file="$2"  # Can be temp file path or content string

  echo ""
  echo -e "${BOLD}--- Local: $filepath${NC}"
  echo -e "${BOLD}+++ Upstream: $filepath${NC}"
  echo ""

  if command -v diff &>/dev/null; then
    # upstream_file is already a temp file path
    diff -u "$filepath" "$upstream_file" || true
  else
    echo "(diff not available - showing upstream content)"
    printf '%s\n' "$upstream_content"
  fi

  echo ""
}

###############################################################################
# Directory Installation
###############################################################################

create_directories() {
  if $DRY_RUN; then
    log_info "Checking directories..."
  else
    log_info "Creating directories..."
  fi

  local dir
  for dir in "${CREATE_DIRS[@]}"; do
    if [ ! -d "$dir" ]; then
      if $DRY_RUN; then
        log_action "Create directory: $dir"
      else
        mkdir -p "$dir"
        log_success "Created: $dir"
      fi
    fi
  done
}

###############################################################################
# Copy-As-Is File Installation
###############################################################################

install_copy_as_is() {
  # Clear any previous progress line
  printf "\r%-80s\r" "" >&2
  if $DRY_RUN; then
    log_info "Checking copy-as-is files..."
  else
    log_info "Installing copy-as-is files..."
  fi

  local filepath
  local count=0
  local total=${#COPY_AS_IS[@]}
  for filepath in "${COPY_AS_IS[@]}"; do
    ((count++))
    install_copy_as_is_file "$filepath" "$count" "$total"
  done
  # Clear progress line (stderr for immediate flush)
  printf "                                                                              \r" >&2
}

install_copy_as_is_file() {
  local filepath="$1"
  local count="${2:-}"
  local total="${3:-}"

  # Show progress (stderr is unbuffered, so progress displays immediately)
  if [ -n "$count" ] && [ -n "$total" ]; then
    printf "\r  [%d/%d] Checking: %-50s" "$count" "$total" "$filepath" >&2
  else
    printf "\r  Checking: %-60s" "$filepath" >&2
  fi

  # Fetch upstream content to temp file (preserves trailing newlines)
  local temp_file=".quest-temp.$$"
  if ! fetch_file_to_temp "$filepath" "$temp_file" 2>/dev/null; then
    log_warn "Could not fetch: $filepath (may not exist in upstream yet)"
    rm -f "$temp_file"
    return 0  # Continue with other files
  fi

  # Calculate upstream checksum from temp file (accurate, preserves newlines)
  local upstream_checksum
  upstream_checksum=$(get_file_checksum "$temp_file")

  # Case 1: File does not exist locally
  if [ ! -f "$filepath" ]; then
    ensure_parent_dir "$filepath"
    if $DRY_RUN; then
      log_action "Create: $filepath"
      ((DRY_RUN_WOULD_CREATE++))
    else
      mv "$temp_file" "$filepath"
      log_success "Created: $filepath"
    fi
    rm -f "$temp_file"
    set_updated_checksum "$filepath" "$upstream_checksum"
    return 0
  fi

  # File exists - check if it matches upstream
  local local_checksum
  local_checksum=$(get_file_checksum "$filepath")

  if [ "$local_checksum" = "$upstream_checksum" ]; then
    rm -f "$temp_file"
    # Already up to date - just ensure checksum is stored
    set_updated_checksum "$filepath" "$upstream_checksum"
    $DRY_RUN && ((DRY_RUN_UP_TO_DATE++))
    return 0
  fi

  # Case 2: File exists and is pristine (unmodified from last install)
  if is_file_pristine "$filepath"; then
    if $DRY_RUN; then
      log_action "Update: $filepath"
      ((DRY_RUN_WOULD_UPDATE++))
    else
      mv "$temp_file" "$filepath"
      log_success "Updated: $filepath"
    fi
    rm -f "$temp_file"
    set_updated_checksum "$filepath" "$upstream_checksum"
    return 0
  fi

  # Case 3: File exists and has local modifications
  if $DRY_RUN; then
    rm -f "$temp_file"
    # Clear progress line before warning
    printf "\r%-80s\r" "" >&2
    log_warn "Modified: $filepath (would prompt to overwrite/skip)"
    ((DRY_RUN_MODIFIED++))
    return 0
  fi

  # Special case: when running the installer from this repo path, avoid
  # prompting on the installer file itself. Self-update is already handled
  # earlier by check_self_update(); prompting here can look like a hang.
  local running_script_rel="${SCRIPT_PATH#$(pwd)/}"
  if [ "$filepath" = "scripts/quest_installer.sh" ] && [ "$running_script_rel" = "$filepath" ]; then
    rm -f "$temp_file"
    # Keep local checksum so this run remains non-blocking and deterministic.
    set_updated_checksum "$filepath" "$local_checksum"
    log_info "Keeping current running installer: $filepath"
    return 0
  fi

  if $FORCE_MODE; then
    rm -f "$temp_file"
    log_warn "Skipping modified file: $filepath"
    # Keep existing checksum
    local existing
    if existing=$(get_stored_checksum "$filepath"); then
      set_updated_checksum "$filepath" "$existing"
    fi
    return 0
  fi

  # Interactive mode - prompt user
  while true; do
    local action
    action=$(prompt_file_action "$filepath")

    case "$action" in
      o)
        # Overwrite
        mv "$temp_file" "$filepath"
        log_success "Overwrote: $filepath"
        set_updated_checksum "$filepath" "$upstream_checksum"
        return 0
        ;;
      s)
        # Skip
        rm -f "$temp_file"
        log_info "Skipped: $filepath"
        local existing
        if existing=$(get_stored_checksum "$filepath"); then
          set_updated_checksum "$filepath" "$existing"
        fi
        return 0
        ;;
      d)
        # Show diff and re-prompt
        show_diff "$filepath" "$temp_file"
        ;;
    esac
  done
}

###############################################################################
# User-Customized File Installation
###############################################################################

install_user_customized() {
  # Clear any previous progress line
  printf "\r%-80s\r" "" >&2
  if $DRY_RUN; then
    log_info "Checking user-customized files..."
  else
    log_info "Installing user-customized files..."
  fi

  local filepath
  local count=0
  local total=${#USER_CUSTOMIZED[@]}
  for filepath in "${USER_CUSTOMIZED[@]}"; do
    ((count++))
    install_user_customized_file "$filepath" "$count" "$total"
  done
  # Clear progress line (stderr for immediate flush)
  printf "                                                                              \r" >&2
}

install_user_customized_file() {
  local filepath="$1"
  local count="${2:-}"
  local total="${3:-}"

  # Show progress (stderr is unbuffered, so progress displays immediately)
  if [ -n "$count" ] && [ -n "$total" ]; then
    printf "\r  [%d/%d] Checking: %-50s" "$count" "$total" "$filepath" >&2
  else
    printf "\r  Checking: %-60s" "$filepath" >&2
  fi

  # Fetch upstream content to temp file
  local temp_file=".quest-temp.$$"
  if ! fetch_file_to_temp "$filepath" "$temp_file" 2>/dev/null; then
    log_warn "Could not fetch: $filepath (may not exist in upstream yet)"
    rm -f "$temp_file"
    return 0  # Continue with other files
  fi

  # Case 1: File does not exist locally - create it
  if [ ! -f "$filepath" ]; then
    ensure_parent_dir "$filepath"
    if $DRY_RUN; then
      log_action "Create: $filepath (customize after install)"
    else
      mv "$temp_file" "$filepath"
      log_success "Created: $filepath (customize as needed)"
    fi
    rm -f "$temp_file"
    return 0
  fi

  # Case 2: File exists - check if upstream has changes
  local local_checksum upstream_checksum
  local_checksum=$(get_file_checksum "$filepath")
  upstream_checksum=$(get_file_checksum "$temp_file")

  if [ "$local_checksum" = "$upstream_checksum" ]; then
    # No changes
    rm -f "$temp_file"
    return 0
  fi

  # Upstream differs - create .quest_updated file
  local updated_path="${filepath}.quest_updated"
  if $DRY_RUN; then
    log_action "Create: $updated_path (upstream has changes)"
  else
    mv "$temp_file" "$updated_path"
    log_warn "Created: $updated_path (review and merge manually)"
  fi
  rm -f "$temp_file"
}

###############################################################################
# Merge-Carefully File Installation
###############################################################################

install_merge_carefully() {
  # Clear any previous progress line
  printf "\r%-80s\r" "" >&2
  if $DRY_RUN; then
    log_info "Checking settings files..."
  else
    log_info "Installing settings files..."
  fi

  local filepath
  local count=0
  local total=${#MERGE_CAREFULLY[@]}
  for filepath in "${MERGE_CAREFULLY[@]}"; do
    ((count++))
    install_merge_carefully_file "$filepath" "$count" "$total"
  done
  # Clear progress line (stderr for immediate flush)
  printf "                                                                              \r" >&2
}

install_merge_carefully_file() {
  local filepath="$1"
  local count="${2:-}"
  local total="${3:-}"

  # Show progress (stderr is unbuffered, so progress displays immediately)
  if [ -n "$count" ] && [ -n "$total" ]; then
    printf "\r  [%d/%d] Checking: %-50s" "$count" "$total" "$filepath" >&2
  else
    printf "\r  Checking: %-60s" "$filepath" >&2
  fi

  # Fetch upstream content to temp file
  local temp_file=".quest-temp.$$"
  if ! fetch_file_to_temp "$filepath" "$temp_file" 2>/dev/null; then
    # File may not exist in upstream (e.g., settings.local.json)
    rm -f "$temp_file"
    return 0
  fi

  # Case 1: File does not exist locally - create it
  if [ ! -f "$filepath" ]; then
    ensure_parent_dir "$filepath"
    if $DRY_RUN; then
      log_action "Create: $filepath"
    else
      mv "$temp_file" "$filepath"
      log_success "Created: $filepath"
    fi
    rm -f "$temp_file"
    return 0
  fi

  # Case 2: File exists - check if upstream has changes
  local local_checksum upstream_checksum
  local_checksum=$(get_file_checksum "$filepath")
  upstream_checksum=$(get_file_checksum "$temp_file")

  if [ "$local_checksum" = "$upstream_checksum" ]; then
    # No changes
    rm -f "$temp_file"
    return 0
  fi

  # Upstream differs - handle based on mode
  if $FORCE_MODE; then
    # In force mode, create .quest_updated file (safe default)
    local updated_path="${filepath}.quest_updated"
    if $DRY_RUN; then
      log_action "Create: $updated_path (upstream has changes)"
    else
      mv "$temp_file" "$updated_path"
      log_warn "Created: $updated_path (merge manually)"
    fi
    rm -f "$temp_file"
    return 0
  fi

  # Interactive mode - show diff and offer options
  echo ""
  log_warn "Settings file has upstream changes: $filepath"
  show_diff "$filepath" "$temp_file"

  echo "Options:"
  echo "  [S]kip - Keep local file unchanged"
  echo "  [O]verwrite - Replace with upstream version"
  echo "  [U]pdate file - Create .quest_updated for manual merge"
  echo ""
  echo -n "Choice [S/o/u]: "
  read -r response

  case "$response" in
    [oO])
      if $DRY_RUN; then
        log_action "Overwrite: $filepath"
      else
        mv "$temp_file" "$filepath"
        log_success "Overwrote: $filepath"
      fi
      ;;
    [uU])
      local updated_path="${filepath}.quest_updated"
      if $DRY_RUN; then
        log_action "Create: $updated_path"
      else
        mv "$temp_file" "$updated_path"
        log_info "Created: $updated_path (merge manually)"
      fi
      ;;
    *)
      log_info "Skipped: $filepath"
      ;;
  esac
  rm -f "$temp_file"
}

###############################################################################
# Set Executable Bits
###############################################################################

set_executable_bits() {
  # Clear any previous progress line
  printf "\r%-80s\r" "" >&2
  log_info "Setting executable permissions..."

  local filepath
  for filepath in "${EXECUTABLE_FILES[@]}"; do
    if [ -f "$filepath" ]; then
      set_executable "$filepath"
    fi
  done
}

###############################################################################
# Gitignore Update
###############################################################################

update_gitignore() {
  if [ ! -f ".gitignore" ]; then
    if $DRY_RUN; then
      log_action "Create .gitignore with .quest/ entry"
    else
      echo ".quest/" > ".gitignore"
      log_success "Created .gitignore with .quest/ entry"
    fi
    return
  fi

  # Check if .quest/ is already in .gitignore
  if grep -q "^\.quest/" ".gitignore" 2>/dev/null || \
     grep -q "^\.quest$" ".gitignore" 2>/dev/null; then
    return
  fi

  # Add .quest/ to .gitignore
  if $DRY_RUN; then
    log_action "Add .quest/ to .gitignore"
  else
    echo "" >> ".gitignore"
    echo "# Quest ephemeral state" >> ".gitignore"
    echo ".quest/" >> ".gitignore"
    log_success "Added .quest/ to .gitignore"
  fi
}

###############################################################################
# Validation
###############################################################################

run_validation() {
  log_info "Running validation..."

  if [ ! -f "scripts/validate-quest-config.sh" ]; then
    log_warn "Validation script not found - skipping"
    return
  fi

  if [ ! -x "scripts/validate-quest-config.sh" ]; then
    chmod +x "scripts/validate-quest-config.sh"
  fi

  if $DRY_RUN; then
    log_action "Run scripts/validate-quest-config.sh"
    return
  fi

  echo ""
  if ./scripts/validate-quest-config.sh; then
    log_success "Validation passed"
  else
    log_warn "Validation had issues - review output above"
  fi
}

###############################################################################
# Self-Update
###############################################################################

check_self_update() {
  if $SKIP_SELF_UPDATE; then
    return 0
  fi

  log_info "Checking for installer updates..."

  # Fetch upstream installer
  local upstream_script
  if ! upstream_script=$(fetch_file "scripts/quest_installer.sh" 2>/dev/null); then
    log_warn "Could not check for installer updates"
    return 0
  fi

  # Compare checksums using SCRIPT_PATH (handles "bash script.sh" invocation)
  local local_checksum upstream_checksum
  local_checksum=$(get_file_checksum "$SCRIPT_PATH")
  upstream_checksum=$(printf '%s\n' "$upstream_script" | get_content_checksum)

  if [ "$local_checksum" = "$upstream_checksum" ]; then
    return 0
  fi

  # Installer differs
  log_warn "A newer installer is available"

  if $DRY_RUN; then
    log_action "Would update installer and re-run"
    return 0
  fi

  if prompt_yn "Update installer now?"; then
    # Write new installer using SCRIPT_PATH (not $0 which could be "bash")
    printf '%s\n' "$upstream_script" > "$SCRIPT_PATH"
    chmod +x "$SCRIPT_PATH"
    log_success "Installer updated"

    # Re-exec with skip-self-update flag, preserving original arguments
    log_info "Re-running updated installer..."
    exec "$SCRIPT_PATH" --skip-self-update "${ORIGINAL_ARGS[@]}"
  fi
}

###############################################################################
# Next Steps
###############################################################################

print_next_steps() {
  echo ""

  if $DRY_RUN; then
    echo -e "${BOLD}=== Dry Run Complete ===${NC}"
    echo ""
    echo "Summary:"
    echo "  Files to create:  $DRY_RUN_WOULD_CREATE"
    echo "  Files to update:  $DRY_RUN_WOULD_UPDATE"
    echo "  Files up-to-date: $DRY_RUN_UP_TO_DATE"
    if [ "$DRY_RUN_MODIFIED" -gt 0 ]; then
      echo -e "  ${YELLOW}Files modified:     $DRY_RUN_MODIFIED (would prompt)${NC}"
    fi
    echo ""
    echo "No files were modified. This was a preview of what would happen."
    echo ""
    echo "To perform the actual installation, run without --check:"
    echo "  ./scripts/quest_installer.sh"
    echo ""
    return
  fi

  echo -e "${BOLD}=== Installation Complete ===${NC}"
  echo ""

  if ! $HAS_QUEST; then
    echo "Quest has been installed in this repository."
    echo ""
    echo "Next steps:"
    echo "  1. Review and customize .ai/allowlist.json for your project"
    echo "  2. Review and customize .ai/context_digest.md"
    echo "  3. Commit the Quest files to your repository"
    echo ""
    echo "Optional: Install pre-commit hook to validate Quest config on each commit:"
    echo "  ./scripts/validate-quest-config.sh --install"
    echo "  (Validates: .gitignore has .quest/, allowlist.json is valid, role files have required sections)"
    echo ""
  else
    echo "Quest has been updated to version ${UPSTREAM_SHA:0:8}."
    echo ""
    echo "Review any .quest_updated files for upstream changes to merge."
    echo ""
  fi

  echo "For more information:"
  echo "  - Quest documentation: .ai/quest.md"
  echo "  - Available skills: .skills/SKILLS.md"
  echo "  - Repository: https://github.com/${UPSTREAM_REPO}"

  # Optional interactive docs preview.
  prompt_view_docs
}

###############################################################################
# Main Installation Flow
###############################################################################

run_install() {
  # Auto-cd to repository root if in a subdirectory
  if git rev-parse --show-toplevel &>/dev/null; then
    local git_root
    git_root=$(git rev-parse --show-toplevel)
    if [ "$PWD" != "$git_root" ]; then
      cd "$git_root" || {
        log_error "Could not change to repository root: $git_root"
        exit 1
      }
      log_info "Changed to repository root: $git_root"
    fi
  fi

  # Fetch latest release info for display
  fetch_latest_release

  echo ""
  echo -e "${BOLD}Quest Installer${NC} (latest release: ${LATEST_RELEASE})"

  if [ "$UPSTREAM_BRANCH" != "main" ]; then
    log_info "Using upstream branch: ${UPSTREAM_BRANCH}"
  fi

  if $DRY_RUN; then
    echo ""
    echo -e "${YELLOW}══════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  DRY RUN MODE - No files will be created or modified${NC}"
    echo -e "${YELLOW}══════════════════════════════════════════════════════════${NC}"
  fi
  echo ""

  # Check prerequisites
  check_prerequisites

  # Detect current state (git repo, Quest installed, etc.)
  detect_repo_state

  # Confirm source when defaulting to main with no explicit source flag.
  confirm_install_source

  # Always show selected upstream source for transparency.
  log_info "Using upstream branch: ${UPSTREAM_BRANCH}"

  # Fetch upstream version (sets UPSTREAM_SHA)
  fetch_upstream_version

  # Load file manifest from upstream
  load_manifest

  # Load upstream checksums
  load_upstream_checksums || true

  # Load local checksums
  load_local_checksums

  # Initialize updated checksums from local
  init_updated_checksums

  # Check for self-update (unless already done)
  check_self_update

  # Check if already up to date
  if $HAS_QUEST && [ "$LOCAL_VERSION" = "$UPSTREAM_SHA" ]; then
    log_success "Quest is already up to date (${UPSTREAM_SHA:0:8})"
    exit 0
  fi

  # Show what we're doing
  if $HAS_QUEST; then
    log_info "Updating Quest from ${LOCAL_VERSION:0:8} to ${UPSTREAM_SHA:0:8}"
  else
    log_info "Installing Quest (version ${UPSTREAM_SHA:0:8})"
  fi

  # Suggest creating a branch (if in git repo and not force mode)
  if $IS_GIT_REPO && ! $FORCE_MODE && ! $DRY_RUN; then
    local current_branch
    current_branch=$(git branch --show-current 2>/dev/null || echo "")

    if [ "$current_branch" = "main" ] || [ "$current_branch" = "master" ]; then
      if prompt_yn "Create a new branch for Quest changes?" "y"; then
        local branch_name="quest-update-$(date +%Y%m%d)"
        git checkout -b "$branch_name"
        log_success "Created branch: $branch_name"
      fi
    fi
  fi

  echo ""

  # Create directories
  create_directories

  # Install files by category
  install_copy_as_is
  install_user_customized
  install_merge_carefully

  # Set executable bits
  set_executable_bits

  # Update gitignore
  update_gitignore

  # Save checksums
  save_checksums

  # Update version marker
  update_version_marker

  # Run validation
  run_validation

  # Print next steps
  print_next_steps
}

###############################################################################
# Argument Parsing and Entrypoint
###############################################################################

parse_args() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --check)
        DRY_RUN=true
        shift
        ;;
      --force)
        FORCE_MODE=true
        shift
        ;;
      --branch)
        if [ -z "${2:-}" ]; then
          log_error "--branch requires a branch name"
          exit 1
        fi
        UPSTREAM_BRANCH="$2"
        SOURCE_EXPLICIT=true
        shift 2
        ;;
      --skip-self-update)
        SKIP_SELF_UPDATE=true
        shift
        ;;
      --help|-h)
        show_help
        ;;
      *)
        log_error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
    esac
  done
}

# Store original args for re-exec after self-update
ORIGINAL_ARGS=("$@")

parse_args "$@"
run_install
