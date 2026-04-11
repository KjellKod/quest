#!/usr/bin/env bash
# Test harness for scripts/quest_validate-handoff-contracts.sh
# Run: bash tests/test-validate-handoff-contracts.sh

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
SCRIPT="$REPO_ROOT/scripts/quest_validate-handoff-contracts.sh"

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

test_validate_handoff_contracts_passes() {
  local output
  output=$(bash "$SCRIPT" 2>&1)
  local rc=$?
  [ "$rc" -eq 0 ] && echo "$output" | grep -q "All checks passed"
}

test_validate_handoff_contracts_checks_bridge_runtime_dispatch() {
  local output
  output=$(bash "$SCRIPT" 2>&1)
  local rc=$?
  [ "$rc" -eq 0 ] && echo "$output" | grep -q "Workflow documents bridge probing and runtime-based dispatch"
}

run_test test_validate_handoff_contracts_passes
run_test test_validate_handoff_contracts_checks_bridge_runtime_dispatch

echo ""
echo "Tests run: $TESTS_RUN"
echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"

if [ "$TESTS_FAILED" -eq 0 ]; then
  exit 0
else
  exit 1
fi
