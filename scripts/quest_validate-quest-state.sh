#!/usr/bin/env bash
# Quest state validation script
# Validates state.json and artifact prerequisites before phase transitions.
#
# Usage: quest_validate-quest-state.sh <quest-dir> <target-phase>
# Exit codes: 0 = valid, 1 = validation failed, 2 = usage error
#
# Checks:
#   - state.json exists and is valid JSON
#   - Current phase matches expected predecessor for target phase
#   - Required artifacts from previous phase exist
#   - Semantic content checks on handoff JSON files (where required)
#   - plan_iteration / fix_iteration within bounds (warns, does not fail)
#
# Dependencies: bash, jq, standard POSIX utilities
# No network access required.
#
# Design note: This script is intentionally stricter than the workflow's
# fallback behavior. The workflow allows text-based handoff parsing when
# handoff.json files are missing. This script requires handoff.json files
# for semantic checks (arbiter verdict, review outcomes). This strictness
# incentivizes agents to write handoff.json and pushes the system toward
# structured handoff as the norm rather than the exception.

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
SCRIPT_NAME="$(basename "$0")"

ERRORS=0
CURRENT_PHASE=""
QUEST_MODE="workflow"
PLAN_ITERATION=0
FIX_ITERATION=0
MAX_PLAN_ITERATIONS=4
MAX_FIX_ITERATIONS=3
SOLO_MAX_FIX_ITERATIONS=2
REVIEW_BACKLOG_ACTIONABLE_COUNT=""
REVIEW_BACKLOG_HUMAN_DECISION_COUNT=0

# Colors for output (disabled if not a terminal)
if [ -t 1 ]; then
  RED='\033[0;31m'
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  NC='\033[0m'
else
  RED=''
  GREEN=''
  YELLOW=''
  NC=''
fi

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; ERRORS=$((ERRORS + 1)); }
warn() { echo -e "${YELLOW}[WARN]${NC} $1" >&2; }

# --help: show usage
show_help() {
  cat <<EOF
Usage: $SCRIPT_NAME <quest-dir> <target-phase>

Validates quest state prerequisites before a phase transition.

Arguments:
  quest-dir     Path to the quest directory (e.g., .quest/feature-x_2026-02-15__1430 or .quest/2026-02-15_1430__feature-x)
  target-phase  The phase to transition to

Exit codes:
  0  All prerequisites met
  1  Validation failed (missing artifacts, invalid transition, etc.)
  2  Usage error (bad arguments, missing quest directory)

Valid target phases:
  plan, plan_reviewed, presenting, presentation_complete,
  building, reviewing, fixing, complete

Note: plan_reviewed -> building is NOT allowed. Presentation is mandatory.

Dependencies: bash, jq
EOF
  exit 0
}

# Read iteration bounds from .ai/allowlist.json (with defaults)
read_max_iterations() {
  local allowlist="$REPO_ROOT/.ai/allowlist.json"
  if [ -f "$allowlist" ] && command -v jq &>/dev/null; then
    local val
    val=$(jq -r '.gates.max_plan_iterations // empty' "$allowlist" 2>/dev/null)
    if [ -n "$val" ]; then
      if [[ "$val" =~ ^[0-9]+$ ]] && [ "$val" -ge 1 ]; then
        MAX_PLAN_ITERATIONS="$val"
      else
        warn "allowlist max_plan_iterations is not a valid integer: '$val' (using default $MAX_PLAN_ITERATIONS)"
      fi
    fi
    val=$(jq -r '.gates.max_fix_iterations // empty' "$allowlist" 2>/dev/null)
    if [ -n "$val" ]; then
      if [[ "$val" =~ ^[0-9]+$ ]] && [ "$val" -ge 1 ]; then
        MAX_FIX_ITERATIONS="$val"
      else
        warn "allowlist max_fix_iterations is not a valid integer: '$val' (using default $MAX_FIX_ITERATIONS)"
      fi
    fi
    val=$(jq -r '.solo.max_fix_iterations // empty' "$allowlist" 2>/dev/null)
    if [ -n "$val" ]; then
      if [[ "$val" =~ ^[0-9]+$ ]] && [ "$val" -ge 1 ]; then
        SOLO_MAX_FIX_ITERATIONS="$val"
      else
        warn "allowlist solo.max_fix_iterations is not a valid integer: '$val' (using default $SOLO_MAX_FIX_ITERATIONS)"
      fi
    fi
  fi
}

