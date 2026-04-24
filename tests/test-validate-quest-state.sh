#!/usr/bin/env bash
# Test harness for scripts/quest_validate-quest-state.sh
# Run: bash tests/test-validate-quest-state.sh
# Exit 0 = all tests pass, 1 = some tests failed

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
SCRIPT="$REPO_ROOT/scripts/quest_validate-quest-state.sh"

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
  local quest_mode="${5:-workflow}"
  cat > "$dir/state.json" <<EOF
{
  "quest_id": "test-quest_2026-01-01__0000",
  "slug": "test-quest",
  "phase": "$phase",
  "status": "in_progress",
  "quest_mode": "$quest_mode",
  "plan_iteration": $plan_iter,
  "fix_iteration": $fix_iter,
  "last_role": "test",
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
EOF
}

write_valid_review_findings() {
  local filepath="$1"
  cat > "$filepath" <<EOF
[
  {
    "finding_id": "PF-001",
    "source": "plan-reviewer-a",
    "kind": "plan_review",
    "severity": "medium",
    "confidence": "medium",
    "path": "phase_01_plan/plan.md",
    "line": null,
    "summary": "Clarify acceptance criteria mapping.",
    "why_it_matters": "Planner/builder alignment depends on explicit AC mapping.",
    "evidence": ["Reviewer note"],
    "action": "Add explicit AC coverage lines.",
    "needs_test": false,
    "write_scope": ["phase_01_plan/plan.md"],
    "related_acceptance_criteria": ["AC-1"]
  }
]
EOF
}

write_review_backlog() {
  local filepath="$1"
  local mode="$2"
  local phase="${3:-review}"
  local decision="drop"
  local needs_validation='[]'
  local needs_test='false'
  local owner="scripts"
  local batch="scripts/example.py"

  case "$mode" in
    actionable)
      decision="fix_now"
      needs_validation='["unit_test"]'
      needs_test='true'
      ;;
    human_decision)
      decision="needs_human_decision"
      ;;
    clean)
      decision="drop"
      ;;
    plan_actionable)
      # Plan-phase canonical: every item flows to the builder.
      decision="fix_now"
      needs_validation='["unit_test", "typecheck", "lint"]'
      needs_test='true'
      phase="plan"
      owner="builder"
      batch="correctness-scripts"
      ;;
    plan_verify_first)
      decision="verify_first"
      needs_validation='["unit_test", "typecheck", "lint"]'
      needs_test='true'
      phase="plan"
      owner="builder"
      batch="correctness-scripts"
      ;;
    *)
      decision="drop"
      ;;
  esac

  cat > "$filepath" <<EOF
{
  "version": 1,
  "generated_at": "2026-04-16T00:00:00Z",
  "at_loop_cap": false,
  "phase": "$phase",
  "allowed_decisions": [
    "fix_now",
    "verify_first",
    "defer",
    "drop",
    "needs_human_decision"
  ],
  "counts": {
    "fix_now": $([ "$decision" = "fix_now" ] && echo 1 || echo 0),
    "verify_first": $([ "$decision" = "verify_first" ] && echo 1 || echo 0),
    "defer": 0,
    "drop": $([ "$decision" = "drop" ] && echo 1 || echo 0),
    "needs_human_decision": $([ "$decision" = "needs_human_decision" ] && echo 1 || echo 0)
  },
  "items": [
    {
      "finding_id": "RF-001",
      "source": "code-reviewer-a",
      "kind": "correctness",
      "severity": "medium",
      "confidence": "medium",
      "path": "scripts/example.py",
      "line": 10,
      "summary": "Example review backlog item.",
      "why_it_matters": "Used to validate backlog contract handling.",
      "evidence": ["Example evidence"],
      "action": "Add targeted coverage.",
      "needs_test": $needs_test,
      "write_scope": ["scripts/example.py"],
      "related_acceptance_criteria": ["AC-1"],
      "decision": "$decision",
      "decision_confidence": "medium",
      "reason": "Example reason",
      "needs_validation": $needs_validation,
      "owner": "$owner",
      "batch": "$batch"
    }
  ]
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
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-a.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-b.md"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  write_valid_review_findings "$tmpdir/phase_01_plan/review_findings.json"
  write_review_backlog "$tmpdir/phase_01_plan/review_backlog.json" "plan_actionable"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_valid_plan_to_plan_reviewed_solo_without_findings() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan" 1 0 "solo"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-a.md"
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
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-a.md"
  # Missing review_plan-reviewer-b.md
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  write_valid_review_findings "$tmpdir/phase_01_plan/review_findings.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -q "review_plan-reviewer-b.md"
}

