#!/usr/bin/env bash
# Test harness for scripts/validate-quest-state.sh
# Run: bash tests/test-validate-quest-state.sh
# Exit 0 = all tests pass, 1 = some tests failed

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
SCRIPT="$REPO_ROOT/scripts/validate-quest-state.sh"

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

# Helper: create a minimal valid state.json
create_state_json() {
  local dir="$1"
  local phase="$2"
  local plan_iter="${3:-1}"
  local fix_iter="${4:-0}"
  cat > "$dir/state.json" <<EOF
{
  "quest_id": "test-quest_2026-01-01__0000",
  "slug": "test-quest",
  "phase": "$phase",
  "status": "in_progress",
  "plan_iteration": $plan_iter,
  "fix_iteration": $fix_iter,
  "last_role": "test",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
EOF
}

# ---- Test Cases ----

test_missing_state_json() {
  local tmpdir
  tmpdir=$(mktemp -d)
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -qi "state.json"
}

test_invalid_json() {
  local tmpdir
  tmpdir=$(mktemp -d)
  echo "not json {{{" > "$tmpdir/state.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -qi "json"
}

test_valid_plan_to_plan_reviewed() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  touch "$tmpdir/phase_01_plan/review_claude.md"
  touch "$tmpdir/phase_01_plan/review_codex.md"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_missing_artifact_plan_to_plan_reviewed() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  touch "$tmpdir/phase_01_plan/review_claude.md"
  # Missing review_codex.md
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -q "review_codex.md"
}

test_valid_plan_reviewed_to_building() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan_reviewed"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  echo '{"status":"complete","next":"builder","summary":"approved"}' > "$tmpdir/phase_01_plan/handoff_arbiter.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "building" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_plan_reviewed_to_building_arbiter_says_iterate() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan_reviewed"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  echo '{"status":"complete","next":"planner","summary":"iterate"}' > "$tmpdir/phase_01_plan/handoff_arbiter.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "building" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -qi "arbiter"
}

test_plan_reviewed_to_building_missing_arbiter_handoff() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan_reviewed"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  # No handoff_arbiter.json
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "building" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]"
}

test_valid_building_to_reviewing() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "building"
  mkdir -p "$tmpdir/phase_02_implementation"
  touch "$tmpdir/phase_02_implementation/pr_description.md"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "reviewing" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_building_to_reviewing_empty_dir() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "building"
  mkdir -p "$tmpdir/phase_02_implementation"
  # Empty directory
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "reviewing" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]"
}

test_valid_reviewing_to_complete() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_claude.md"
  touch "$tmpdir/phase_03_review/review_codex.md"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_claude.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_codex.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "complete" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_reviewing_to_complete_has_issues() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_claude.md"
  touch "$tmpdir/phase_03_review/review_codex.md"
  echo '{"status":"complete","next":"fixer","summary":"found issues"}' > "$tmpdir/phase_03_review/handoff_claude.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_codex.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "complete" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -qi "clean"
}

test_valid_reviewing_to_fixing() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_claude.md"
  touch "$tmpdir/phase_03_review/review_codex.md"
  echo '{"status":"complete","next":"fixer","summary":"found issues"}' > "$tmpdir/phase_03_review/handoff_claude.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_codex.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "fixing" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_reviewing_to_fixing_both_clean() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_claude.md"
  touch "$tmpdir/phase_03_review/review_codex.md"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_claude.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_codex.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "fixing" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]"
}

test_invalid_transition() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "complete"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]"
}

test_plan_iteration_exceeded() {
  local tmpdir stderr_file
  tmpdir=$(mktemp -d)
  stderr_file=$(mktemp)
  create_state_json "$tmpdir" "plan" 4 0
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  local output stderr_output
  output=$(bash "$SCRIPT" "$tmpdir" "plan" 2>"$stderr_file")
  local rc=$?
  stderr_output=$(cat "$stderr_file")
  rm -f "$stderr_file"
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ] && echo "$stderr_output" | grep -q "\[WARN\]"
}

test_fix_iteration_exceeded() {
  local tmpdir stderr_file
  tmpdir=$(mktemp -d)
  stderr_file=$(mktemp)
  create_state_json "$tmpdir" "fixing" 1 3
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_fix_feedback_discussion.md"
  local output stderr_output
  output=$(bash "$SCRIPT" "$tmpdir" "reviewing" 2>"$stderr_file")
  local rc=$?
  stderr_output=$(cat "$stderr_file")
  rm -f "$stderr_file"
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ] && echo "$stderr_output" | grep -q "\[WARN\]"
}

test_plan_iteration_within_bounds() {
  local tmpdir stderr_file
  tmpdir=$(mktemp -d)
  stderr_file=$(mktemp)
  create_state_json "$tmpdir" "plan" 2 0
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  local output stderr_output
  output=$(bash "$SCRIPT" "$tmpdir" "plan" 2>"$stderr_file")
  local rc=$?
  stderr_output=$(cat "$stderr_file")
  rm -f "$stderr_file"
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ] && echo "$output" | grep -q "\[PASS\]" && ! echo "$stderr_output" | grep -q "\[WARN\]"
}

