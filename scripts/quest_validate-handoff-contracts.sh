#!/bin/bash
# Validate handoff contract consistency

set -e  # Exit on first error

ERRORS=0

echo "=== Handoff Contract Validation ==="
echo ""

ROLE_FILES=(
  ".skills/quest/agents/planner.md"
  ".skills/quest/agents/plan-reviewer.md"
  ".skills/quest/agents/arbiter.md"
  ".skills/quest/agents/builder.md"
  ".skills/quest/agents/code-reviewer.md"
  ".skills/quest/agents/fixer.md"
)
EXPECTED_ROLE_COUNT=6

if [ "${#ROLE_FILES[@]}" -ne "$EXPECTED_ROLE_COUNT" ]; then
  echo "❌ Role file enumeration error: expected $EXPECTED_ROLE_COUNT, got ${#ROLE_FILES[@]}"
  exit 1
fi

for role_file in "${ROLE_FILES[@]}"; do
  if [ ! -f "$role_file" ]; then
    echo "❌ Missing role file: $role_file"
    ERRORS=$((ERRORS + 1))
  fi
done

if [ "$ERRORS" -gt 0 ]; then
  echo ""
  echo "❌ Found $ERRORS role-file existence error(s)"
  exit 1
fi

echo "1. Checking all role files have text format (not JSON)..."
JSON_COUNT=$(grep -l "\"role\":" "${ROLE_FILES[@]}" 2>/dev/null | wc -l | tr -d ' ')
if [ "$JSON_COUNT" -eq 0 ]; then
  echo "   ✅ No JSON contracts found in role files"
else
  echo "   ❌ Found $JSON_COUNT role files with JSON contracts"
  grep -l "\"role\":" "${ROLE_FILES[@]}" || true
  ERRORS=$((ERRORS + 1))
fi

echo ""
echo "2. Checking all role files have ---HANDOFF--- format..."
HANDOFF_COUNT=$(grep -l "^---HANDOFF---$" "${ROLE_FILES[@]}" 2>/dev/null | wc -l | tr -d ' ')
if [ "$HANDOFF_COUNT" -eq "$EXPECTED_ROLE_COUNT" ]; then
  echo "   ✅ All $EXPECTED_ROLE_COUNT role files have ---HANDOFF--- format"
else
  echo "   ⚠️  Found $HANDOFF_COUNT/$EXPECTED_ROLE_COUNT role files with ---HANDOFF--- format"
  echo "   (This is informational - role files define the contract, they don't need to contain literal examples)"
fi

echo ""
echo "3. Checking for 'Context Is In Your Prompt' contradictions..."
CONTEXT_COUNT=$(grep -l "Context Is In Your Prompt" "${ROLE_FILES[@]}" 2>/dev/null | wc -l | tr -d ' ')
if [ "$CONTEXT_COUNT" -eq 0 ]; then
  echo "   ✅ No 'Context Is In Your Prompt' found"
else
  echo "   ❌ Found in $CONTEXT_COUNT files"
  grep -l "Context Is In Your Prompt" "${ROLE_FILES[@]}" || true
  ERRORS=$((ERRORS + 1))
fi

