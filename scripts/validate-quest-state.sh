#!/usr/bin/env bash
# Quest state validation script
# Validates state.json and artifact prerequisites before phase transitions.
#
# Usage: validate-quest-state.sh <quest-dir> <target-phase>
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
  quest-dir     Path to the quest directory (e.g., .quest/feature-x_2026-02-15__1430)
  target-phase  The phase to transition to

Exit codes:
  0  All prerequisites met
  1  Validation failed (missing artifacts, invalid transition, etc.)
  2  Usage error (bad arguments, missing quest directory)

Valid target phases:
  plan, plan_reviewed, presenting, presentation_complete,
  building, reviewing, fixing, complete

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
    "plan_reviewed->building") valid=true ;;
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
      # No arbiter semantic re-check here. The arbiter approves at plan->plan_reviewed.
      # The presentation path only shows the plan to the user; it doesn't change approval.
      check_file "$quest_dir/phase_01_plan/plan.md"
      ;;
    "plan_reviewed->building")
      check_file "$quest_dir/phase_01_plan/plan.md"
      ;;
    "building->reviewing")
      check_dir_nonempty "$quest_dir/phase_02_implementation"
      ;;
    "reviewing->fixing")
      check_file "$quest_dir/phase_03_review/review_code-reviewer-a.md"
      if [ "$QUEST_MODE" != "solo" ]; then
        check_file "$quest_dir/phase_03_review/review_code-reviewer-b.md"
      fi
      ;;
    "reviewing->complete")
      check_file "$quest_dir/phase_03_review/review_code-reviewer-a.md"
      if [ "$QUEST_MODE" != "solo" ]; then
        check_file "$quest_dir/phase_03_review/review_code-reviewer-b.md"
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

# Semantic content checks on handoff JSON files
validate_semantic_content() {
  local quest_dir="$1"
  local current="$2"
  local target="$3"

  case "${current}->${target}" in
    "plan_reviewed->building")
      if [ "$QUEST_MODE" = "solo" ]; then
        # Solo: reviewer A's verdict (remapped by workflow to next=builder)
        local reviewer_a_file="$quest_dir/phase_01_plan/handoff_plan-reviewer-a.json"
        if [ ! -f "$reviewer_a_file" ]; then
          fail "Semantic check: handoff_plan-reviewer-a.json not found at $reviewer_a_file"
          return
        fi
        local next_val
        next_val=$(jq -r '.next' "$reviewer_a_file" 2>/dev/null)
        # Workflow remaps "arbiter" → "builder" in solo mode; accept both
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
      local reviewer_a_file="$quest_dir/phase_03_review/handoff_code-reviewer-a.json"
      local has_fixer=false

      if [ -f "$reviewer_a_file" ]; then
        local reviewer_a_next
        reviewer_a_next=$(jq -r '.next' "$reviewer_a_file" 2>/dev/null)
        if [ "$reviewer_a_next" = "fixer" ]; then
          has_fixer=true
        fi
      fi

      if [ "$QUEST_MODE" != "solo" ]; then
        local reviewer_b_file="$quest_dir/phase_03_review/handoff_code-reviewer-b.json"
        if [ -f "$reviewer_b_file" ]; then
          local reviewer_b_next
          reviewer_b_next=$(jq -r '.next' "$reviewer_b_file" 2>/dev/null)
          if [ "$reviewer_b_next" = "fixer" ]; then
            has_fixer=true
          fi
        fi
      fi

      if [ "$has_fixer" = true ]; then
        pass "Semantic check: at least one reviewer indicates issues (next=fixer)"
      else
        fail "Semantic check: no reviewer indicates issues requiring fixing"
      fi
      ;;
    "reviewing->complete")
      local reviewer_a_file="$quest_dir/phase_03_review/handoff_code-reviewer-a.json"
      local all_clean=true

      if [ -f "$reviewer_a_file" ]; then
        local reviewer_a_next
        # Note: jq -r outputs "null" for both JSON null and missing .next field.
        # This is acceptable since agents always write structured handoff JSON.
        reviewer_a_next=$(jq -r '.next' "$reviewer_a_file" 2>/dev/null)
        if [ "$reviewer_a_next" != "null" ]; then
          all_clean=false
        fi
      else
        all_clean=false
      fi

      if [ "$QUEST_MODE" != "solo" ]; then
        local reviewer_b_file="$quest_dir/phase_03_review/handoff_code-reviewer-b.json"
        if [ -f "$reviewer_b_file" ]; then
          local reviewer_b_next
          reviewer_b_next=$(jq -r '.next' "$reviewer_b_file" 2>/dev/null)
          if [ "$reviewer_b_next" != "null" ]; then
            all_clean=false
          fi
        else
          all_clean=false
        fi
      fi

      if [ "$all_clean" = true ]; then
        if [ "$QUEST_MODE" = "solo" ]; then
          pass "Semantic check: reviewer A reports clean (next=null, solo mode)"
        else
          pass "Semantic check: both reviewers report clean (next=null)"
        fi
      else
        if [ "$QUEST_MODE" = "solo" ]; then
          fail "Semantic check: reviewer A is not clean (handoff file must have next=null)"
        else
          fail "Semantic check: reviews are not both clean (both handoff files must have next=null)"
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
  # Handle --help
  case "${1:-}" in
    --help|-h)
      show_help
      ;;
  esac

  # Usage check
  if [ $# -lt 2 ]; then
    echo "Usage: $SCRIPT_NAME <quest-dir> <target-phase>" >&2
    echo "Run '$SCRIPT_NAME --help' for details." >&2
    exit 2
  fi

  local quest_dir="$1"
  local target_phase="$2"

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

  validate_transition "$CURRENT_PHASE" "$target_phase"
  validate_artifacts "$quest_dir" "$CURRENT_PHASE" "$target_phase"
  validate_semantic_content "$quest_dir" "$CURRENT_PHASE" "$target_phase"
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
