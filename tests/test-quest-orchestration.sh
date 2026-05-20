#!/usr/bin/env bash
# Test harness for per-quest orchestration override behaviour.
# Run: bash tests/test-quest-orchestration.sh
# Exit 0 = all tests pass, 1 = some tests failed
#
# Source: SKILL.md §8.5 last sync 2026-05-18
#
# The chooser itself is markdown prose for an orchestrator LLM, so these tests
# exercise the contract those instructions encode via scripts/quest_runtime/
# orchestration.py. When the SKILL.md prose changes, this harness MUST be
# re-aligned so the tests do not drift from the actual behaviour.

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
WORKFLOW_MD="$REPO_ROOT/.skills/quest/delegation/workflow.md"
PY_HELPER='import sys, pathlib; sys.path.insert(0, str(pathlib.Path("'"$REPO_ROOT"'/scripts").resolve()));'

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

# ---- Helpers ----

write_allowlist_snapshot() {
  # $1 = path to write snapshot json
  cat > "$1" <<'EOF'
{
  "version": 2,
  "models": {
    "planner": "gpt-5.5",
    "plan-reviewer-a": "claude",
    "plan-reviewer-b": "gpt-5.5",
    "arbiter": "claude",
    "builder": "gpt-5.5",
    "code-reviewer-a": "claude",
    "code-reviewer-b": "gpt-5.5",
    "fixer": "gpt-5.5"
  }
}
EOF
}

write_preflight_cache() {
  # $1 = path, $2 = "true" or "false"
  local available="$2"
  mkdir -p "$(dirname "$1")"
  cat > "$1" <<EOF
{
  "payload": {
    "available": $available
  }
}
EOF
}

# ---- Test cases ----

test_chooser_default_writer_contract() {
  # Default path: orchestration.json mirrors the allowlist snapshot models
  # block, with source=default and overridden_roles=[].
  local tmpdir orch_file snapshot_file
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/logs"
  snapshot_file="$tmpdir/logs/allowlist_snapshot.json"
  orch_file="$tmpdir/orchestration.json"
  write_allowlist_snapshot "$snapshot_file"

  python3 - "$tmpdir" <<PY
${PY_HELPER}
import json, sys
from pathlib import Path
from quest_runtime.orchestration import write_default_from_allowlist
quest_dir = Path(sys.argv[1])
snapshot = json.loads((quest_dir / "logs" / "allowlist_snapshot.json").read_text())
write_default_from_allowlist(
    quest_dir / "orchestration.json",
    snapshot["models"],
    preflight_validated_at="2026-05-18T05:42:13Z",
)
PY
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    rm -rf "$tmpdir"
    return 1
  fi

  python3 - "$orch_file" "$snapshot_file" <<'PY' || { rm -rf "$tmpdir"; return 1; }
import json, sys
orch = json.loads(open(sys.argv[1]).read())
snap = json.loads(open(sys.argv[2]).read())
assert orch["version"] == 1, orch
assert orch["source"] == "default", orch
assert orch["overridden_roles"] == [], orch
assert orch["preflight_validated_at"] == "2026-05-18T05:42:13Z", orch
expected_keys = ["planner","plan-reviewer-a","plan-reviewer-b","arbiter","builder","code-reviewer-a","code-reviewer-b","fixer"]
assert list(orch["models"].keys()) == expected_keys, orch["models"]
for k in expected_keys:
    assert orch["models"][k] == snap["models"][k], (k, orch["models"][k], snap["models"][k])
PY
  rm -rf "$tmpdir"
}

test_chooser_override_writer_contract() {
  # Override path: requested role swapped, the rest match the snapshot.
  local tmpdir orch_file
  tmpdir=$(mktemp -d)
  orch_file="$tmpdir/orchestration.json"

  python3 - "$orch_file" <<'PY' || { rm -rf "$tmpdir"; return 1; }
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
PY
  # We rely on the runtime path being available; re-shim via PY_HELPER.
  python3 - "$orch_file" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import json, sys
from pathlib import Path
from quest_runtime.orchestration import (
    apply_overrides, build_default_models, parse_override_line,
    write_orchestration_json,
)
allowlist_models = {
    "planner": "gpt-5.5", "plan-reviewer-a": "claude",
    "plan-reviewer-b": "gpt-5.5", "arbiter": "claude",
    "builder": "gpt-5.5", "code-reviewer-a": "claude",
    "code-reviewer-b": "gpt-5.5", "fixer": "gpt-5.5",
}
defaults = build_default_models(allowlist_models)
overrides = parse_override_line("planner=claude, builder=claude")
merged, overridden, ignored = apply_overrides(defaults, overrides, quest_mode="workflow")
write_orchestration_json(
    Path(sys.argv[1]),
    models=merged,
    source="overridden",
    overridden_roles=overridden,
    preflight_validated_at="2026-05-18T05:42:13Z",
)
PY

  python3 - "$orch_file" <<'PY' || { rm -rf "$tmpdir"; return 1; }
import json, sys
orch = json.loads(open(sys.argv[1]).read())
assert orch["version"] == 1
assert orch["source"] == "overridden"
assert orch["overridden_roles"] == ["planner", "builder"], orch["overridden_roles"]
assert orch["models"]["planner"] == "claude"
assert orch["models"]["builder"] == "claude"
assert orch["models"]["arbiter"] == "claude"
assert orch["models"]["plan-reviewer-b"] == "gpt-5.5"
PY
  rm -rf "$tmpdir"
}