# Validate state.json exists and is parseable
validate_state_json() {
  local quest_dir="$1"
  local state_file="$quest_dir/state.json"

  if [ ! -f "$state_file" ]; then
    fail "state.json not found at $state_file"
    return
  fi

  if ! command -v jq &>/dev/null; then
    fail "jq is required but not installed"
    return
  fi

  if ! jq empty "$state_file" 2>/dev/null; then
    fail "state.json is not valid JSON"
    return
  fi
  pass "state.json exists and is valid JSON"

  CURRENT_PHASE=$(jq -r '.phase // empty' "$state_file" 2>/dev/null)
  QUEST_MODE=$(jq -r '.quest_mode // "workflow"' "$state_file" 2>/dev/null)
  if [ -z "$QUEST_MODE" ] || [ "$QUEST_MODE" = "null" ]; then
    QUEST_MODE="workflow"
  fi
  if [ "$QUEST_MODE" = "solo" ] && [ "$SOLO_MAX_FIX_ITERATIONS" -lt "$MAX_FIX_ITERATIONS" ]; then
    MAX_FIX_ITERATIONS="$SOLO_MAX_FIX_ITERATIONS"
  fi
  local raw_plan_iter raw_fix_iter
  raw_plan_iter=$(jq -r '.plan_iteration // 0' "$state_file" 2>/dev/null)
  raw_fix_iter=$(jq -r '.fix_iteration // 0' "$state_file" 2>/dev/null)

  # Validate iteration fields are numeric
  if ! [[ "$raw_plan_iter" =~ ^[0-9]+$ ]]; then
    fail "plan_iteration is not a valid integer: '$raw_plan_iter'"
    raw_plan_iter=0
  fi
  if ! [[ "$raw_fix_iter" =~ ^[0-9]+$ ]]; then
    fail "fix_iteration is not a valid integer: '$raw_fix_iter'"
    raw_fix_iter=0
  fi

  PLAN_ITERATION="$raw_plan_iter"
  FIX_ITERATION="$raw_fix_iter"

  if [ -z "$CURRENT_PHASE" ]; then
    fail "state.json missing 'phase' field"
  fi
}

# Validate the transition is allowed
# Returns the transition key if valid, empty string if not
validate_transition() {
  local current="$1"
  local target="$2"

  # Allowed transitions: current->target
  local valid=false
  case "${current}->${target}" in
    "plan->plan_reviewed") valid=true ;;
    "plan->plan")          valid=true ;;
    "plan_reviewed->presenting") valid=true ;;
    "presenting->presentation_complete") valid=true ;;
    "presentation_complete->building") valid=true ;;
    "building->reviewing") valid=true ;;
    "reviewing->fixing")   valid=true ;;
    "reviewing->complete") valid=true ;;
    "fixing->reviewing")   valid=true ;;
  esac

  if [ "$valid" = true ]; then
    pass "Transition $current -> $target is valid"
  else
    fail "Invalid transition: $current -> $target (not in allowed transition table)"
  fi
}