test_plan_to_plan_reviewed_requires_canonical_artifacts_in_workflow_mode() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-a.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-b.md"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "review_findings.json" && echo "$output" | grep -q "review_backlog.json"
}

test_plan_reviewed_to_building_rejected() {
  # plan_reviewed->building is no longer allowed; presentation is mandatory.
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
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -q "Invalid transition"
}

test_presentation_complete_to_building_arbiter_approved() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "presentation_complete"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  echo '{"status":"complete","next":"builder","summary":"approved"}' > "$tmpdir/phase_01_plan/handoff_arbiter.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "building" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_presentation_complete_to_building_arbiter_says_iterate() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "presentation_complete"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  echo '{"status":"complete","next":"planner","summary":"iterate"}' > "$tmpdir/phase_01_plan/handoff_arbiter.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "building" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -qi "arbiter"
}

test_presentation_complete_to_building_missing_arbiter_handoff() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "presentation_complete"
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
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  write_review_backlog "$tmpdir/phase_03_review/review_backlog.json" "clean"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
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
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  write_review_backlog "$tmpdir/phase_03_review/review_backlog.json" "actionable"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "complete" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -qi "actionable"
}

test_reviewing_to_complete_blocked_by_needs_human_decision() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  write_review_backlog "$tmpdir/phase_03_review/review_backlog.json" "human_decision"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "complete" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "needs_human_decision"
}

test_reviewing_to_complete_blocked_by_reviewer_fixer_handoff() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  write_review_backlog "$tmpdir/phase_03_review/review_backlog.json" "clean"
  echo '{"status":"complete","next":"fixer","summary":"found issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "complete" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "code-reviewer-a requested fixes"
}

test_reviewing_to_complete_requires_reviewer_handoffs() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  write_review_backlog "$tmpdir/phase_03_review/review_backlog.json" "clean"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "complete" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "handoff_code-reviewer-a.json" && echo "$output" | grep -q "handoff_code-reviewer-b.json"
}

test_reviewing_to_complete_rejects_invalid_reviewer_handoff_json() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  write_review_backlog "$tmpdir/phase_03_review/review_backlog.json" "clean"
  echo 'not-json' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "complete" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "handoff is not valid JSON"
}

test_reviewing_to_complete_rejects_missing_next_in_handoff() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  write_review_backlog "$tmpdir/phase_03_review/review_backlog.json" "clean"
  echo '{"status":"complete","summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "complete" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q 'handoff next must be explicitly present'
}

test_reviewing_to_complete_rejects_blocked_reviewer_handoff_status() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  write_review_backlog "$tmpdir/phase_03_review/review_backlog.json" "clean"
  echo '{"status":"blocked","next":null,"summary":"stopped"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "complete" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q 'reviewer handoff status must be explicitly present and equal "complete"'
}

test_reviewing_to_complete_rejects_needs_human_reviewer_handoff_status() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  write_review_backlog "$tmpdir/phase_03_review/review_backlog.json" "clean"
  echo '{"status":"needs_human","next":null,"summary":"need input"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "complete" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q 'reviewer handoff status must be explicitly present and equal "complete"'
}

test_reviewing_to_complete_rejects_invalid_review_backlog_schema() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  cat > "$tmpdir/phase_03_review/review_backlog.json" <<EOF
{
  "version": 1,
  "items": [
    {
      "finding_id": "RF-001",
      "decision": "drop"
    }
  ]
}
EOF
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "complete" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "review backlog schema invalid"
}

test_plan_to_plan_reviewed_rejects_invalid_backlog_item_schema() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-a.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-b.md"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  write_valid_review_findings "$tmpdir/phase_01_plan/review_findings.json"
  cat > "$tmpdir/phase_01_plan/review_backlog.json" <<EOF
{
  "version": 1,
  "items": [
    {
      "finding_id": "RF-001",
      "decision": "bogus"
    }
  ]
}
EOF
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "review backlog schema invalid"
}

