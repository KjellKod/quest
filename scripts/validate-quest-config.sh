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
  - .opencode/ files (if directory exists): opencode.json, agents, SKILL.md, command
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

  local role_files=()
  while IFS= read -r role_file; do
    role_files+=("$role_file")
  done < <(find "$quest_roles_dir" -name "*.md" ! -name "README.md" -type f | sort)
  if [ "${#role_files[@]}" -eq 0 ]; then
    fail "No role files found in .skills/quest/agents/"
    return
  fi

  # quest_agent.md in .ai/roles/ is optional; validate if present.
  if [ -f "$quest_agent_file" ]; then
    role_files+=("$quest_agent_file")
  fi

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

# Validate OpenCode files (only if .opencode/ exists)
validate_opencode() {
  if [ ! -d "$REPO_ROOT/.opencode" ]; then
    return
  fi

  echo ""
  echo "--- OpenCode Validation ---"

  # Check opencode.json
  validate_json "$REPO_ROOT/.opencode/opencode.json"

  # Check SKILL.md
  if [ -f "$REPO_ROOT/.opencode/skills/quest/SKILL.md" ]; then
    pass ".opencode/skills/quest/SKILL.md exists"
  else
    fail ".opencode/skills/quest/SKILL.md does not exist"
  fi

  # Check command file
  if [ -f "$REPO_ROOT/.opencode/commands/quest.md" ]; then
    pass ".opencode/commands/quest.md exists"
  else
    fail ".opencode/commands/quest.md does not exist"
  fi

  # Check agent files (expect 6)
  local agent_dir="$REPO_ROOT/.opencode/agents"
  if [ ! -d "$agent_dir" ]; then
    fail ".opencode/agents/ directory does not exist"
    return
  fi

  local agent_count=0
  local agent_file
  for agent_file in "$agent_dir"/*.md; do
    [ -f "$agent_file" ] || continue
    agent_count=$((agent_count + 1))
    local filename
    filename=$(basename "$agent_file")

    # Verify YAML frontmatter (starts with ---, has name: and description:)
    local has_frontmatter=true
    if ! head -1 "$agent_file" | grep -q "^---"; then
      has_frontmatter=false
    fi
    if ! grep -q "^name:" "$agent_file"; then
      has_frontmatter=false
    fi
    if ! grep -q "^description:" "$agent_file"; then
      has_frontmatter=false
    fi

    if [ "$has_frontmatter" = true ]; then
      pass ".opencode/agents/$filename has YAML frontmatter"
    else
      fail ".opencode/agents/$filename missing YAML frontmatter (name/description)"
    fi
  done

  if [ "$agent_count" -ge 6 ]; then
    pass ".opencode/agents/ has $agent_count agent files (expected 6+)"
  else
    fail ".opencode/agents/ has $agent_count agent files (expected 6)"
  fi

  # Check for model drift between allowlist model_routing.opencode and opencode.json
  # Maps allowlist role keys to opencode.json agent keys
  if command -v jq &>/dev/null; then
    local allowlist="$REPO_ROOT/.ai/allowlist.json"
    local ocjson="$REPO_ROOT/.opencode/opencode.json"
    if jq -e '.model_routing.opencode' "$allowlist" &>/dev/null; then
      local drift=false
      # Format: "routing_key:agent_key"
      local mapping
      for mapping in \
        "planner:planner" \
        "reviewer_a:plan-reviewer-a" \
        "reviewer_b:plan-reviewer-b" \
        "builder:builder" \
        "code_reviewer_a:code-reviewer-a" \
        "code_reviewer_b:code-reviewer-b" \
        "arbiter:arbiter"; do
        local routing_key="${mapping%%:*}"
        local agent_key="${mapping##*:}"
        local model_routing model_oc
        model_routing=$(jq -r ".model_routing.opencode.${routing_key} // empty" "$allowlist" 2>/dev/null)
        model_oc=$(jq -r ".agents.\"${agent_key}\".model // empty" "$ocjson" 2>/dev/null)
        if [ -n "$model_routing" ] && [ -n "$model_oc" ] && [ "$model_routing" != "$model_oc" ]; then
          echo -e "${GREEN}[WARN]${NC} Model drift: allowlist model_routing.opencode.${routing_key}=${model_routing} != opencode.json ${agent_key}=${model_oc}"
          drift=true
        elif [ -n "$model_routing" ] && [ -z "$model_oc" ]; then
          echo -e "${GREEN}[WARN]${NC} Model drift: allowlist has model_routing.opencode.${routing_key}=${model_routing} but opencode.json missing ${agent_key}"
          drift=true
        elif [ -z "$model_routing" ] && [ -n "$model_oc" ]; then
          echo -e "${GREEN}[WARN]${NC} Model drift: opencode.json has ${agent_key}=${model_oc} but allowlist missing model_routing.opencode.${routing_key}"
          drift=true
        fi
      done
      if [ "$drift" = false ]; then
        pass "No model drift between allowlist model_routing.opencode and opencode.json"
      fi
    fi
  fi
}

echo "=== Quest Configuration Validation ==="
echo ""

check_gitignore
validate_json "$REPO_ROOT/.ai/allowlist.json"
validate_schema
validate_roles
validate_opencode

echo ""
if [ $ERRORS -eq 0 ]; then
  echo -e "${GREEN}All validations passed!${NC}"
  exit 0
else
  echo -e "${RED}$ERRORS validation(s) failed${NC}"
  exit 1
fi
