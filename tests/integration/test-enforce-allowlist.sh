#!/usr/bin/env bash
# Integration tests for .claude/hooks/enforce-allowlist.sh bash->python bridge.
# Run: bash tests/integration/test-enforce-allowlist.sh

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
HOOK_SCRIPT="$REPO_ROOT/.claude/hooks/enforce-allowlist.sh"
ALLOWLIST_FILE="$REPO_ROOT/.ai/allowlist.json"

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

run_test() {
  local name="$1"
  TESTS_RUN=$((TESTS_RUN + 1))
  if "$name"; then
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo "[PASS] $name"
  else
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo "[FAIL] $name"
  fi
}

run_hook_for_command() {
  local role="$1"
  local command="$2"
  local payload
  payload=$(jq -cn --arg cmd "$command" '{tool:"Bash",input:{command:$cmd}}')
  printf '%s' "$payload" | "$HOOK_SCRIPT" "$role"
}

run_hook_for_write() {
  local role="$1"
  local file_path="$2"
  local payload
  payload=$(jq -cn --arg path "$file_path" '{tool:"Write",input:{file_path:$path}}')
  printf '%s' "$payload" | "$HOOK_SCRIPT" "$role"
}

set_builder_file_write_patterns() {
  local patterns_json="$1"
  python3 - "$ALLOWLIST_FILE" "$patterns_json" <<'PY'
import json
import sys

path = sys.argv[1]
patterns = json.loads(sys.argv[2])
with open(path, encoding="utf-8") as fh:
    data = json.load(fh)
data["role_permissions"]["builder_agent"]["file_write"] = patterns
with open(path, "w", encoding="utf-8") as fh:
    json.dump(data, fh, indent=2)
    fh.write("\n")
PY
}

test_bridge_allows_manifest_validation_command() {
  local output rc
  output=$(run_hook_for_command "builder_agent" "bash scripts/quest_validate-manifest.sh" 2>&1)
  rc=$?
  [ "$rc" -eq 0 ] && [ -z "$output" ]
}

test_bridge_rejects_compound_bypass() {
  local output rc
  output=$(run_hook_for_command "builder_agent" "python3 -m pytest && rm -rf /" 2>&1)
  rc=$?
  [ "$rc" -eq 2 ] &&
    echo "$output" | grep -q "BLOCKED:" &&
    echo "$output" | grep -q "blocked_metacharacter"
}

test_file_write_allows_nested_double_star_path() {
  local output rc
  output=$(run_hook_for_write "builder_agent" "$REPO_ROOT/scripts/quest_dashboard/render.py" 2>&1)
  rc=$?
  [ "$rc" -eq 0 ] && [ -z "$output" ]
}

test_file_write_allows_nested_docs_output() {
  local output rc
  output=$(run_hook_for_write "builder_agent" "$REPO_ROOT/docs/dashboard/index.html" 2>&1)
  rc=$?
  [ "$rc" -eq 0 ] && [ -z "$output" ]
}

test_file_write_allows_root_markdown_for_double_star_slash_pattern() {
  local backup output_root output_nested rc_root rc_nested
  backup=$(mktemp) || return 1
  cp "$ALLOWLIST_FILE" "$backup" || {
    rm -f "$backup"
    return 1
  }
  trap 'mv "$backup" "$ALLOWLIST_FILE"' RETURN

  set_builder_file_write_patterns '["**/*.md"]' || return 1

  output_root=$(run_hook_for_write "builder_agent" "$REPO_ROOT/README.md" 2>&1)
  rc_root=$?
  output_nested=$(run_hook_for_write "builder_agent" "$REPO_ROOT/docs/guides/quest_setup.md" 2>&1)
  rc_nested=$?

  trap - RETURN
  mv "$backup" "$ALLOWLIST_FILE" || return 1

  [ "$rc_root" -eq 0 ] &&
    [ -z "$output_root" ] &&
    [ "$rc_nested" -eq 0 ] &&
    [ -z "$output_nested" ]
}

test_file_write_allows_role_scoped_quest_path() {
  local output rc
  output=$(run_hook_for_write "arbiter_agent" "$REPO_ROOT/.quest/state.json" 2>&1)
  rc=$?
  [ "$rc" -eq 0 ] && [ -z "$output" ]
}

test_file_write_rejects_traversal_out_of_allowed_root() {
  local output rc
  output=$(run_hook_for_write "arbiter_agent" "$REPO_ROOT/.quest/../scripts/quest_state.py" 2>&1)
  rc=$?
  [ "$rc" -eq 2 ] &&
    echo "$output" | grep -q "BLOCKED:" &&
    echo "$output" | grep -q ".quest/../scripts/quest_state.py"
}

test_file_write_rejects_unlisted_dashboard_source_path() {
  local output rc
  output=$(run_hook_for_write "builder_agent" "$REPO_ROOT/dashboard/src/App.tsx" 2>&1)
  rc=$?
  [ "$rc" -eq 2 ] &&
    echo "$output" | grep -q "BLOCKED:" &&
    echo "$output" | grep -q "dashboard/src/App.tsx"
}

if [ ! -x "$HOOK_SCRIPT" ]; then
  echo "[SKIP] Hook script is missing or not executable: $HOOK_SCRIPT"
  exit 0
fi

run_test test_bridge_allows_manifest_validation_command
run_test test_bridge_rejects_compound_bypass
run_test test_file_write_allows_nested_double_star_path
run_test test_file_write_allows_nested_docs_output
run_test test_file_write_allows_root_markdown_for_double_star_slash_pattern
run_test test_file_write_allows_role_scoped_quest_path
run_test test_file_write_rejects_traversal_out_of_allowed_root
run_test test_file_write_rejects_unlisted_dashboard_source_path

echo ""
echo "Tests run: $TESTS_RUN"
echo "Passed:    $TESTS_PASSED"
echo "Failed:    $TESTS_FAILED"

if [ "$TESTS_FAILED" -ne 0 ]; then
  exit 1
fi