test_plan_to_plan_reviewed_rejects_false_typed_backlog_fields() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-a.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-b.md"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  write_valid_review_findings "$tmpdir/phase_01_plan/review_findings.json"
  write_review_backlog "$tmpdir/phase_01_plan/review_backlog.json" "clean"
  python3 - <<'PY' "$tmpdir/phase_01_plan/review_backlog.json"
import json
import sys
path = sys.argv[1]
data = json.loads(open(path, encoding="utf-8").read())
data["items"][0]["decision"] = False
data["items"][0]["line"] = False
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
    handle.write("\n")
PY
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "invalid decision" && echo "$output" | grep -q "field 'line' must be null or an integer >= 1"
}

test_plan_to_plan_reviewed_rejects_invalid_backlog_finding_fields() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-a.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-b.md"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  write_valid_review_findings "$tmpdir/phase_01_plan/review_findings.json"
  write_review_backlog "$tmpdir/phase_01_plan/review_backlog.json" "clean"
  python3 - <<'PY' "$tmpdir/phase_01_plan/review_backlog.json"
import json
import sys
path = sys.argv[1]
data = json.loads(open(path, encoding="utf-8").read())
data["items"][0]["severity"] = "bogus"
data["items"][0]["summary"] = ""
with open(path, "w", encoding="utf-8") as handle:
    json.dump(data, handle, indent=2)
    handle.write("\n")
PY
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "review backlog schema invalid" && echo "$output" | grep -q "field 'severity'" && echo "$output" | grep -q "field 'summary'"
}

test_plan_to_plan_reviewed_rejects_review_phase_backlog() {
  # Guard: a future orchestrator that forgets --phase plan would build a
  # review-phase backlog (with decision values like verify_first/drop) and
  # still pass schema checks. The validator must reject it so approved
  # plans never fall through without canonical plan-phase defaults.
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-a.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-b.md"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  write_valid_review_findings "$tmpdir/phase_01_plan/review_findings.json"
  # "actionable" mode with default phase="review" -> schema valid but
  # phase mismatch.
  write_review_backlog "$tmpdir/phase_01_plan/review_backlog.json" "actionable" "review"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -q "expected phase='plan'"
}

test_plan_to_plan_reviewed_rejects_non_actionable_decision() {
  # Plan-phase approval requires every item to match the canonical plan-phase
  # producer, which hardcodes decision=fix_now. Any other decision in a
  # plan-phase backlog is drift -- a drop/defer/needs_human_decision item
  # must fail -- even if phase="plan" is set.
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-a.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-b.md"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  write_valid_review_findings "$tmpdir/phase_01_plan/review_findings.json"
  # phase="plan" but decision="drop" -> must fail the canonical check
  write_review_backlog "$tmpdir/phase_01_plan/review_backlog.json" "clean" "plan"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -q "must be 'fix_now'"
}

test_plan_to_plan_reviewed_rejects_verify_first_decision() {
  # verify_first is legitimate in review-phase backlogs but not plan-phase:
  # the canonical _plan_phase_decision helper only emits fix_now.
  # A drifted producer that emits verify_first under phase="plan" must fail.
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-a.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-b.md"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  write_valid_review_findings "$tmpdir/phase_01_plan/review_findings.json"
  # Hand-write a plan-phase backlog whose decision is verify_first
  cat > "$tmpdir/phase_01_plan/review_backlog.json" <<'EOF'
{
  "version": 1,
  "generated_at": "2026-04-23T00:00:00Z",
  "at_loop_cap": false,
  "phase": "plan",
  "allowed_decisions": ["fix_now", "verify_first", "defer", "drop", "needs_human_decision"],
  "counts": {"fix_now": 0, "verify_first": 1, "defer": 0, "drop": 0, "needs_human_decision": 0},
  "items": [
    {
      "finding_id": "RF-001",
      "source": "code-reviewer-a",
      "kind": "correctness",
      "severity": "medium",
      "confidence": "medium",
      "path": "scripts/example.py",
      "line": 10,
      "summary": "Potential issue in edge-case handling.",
      "why_it_matters": "Could break behavior for uncommon inputs.",
      "evidence": ["Reproducible with malformed payload."],
      "action": "Add guard and tests for this edge case.",
      "needs_test": true,
      "write_scope": ["scripts/example.py"],
      "related_acceptance_criteria": ["AC-1"],
      "decision": "verify_first",
      "decision_confidence": "medium",
      "reason": "Drift: plan-phase producer should emit fix_now.",
      "needs_validation": ["unit_test"],
      "owner": "builder",
      "batch": "correctness-scripts"
    }
  ]
}
EOF
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -q "verify_first"
}