echo ""
echo "4. Checking workflow documents Claude bridge probe and runtime dispatch..."
BRIDGE_SCRIPT_COUNT=$(grep -c "scripts/quest_claude_bridge.py" .skills/quest/delegation/workflow.md || true)
BRIDGE_PROBE_COUNT=$(grep -c "claude_bridge_available" .skills/quest/delegation/workflow.md || true)
BRIDGE_PROBE_HELPER_COUNT=$(grep -c "scripts/quest_claude_probe.py" .skills/quest/delegation/workflow.md || true)
RUNTIME_SELECTION_COUNT=$(grep -c "selected model/runtime" .skills/quest/delegation/workflow.md || true)
BRIDGE_RUNNER_COUNT=$(grep -c "scripts/quest_claude_runner.py" .skills/quest/delegation/workflow.md || true)
BYPASS_PERMS_COUNT=$(grep -c "bypassPermissions" .skills/quest/delegation/workflow.md || true)
STATE_HELPER_COUNT=$(grep -c "scripts/quest_state.py" .skills/quest/delegation/workflow.md || true)
NATIVE_TASK_COUNT=$(grep -c 'native `Task(...)\` is available\|native `Task(...)` when available' .skills/quest/delegation/workflow.md || true)
CODEX_HOST_COUNT=$(grep -c "orchestrator is Codex" .skills/quest/delegation/workflow.md || true)
if [ "$BRIDGE_SCRIPT_COUNT" -gt 0 ] && [ "$BRIDGE_PROBE_COUNT" -gt 0 ] && [ "$BRIDGE_PROBE_HELPER_COUNT" -gt 0 ] && [ "$RUNTIME_SELECTION_COUNT" -gt 0 ] && [ "$BRIDGE_RUNNER_COUNT" -gt 0 ] && [ "$BYPASS_PERMS_COUNT" -gt 0 ] && [ "$STATE_HELPER_COUNT" -gt 0 ] && [ "$NATIVE_TASK_COUNT" -gt 0 ] && [ "$CODEX_HOST_COUNT" -gt 0 ]; then
  echo "   ✅ Workflow documents bridge probing and runtime-based dispatch"
else
  echo "   ❌ Workflow is missing bridge probing or runtime-selection guidance"
  echo "      scripts/quest_claude_bridge.py refs: $BRIDGE_SCRIPT_COUNT"
  echo "      claude_bridge_available refs: $BRIDGE_PROBE_COUNT"
  echo "      scripts/quest_claude_probe.py refs: $BRIDGE_PROBE_HELPER_COUNT"
  echo "      selected model/runtime refs: $RUNTIME_SELECTION_COUNT"
  echo "      scripts/quest_claude_runner.py refs: $BRIDGE_RUNNER_COUNT"
  echo "      bypassPermissions refs: $BYPASS_PERMS_COUNT"
  echo "      scripts/quest_state.py refs: $STATE_HELPER_COUNT"
  echo "      native Task refs: $NATIVE_TASK_COUNT"
  echo "      orchestrator is Codex refs: $CODEX_HOST_COUNT"
  ERRORS=$((ERRORS + 1))
fi

echo ""
echo "5. Checking ARTIFACTS field in minimal example..."
if grep -A 10 "Example minimal prompt" .skills/quest/delegation/workflow.md | grep -q "ARTIFACTS"; then
  echo "   ✅ Minimal example includes ARTIFACTS"
else
  echo "   ❌ Minimal example missing ARTIFACTS"
  ERRORS=$((ERRORS + 1))
fi

echo ""
echo "6. Checking helper scripts referenced in workflow.md exist on disk..."
HELPER_SCRIPTS=(
  "scripts/quest_state.py"
  "scripts/quest_claude_bridge.py"
  "scripts/quest_claude_runner.py"
  "scripts/quest_claude_probe.py"
  "scripts/quest_validate-quest-state.sh"
)
MISSING_HELPERS=0
for helper in "${HELPER_SCRIPTS[@]}"; do
  if [ ! -f "$helper" ]; then
    echo "   ❌ Missing helper script: $helper (referenced in workflow.md)"
    MISSING_HELPERS=$((MISSING_HELPERS + 1))
  fi
done
if [ "$MISSING_HELPERS" -eq 0 ]; then
  echo "   ✅ All ${#HELPER_SCRIPTS[@]} referenced helper scripts exist"
else
  echo "   ❌ $MISSING_HELPERS helper script(s) missing"
  ERRORS=$((ERRORS + 1))
fi

echo ""
echo "=== Validation Complete ==="

if [ $ERRORS -gt 0 ]; then
  echo ""
  echo "❌ Found $ERRORS error(s)"
  exit 1
else
  echo ""
  echo "✅ All checks passed"
  exit 0
fi