# Check that required artifact files exist for the given transition
validate_artifacts() {
  local quest_dir="$1"
  local current="$2"
  local target="$3"

  case "${current}->${target}" in
    "plan->plan_reviewed")
      check_file "$quest_dir/phase_01_plan/plan.md"
      check_file "$quest_dir/phase_01_plan/review_plan-reviewer-a.md"
      if [ "$QUEST_MODE" != "solo" ]; then
        check_file "$quest_dir/phase_01_plan/review_plan-reviewer-b.md"
        check_file "$quest_dir/phase_01_plan/arbiter_verdict.md"
        check_file "$quest_dir/phase_01_plan/review_findings.json"
        check_file "$quest_dir/phase_01_plan/review_backlog.json"
      fi
      ;;
    "plan->plan")
      if [ "$QUEST_MODE" = "solo" ]; then
        # Solo: reviewer A verdict triggers re-plan (no arbiter)
        check_file "$quest_dir/phase_01_plan/review_plan-reviewer-a.md"
      else
        check_file "$quest_dir/phase_01_plan/arbiter_verdict.md"
      fi
      ;;
    "plan_reviewed->presenting")
      check_file "$quest_dir/phase_01_plan/plan.md"
      ;;
    "presenting->presentation_complete")
      check_file "$quest_dir/phase_01_plan/plan.md"
      ;;
    "presentation_complete->building")
      # Artifact check: plan exists. Semantic check in validate_semantic_content
      # verifies arbiter/reviewer-A approval from the plan_reviewed phase.
      check_file "$quest_dir/phase_01_plan/plan.md"
      ;;
    "building->reviewing")
      check_dir_nonempty "$quest_dir/phase_02_implementation"
      ;;
    "reviewing->fixing")
      check_file "$quest_dir/phase_03_review/review_code-reviewer-a.md"
      check_file "$quest_dir/phase_03_review/review_backlog.json"
      if [ "$QUEST_MODE" != "solo" ]; then
        check_file "$quest_dir/phase_03_review/review_code-reviewer-b.md"
      fi
      ;;
    "reviewing->complete")
      check_file "$quest_dir/phase_03_review/review_code-reviewer-a.md"
      check_file "$quest_dir/phase_03_review/review_backlog.json"
      check_file "$quest_dir/phase_03_review/handoff_code-reviewer-a.json"
      if [ "$QUEST_MODE" != "solo" ]; then
        check_file "$quest_dir/phase_03_review/review_code-reviewer-b.md"
        check_file "$quest_dir/phase_03_review/handoff_code-reviewer-b.json"
      fi
      ;;
    "fixing->reviewing")
      check_file "$quest_dir/phase_03_review/review_fix_feedback_discussion.md"
      ;;
  esac
}

check_file() {
  local filepath="$1"
  if [ -f "$filepath" ]; then
    pass "Artifact exists: $filepath"
  else
    fail "Missing artifact: $filepath"
  fi
}

validate_review_findings_schema() {
  local findings_file="$1"
  local validator="$REPO_ROOT/scripts/quest_review_intelligence.py"

  if [ ! -f "$validator" ]; then
    fail "Semantic check: review findings validator not found at $validator"
    return
  fi

  local validation_output
  validation_output=$(python3 "$validator" validate-findings --input "$findings_file" 2>&1)
  local rc=$?
  if [ "$rc" -eq 0 ]; then
    pass "Semantic check: review findings schema valid ($findings_file)"
  else
    fail "Semantic check: review findings schema invalid ($findings_file): $validation_output"
  fi
}

