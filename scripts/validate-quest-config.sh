#!/usr/bin/env bash
# Quest configuration validation script
# Run locally or as pre-commit hook
# Exit 0 = success, non-zero = failure

set -e

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
SCRIPT_NAME="$(basename "$0")"

# --help: show usage
show_help() {
  cat <<EOF
Usage: $SCRIPT_NAME [OPTIONS]

Validates quest configuration files (.ai/ directory).

Options:
  --install   Install as pre-commit hook (symlink)
  --uninstall Remove pre-commit hook
  --help      Show this help message

When run without options, validates:
  - .quest/ is in .gitignore
  - .ai/allowlist.json is valid JSON
  - .ai/allowlist.json matches schema (if ajv installed)
  - .skills/quest/agents/*.md and .ai/roles/quest_agent.md have required sections
  - .opencode/opencode.json is valid JSON (if present)
  - .opencode/agents/*.md have required frontmatter and ## Output section
  - .opencode/skills/*/SKILL.md have valid frontmatter
  - .opencode/commands/*.md have valid frontmatter
EOF
  exit 0
}

# --install: symlink script as pre-commit hook
install_hook() {
  local hook_path="$REPO_ROOT/.git/hooks/pre-commit"
  local script_path="$REPO_ROOT/scripts/validate-quest-config.sh"

  if [ -e "$hook_path" ]; then
    if [ -L "$hook_path" ]; then
      echo "Replacing existing pre-commit symlink..."
      rm "$hook_path"
    else
      echo "Error: $hook_path already exists and is not a symlink."
      echo "Back it up and remove it first, or manually integrate the validation."
      exit 1
    fi
  fi

  ln -s "../../scripts/validate-quest-config.sh" "$hook_path"
  echo "Installed pre-commit hook: $hook_path -> $script_path"
  exit 0
}

# --uninstall: remove pre-commit hook if it's our symlink
uninstall_hook() {
  local hook_path="$REPO_ROOT/.git/hooks/pre-commit"

  if [ ! -e "$hook_path" ]; then
    echo "No pre-commit hook installed."
    exit 0
  fi

  if [ -L "$hook_path" ]; then
    local target
    target=$(readlink "$hook_path")
    if [[ "$target" == *"validate-quest-config.sh" ]]; then
      rm "$hook_path"
      echo "Removed pre-commit hook."
      exit 0
    fi
  fi

  echo "Error: pre-commit hook exists but is not our symlink. Remove manually."
  exit 1
}

# Parse arguments
case "${1:-}" in
  --help|-h)
    show_help
    ;;
  --install)
    install_hook
    ;;
  --uninstall)
    uninstall_hook
    ;;
esac
ERRORS=0

# Colors for output (disabled if not a terminal)
if [ -t 1 ]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  NC='\033[0m'
else
  RED=''
  GREEN=''
  NC=''
fi

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; ERRORS=$((ERRORS + 1)); }

# Check .quest/ is in .gitignore
check_gitignore() {
  if grep -q "^\.quest/" "$REPO_ROOT/.gitignore" 2>/dev/null || \
     grep -q "^\.quest$" "$REPO_ROOT/.gitignore" 2>/dev/null; then
    pass ".quest/ is in .gitignore"
  else
    fail ".quest/ is NOT in .gitignore - add '.quest/' to prevent committing ephemeral state"
  fi
}

# Validate JSON syntax (pure bash fallback, prefers jq)
validate_json() {
  local file="$1"
  if [ ! -f "$file" ]; then
    fail "$file does not exist"
    return
  fi

  if command -v jq &>/dev/null; then
    if jq empty "$file" 2>/dev/null; then
      pass "$file is valid JSON"
    else
      fail "$file is invalid JSON"
    fi
  else
    # Pure bash: check for basic JSON structure
    if head -c1 "$file" | grep -q '{' && tail -c2 "$file" | grep -q '}'; then
      pass "$file appears to be JSON (install jq for full validation)"
    else
      fail "$file does not appear to be valid JSON"
    fi
  fi
}

# Validate JSON against schema (requires ajv)
validate_schema() {
  local json_file="$REPO_ROOT/.ai/allowlist.json"
  local schema_file="$REPO_ROOT/.ai/schemas/allowlist.schema.json"

  if [ ! -f "$schema_file" ]; then
    fail "Schema file $schema_file does not exist"
    return
  fi

  if command -v ajv &>/dev/null; then
    if ajv validate -s "$schema_file" -d "$json_file" --spec=draft2020 2>/dev/null; then
      pass "allowlist.json validates against schema"
    else
      fail "allowlist.json does not validate against schema"
    fi
  else
    echo -e "${GREEN}[WARN]${NC} Schema validation skipped (ajv not installed)"
  fi
}

# Validate role markdown files have required sections
validate_roles() {
  local quest_roles_dir="$REPO_ROOT/.skills/quest/agents"
  local quest_agent_file="$REPO_ROOT/.ai/roles/quest_agent.md"
  if [ ! -d "$quest_roles_dir" ]; then
    fail ".skills/quest/agents/ directory does not exist"
    return
  fi

  if [ ! -f "$quest_agent_file" ]; then
    fail ".ai/roles/quest_agent.md does not exist"
    return
  fi

  local role_files=()
  while IFS= read -r role_file; do
    role_files+=("$role_file")
  done < <(find "$quest_roles_dir" -name "*.md" ! -name "README.md" -type f | sort)
  if [ "${#role_files[@]}" -eq 0 ]; then
    fail "No role files found in .skills/quest/agents/"
    return
  fi

  # quest_agent.md stays in .ai/roles/ and must be validated too.
  role_files+=("$quest_agent_file")

  local role_file
  for role_file in "${role_files[@]}"; do
    local filename
    filename=$(basename "$role_file")
    local missing=""

    # Check ## Role OR ## Overview (both describe the role's purpose)
    if ! grep -q "^## Role" "$role_file" && ! grep -q "^## Overview" "$role_file"; then
      missing="$missing Role/Overview,"
    fi

    # Check for Tool OR Instances (plan_review_agent uses Instances)
    if ! grep -q "^## Tool" "$role_file" && ! grep -q "^## Instances" "$role_file"; then
      missing="$missing Tool/Instances,"
    fi

    # Check for Context Required OR Context Available OR Overview
    if ! grep -q "^## Context Required" "$role_file" && \
       ! grep -q "^## Context Available" "$role_file" && \
       ! grep -q "^## Overview" "$role_file"; then
      missing="$missing Context Required/Context Available/Overview,"
    fi

    # Check ## Output Contract (required for all)
    grep -q "^## Output Contract" "$role_file" || missing="$missing Output Contract,"

    # quest_agent.md is exempt from Responsibilities and Allowed Actions
    # because its Routing Rules table serves the same purpose
    if [ "$filename" != "quest_agent.md" ]; then
      grep -q "^## Responsibilities" "$role_file" || missing="$missing Responsibilities,"
      grep -q "^## Allowed Actions" "$role_file" || missing="$missing Allowed Actions,"
    fi

    if [ -z "$missing" ]; then
      pass "$filename has all required sections"
    else
      missing="${missing%,}" # Remove trailing comma
      fail "$filename missing sections:$missing"
    fi
  done
}

# Validate OpenCode opencode.json
validate_opencode_json() {
  local opencode_json="$REPO_ROOT/.opencode/opencode.json"
  if [ ! -f "$opencode_json" ]; then
    fail ".opencode/opencode.json does not exist"
    return
  fi

  if command -v jq &>/dev/null; then
    if jq empty "$opencode_json" 2>/dev/null; then
      pass ".opencode/opencode.json is valid JSON"
    else
      fail ".opencode/opencode.json is invalid JSON"
    fi
  else
    # Pure bash: check for basic JSON structure
    if head -c1 "$opencode_json" | grep -q '{' && tail -c2 "$opencode_json" | grep -q '}'; then
      pass ".opencode/opencode.json appears to be JSON (install jq for full validation)"
    else
      fail ".opencode/opencode.json does not appear to be valid JSON"
    fi
  fi
}

# Validate OpenCode agent files have required frontmatter and sections
validate_opencode_agents() {
  local agents_dir="$REPO_ROOT/.opencode/agents"
  if [ ! -d "$agents_dir" ]; then
    fail ".opencode/agents/ directory does not exist"
    return
  fi

  local agent_files=()
  while IFS= read -r agent_file; do
    agent_files+=("$agent_file")
  done < <(find "$agents_dir" -name "*.md" ! -name "README.md" -type f | sort)

  if [ "${#agent_files[@]}" -eq 0 ]; then
    fail "No agent files found in .opencode/agents/"
    return
  fi

  local agent_file
  for agent_file in "${agent_files[@]}"; do
    local filename
    filename=$(basename "$agent_file")
    local missing=""

    # Check YAML frontmatter exists (--- at start)
    if ! head -3 "$agent_file" | grep -q "^---"; then
      missing="$missing YAML frontmatter,"
    fi

    # Check frontmatter contains name: field
    if ! grep -q "^name:" "$agent_file"; then
      missing="$missing name: field,"
    fi

    # Check frontmatter contains description: field
    if ! grep -q "^description:" "$agent_file"; then
      missing="$missing description: field,"
    fi

    # Check for ## Output section
    if ! grep -q "^## Output" "$agent_file"; then
      missing="$missing ## Output section,"
    fi

    if [ -z "$missing" ]; then
      pass "$filename has all required frontmatter and sections"
    else
      missing="${missing%,}" # Remove trailing comma
      fail "$filename missing:$missing"
    fi
  done
}

# Validate OpenCode skill files have valid frontmatter
validate_opencode_skills() {
  local skills_dir="$REPO_ROOT/.opencode/skills"
  if [ ! -d "$skills_dir" ]; then
    fail ".opencode/skills/ directory does not exist"
    return
  fi

  local skill_files=()
  while IFS= read -r skill_file; do
    skill_files+=("$skill_file")
  done < <(find "$skills_dir" -name "SKILL.md" -type f | sort)

  if [ "${#skill_files[@]}" -eq 0 ]; then
    fail "No SKILL.md files found in .opencode/skills/"
    return
  fi

  local skill_file
  for skill_file in "${skill_files[@]}"; do
    local filename
    filename=$(basename "$skill_file")
    local skill_name
    skill_name=$(dirname "$skill_file" | xargs basename)
    local missing=""

    # Check YAML frontmatter exists (--- at start)
    if ! head -3 "$skill_file" | grep -q "^---"; then
      missing="$missing YAML frontmatter,"
    fi

    # Check frontmatter contains name: field
    if ! grep -q "^name:" "$skill_file"; then
      missing="$missing name: field,"
    fi

    # Check frontmatter contains description: field
    if ! grep -q "^description:" "$skill_file"; then
      missing="$missing description: field,"
    fi

    if [ -z "$missing" ]; then
      pass "$skill_name/SKILL.md has valid frontmatter"
    else
      missing="${missing%,}" # Remove trailing comma
      fail "$skill_name/SKILL.md missing:$missing"
    fi
  done
}

# Validate OpenCode command files have valid frontmatter
validate_opencode_commands() {
  local commands_dir="$REPO_ROOT/.opencode/commands"
  if [ ! -d "$commands_dir" ]; then
    fail ".opencode/commands/ directory does not exist"
    return
  fi

  local command_files=()
  while IFS= read -r command_file; do
    command_files+=("$command_file")
  done < <(find "$commands_dir" -name "*.md" ! -name "README.md" -type f | sort)

  if [ "${#command_files[@]}" -eq 0 ]; then
    fail "No command files found in .opencode/commands/"
    return
  fi

  local command_file
  for command_file in "${command_files[@]}"; do
    local filename
    filename=$(basename "$command_file")
    local missing=""

    # Check YAML frontmatter exists (--- at start)
    if ! head -3 "$command_file" | grep -q "^---"; then
      missing="$missing YAML frontmatter,"
    fi

    # Check frontmatter contains description: field
    if ! grep -q "^description:" "$command_file"; then
      missing="$missing description: field,"
    fi

    if [ -z "$missing" ]; then
      pass "$filename has valid frontmatter"
    else
      missing="${missing%,}" # Remove trailing comma
      fail "$filename missing:$missing"
    fi
  done
}

echo "=== Quest Configuration Validation ==="
echo ""

check_gitignore
validate_json "$REPO_ROOT/.ai/allowlist.json"
validate_schema
validate_roles

# OpenCode validation (if .opencode/ directory exists)
if [ -d "$REPO_ROOT/.opencode" ]; then
  validate_opencode_json
  validate_opencode_agents
  validate_opencode_skills
  validate_opencode_commands
else
  echo -e "${GREEN}[SKIP]${NC} .opencode/ directory not found - skipping OpenCode validation"
fi

echo ""
if [ $ERRORS -eq 0 ]; then
  echo -e "${GREEN}All validations passed!${NC}"
  exit 0
else
  echo -e "${RED}$ERRORS validation(s) failed${NC}"
  exit 1
fi
