#!/usr/bin/env bash
# Quest Installer Script
# Installs and updates Quest in any repository
# Usage: quest_installer.sh [--check|--force|--help]
#
# Copyright (c) 2026 Quest Authors
# License: MIT

set -e

###############################################################################
# Configuration Constants
###############################################################################

SCRIPT_VERSION="1.0.0"
UPSTREAM_REPO="KjellKod/quest"
UPSTREAM_BRANCH="choices"
RAW_BASE="https://raw.githubusercontent.com/${UPSTREAM_REPO}"
SCRIPT_NAME="$(basename "$0")"

# Resolve script path reliably (handles both direct execution and sourcing)
# Uses BASH_SOURCE[0] instead of $0 to handle "bash script.sh" invocation
SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

# Mode flags (set by argument parsing)
DRY_RUN=false
FORCE_MODE=false
SKIP_SELF_UPDATE=false

# State variables (set during execution)
IS_GIT_REPO=false
HAS_QUEST=false
LOCAL_VERSION=""
UPSTREAM_SHA=""

###############################################################################
# Cleanup Trap
###############################################################################

cleanup() {
  rm -f ".quest-checksums.tmp.$$" 2>/dev/null
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

log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
  echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

log_action() {
  if $DRY_RUN; then
    echo -e "${YELLOW}[DRY-RUN]${NC} Would: $1"
  else
    echo -e "${GREEN}[ACTION]${NC} $1"
  fi
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
  cat <<EOF
${BOLD}Quest Installer${NC} v${SCRIPT_VERSION}

Installs and updates Quest in any repository.

${BOLD}Usage:${NC}
  $SCRIPT_NAME [OPTIONS]

${BOLD}Options:${NC}
  --check     Dry-run mode: show what would change without modifying files
  --force     Non-interactive mode: accept safe defaults, skip modified files
  --help      Show this help message

${BOLD}Examples:${NC}
  $SCRIPT_NAME              # Interactive install/update
  $SCRIPT_NAME --check      # Preview changes
  $SCRIPT_NAME --force      # CI/automation mode

${BOLD}File Categories:${NC}
  - Copy as-is:      Replaced with upstream (if unmodified)
  - User-customized: Never overwritten (.quest_updated suffix for upstream changes)
  - Merge carefully: Manual merge offered for settings files

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
    log_warn "Could not fetch checksums.txt - will calculate checksums from content"
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
  # Check if in git repo
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
  local upstream_content="$2"

  echo ""
  echo -e "${BOLD}--- Local: $filepath${NC}"
  echo -e "${BOLD}+++ Upstream: $filepath${NC}"
  echo ""

  if command -v diff &>/dev/null; then
    # Create temp file for upstream content
    local tmp_file
    tmp_file=$(mktemp)
    printf '%s\n' "$upstream_content" > "$tmp_file"
    diff -u "$filepath" "$tmp_file" || true
    rm -f "$tmp_file"
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

  # Fetch upstream content
  local upstream_content
  if ! upstream_content=$(fetch_file "$filepath" 2>/dev/null); then
    log_warn "Could not fetch: $filepath (may not exist in upstream yet)"
    return 0  # Continue with other files
  fi

  # Get upstream checksum (from manifest or calculate)
  local upstream_checksum
  if ! upstream_checksum=$(get_upstream_checksum "$filepath"); then
    # Calculate from fetched content
    upstream_checksum=$(echo "$upstream_content" | get_content_checksum)
  fi

  # Case 1: File does not exist locally
  if [ ! -f "$filepath" ]; then
    ensure_parent_dir "$filepath"
    if $DRY_RUN; then
      log_action "Create: $filepath"
    else
      printf '%s\n' "$upstream_content" > "$filepath"
      log_success "Created: $filepath"
    fi
    set_updated_checksum "$filepath" "$upstream_checksum"
    return 0
  fi

  # File exists - check if it matches upstream (optimization from arbiter)
  local local_checksum
  local_checksum=$(get_file_checksum "$filepath")

  if [ "$local_checksum" = "$upstream_checksum" ]; then
    # Already up to date - just ensure checksum is stored
    set_updated_checksum "$filepath" "$upstream_checksum"
    return 0
  fi

  # Case 2: File exists and is pristine (unmodified from last install)
  if is_file_pristine "$filepath"; then
    if $DRY_RUN; then
      log_action "Update: $filepath"
    else
      printf '%s\n' "$upstream_content" > "$filepath"
      log_success "Updated: $filepath"
    fi
    set_updated_checksum "$filepath" "$upstream_checksum"
    return 0
  fi

  # Case 3: File exists and has local modifications
  if $DRY_RUN; then
    log_warn "Modified: $filepath (would prompt to overwrite/skip)"
    return 0
  fi

  if $FORCE_MODE; then
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
        printf '%s\n' "$upstream_content" > "$filepath"
        log_success "Overwrote: $filepath"
        set_updated_checksum "$filepath" "$upstream_checksum"
        return 0
        ;;
      s)
        # Skip
        log_info "Skipped: $filepath"
        local existing
        if existing=$(get_stored_checksum "$filepath"); then
          set_updated_checksum "$filepath" "$existing"
        fi
        return 0
        ;;
      d)
        # Show diff and re-prompt
        show_diff "$filepath" "$upstream_content"
        ;;
    esac
  done
}

