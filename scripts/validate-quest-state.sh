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

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
SCRIPT_NAME="$(basename "$0")"

ERRORS=0
CURRENT_PHASE=""
PLAN_ITERATION=0
FIX_ITERATION=0
MAX_PLAN_ITERATIONS=4
MAX_FIX_ITERATIONS=3

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
      if [[ "$val" =~ ^[0-9]+$ ]]; then
        MAX_PLAN_ITERATIONS="$val"
      else
        warn "allowlist max_plan_iterations is not a valid integer: '$val' (using default $MAX_PLAN_ITERATIONS)"
      fi
    fi
    val=$(jq -r '.gates.max_fix_iterations // empty' "$allowlist" 2>/dev/null)
    if [ -n "$val" ]; then
      if [[ "$val" =~ ^[0-9]+$ ]]; then
        MAX_FIX_ITERATIONS="$val"
      else
        warn "allowlist max_fix_iterations is not a valid integer: '$val' (using default $MAX_FIX_ITERATIONS)"
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
      check_file "$quest_dir/phase_01_plan/review_claude.md"
      check_file "$quest_dir/phase_01_plan/review_codex.md"
      check_file "$quest_dir/phase_01_plan/arbiter_verdict.md"
      ;;
    "plan->plan")
      check_file "$quest_dir/phase_01_plan/arbiter_verdict.md"
      ;;
    "plan_reviewed->presenting")
      check_file "$quest_dir/phase_01_plan/plan.md"
      ;;
    "presenting->presentation_complete")
      check_file "$quest_dir/phase_01_plan/plan.md"
      ;;
    "presentation_complete->building")
      check_file "$quest_dir/phase_01_plan/plan.md"
      ;;
    "plan_reviewed->building")
      check_file "$quest_dir/phase_01_plan/plan.md"
      ;;
    "building->reviewing")
      check_dir_nonempty "$quest_dir/phase_02_implementation"
      ;;
    "reviewing->fixing")
      check_file "$quest_dir/phase_03_review/review_claude.md"
      check_file "$quest_dir/phase_03_review/review_codex.md"
      ;;
    "reviewing->complete")
      check_file "$quest_dir/phase_03_review/review_claude.md"
      check_file "$quest_dir/phase_03_review/review_codex.md"
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
      ;;
    "reviewing->fixing")
      local claude_file="$quest_dir/phase_03_review/handoff_claude.json"
      local codex_file="$quest_dir/phase_03_review/handoff_codex.json"
      local has_fixer=false

      if [ -f "$claude_file" ]; then
        local claude_next
        claude_next=$(jq -r '.next' "$claude_file" 2>/dev/null)
        if [ "$claude_next" = "fixer" ]; then
          has_fixer=true
        fi
      fi
      if [ -f "$codex_file" ]; then
        local codex_next
        codex_next=$(jq -r '.next' "$codex_file" 2>/dev/null)
        if [ "$codex_next" = "fixer" ]; then
          has_fixer=true
        fi
      fi

      if [ "$has_fixer" = true ]; then
        pass "Semantic check: at least one reviewer indicates issues (next=fixer)"
      else
        fail "Semantic check: no reviewer indicates issues requiring fixing"
      fi
      ;;
    "reviewing->complete")
      local claude_file="$quest_dir/phase_03_review/handoff_claude.json"
      local codex_file="$quest_dir/phase_03_review/handoff_codex.json"
      local both_clean=true

      if [ -f "$claude_file" ]; then
        local claude_next
        claude_next=$(jq -r '.next' "$claude_file" 2>/dev/null)
        if [ "$claude_next" != "null" ]; then
          both_clean=false
        fi
      else
        both_clean=false
      fi

      if [ -f "$codex_file" ]; then
        local codex_next
        codex_next=$(jq -r '.next' "$codex_file" 2>/dev/null)
        if [ "$codex_next" != "null" ]; then
          both_clean=false
        fi
      else
        both_clean=false
      fi

      if [ "$both_clean" = true ]; then
        pass "Semantic check: both reviewers report clean (next=null)"
      else
        fail "Semantic check: reviews are not both clean (both handoff files must have next=null)"
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
    echo ""
    echo "$ERRORS validation(s) failed"
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
    exit 1
  fi
  echo "All validations passed!"
  exit 0
}

main "$@"
