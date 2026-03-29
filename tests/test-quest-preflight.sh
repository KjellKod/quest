#!/usr/bin/env bash
# Test harness for Quest preflight behavior
# Run: bash tests/test-quest-preflight.sh

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PREFLIGHT_SCRIPT="$REPO_ROOT/scripts/quest_preflight.sh"

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

write_logged_in_claude() {
  local path="$1"
  cat > "$path" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = "auth" ] && [ "$2" = "status" ]; then
  cat <<'JSON'
{"loggedIn":true,"authMethod":"claude.ai","apiProvider":"firstParty"}
JSON
  exit 0
fi
echo "unexpected claude invocation" >&2
exit 1
EOF
  chmod +x "$path"
}

write_logged_out_claude() {
  local path="$1"
  cat > "$path" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = "auth" ] && [ "$2" = "status" ]; then
  cat <<'JSON'
{"loggedIn":false,"authMethod":"none","apiProvider":"firstParty"}
JSON
  exit 0
fi
echo "unexpected claude invocation" >&2
exit 1
EOF
  chmod +x "$path"
}

write_success_bridge() {
  local path="$1"
  cat > "$path" <<'EOF'
#!/usr/bin/env python3
import json
import pathlib
import sys

args = sys.argv[1:]
prompt_file = pathlib.Path(args[args.index("--prompt-file") + 1])
artifact_path = prompt_file.parent / "probe_artifact.txt"
handoff_path = prompt_file.parent / "probe_handoff.json"

artifact_path.write_text("ok", encoding="utf-8")
handoff_path.write_text(
    json.dumps(
        {
            "status": "complete",
            "artifacts": [str(artifact_path)],
            "next": None,
            "summary": "probe ok",
        }
    ),
    encoding="utf-8",
)
print("---HANDOFF---")
print("STATUS: complete")
print(f"ARTIFACTS: {artifact_path}")
print("NEXT: null")
print("SUMMARY: probe ok")
EOF
  chmod +x "$path"
}

write_failing_bridge() {
  local path="$1"
  cat > "$path" <<'EOF'
#!/usr/bin/env python3
import sys

print("Not logged in · Please run /login", end="")
sys.exit(1)
EOF
  chmod +x "$path"
}

write_generic_failure_bridge() {
  local path="$1"
  cat > "$path" <<'EOF'
#!/usr/bin/env python3
import sys

print("bridge transport failed", end="")
sys.exit(1)
EOF
  chmod +x "$path"
}

test_quest_preflight_caches_successful_codex_bridge_probe() {
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/bin"
  write_logged_in_claude "$tmpdir/bin/claude"
  write_success_bridge "$tmpdir/fake_bridge.py"

  local cache_file output rc available source runtime_requirement cache_hit cached_source
  cache_file="$tmpdir/claude_bridge_cache.json"
  output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_CLAUDE_BRIDGE_SCRIPT="$tmpdir/fake_bridge.py" \
    QUEST_PREFLIGHT_CACHE_FILE="$cache_file" \
    QUEST_PREFLIGHT_CACHE_TTL_SECONDS=3600 \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>&1)
  rc=$?
  available=$(printf '%s' "$output" | jq -r '.available')
  source=$(printf '%s' "$output" | jq -r '.source')
  runtime_requirement=$(printf '%s' "$output" | jq -r '.runtime_requirement')
  cache_hit=$(printf '%s' "$output" | jq -r '.checks.cache_hit')
  cached_source=$(jq -r '.payload.source' "$cache_file")
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$available" = "true" ] &&
    [ "$source" = "live_probe" ] &&
    [ "$runtime_requirement" = "host_context" ] &&
    [ "$cache_hit" = "false" ] &&
    [ "$cached_source" = "live_probe" ]
}