test_plan_to_plan_reviewed_rejects_review_owner_and_batch() {
  # Plan-phase build-backlog routes every item to the builder and uses the
  # deterministic <kind>-<path-group> batch slug.
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-a.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-b.md"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  write_valid_review_findings "$tmpdir/phase_01_plan/review_findings.json"
  # decision=fix_now and phase=plan, but review-phase owner/batch defaults.
  write_review_backlog "$tmpdir/phase_01_plan/review_backlog.json" "actionable" "plan"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]" && echo "$output" | grep -q "must be 'builder'" && echo "$output" | grep -q "must be 'correctness-scripts'"
}

test_plan_to_plan_reviewed_accepts_canonical_raw_write_scope_sorting() {
  # The canonical Python builder filters whitespace-only write_scope entries,
  # sorts the original strings, then trims the selected candidate. Keep the
  # shell validator aligned so it does not reject valid plan-phase backlogs.
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "plan"
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-a.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-b.md"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"
  write_valid_review_findings "$tmpdir/phase_01_plan/review_findings.json"
  cat > "$tmpdir/phase_01_plan/review_backlog.json" <<'EOF'
{
  "version": 1,
  "generated_at": "2026-04-23T00:00:00Z",
  "at_loop_cap": false,
  "phase": "plan",
  "allowed_decisions": ["fix_now", "verify_first", "defer", "drop", "needs_human_decision"],
  "counts": {"fix_now": 1, "verify_first": 0, "defer": 0, "drop": 0, "needs_human_decision": 0},
  "items": [
    {
      "finding_id": "RF-001",
      "source": "code-reviewer-a",
      "kind": "correctness",
      "severity": "medium",
      "confidence": "medium",
      "path": "scripts/example.py",
      "line": 10,
      "summary": "Potential issue in edge-case handling.",
      "why_it_matters": "Could break behavior for uncommon inputs.",
      "evidence": ["Reproducible with malformed payload."],
      "action": "Add guard and tests for this edge case.",
      "needs_test": true,
      "write_scope": [" zeta/example.py", "alpha/example.py"],
      "related_acceptance_criteria": ["AC-1"],
      "decision": "fix_now",
      "decision_confidence": "medium",
      "reason": "Plan-phase canonical default: builder implements this finding now.",
      "needs_validation": ["unit_test", "typecheck", "lint"],
      "owner": "builder",
      "batch": "correctness-zeta"
    }
  ]
}
EOF
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "plan_reviewed" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_valid_reviewing_to_fixing() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  write_review_backlog "$tmpdir/phase_03_review/review_backlog.json" "actionable"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "fixing" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_reviewing_to_fixing_rejects_invalid_review_backlog_schema() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  cat > "$tmpdir/phase_03_review/review_backlog.json" <<EOF
{
  "version": 1,
  "items": [
    {
      "finding_id": "RF-001",
      "decision": "fix_now"
    }
  ]
}
EOF
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "fixing" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "review backlog schema invalid"
}

test_reviewing_to_fixing_both_clean() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  write_review_backlog "$tmpdir/phase_03_review/review_backlog.json" "clean"
  echo '{"status":"complete","next":"fixer","summary":"found issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "fixing" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q "\[FAIL\]"
}

test_reviewing_to_fixing_rejects_blocked_reviewer_handoff_status() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  write_review_backlog "$tmpdir/phase_03_review/review_backlog.json" "actionable"
  echo '{"status":"blocked","next":"fixer","summary":"stopped"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "fixing" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q 'reviewer handoff status must be explicitly present and equal "complete"'
}