validate_review_backlog_schema() {
  local backlog_file="$1"
  local original_actionable="$REVIEW_BACKLOG_ACTIONABLE_COUNT"
  local original_human="$REVIEW_BACKLOG_HUMAN_DECISION_COUNT"
  local validator="$REPO_ROOT/scripts/quest_review_intelligence.py"

  if ! read_review_backlog_actionable_count "$backlog_file"; then
    return 1
  fi

  if [ ! -f "$validator" ]; then
    fail "Semantic check: review findings validator not found at $validator"
    return 1
  fi

  local backlog_validation_output
  backlog_validation_output=$(python3 "$validator" validate-backlog --input "$backlog_file" 2>&1)
  local backlog_rc=$?

  local item_errors
  item_errors=$(jq -r '
    def required_decision_fields:
      ["decision", "decision_confidence", "reason", "needs_validation", "owner", "batch"];
    def allowed_decisions:
      ["fix_now", "verify_first", "defer", "drop", "needs_human_decision"];
    def allowed_confidence:
      ["high", "medium", "low"];
    [
      if (.items | type) != "array" then
        "top-level items must be an array"
      else empty end,
      (.items // []) | to_entries[] |
      . as $entry |
      (required_decision_fields[] as $field | select(($entry.value | has($field)) | not) | "[\($entry.key)] missing field \($field)"),
      (if (($entry.value | has("decision")) and (($entry.value.decision | type) != "string" or ((allowed_decisions | index($entry.value.decision)) == null))) then
        "[\($entry.key)] invalid decision"
      else empty end),
      (if (($entry.value | has("decision_confidence")) and (($entry.value.decision_confidence | type) != "string" or ((allowed_confidence | index($entry.value.decision_confidence)) == null))) then
        "[\($entry.key)] invalid decision_confidence"
      else empty end),
      (if (($entry.value | has("reason")) and (($entry.value.reason | type) != "string" or ($entry.value.reason | length) == 0)) then
        "[\($entry.key)] invalid reason"
      else empty end),
      (if (($entry.value | has("owner")) and (($entry.value.owner | type) != "string" or ($entry.value.owner | length) == 0)) then
        "[\($entry.key)] invalid owner"
      else empty end),
      (if (($entry.value | has("batch")) and (($entry.value.batch | type) != "string" or ($entry.value.batch | length) == 0)) then
        "[\($entry.key)] invalid batch"
      else empty end),
      (if (($entry.value | has("needs_validation")) and (($entry.value.needs_validation | type) != "array" or ([($entry.value.needs_validation[]? | strings)] | length) != ($entry.value.needs_validation | length))) then
        "[\($entry.key)] invalid needs_validation"
      else empty end),
      (if (($entry.value | has("evidence")) and (($entry.value.evidence | type) != "array" or ([($entry.value.evidence[]? | strings)] | length) != ($entry.value.evidence | length))) then
        "[\($entry.key)] invalid evidence"
      else empty end),
      (if (($entry.value | has("write_scope")) and (($entry.value.write_scope | type) != "array" or ([($entry.value.write_scope[]? | strings)] | length) != ($entry.value.write_scope | length))) then
        "[\($entry.key)] invalid write_scope"
      else empty end),
      (if (($entry.value | has("related_acceptance_criteria")) and (($entry.value.related_acceptance_criteria | type) != "array" or ([($entry.value.related_acceptance_criteria[]? | strings)] | length) != ($entry.value.related_acceptance_criteria | length))) then
        "[\($entry.key)] invalid related_acceptance_criteria"
      else empty end),
      (if (($entry.value | has("needs_test")) and (($entry.value.needs_test | type) != "boolean")) then
        "[\($entry.key)] invalid needs_test"
      else empty end)
    ] | .[]' "$backlog_file" 2>/dev/null)

  local combined_errors=""
  if [ "$backlog_rc" -ne 0 ]; then
    combined_errors="$backlog_validation_output"
  fi
  if [ -n "$item_errors" ]; then
    if [ -n "$combined_errors" ]; then
      combined_errors="$combined_errors
$item_errors"
    else
      combined_errors="$item_errors"
    fi
  fi

  if [ -n "$combined_errors" ]; then
    fail "Semantic check: review backlog schema invalid ($backlog_file): $combined_errors"
    return 1
  fi

  REVIEW_BACKLOG_ACTIONABLE_COUNT="$original_actionable"
  REVIEW_BACKLOG_HUMAN_DECISION_COUNT="$original_human"
  pass "Semantic check: review backlog is valid ($backlog_file)"
}

validate_plan_phase_backlog() {
  # Plan-phase approval requires:
  #   1. backlog["phase"] == "plan" (asserted via the CLI validator)
  #   2. every backlog item matches the canonical plan-phase defaults
  #      produced by build-backlog --phase plan: decision=fix_now,
  #      owner=builder, and batch=<slugified kind>-<path group>. A drifted
  #      producer can otherwise emit review-style semantics under phase="plan"
  #      and still pass schema checks.
  local backlog_file="$1"
  local validator="$REPO_ROOT/scripts/quest_review_intelligence.py"

  if [ ! -f "$validator" ]; then
    fail "Semantic check: review backlog validator not found at $validator"
    return 1
  fi

  local phase_output
  phase_output=$(python3 "$validator" validate-backlog --input "$backlog_file" --expected-phase plan --strict-plan-defaults 2>&1)
  local phase_rc=$?
  if [ "$phase_rc" -ne 0 ]; then
    fail "Semantic check: plan-phase backlog check failed ($backlog_file): $phase_output"
    return 1
  fi

  pass "Semantic check: plan-phase backlog matches canonical plan defaults ($backlog_file)"
  return 0
}

read_required_reviewer_handoff() {
  local handoff_file="$1"
  local next_value=""

  if [ ! -f "$handoff_file" ]; then
    fail "Semantic check: handoff not found at $handoff_file"
    return 1
  fi

  if ! jq empty "$handoff_file" 2>/dev/null; then
    fail "Semantic check: handoff is not valid JSON ($handoff_file)"
    return 1
  fi

  if ! jq -e 'has("status") and .status == "complete"' "$handoff_file" >/dev/null 2>&1; then
    fail "Semantic check: reviewer handoff status must be explicitly present and equal \"complete\" ($handoff_file)"
    return 1
  fi

  if ! jq -e 'has("next") and (.next == null or .next == "fixer")' "$handoff_file" >/dev/null 2>&1; then
    fail "Semantic check: handoff next must be explicitly present and be null or \"fixer\" ($handoff_file)"
    return 1
  fi

  next_value=$(jq -r '.next' "$handoff_file" 2>/dev/null)
  if [ "$next_value" = "null" ]; then
    next_value=""
  fi

  REQUIRED_HANDOFF_NEXT="$next_value"
  return 0
}

check_dir_nonempty() {
  local dirpath="$1"
  if [ ! -d "$dirpath" ]; then
    fail "Directory does not exist: $dirpath"
    return
  fi
  # Check if directory has any files (not just subdirs)
  local first_file
  first_file=$(find "$dirpath" -type f 2>/dev/null | head -1)
  if [ -n "$first_file" ]; then
    pass "Directory exists and is non-empty: $dirpath"
  else
    fail "Directory is empty: $dirpath"
  fi
}

read_review_backlog_actionable_count() {
  local backlog_file="$1"

  if [ ! -f "$backlog_file" ]; then
    fail "Semantic check: review backlog not found at $backlog_file"
    return 1
  fi

  if ! jq empty "$backlog_file" 2>/dev/null; then
    fail "Semantic check: review backlog is not valid JSON ($backlog_file)"
    return 1
  fi

  local has_items_array
  has_items_array=$(jq -r 'if (.items | type) == "array" then "yes" else "no" end' "$backlog_file" 2>/dev/null)
  if [ "$has_items_array" != "yes" ]; then
    fail "Semantic check: review backlog must contain an items array ($backlog_file)"
    return 1
  fi

  local actionable_count
  actionable_count=$(jq '[.items[]? | select((.decision // "") == "fix_now" or (.decision // "") == "verify_first")] | length' "$backlog_file" 2>/dev/null)
  if ! [[ "$actionable_count" =~ ^[0-9]+$ ]]; then
    fail "Semantic check: review backlog actionable count is invalid ($backlog_file)"
    return 1
  fi

  REVIEW_BACKLOG_ACTIONABLE_COUNT="$actionable_count"

  REVIEW_BACKLOG_HUMAN_DECISION_COUNT=$(jq '[.items[]? | select((.decision // "") == "needs_human_decision")] | length' "$backlog_file" 2>/dev/null)
  if ! [[ "$REVIEW_BACKLOG_HUMAN_DECISION_COUNT" =~ ^[0-9]+$ ]]; then
    REVIEW_BACKLOG_HUMAN_DECISION_COUNT=0
  fi

  return 0
}

# Semantic content checks on handoff/backlog artifacts
validate_semantic_content() {
  local quest_dir="$1"
  local current="$2"
  local target="$3"

  case "${current}->${target}" in
    "plan->plan_reviewed")
      if [ "$QUEST_MODE" != "solo" ]; then
        local findings_file="$quest_dir/phase_01_plan/review_findings.json"
        local backlog_file="$quest_dir/phase_01_plan/review_backlog.json"
        validate_review_findings_schema "$findings_file"
        if validate_review_backlog_schema "$backlog_file"; then
          validate_plan_phase_backlog "$backlog_file"
        fi
      fi
      ;;
    "presentation_complete->building")
      if [ "$QUEST_MODE" = "solo" ]; then
        local reviewer_a_file="$quest_dir/phase_01_plan/handoff_plan-reviewer-a.json"
        if [ ! -f "$reviewer_a_file" ]; then
          fail "Semantic check: handoff_plan-reviewer-a.json not found at $reviewer_a_file"
          return
        fi
        local next_val
        next_val=$(jq -r '.next' "$reviewer_a_file" 2>/dev/null)
        if [ "$next_val" = "builder" ] || [ "$next_val" = "arbiter" ]; then
          pass "Semantic check: reviewer A approved for building (next=$next_val, solo mode)"
        else
          fail "Semantic check: reviewer A did not approve for building (next=$next_val, expected builder or arbiter)"
        fi
      else
        local arbiter_file="$quest_dir/phase_01_plan/handoff_arbiter.json"
        if [ ! -f "$arbiter_file" ]; then
          fail "Semantic check: handoff_arbiter.json not found at $arbiter_file"
          return
        fi
        local next_val
        next_val=$(jq -r '.next' "$arbiter_file" 2>/dev/null)
        if [ "$next_val" = "builder" ]; then
          pass "Semantic check: arbiter approved (next=builder)"
        else
          fail "Semantic check: arbiter did not approve for building (next=$next_val, expected builder)"
        fi
      fi
      ;;
    "reviewing->fixing")
      local backlog_file="$quest_dir/phase_03_review/review_backlog.json"
      local actionable_count
      if ! validate_review_backlog_schema "$backlog_file"; then
        return
      fi
      if ! read_review_backlog_actionable_count "$backlog_file"; then
        return
      fi
      actionable_count="$REVIEW_BACKLOG_ACTIONABLE_COUNT"

      if [[ "$actionable_count" =~ ^[0-9]+$ ]] && [ "$actionable_count" -gt 0 ]; then
        pass "Semantic check: review backlog has actionable findings (fix_now/verify_first)"
      else
        fail "Semantic check: review backlog has no actionable findings for fixing"
      fi

      local reviewer_a_handoff="$quest_dir/phase_03_review/handoff_code-reviewer-a.json"
      if ! read_required_reviewer_handoff "$reviewer_a_handoff"; then
        return
      fi

      if [ "$QUEST_MODE" != "solo" ]; then
        local reviewer_b_handoff="$quest_dir/phase_03_review/handoff_code-reviewer-b.json"
        if ! read_required_reviewer_handoff "$reviewer_b_handoff"; then
          return
        fi
      fi
      ;;
    "reviewing->complete")
      local backlog_file="$quest_dir/phase_03_review/review_backlog.json"
      local actionable_count
      if ! validate_review_backlog_schema "$backlog_file"; then
        return
      fi
      if ! read_review_backlog_actionable_count "$backlog_file"; then
        return
      fi
      actionable_count="$REVIEW_BACKLOG_ACTIONABLE_COUNT"

      if [[ "$actionable_count" =~ ^[0-9]+$ ]] && [ "$actionable_count" -eq 0 ]; then
        pass "Semantic check: review backlog has no actionable findings"
      else
        fail "Semantic check: review backlog still has actionable findings; cannot complete"
      fi

      # Block completion while needs_human_decision items remain
      if [ "$REVIEW_BACKLOG_HUMAN_DECISION_COUNT" -gt 0 ]; then
        fail "Semantic check: review backlog has $REVIEW_BACKLOG_HUMAN_DECISION_COUNT needs_human_decision item(s); cannot auto-complete"
      fi

      # Safety check: block completion if any reviewer handoff requested fixes
      local reviewer_a_handoff="$quest_dir/phase_03_review/handoff_code-reviewer-a.json"
      local next_a
      if ! read_required_reviewer_handoff "$reviewer_a_handoff"; then
        return
      fi
      next_a="$REQUIRED_HANDOFF_NEXT"
      if [ "$next_a" = "fixer" ]; then
        fail "Semantic check: code-reviewer-a requested fixes (next=fixer) but completion attempted"
      fi

      if [ "$QUEST_MODE" != "solo" ]; then
        local reviewer_b_handoff="$quest_dir/phase_03_review/handoff_code-reviewer-b.json"
        local next_b
        if ! read_required_reviewer_handoff "$reviewer_b_handoff"; then
          return
        fi
        next_b="$REQUIRED_HANDOFF_NEXT"
        if [ "$next_b" = "fixer" ]; then
          fail "Semantic check: code-reviewer-b requested fixes (next=fixer) but completion attempted"
        fi
      fi
      ;;
  esac
}

