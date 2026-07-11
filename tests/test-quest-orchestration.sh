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
OPENCODE_QUEST_MD="$REPO_ROOT/.opencode/agents/quest.md"
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
    "review-arbiter": "claude",
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
expected_keys = ["planner","plan-reviewer-a","plan-reviewer-b","arbiter","builder","code-reviewer-a","code-reviewer-b","review-arbiter","fixer"]
assert list(orch["models"].keys()) == expected_keys, orch["models"]
for k in expected_keys:
    assert orch["models"][k] == snap["models"][k], (k, orch["models"][k], snap["models"][k])
PY
  rm -rf "$tmpdir"
}

test_chooser_default_writer_remaps_unavailable_active_models() {
  # If the user continues a Codex-led quest without Claude bridge availability,
  # the default path must not persist unavailable Claude-family active roles.
  local tmpdir orch_file
  tmpdir=$(mktemp -d)
  orch_file="$tmpdir/orchestration.json"

  python3 - "$orch_file" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import json, sys
from pathlib import Path
from quest_runtime.orchestration import write_default_from_allowlist

write_default_from_allowlist(
    Path(sys.argv[1]),
    {
        "planner": "gpt-5.5",
        "plan-reviewer-a": "claude",
        "plan-reviewer-b": "gpt-5.5",
        "arbiter": "claude",
        "builder": "gpt-5.5",
        "code-reviewer-a": "claude-opus-4.7",
        "code-reviewer-b": "gpt-5.5",
        "fixer": "gpt-5.5",
    },
    orchestrator="codex",
    codex_available=True,
    claude_available=False,
    quest_mode="workflow",
    remap_unavailable=True,
    preflight_validated_at="2026-05-18T05:42:13Z",
)
orch = json.loads(Path(sys.argv[1]).read_text())
assert orch["models"]["plan-reviewer-a"] == "gpt-5.6-sol", orch
assert orch["models"]["arbiter"] == "gpt-5.6-sol", orch
assert orch["models"]["code-reviewer-a"] == "gpt-5.6-sol", orch
assert orch["models"]["builder"] == "gpt-5.5", orch
PY
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
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
assert result["plan-reviewer-a"] == "claude-opus-4-8", result
assert result["plan-reviewer-b"] == "gpt-5.6-terra", result
assert result["arbiter"] == "claude-opus-4-8", result
assert result["code-reviewer-a"] == "claude-opus-4-8", result
assert result["code-reviewer-b"] == "gpt-5.6-terra", result
assert result["fixer"] == "gpt-5.6-terra", result
PY
}

test_repo_default_models_match_recommended_matrix() {
  python3 - <<PY
${PY_HELPER}
import json
from pathlib import Path
from quest_runtime.orchestration import CODEX_NATIVE_FALLBACK_MODEL, DEFAULT_MODELS

expected = {
    "planner": "gpt-5.6-sol",
    "plan-reviewer-a": "claude-opus-4-8",
    "plan-reviewer-b": "gpt-5.6-terra",
    "arbiter": "claude-opus-4-8",
    "builder": "gpt-5.6-sol",
    "code-reviewer-a": "claude-opus-4-8",
    "code-reviewer-b": "gpt-5.6-terra",
    "review-arbiter": "claude-opus-4-8",
    "fixer": "gpt-5.6-terra",
}
allowlist = json.loads(Path(".ai/allowlist.json").read_text())
assert DEFAULT_MODELS == expected, DEFAULT_MODELS
assert allowlist["models"] == expected, allowlist["models"]
assert CODEX_NATIVE_FALLBACK_MODEL == "gpt-5.6-sol", CODEX_NATIVE_FALLBACK_MODEL
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
  # model is unavailable and is_model_available must reject it. Claude-family
  # model names are still available in Claude-led sessions because they do not
  # use the Codex runtime.
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
assert is_model_available("claude-opus-4.7", codex_available=codex_available) is True
assert is_model_available("claude-sonnet-4-5", codex_available=codex_available) is True
# codex / gpt-5.5 should be rejected when codex unavailable
assert is_model_available("codex", codex_available=codex_available) is False
assert is_model_available("gpt-5.5", codex_available=codex_available) is False
# When cache flips true, non-claude models are accepted again
PY
  local rc=$?
  rm -rf "$tmpdir"
  [ "$rc" -eq 0 ]
}

