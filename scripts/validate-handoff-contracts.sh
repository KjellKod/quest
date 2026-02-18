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
echo "4. Checking workflow has Codex-only invocations..."
TASK_COUNT=$(grep -c "Task tool with.*agent" .skills/quest/delegation/workflow.md || true)
CODEX_COUNT=$(grep -c "mcp__codex__codex" .skills/quest/delegation/workflow.md || true)
if [ "$TASK_COUNT" -eq 0 ]; then
  echo "   ✅ No Task tool invocations found (Codex-only: $CODEX_COUNT)"
else
  echo "   ❌ Found $TASK_COUNT Task tool invocations (should be 0, Codex-only)"
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