test_default_models_fill_missing_allowlist_keys() {
  python3 - <<PY
${PY_HELPER}
from quest_runtime.orchestration import build_default_models
result = build_default_models({"planner": "gpt-5.5", "builder": "claude"})
assert result["planner"] == "gpt-5.5", result
assert result["builder"] == "claude", result
assert result["plan-reviewer-a"] == "claude", result
assert result["plan-reviewer-b"] == "gpt-5.5", result
assert result["arbiter"] == "claude", result
assert result["code-reviewer-a"] == "claude", result
assert result["code-reviewer-b"] == "gpt-5.5", result
assert result["fixer"] == "gpt-5.5", result
PY
}

test_chooser_ignores_unused_solo_roles() {
  python3 - <<PY
${PY_HELPER}
from quest_runtime.orchestration import apply_overrides, build_default_models, parse_override_line
defaults = build_default_models({
    "planner": "claude",
    "plan-reviewer-a": "claude",
    "plan-reviewer-b": "gpt-5.5",
    "arbiter": "gpt-5.5",
    "builder": "claude",
    "code-reviewer-a": "claude",
    "code-reviewer-b": "gpt-5.5",
    "fixer": "claude",
})
overrides = parse_override_line("arbiter=claude, plan-reviewer-b=claude, builder=gpt-5.5")
merged, overridden, ignored = apply_overrides(defaults, overrides, quest_mode="solo")
assert merged["arbiter"] == "gpt-5.5", merged
assert merged["plan-reviewer-b"] == "gpt-5.5", merged
assert merged["builder"] == "gpt-5.5", merged
assert overridden == ["builder"], overridden
assert ignored == ["arbiter", "plan-reviewer-b"], ignored
PY
}