test_help_flag() {
  local output
  output=$(bash "$SCRIPT" --help 2>&1)
  local rc=$?
  [ "$rc" -eq 0 ] && echo "$output" | grep -qi "usage"
}

test_missing_args() {
  local output
  output=$(bash "$SCRIPT" 2>&1)
  local rc=$?
  [ "$rc" -eq 2 ] && echo "$output" | grep -qi "usage"
}

test_valid_fixing_to_reviewing() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "fixing" 1 1
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_fix_feedback_discussion.md"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "reviewing" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_building_to_reviewing_no_dir() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "building"
  # No phase_02_implementation directory
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "reviewing" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]"
}

test_nonexistent_quest_dir() {
  local output
  output=$(bash "$SCRIPT" "/nonexistent/path/to/quest" "building" 2>&1)
  local rc=$?
  [ "$rc" -eq 2 ] && echo "$output" | grep -qi "not found"
}

test_non_numeric_iteration_fields() {
  local tmpdir
  tmpdir=$(mktemp -d)
  cat > "$tmpdir/state.json" <<EOF
{
  "quest_id": "test-quest_2026-01-01__0000",
  "slug": "test-quest",
  "phase": "plan",
  "status": "in_progress",
  "plan_iteration": "oops",
  "fix_iteration": "bad",
  "last_role": "test",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
EOF
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -qi "plan_iteration"
}

test_valid_plan_reviewed_to_presenting() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan_reviewed"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "presenting" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_valid_presenting_to_presentation_complete() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "presenting"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "presentation_complete" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_valid_presentation_complete_to_building() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "presentation_complete"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "building" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_non_numeric_allowlist_iterations() {
  local tmpdir stderr_file
  tmpdir=$(mktemp -d)
  stderr_file=$(mktemp)
  create_state_json "$tmpdir" "plan" 2 0
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  # Create a fake git repo with non-numeric allowlist iteration values.
  # The script resolves REPO_ROOT via git rev-parse, so we must run from
  # inside this fake repo for it to pick up the allowlist.
  local fakerepo
  fakerepo=$(mktemp -d)
  git -C "$fakerepo" init --quiet
  mkdir -p "$fakerepo/.ai"
  cat > "$fakerepo/.ai/allowlist.json" <<AEOF
{
  "gates": {
    "max_plan_iterations": "nope",
    "max_fix_iterations": "bad"
  }
}
AEOF
  mkdir -p "$fakerepo/scripts"
  cp "$SCRIPT" "$fakerepo/scripts/validate-quest-state.sh"
  local output stderr_output
  output=$(cd "$fakerepo" && bash scripts/validate-quest-state.sh "$tmpdir" "plan" 2>"$stderr_file")
  local rc=$?
  stderr_output=$(cat "$stderr_file")
  rm -f "$stderr_file"
  rm -rf "$tmpdir" "$fakerepo"
  # Should still pass (warnings only, defaults used), and stderr should have WARN
  [ "$rc" -eq 0 ] && echo "$stderr_output" | grep -q "\[WARN\]" && echo "$stderr_output" | grep -qi "max_plan_iterations"
}

# ---- Run all tests ----

echo "=== Quest State Validation Tests ==="
echo ""

run_test test_missing_state_json
run_test test_invalid_json
run_test test_valid_plan_to_plan_reviewed
run_test test_missing_artifact_plan_to_plan_reviewed
run_test test_valid_plan_reviewed_to_building
run_test test_plan_reviewed_to_building_arbiter_says_iterate
run_test test_plan_reviewed_to_building_missing_arbiter_handoff
run_test test_valid_building_to_reviewing
run_test test_building_to_reviewing_empty_dir
run_test test_valid_reviewing_to_complete
run_test test_reviewing_to_complete_has_issues
run_test test_valid_reviewing_to_fixing
run_test test_reviewing_to_fixing_both_clean
run_test test_invalid_transition
run_test test_plan_iteration_exceeded
run_test test_fix_iteration_exceeded
run_test test_plan_iteration_within_bounds
run_test test_help_flag
run_test test_missing_args
run_test test_valid_fixing_to_reviewing
run_test test_building_to_reviewing_no_dir
run_test test_nonexistent_quest_dir
run_test test_non_numeric_iteration_fields
run_test test_valid_plan_reviewed_to_presenting
run_test test_valid_presenting_to_presentation_complete
run_test test_valid_presentation_complete_to_building
run_test test_non_numeric_allowlist_iterations

echo ""
echo "=== Results ==="
echo "Total: $TESTS_RUN  Passed: $TESTS_PASSED  Failed: $TESTS_FAILED"

if [ "$TESTS_FAILED" -eq 0 ]; then
  echo "All tests passed!"
  exit 0
else
  echo "$TESTS_FAILED test(s) failed"
  exit 1
fi