test_chooser_gates_claude_family_in_codex_led_session() {
  python3 - <<PY
${PY_HELPER}
from quest_runtime.orchestration import is_model_available_for_orchestrator

assert is_model_available_for_orchestrator(
    "gpt-5.5",
    orchestrator="codex",
    codex_available=True,
    claude_available=False,
) is True
assert is_model_available_for_orchestrator(
    "claude",
    orchestrator="codex",
    codex_available=True,
    claude_available=False,
) is False
assert is_model_available_for_orchestrator(
    "claude-opus-4.7",
    orchestrator=" Codex ",
    codex_available=True,
    claude_available=True,
) is True
PY
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

test_chooser_accepts_wrapped_json_overrides() {
  python3 - <<PY
${PY_HELPER}
from quest_runtime.orchestration import parse_override_line, Override
result = parse_override_line('''{
  "models": {
    "planner": "gpt-5.6-sol",
    "builder": "claude-opus-4-8"
  }
}''')
assert result == [
    Override("planner", "gpt-5.6-sol"),
    Override("builder", "claude-opus-4-8"),
], result
PY
}

test_chooser_accepts_models_json_fragment() {
  # This is the exact shape users commonly paste after copying a models block.
  python3 - <<PY
${PY_HELPER}
from quest_runtime.orchestration import parse_override_line, Override
result = parse_override_line('''"models": {
  "planner": "gpt-5.6-sol",
  "fixer": "gpt-5.6-terra"
}''')
assert result == [
    Override("planner", "gpt-5.6-sol"),
    Override("fixer", "gpt-5.6-terra"),
], result
PY
}

test_chooser_accepts_direct_json_role_map() {
  python3 - <<PY
${PY_HELPER}
from quest_runtime.orchestration import parse_override_line, Override
result = parse_override_line('''{
  "Planner": "gpt-5.6-sol",
  "code-reviewer-a": "claude-opus-4-8"
}''')
assert result == [
    Override("planner", "gpt-5.6-sol"),
    Override("code-reviewer-a", "claude-opus-4-8"),
], result
PY
}

test_chooser_rejects_invalid_json_override_values() {
  python3 - <<PY
${PY_HELPER}
from quest_runtime.orchestration import parse_override_line, OverrideParseError
bad_inputs = (
    '{"models": {"planner": null}}',
    '{"models": {"planner": ""}}',
    '{"models": {"plannr": "gpt-5.6-sol"}}',
    '{"models": ["gpt-5.6-sol"]}',
    '{"models": {"planner": "gpt-5.6-sol"}',
)
for bad in bad_inputs:
    try:
        parse_override_line(bad)
    except OverrideParseError:
        continue
    raise SystemExit(f"Expected OverrideParseError for {bad!r}")
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
for k in ["planner","plan-reviewer-a","plan-reviewer-b","arbiter","builder","code-reviewer-a","code-reviewer-b","review-arbiter","fixer"]:
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
    "planner": "claude",
    "plan-reviewer-a": "claude",
    "plan-reviewer-b": "claude",
    "arbiter": "claude",
    "builder": "claude",
    "code-reviewer-a": "claude",
    "code-reviewer-b": "claude",
    "fixer": "claude"
  }
}
EOF
  python3 - "$tmpdir" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import json
import sys
from pathlib import Path
from quest_runtime.orchestration import migrate_from_snapshot
written = migrate_from_snapshot(Path(sys.argv[1]))
assert written is True, "expected legacy role backfill write"
orch = json.loads((Path(sys.argv[1]) / "orchestration.json").read_text())
assert orch["models"]["review-arbiter"] == "claude-opus-4-8", orch["models"]
PY

  rm -f "$tmpdir/orchestration.json"
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

test_resume_backfills_existing_legacy_orchestration_json() {
  # Existing orchestration.json created before review-arbiter was introduced
  # should self-heal on resume.
  local tmpdir
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

  python3 - "$tmpdir" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import json
import sys
from pathlib import Path
from quest_runtime.orchestration import migrate_from_snapshot
quest_dir = Path(sys.argv[1])
written = migrate_from_snapshot(quest_dir)
assert written is True, "expected legacy backfill write"
orch = json.loads((quest_dir / "orchestration.json").read_text())
assert orch["models"]["review-arbiter"] == "claude-opus-4-8", orch["models"]
assert orch["source"] == "overridden", orch
assert orch["overridden_roles"] == ["planner", "builder"], orch
PY

  rm -rf "$tmpdir"
}

test_resume_backfills_transport_keys_on_pre_transport_orchestration_json() {
  # orchestration.json written before claude_role_transport existed should
  # self-heal on resume: transport keys added at defaults, everything else
  # (models, source, overrides, timestamp) preserved.
  local tmpdir
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
    "review-arbiter": "claude",
    "fixer": "claude"
  },
  "source": "overridden",
  "overridden_roles": ["planner", "builder"],
  "preflight_validated_at": "2026-05-18T05:42:13Z"
}
EOF

  python3 - "$tmpdir" <<PY || { rm -rf "$tmpdir"; return 1; }