# Check iteration bounds (warn only, do not fail)
validate_iteration_bounds() {
  local target="$1"
  local plan_iter="$2"
  local fix_iter="$3"

  case "$target" in
    "plan")
      if [ "$plan_iter" -ge "$MAX_PLAN_ITERATIONS" ]; then
        warn "Plan iteration $plan_iter >= max $MAX_PLAN_ITERATIONS (iteration bounds exceeded)"
      else
        pass "Plan iteration $plan_iter within bounds (max $MAX_PLAN_ITERATIONS)"
      fi
      ;;
    "reviewing")
      # Only check fix iteration if coming from fixing (check source phase, not counter value)
      if [ "$CURRENT_PHASE" = "fixing" ]; then
        if [ "$fix_iter" -ge "$MAX_FIX_ITERATIONS" ]; then
          warn "Fix iteration $fix_iter >= max $MAX_FIX_ITERATIONS (iteration bounds exceeded)"
        else
          pass "Fix iteration $fix_iter within bounds (max $MAX_FIX_ITERATIONS)"
        fi
      fi
      ;;
    "fixing")
      if [ "$fix_iter" -ge "$MAX_FIX_ITERATIONS" ]; then
        warn "Fix iteration $fix_iter >= max $MAX_FIX_ITERATIONS (iteration bounds exceeded)"
      else
        pass "Fix iteration $fix_iter within bounds (max $MAX_FIX_ITERATIONS)"
      fi
      ;;
  esac
}

