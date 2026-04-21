#!/usr/bin/env bash
# Integration tests for .claude/hooks/enforce-allowlist.sh bash->python bridge.
# Run: bash tests/integration/test-enforce-allowlist.sh

set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
HOOK_SCRIPT="$REPO_ROOT/.claude/hooks/enforce-allowlist.sh"

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

if [ ! -x "$HOOK_SCRIPT" ]; then
  echo "[SKIP] Hook script is missing or not executable: $HOOK_SCRIPT"
  exit 0
fi

run_test test_bridge_allows_manifest_validation_command
run_test test_bridge_rejects_compound_bypass

echo ""
echo "Tests run: $TESTS_RUN"
echo "Passed:    $TESTS_PASSED"
echo "Failed:    $TESTS_FAILED"

if [ "$TESTS_FAILED" -ne 0 ]; then
  exit 1
fi