test_quest_preflight_uses_cached_success_when_live_probe_fails() {
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/bin"
  write_logged_in_claude "$tmpdir/bin/claude"
  write_success_bridge "$tmpdir/fake_bridge.py"

  local cache_file prime_output output rc available source cache_hit auth_logged_in bridge_reachable probe_message cached_at
  cache_file="$tmpdir/claude_bridge_cache.json"
  prime_output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_CLAUDE_BRIDGE_SCRIPT="$tmpdir/fake_bridge.py" \
    QUEST_PREFLIGHT_CACHE_FILE="$cache_file" \
    QUEST_PREFLIGHT_CACHE_TTL_SECONDS=3600 \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>&1)

  write_logged_out_claude "$tmpdir/bin/claude"
  write_failing_bridge "$tmpdir/failing_bridge.py"

  output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_CLAUDE_BRIDGE_SCRIPT="$tmpdir/failing_bridge.py" \
    QUEST_PREFLIGHT_CACHE_FILE="$cache_file" \
    QUEST_PREFLIGHT_CACHE_TTL_SECONDS=3600 \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>&1)
  rc=$?
  available=$(printf '%s' "$output" | jq -r '.available')
  source=$(printf '%s' "$output" | jq -r '.source')
  cache_hit=$(printf '%s' "$output" | jq -r '.checks.cache_hit')
  auth_logged_in=$(printf '%s' "$output" | jq -r '.checks.claude_auth_logged_in')
  bridge_reachable=$(printf '%s' "$output" | jq -r '.checks.bridge_reachable')
  probe_message=$(printf '%s' "$output" | jq -r '.diagnostic.probe_message')
  cached_at=$(printf '%s' "$output" | jq -r '.cache.cached_at')
  rm -rf "$tmpdir"

  [ -n "$prime_output" ] &&
    [ "$rc" -eq 0 ] &&
    [ "$available" = "true" ] &&
    [ "$source" = "success_cache" ] &&
    [ "$cache_hit" = "true" ] &&
    [ "$auth_logged_in" = "false" ] &&
    [ "$bridge_reachable" = "true" ] &&
    [ "$probe_message" = "Not logged in · Please run /login" ] &&
    [ "$cached_at" != "null" ]
}

test_quest_preflight_does_not_use_cached_success_for_non_auth_probe_failure() {
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/bin"
  write_logged_in_claude "$tmpdir/bin/claude"
  write_success_bridge "$tmpdir/fake_bridge.py"

  local cache_file prime_output output rc available source cache_hit warning probe_message
  cache_file="$tmpdir/claude_bridge_cache.json"
  prime_output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_CLAUDE_BRIDGE_SCRIPT="$tmpdir/fake_bridge.py" \
    QUEST_PREFLIGHT_CACHE_FILE="$cache_file" \
    QUEST_PREFLIGHT_CACHE_TTL_SECONDS=3600 \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>&1)

  write_generic_failure_bridge "$tmpdir/generic_failure_bridge.py"

  output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_CLAUDE_BRIDGE_SCRIPT="$tmpdir/generic_failure_bridge.py" \
    QUEST_PREFLIGHT_CACHE_FILE="$cache_file" \
    QUEST_PREFLIGHT_CACHE_TTL_SECONDS=3600 \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>&1)
  rc=$?
  available=$(printf '%s' "$output" | jq -r '.available')
  source=$(printf '%s' "$output" | jq -r '.source')
  cache_hit=$(printf '%s' "$output" | jq -r '.checks.cache_hit')
  warning=$(printf '%s' "$output" | jq -r '.warning[0]')
  probe_message=$(printf '%s' "$output" | jq -r '.diagnostic.probe_message')
  rm -rf "$tmpdir"

  [ -n "$prime_output" ] &&
    [ "$rc" -eq 0 ] &&
    [ "$available" = "false" ] &&
    [ "$source" = "live_probe" ] &&
    [ "$cache_hit" = "false" ] &&
    [ "$warning" = "Claude bridge not available -- quest will run Codex-only (all roles)." ] &&
    [ "$probe_message" = "bridge transport failed" ]
}

run_test test_quest_preflight_caches_successful_codex_bridge_probe
run_test test_quest_preflight_uses_cached_success_when_live_probe_fails
run_test test_quest_preflight_does_not_use_cached_success_for_non_auth_probe_failure

echo ""
echo "Tests run: $TESTS_RUN"
echo "Passed:    $TESTS_PASSED"
echo "Failed:    $TESTS_FAILED"

if [ $TESTS_FAILED -ne 0 ]; then
  exit 1
fi