test_reviewing_to_fixing_rejects_needs_human_reviewer_handoff_status() {
  local tmpdir
  tmpdir=$(mktemp -d)
  create_state_json "$tmpdir" "reviewing"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_code-reviewer-a.md"
  touch "$tmpdir/phase_03_review/review_code-reviewer-b.md"
  write_review_backlog "$tmpdir/phase_03_review/review_backlog.json" "actionable"
  echo '{"status":"needs_human","next":"fixer","summary":"need input"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-a.json"
  echo '{"status":"complete","next":null,"summary":"no issues"}' > "$tmpdir/phase_03_review/handoff_code-reviewer-b.json"
  local output
  output=$(bash "$SCRIPT" "$tmpdir" "fixing" 2>&1)
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 1 ] && echo "$output" | grep -q 'reviewer handoff status must be explicitly present and equal "complete"'
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

test_fix_iteration_exceeded_uses_solo_cap() {
  local tmpdir stderr_file fakerepo
  tmpdir=$(mktemp -d)
  stderr_file=$(mktemp)
  create_state_json "$tmpdir" "fixing" 1 2 "solo"
  mkdir -p "$tmpdir/phase_03_review"
  touch "$tmpdir/phase_03_review/review_fix_feedback_discussion.md"

  fakerepo=$(mktemp -d)
  git -C "$fakerepo" init --quiet
  mkdir -p "$fakerepo/.ai" "$fakerepo/scripts"
  cat > "$fakerepo/.ai/allowlist.json" <<AEOF
{
  "solo": {
    "max_fix_iterations": 2
  },
  "gates": {
    "max_plan_iterations": 4,
    "max_fix_iterations": 3
  }
}
AEOF
  cp "$SCRIPT" "$fakerepo/scripts/quest_validate-quest-state.sh"

  local output stderr_output
  output=$(cd "$fakerepo" && bash scripts/quest_validate-quest-state.sh "$tmpdir" "reviewing" 2>"$stderr_file")
  local rc=$?
  stderr_output=$(cat "$stderr_file")
  rm -f "$stderr_file"
  rm -rf "$tmpdir" "$fakerepo"
  [ "$rc" -eq 0 ] && echo "$stderr_output" | grep -q "max 2"
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
  echo '{"status":"complete","next":"builder","summary":"approved"}' > "$tmpdir/phase_01_plan/handoff_arbiter.json"
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
  "solo": {
    "max_fix_iterations": "bad"
  },
  "gates": {
    "max_plan_iterations": "nope",
    "max_fix_iterations": "bad"
  }
}
AEOF
  mkdir -p "$fakerepo/scripts"
  cp "$SCRIPT" "$fakerepo/scripts/quest_validate-quest-state.sh"
  local output stderr_output
  output=$(cd "$fakerepo" && bash scripts/quest_validate-quest-state.sh "$tmpdir" "plan" 2>"$stderr_file")
  local rc=$?
  stderr_output=$(cat "$stderr_file")
  rm -f "$stderr_file"
  rm -rf "$tmpdir" "$fakerepo"
  # Should still pass (warnings only, defaults used), and stderr should have WARN
  [ "$rc" -eq 0 ] && echo "$stderr_output" | grep -q "\[WARN\]" && echo "$stderr_output" | grep -qi "solo.max_fix_iterations"
}

test_zero_allowlist_iterations_are_rejected() {
  local tmpdir stderr_file fakerepo
  tmpdir=$(mktemp -d)
  stderr_file=$(mktemp)
  create_state_json "$tmpdir" "plan" 2 0
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/arbiter_verdict.md"

  fakerepo=$(mktemp -d)
  git -C "$fakerepo" init --quiet
  mkdir -p "$fakerepo/.ai" "$fakerepo/scripts"
  cat > "$fakerepo/.ai/allowlist.json" <<AEOF
{
  "solo": {
    "max_fix_iterations": 0
  },
  "gates": {
    "max_plan_iterations": 0,
    "max_fix_iterations": 0
  }
}
AEOF
  cp "$SCRIPT" "$fakerepo/scripts/quest_validate-quest-state.sh"

  local output stderr_output
  output=$(cd "$fakerepo" && bash scripts/quest_validate-quest-state.sh "$tmpdir" "plan" 2>"$stderr_file")
  local rc=$?
  stderr_output=$(cat "$stderr_file")
  rm -f "$stderr_file"
  rm -rf "$tmpdir" "$fakerepo"
  [ "$rc" -eq 0 ] && echo "$stderr_output" | grep -q "\[WARN\]" && echo "$stderr_output" | grep -qi "max_plan_iterations"
}