${PY_HELPER}
import json
import sys
from pathlib import Path
from quest_runtime.orchestration import migrate_from_snapshot
quest_dir = Path(sys.argv[1])
written = migrate_from_snapshot(quest_dir)
assert written is True, "expected transport-key backfill write"
orch = json.loads((quest_dir / "orchestration.json").read_text())
assert orch["claude_role_transport"] == "auto", orch
assert orch["claude_transport_resolved"] is None, orch
assert orch["claude_transport_downgraded"] is False, orch
assert orch["models"]["planner"] == "claude", orch["models"]
assert orch["source"] == "overridden", orch
assert orch["overridden_roles"] == ["planner", "builder"], orch
assert orch["preflight_validated_at"] == "2026-05-18T05:42:13Z", orch
PY

  rm -rf "$tmpdir"
}

test_resume_rejects_present_but_invalid_claude_role_transport() {
  # A present-but-invalid transport must fail closed, not be silently coerced
  # to "auto" (a mistyped forced transport would otherwise resume differently).
  local tmpdir
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
    "review-arbiter": "claude",
    "fixer": "claude"
  },
  "claude_role_transport": "bridg",
  "claude_transport_resolved": null,
  "claude_transport_downgraded": false,
  "source": "overridden",
  "overridden_roles": [],
  "preflight_validated_at": "2026-05-18T05:42:13Z"
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
    assert "claude_role_transport" in str(exc), exc
    sys.exit(0)
raise SystemExit("expected ValueError for present-but-invalid transport")
PY

  rm -rf "$tmpdir"
}

test_resume_does_not_modify_existing_complete_orchestration_json() {
  # Existing complete orchestration.json must be preserved byte-for-byte.
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
    "review-arbiter": "claude",
    "fixer": "claude"
  },
  "claude_role_transport": "auto",
  "claude_transport_resolved": null,
  "claude_transport_downgraded": false,
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

test_workflow_defaults_are_not_dispatch_fallbacks() {
  if grep -n 'defaults above apply when a key is missing' "$WORKFLOW_MD"; then
    return 1
  fi
  if grep -n 'missing or non-string active-role model keys' "$WORKFLOW_MD"; then
    return 1
  fi
  return 0
}

test_opencode_dispatch_uses_orchestration_json() {
  if grep -n 'For these roles, use `codex_codex`' "$OPENCODE_QUEST_MD"; then
    return 1
  fi
  if grep -n 'All other roles use `task`' "$OPENCODE_QUEST_MD"; then
    return 1
  fi
  if ! grep -q '.quest/<id>/orchestration.json' "$OPENCODE_QUEST_MD"; then
    return 1
  fi
  return 0
}

# ---- Run all tests ----

echo "=== Quest Orchestration Tests ==="
echo ""

run_test test_chooser_default_writer_contract
run_test test_chooser_default_writer_remaps_unavailable_active_models
run_test test_chooser_override_writer_contract
run_test test_default_models_fill_missing_allowlist_keys
run_test test_repo_default_models_match_recommended_matrix
run_test test_chooser_ignores_unused_solo_roles
run_test test_chooser_rejects_unavailable_codex_model
run_test test_chooser_gates_claude_family_in_codex_led_session
run_test test_chooser_accepts_top_level_preflight_available
run_test test_chooser_requires_literal_true_preflight_available
run_test test_chooser_accepts_valid_model_names_with_dashes
run_test test_chooser_accepts_wrapped_json_overrides
run_test test_chooser_accepts_models_json_fragment
run_test test_chooser_accepts_direct_json_role_map
run_test test_chooser_rejects_invalid_json_override_values
run_test test_chooser_rejects_unknown_role
run_test test_chooser_rejects_multiple_equals
run_test test_chooser_skips_empty_pieces
run_test test_chooser_normalizes_role_case
run_test test_resume_migrates_missing_orchestration_json
run_test test_resume_reports_missing_or_invalid_snapshot
run_test test_resume_backfills_existing_legacy_orchestration_json
run_test test_resume_backfills_transport_keys_on_pre_transport_orchestration_json
run_test test_resume_rejects_present_but_invalid_claude_role_transport
run_test test_resume_does_not_modify_existing_complete_orchestration_json
run_test test_workflow_dispatch_reads_orchestration_json_not_allowlist
run_test test_workflow_no_allowlist_models_string
run_test test_workflow_defaults_are_not_dispatch_fallbacks
run_test test_opencode_dispatch_uses_orchestration_json

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
