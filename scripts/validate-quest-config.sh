#!/usr/bin/env bash
# Quest configuration validation script
# Run locally or as pre-commit hook
# Exit 0 = success, non-zero = failure
#
# Usage:
#   ./scripts/validate-quest-config.sh
#
# Pre-commit hook installation:
#   cp scripts/validate-quest-config.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit

set -e

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
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
  local roles_dir="$REPO_ROOT/.ai/roles"
  if [ ! -d "$roles_dir" ]; then
    fail ".ai/roles/ directory does not exist"
    return
  fi

  local role_files
  role_files=$(find "$roles_dir" -name "*.md" -type f)

  if [ -z "$role_files" ]; then
    fail "No role files found in .ai/roles/"
    return
  fi

  for role_file in $role_files; do
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

echo "=== Quest Configuration Validation ==="
echo ""

check_gitignore
validate_json "$REPO_ROOT/.ai/allowlist.json"
validate_schema
validate_roles

echo ""
if [ $ERRORS -eq 0 ]; then
  echo -e "${GREEN}All validations passed!${NC}"
  exit 0
else
  echo -e "${RED}$ERRORS validation(s) failed${NC}"
  exit 1
fi