test_validation_log_written() {
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/phase_01_plan" "$tmpdir/logs"
  echo '{"phase":"plan_reviewed","plan_iteration":1,"fix_iteration":0}' > "$tmpdir/state.json"
  echo "plan content" > "$tmpdir/phase_01_plan/plan.md"

  bash "$SCRIPT" "$tmpdir" "presenting" > /dev/null 2>&1
  local rc=$?
  local has_log=false
  if [ -f "$tmpdir/logs/validation.log" ] && grep -q "plan_reviewed->presenting" "$tmpdir/logs/validation.log" && grep -q "result=pass" "$tmpdir/logs/validation.log"; then
    has_log=true
  fi
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ] && [ "$has_log" = true ]
}

# ---- Run all tests ----

echo "=== Quest State Validation Tests ==="
echo ""

run_test test_missing_state_json
run_test test_invalid_json
run_test test_valid_plan_to_plan_reviewed
run_test test_valid_plan_to_plan_reviewed_solo_without_findings
run_test test_missing_artifact_plan_to_plan_reviewed
run_test test_plan_to_plan_reviewed_requires_canonical_artifacts_in_workflow_mode
run_test test_plan_reviewed_to_building_rejected
run_test test_presentation_complete_to_building_arbiter_approved
run_test test_presentation_complete_to_building_arbiter_says_iterate
run_test test_presentation_complete_to_building_missing_arbiter_handoff
run_test test_valid_building_to_reviewing
run_test test_building_to_reviewing_empty_dir
run_test test_valid_reviewing_to_complete
run_test test_reviewing_to_complete_has_issues
run_test test_reviewing_to_complete_blocked_by_needs_human_decision
run_test test_reviewing_to_complete_blocked_by_reviewer_fixer_handoff
run_test test_reviewing_to_complete_requires_reviewer_handoffs
run_test test_reviewing_to_complete_rejects_invalid_reviewer_handoff_json
run_test test_reviewing_to_complete_rejects_missing_next_in_handoff
run_test test_reviewing_to_complete_rejects_blocked_reviewer_handoff_status
run_test test_reviewing_to_complete_rejects_needs_human_reviewer_handoff_status
run_test test_reviewing_to_complete_rejects_invalid_review_backlog_schema
run_test test_valid_reviewing_to_fixing
run_test test_reviewing_to_fixing_rejects_invalid_review_backlog_schema
run_test test_reviewing_to_fixing_both_clean
run_test test_reviewing_to_fixing_rejects_blocked_reviewer_handoff_status
run_test test_reviewing_to_fixing_rejects_needs_human_reviewer_handoff_status
run_test test_invalid_transition
run_test test_plan_iteration_exceeded
run_test test_fix_iteration_exceeded
run_test test_fix_iteration_exceeded_uses_solo_cap
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
run_test test_plan_to_plan_reviewed_rejects_invalid_backlog_item_schema
run_test test_plan_to_plan_reviewed_rejects_false_typed_backlog_fields
run_test test_plan_to_plan_reviewed_rejects_invalid_backlog_finding_fields
run_test test_plan_to_plan_reviewed_rejects_review_phase_backlog
run_test test_plan_to_plan_reviewed_rejects_non_actionable_decision
run_test test_plan_to_plan_reviewed_rejects_verify_first_decision
run_test test_plan_to_plan_reviewed_rejects_review_owner_and_batch
run_test test_plan_to_plan_reviewed_accepts_canonical_raw_write_scope_sorting
run_test test_non_numeric_allowlist_iterations
run_test test_zero_allowlist_iterations_are_rejected
run_test test_validation_log_written

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