###############################################################################
# User-Customized File Installation
###############################################################################

install_user_customized() {
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

  # Fetch upstream content
  local upstream_content
  if ! upstream_content=$(fetch_file "$filepath" 2>/dev/null); then
    log_warn "Could not fetch: $filepath (may not exist in upstream yet)"
    return 0  # Continue with other files
  fi

  # Case 1: File does not exist locally - create it
  if [ ! -f "$filepath" ]; then
    ensure_parent_dir "$filepath"
    if $DRY_RUN; then
      log_action "Create: $filepath (customize after install)"
    else
      printf '%s\n' "$upstream_content" > "$filepath"
      log_success "Created: $filepath (customize as needed)"
    fi
    return 0
  fi

  # Case 2: File exists - check if upstream has changes
  local local_checksum upstream_checksum
  local_checksum=$(get_file_checksum "$filepath")
  upstream_checksum=$(echo "$upstream_content" | get_content_checksum)

  if [ "$local_checksum" = "$upstream_checksum" ]; then
    # No changes
    return 0
  fi

  # Upstream differs - create .quest_updated file
  local updated_path="${filepath}.quest_updated"
  if $DRY_RUN; then
    log_action "Create: $updated_path (upstream has changes)"
  else
    printf '%s\n' "$upstream_content" > "$updated_path"
    log_warn "Created: $updated_path (review and merge manually)"
  fi
}

###############################################################################
# Merge-Carefully File Installation
###############################################################################

install_merge_carefully() {
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

  # Fetch upstream content
  local upstream_content
  if ! upstream_content=$(fetch_file "$filepath" 2>/dev/null); then
    # File may not exist in upstream (e.g., settings.local.json)
    return 0
  fi

  # Case 1: File does not exist locally - create it
  if [ ! -f "$filepath" ]; then
    ensure_parent_dir "$filepath"
    if $DRY_RUN; then
      log_action "Create: $filepath"
    else
      printf '%s\n' "$upstream_content" > "$filepath"
      log_success "Created: $filepath"
    fi
    return 0
  fi

  # Case 2: File exists - check if upstream has changes
  local local_checksum upstream_checksum
  local_checksum=$(get_file_checksum "$filepath")
  upstream_checksum=$(echo "$upstream_content" | get_content_checksum)

  if [ "$local_checksum" = "$upstream_checksum" ]; then
    # No changes
    return 0
  fi

  # Upstream differs - handle based on mode
  if $FORCE_MODE; then
    # In force mode, create .quest_updated file (safe default)
    local updated_path="${filepath}.quest_updated"
    if $DRY_RUN; then
      log_action "Create: $updated_path (upstream has changes)"
    else
      printf '%s\n' "$upstream_content" > "$updated_path"
      log_warn "Created: $updated_path (merge manually)"
    fi
    return 0
  fi

  # Interactive mode - show diff and offer options
  echo ""
  log_warn "Settings file has upstream changes: $filepath"
  show_diff "$filepath" "$upstream_content"

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
        printf '%s\n' "$upstream_content" > "$filepath"
        log_success "Overwrote: $filepath"
      fi
      ;;
    [uU])
      local updated_path="${filepath}.quest_updated"
      if $DRY_RUN; then
        log_action "Create: $updated_path"
      else
        printf '%s\n' "$upstream_content" > "$updated_path"
        log_info "Created: $updated_path (merge manually)"
      fi
      ;;
    *)
      log_info "Skipped: $filepath"
      ;;
  esac
}

###############################################################################
# Set Executable Bits
###############################################################################

set_executable_bits() {
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
    echo "  3. Optionally install the pre-commit hook:"
    echo "     ./scripts/validate-quest-config.sh --install"
    echo "  4. Commit the Quest files to your repository"
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
}

###############################################################################
# Main Installation Flow
###############################################################################

run_install() {
  echo ""
  echo -e "${BOLD}Quest Installer${NC} v${SCRIPT_VERSION}"

  if $DRY_RUN; then
    echo ""
    echo -e "${YELLOW}══════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  DRY RUN MODE - No files will be created or modified${NC}"
    echo -e "${YELLOW}══════════════════════════════════════════════════════════${NC}"
  fi
  echo ""

  # Check prerequisites
  check_prerequisites

  # Detect current state
  detect_repo_state

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