# Main entry point
main() {
  local used_flag_syntax=false
  # Handle --help
  case "${1:-}" in
    --help|-h)
      show_help
      ;;
  esac

  local quest_dir=""
  local target_phase=""

  while [ $# -gt 0 ]; do
    case "$1" in
      --quest-dir)
        used_flag_syntax=true
        shift
        if [ $# -eq 0 ]; then
          echo "Error: --quest-dir requires a value" >&2
          exit 2
        fi
        quest_dir="$1"
        ;;
      --target|--target-phase)
        used_flag_syntax=true
        shift
        if [ $# -eq 0 ]; then
          echo "Error: --target requires a value" >&2
          exit 2
        fi
        target_phase="$1"
        ;;
      --)
        shift
        break
        ;;
      -*)
        echo "Error: Unknown option: $1" >&2
        exit 2
        ;;
      *)
        if [ -z "$quest_dir" ]; then
          quest_dir="$1"
        elif [ -z "$target_phase" ]; then
          target_phase="$1"
        else
          echo "Error: Unexpected argument: $1" >&2
          exit 2
        fi
        ;;
    esac
    shift
  done

  # Usage check
  if [ -z "$quest_dir" ] || [ -z "$target_phase" ]; then
    echo "Usage: $SCRIPT_NAME <quest-dir> <target-phase>" >&2
    echo "Run '$SCRIPT_NAME --help' for details." >&2
    exit 2
  fi

  if [ ! -d "$quest_dir" ]; then
    echo "Error: Quest directory not found: $quest_dir" >&2
    exit 2
  fi

  echo "=== Quest State Validation ==="
  echo "Quest dir: $quest_dir"
  echo "Target phase: $target_phase"
  echo ""

  # Read iteration bounds from allowlist
  read_max_iterations

  # Run all validators
  validate_state_json "$quest_dir"

  # If state.json could not be parsed, we cannot proceed with further checks
  if [ -z "$CURRENT_PHASE" ]; then
    # Log even on early failure
    local log_dir="$quest_dir/logs"
    if [ -d "$log_dir" ] || mkdir -p "$log_dir" 2>/dev/null; then
      echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') | transition=unknown->$target_phase | result=fail | errors=$ERRORS" >> "$log_dir/validation.log"
    fi
    echo ""
    echo "$ERRORS validation(s) failed"
    echo ""
    echo "AGENT: Validation failed. Do NOT proceed with this phase transition."
    echo "Do NOT modify state.json to work around this failure."
    echo "Report this validation failure to the user and STOP."
    exit 1
  fi

  local checkpoint_plan_reviewed=false
  if [ "$used_flag_syntax" = true ] && [ "$target_phase" = "plan_reviewed" ]; then
    case "$CURRENT_PHASE" in
      plan_reviewed|presenting|presentation_complete|building|reviewing|fixing|complete)
        checkpoint_plan_reviewed=true
        ;;
    esac
  fi

  if [ "$checkpoint_plan_reviewed" = true ]; then
    pass "Checkpoint validation mode: re-validating plan_reviewed artifacts from current phase $CURRENT_PHASE"
    validate_artifacts "$quest_dir" "plan" "plan_reviewed"
    validate_semantic_content "$quest_dir" "plan" "plan_reviewed"
  else
    validate_transition "$CURRENT_PHASE" "$target_phase"
    validate_artifacts "$quest_dir" "$CURRENT_PHASE" "$target_phase"
    validate_semantic_content "$quest_dir" "$CURRENT_PHASE" "$target_phase"
  fi
  validate_iteration_bounds "$target_phase" "$PLAN_ITERATION" "$FIX_ITERATION"

  # Log this validation run
  local log_dir="$quest_dir/logs"
  if [ -d "$log_dir" ] || mkdir -p "$log_dir" 2>/dev/null; then
    local result="pass"
    [ "$ERRORS" -gt 0 ] && result="fail"
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') | transition=$CURRENT_PHASE->$target_phase | result=$result | errors=$ERRORS" >> "$log_dir/validation.log"
  fi

  echo ""
  if [ "$ERRORS" -gt 0 ]; then
    echo "$ERRORS validation(s) failed"
    echo ""
    echo "AGENT: Validation failed. Do NOT proceed with this phase transition."
    echo "Do NOT modify state.json to work around this failure."
    echo "Report this validation failure to the user and STOP."
    exit 1
  fi
  echo "All validations passed!"
  exit 0
}

main "$@"