test_chooser_rejects_unavailable_codex_model() {
  # When preflight cache reports payload.available == false, a non-claude
  # model is unavailable and is_model_available must reject it.
  local tmpdir cache_file
  tmpdir=$(mktemp -d)
  cache_file="$tmpdir/cache/claude_bridge_codex.json"
  write_preflight_cache "$cache_file" "false"

  python3 - "$cache_file" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import sys
from pathlib import Path
from quest_runtime.orchestration import (
    is_model_available, load_codex_available_from_cache,
)
cache = Path(sys.argv[1])
codex_available = load_codex_available_from_cache(cache)
assert codex_available is False, codex_available
# claude is always allowed
assert is_model_available("claude", codex_available=codex_available) is True
# codex / gpt-5.5 should be rejected when codex unavailable
assert is_model_available("codex", codex_available=codex_available) is False
assert is_model_available("gpt-5.5", codex_available=codex_available) is False
# When cache flips true, non-claude models are accepted again
PY
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_chooser_accepts_top_level_preflight_available() {
  # Claude-led preflight emits top-level available=true rather than
  # payload.available.
  local tmpdir cache_file
  tmpdir=$(mktemp -d)
  cache_file="$tmpdir/cache/codex_preflight.json"
  mkdir -p "$(dirname "$cache_file")"
  cat > "$cache_file" <<'EOF'
{
  "available": true
}
EOF

  python3 - "$cache_file" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import sys
from pathlib import Path
from quest_runtime.orchestration import load_codex_available_from_cache
assert load_codex_available_from_cache(Path(sys.argv[1])) is True
PY
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_chooser_requires_literal_true_preflight_available() {
  # Truthy-looking strings must not enable non-Claude models.
  local tmpdir cache_file
  tmpdir=$(mktemp -d)
  cache_file="$tmpdir/cache/codex_preflight.json"
  mkdir -p "$(dirname "$cache_file")"
  cat > "$cache_file" <<'EOF'
{
  "payload": {
    "available": "true"
  }
}
EOF

  python3 - "$cache_file" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import sys
from pathlib import Path
from quest_runtime.orchestration import load_codex_available_from_cache
assert load_codex_available_from_cache(Path(sys.argv[1])) is False
PY
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_chooser_accepts_valid_model_names_with_dashes() {
  # gpt-5.5, claude-opus-4.7, o1-mini must all parse successfully.
  python3 - <<PY
${PY_HELPER}
from quest_runtime.orchestration import parse_override_line, Override
result = parse_override_line(
    "planner=gpt-5.5, builder=claude-opus-4.7, fixer=o1-mini"
)
expected = [
    Override("planner", "gpt-5.5"),
    Override("builder", "claude-opus-4.7"),
    Override("fixer", "o1-mini"),
]
assert result == expected, result
PY
}

test_chooser_rejects_unknown_role() {
  python3 - <<PY
${PY_HELPER}
from quest_runtime.orchestration import parse_override_line, OverrideParseError
try:
    parse_override_line("plannr=claude")
except OverrideParseError as exc:
    assert "Unknown role" in str(exc), exc
    assert "plannr" in str(exc), exc
    raise SystemExit(0)
raise SystemExit("Expected OverrideParseError but none was raised")
PY
}

test_chooser_rejects_multiple_equals() {
  python3 - <<PY
${PY_HELPER}
from quest_runtime.orchestration import parse_override_line, OverrideParseError
for bad in ("planner==claude", "planner=foo=bar", "planner"):
    try:
        parse_override_line(bad)
    except OverrideParseError:
        continue
    raise SystemExit(f"Expected OverrideParseError for {bad!r}")
PY
}

test_chooser_skips_empty_pieces() {
  # A trailing comma should yield zero empty overrides and not raise.
  python3 - <<PY
${PY_HELPER}
from quest_runtime.orchestration import parse_override_line, Override
result = parse_override_line("planner=claude,")
assert result == [Override("planner", "claude")], result
result = parse_override_line(", planner=claude , , builder=claude")
assert result == [
    Override("planner", "claude"),
    Override("builder", "claude"),
], result
result = parse_override_line("")
assert result == [], result
PY
}

test_chooser_normalizes_role_case() {
  # Role names are case-insensitive at input; canonical form is lowercase.
  python3 - <<PY
${PY_HELPER}
from quest_runtime.orchestration import parse_override_line, Override
result = parse_override_line("Planner=claude, BUILDER=claude")
assert result == [
    Override("planner", "claude"),
    Override("builder", "claude"),
], result
PY
}

test_resume_migrates_missing_orchestration_json() {
  # When orchestration.json is absent on resume and the snapshot is present,
  # the migration produces a default orchestration.json from the snapshot.
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/logs"
  write_allowlist_snapshot "$tmpdir/logs/allowlist_snapshot.json"

  python3 - "$tmpdir" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import sys
from pathlib import Path
from quest_runtime.orchestration import migrate_from_snapshot
written = migrate_from_snapshot(Path(sys.argv[1]))
assert written is True, "expected a fresh write"
PY

  python3 - "$tmpdir/orchestration.json" "$tmpdir/logs/allowlist_snapshot.json" <<'PY' || { rm -rf "$tmpdir"; return 1; }
import json, sys, re
orch = json.loads(open(sys.argv[1]).read())
snap = json.loads(open(sys.argv[2]).read())
assert orch["version"] == 1
assert orch["source"] == "default"
assert orch["overridden_roles"] == []
assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", orch["preflight_validated_at"]), orch["preflight_validated_at"]
for k in ["planner","plan-reviewer-a","plan-reviewer-b","arbiter","builder","code-reviewer-a","code-reviewer-b","fixer"]:
    assert orch["models"][k] == snap["models"][k], (k, orch["models"][k], snap["models"][k])
PY
  rm -rf "$tmpdir"
}

test_resume_reports_missing_or_invalid_snapshot() {
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/logs"

  python3 - "$tmpdir" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import sys
from pathlib import Path
from quest_runtime.orchestration import migrate_from_snapshot
try:
    migrate_from_snapshot(Path(sys.argv[1]))
except ValueError as exc:
    assert "Snapshot not readable" in str(exc), exc
else:
    raise SystemExit("expected missing snapshot to raise ValueError")
PY

  printf '{ not json\n' > "$tmpdir/logs/allowlist_snapshot.json"
  python3 - "$tmpdir" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import sys
from pathlib import Path
from quest_runtime.orchestration import migrate_from_snapshot
try:
    migrate_from_snapshot(Path(sys.argv[1]))
except ValueError as exc:
    assert "is not valid JSON" in str(exc), exc
else:
    raise SystemExit("expected invalid snapshot to raise ValueError")
PY

  printf '[]\n' > "$tmpdir/logs/allowlist_snapshot.json"
  python3 - "$tmpdir" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import sys
from pathlib import Path
from quest_runtime.orchestration import migrate_from_snapshot
try:
    migrate_from_snapshot(Path(sys.argv[1]))
except ValueError as exc:
    assert "must be a JSON object" in str(exc), exc
else:
    raise SystemExit("expected non-object snapshot to raise ValueError")
PY

  cat > "$tmpdir/logs/allowlist_snapshot.json" <<'EOF'
{
  "models": {
    "planner": "claude"
  }
}
EOF
  python3 - "$tmpdir" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import sys
from pathlib import Path
from quest_runtime.orchestration import migrate_from_snapshot
try:
    migrate_from_snapshot(Path(sys.argv[1]))
except ValueError as exc:
    assert "Snapshot models missing required role" in str(exc), exc
else:
    raise SystemExit("expected incomplete snapshot to raise ValueError")
PY

  rm -rf "$tmpdir"
}

test_resume_does_not_modify_existing_orchestration_json() {
  # An existing orchestration.json must be preserved byte-for-byte by the
  # resume migration helper.
  local tmpdir orig_bytes new_bytes
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/logs"
  write_allowlist_snapshot "$tmpdir/logs/allowlist_snapshot.json"
  cat > "$tmpdir/orchestration.json" <<'EOF'
{
  "version": 1,
  "models": {
    "planner": "claude",
    "plan-reviewer-a": "claude",
    "plan-reviewer-b": "claude",
    "arbiter": "claude",
    "builder": "claude",
    "code-reviewer-a": "claude",
    "code-reviewer-b": "claude",
    "fixer": "claude"
  },
  "source": "overridden",
  "overridden_roles": ["planner", "builder"],
  "preflight_validated_at": "2026-05-18T05:42:13Z"
}
EOF
  orig_bytes=$(cat "$tmpdir/orchestration.json")

  python3 - "$tmpdir" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import sys
from pathlib import Path
from quest_runtime.orchestration import migrate_from_snapshot
written = migrate_from_snapshot(Path(sys.argv[1]))
assert written is False, "should not touch existing file"
PY

  new_bytes=$(cat "$tmpdir/orchestration.json")
  rm -rf "$tmpdir"
  [ "$orig_bytes" = "$new_bytes" ]
}

test_workflow_dispatch_reads_orchestration_json_not_allowlist() {
  # No models.<role> token in workflow.md should sit alongside a "from
  # allowlist" / ".ai/allowlist.json" reference. Every dispatch read goes
  # through the per-quest orchestration.json now.
  local matches
  matches=$(grep -nE 'models\.[a-zA-Z-]+.*(from allowlist|from the allowlist|\.ai/allowlist\.json)' "$WORKFLOW_MD" || true)
  if [ -n "$matches" ]; then
    echo "Unexpected matches in workflow.md:"
    echo "$matches"
    return 1
  fi
  return 0
}

test_workflow_no_allowlist_models_string() {
  # Mapping table rows in workflow.md may contain bare `models.<role>` tokens
  # without an adjacent "from allowlist" or ".ai/allowlist.json" reference.
  # Those rows are documentation, not dispatch sites, and are intentionally
  # excluded from this contract. The grep pattern below matches only when
  # `models.<role>` appears alongside an allowlist reference within ~60 chars.
  local matches
  matches=$(grep -nE 'models\.[a-zA-Z-]{1,30}.{0,60}(from allowlist|from the allowlist|\.ai/allowlist\.json)' "$WORKFLOW_MD" || true)
  if [ -n "$matches" ]; then
    echo "Found models.<role> still associated with allowlist text:"
    echo "$matches"
    return 1
  fi
  return 0
}

# ---- Run all tests ----

echo "=== Quest Orchestration Tests ==="
echo ""

run_test test_chooser_default_writer_contract
run_test test_chooser_override_writer_contract
run_test test_default_models_fill_missing_allowlist_keys
run_test test_chooser_ignores_unused_solo_roles
run_test test_chooser_rejects_unavailable_codex_model
run_test test_chooser_accepts_top_level_preflight_available
run_test test_chooser_requires_literal_true_preflight_available
run_test test_chooser_accepts_valid_model_names_with_dashes
run_test test_chooser_rejects_unknown_role
run_test test_chooser_rejects_multiple_equals
run_test test_chooser_skips_empty_pieces
run_test test_chooser_normalizes_role_case
run_test test_resume_migrates_missing_orchestration_json
run_test test_resume_reports_missing_or_invalid_snapshot
run_test test_resume_does_not_modify_existing_orchestration_json
run_test test_workflow_dispatch_reads_orchestration_json_not_allowlist
run_test test_workflow_no_allowlist_models_string

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
