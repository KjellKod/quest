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

# Like write_logged_in_claude, but also speaks `agents --json` (bg-capable CLI).
write_bg_capable_claude() {
  local path="$1"
  cat > "$path" <<'EOF'
#!/usr/bin/env bash
if [ "$1" = "auth" ] && [ "$2" = "status" ]; then
  cat <<'JSON'
{"loggedIn":true,"authMethod":"claude.ai","apiProvider":"firstParty"}
JSON
  exit 0
fi
if [ "$1" = "agents" ] && [ "$2" = "--json" ]; then
  echo "[]"
  exit 0
fi
echo "unexpected claude invocation" >&2
exit 1
EOF
  chmod +x "$path"
}

# Forces claude_role_transport for a test scenario.
write_allowlist() {
  local path="$1"
  local transport="$2"
  printf '{"claude_role_transport": "%s"}\n' "$transport" > "$path"
}

# Fake scripts/claude_bg_run.py: writes the probe artifact + handoff next to
# the prompt file (same contract as the success bridge shim) and exits 0.
write_success_bg_runner() {
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
print(json.dumps({"status": "ok", "message": "completed; declared artifacts present"}))
EOF
  chmod +x "$path"
}

write_prompt_not_consumed_bg_runner() {
  local path="$1"
  cat > "$path" <<'EOF'
#!/usr/bin/env python3
import json
import sys

print(json.dumps({
    "status": "blocked",
    "message": "background session registered but did not consume the initial prompt (Claude CLI reported: send a prompt to start)",
}))
sys.exit(4)
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
  write_allowlist "$tmpdir/allowlist.json" "bridge"

  local cache_file output rc available source runtime_requirement cache_hit cached_source
  cache_file="$tmpdir/claude_bridge_cache.json"
  output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
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
  write_allowlist "$tmpdir/allowlist.json" "bridge"

  local cache_file prime_output output rc available source cache_hit auth_logged_in bridge_reachable probe_message cached_at
  cache_file="$tmpdir/claude_bridge_cache.json"
  prime_output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
    QUEST_CLAUDE_BRIDGE_SCRIPT="$tmpdir/fake_bridge.py" \
    QUEST_PREFLIGHT_CACHE_FILE="$cache_file" \
    QUEST_PREFLIGHT_CACHE_TTL_SECONDS=3600 \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>&1)

  write_logged_out_claude "$tmpdir/bin/claude"
  write_failing_bridge "$tmpdir/failing_bridge.py"

  output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
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
  write_allowlist "$tmpdir/allowlist.json" "bridge"

  local cache_file prime_output output rc available source cache_hit warning probe_message
  cache_file="$tmpdir/claude_bridge_cache.json"
  prime_output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
    QUEST_CLAUDE_BRIDGE_SCRIPT="$tmpdir/fake_bridge.py" \
    QUEST_PREFLIGHT_CACHE_FILE="$cache_file" \
    QUEST_PREFLIGHT_CACHE_TTL_SECONDS=3600 \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>&1)

  write_generic_failure_bridge "$tmpdir/generic_failure_bridge.py"

  output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
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

test_quest_preflight_auto_prefers_background_agent_when_probe_succeeds() {
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/bin"
  write_bg_capable_claude "$tmpdir/bin/claude"
  write_success_bg_runner "$tmpdir/fake_bg_runner.py"
  write_allowlist "$tmpdir/allowlist.json" "auto"

  local bg_cache_file output rc transport downgraded available agents_json_ok cached_available
  bg_cache_file="$tmpdir/claude_bg_cache.json"
  output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
    QUEST_CLAUDE_BG_RUNNER_SCRIPT="$tmpdir/fake_bg_runner.py" \
    QUEST_PREFLIGHT_BG_CACHE_FILE="$bg_cache_file" \
    QUEST_PREFLIGHT_CACHE_TTL_SECONDS=3600 \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>&1)
  rc=$?
  transport=$(printf '%s' "$output" | jq -r '.transport')
  downgraded=$(printf '%s' "$output" | jq -r '.transport_downgraded')
  available=$(printf '%s' "$output" | jq -r '.available')
  agents_json_ok=$(printf '%s' "$output" | jq -r '.checks.agents_json_ok')
  cached_available=$(jq -r '.payload.available' "$bg_cache_file")
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$transport" = "background-agent" ] &&
    [ "$downgraded" = "false" ] &&
    [ "$available" = "true" ] &&
    [ "$agents_json_ok" = "true" ] &&
    [ "$cached_available" = "true" ]
}

test_quest_preflight_auto_blocks_instead_of_downgrading_to_bridge() {
  # CLI without `agents --json` support → bg unavailable. In auto mode this is
  # a user decision point, not implicit consent to the API-metered bridge.
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/bin"
  write_logged_in_claude "$tmpdir/bin/claude"
  write_success_bridge "$tmpdir/fake_bridge.py"
  write_allowlist "$tmpdir/allowlist.json" "auto"

  local output rc transport downgraded available warning_text
  output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
    QUEST_CLAUDE_BRIDGE_SCRIPT="$tmpdir/fake_bridge.py" \
    QUEST_PREFLIGHT_CACHE_FILE="$tmpdir/claude_bridge_cache.json" \
    QUEST_PREFLIGHT_BG_CACHE_FILE="$tmpdir/claude_bg_cache.json" \
    QUEST_PREFLIGHT_CACHE_TTL_SECONDS=3600 \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>&1)
  rc=$?
  transport=$(printf '%s' "$output" | jq -r '.transport')
  downgraded=$(printf '%s' "$output" | jq -r '.transport_downgraded')
  available=$(printf '%s' "$output" | jq -r '.available')
  warning_text=$(printf '%s' "$output" | jq -r '.warning | join(" ")')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$transport" = "background-agent" ] &&
    [ "$downgraded" = "false" ] &&
    [ "$available" = "false" ] &&
    printf '%s' "$warning_text" | grep -q "make it explicit"
}

test_quest_preflight_reports_bg_prompt_not_consumed() {
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/bin"
  write_bg_capable_claude "$tmpdir/bin/claude"
  write_prompt_not_consumed_bg_runner "$tmpdir/fake_bg_runner.py"
  write_allowlist "$tmpdir/allowlist.json" "auto"

  local output rc kind warning_text
  output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
    QUEST_CLAUDE_BG_RUNNER_SCRIPT="$tmpdir/fake_bg_runner.py" \
    QUEST_PREFLIGHT_BG_CACHE_FILE="$tmpdir/claude_bg_cache.json" \
    QUEST_PREFLIGHT_CACHE_TTL_SECONDS=3600 \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>&1)
  rc=$?
  kind=$(printf '%s' "$output" | jq -r '.diagnostic.probe_result_kind')
  warning_text=$(printf '%s' "$output" | jq -r '.warning | join(" ")')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$kind" = "bg_initial_prompt_not_consumed" ] &&
    printf '%s' "$warning_text" | grep -q "did not consume the initial prompt"
}

test_quest_preflight_forced_background_agent_blocks_without_bridge_fallback() {
  # Forced background-agent with an incapable CLI must report unavailable
  # (never silently probe/fall back to the bridge).
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/bin"
  write_logged_in_claude "$tmpdir/bin/claude"
  write_success_bridge "$tmpdir/fake_bridge.py"
  write_allowlist "$tmpdir/allowlist.json" "background-agent"

  local output rc transport available warning_text
  output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
    QUEST_CLAUDE_BRIDGE_SCRIPT="$tmpdir/fake_bridge.py" \
    QUEST_PREFLIGHT_BG_CACHE_FILE="$tmpdir/claude_bg_cache.json" \
    QUEST_PREFLIGHT_CACHE_TTL_SECONDS=3600 \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>&1)
  rc=$?
  transport=$(printf '%s' "$output" | jq -r '.transport')
  available=$(printf '%s' "$output" | jq -r '.available')
  warning_text=$(printf '%s' "$output" | jq -r '.warning | join(" ")')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$transport" = "background-agent" ] &&
    [ "$available" = "false" ] &&
    printf '%s' "$warning_text" | grep -q "Background-agent transport not available"
}

test_quest_preflight_rejects_invalid_transport_config() {
  # A present-but-invalid claude_role_transport must fail closed with a config
  # diagnostic — never be coerced to "auto" (a typo could pick a different
  # billing path or silently downgrade to the bridge).
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/bin"
  write_logged_in_claude "$tmpdir/bin/claude"
  write_success_bridge "$tmpdir/fake_bridge.py"
  write_allowlist "$tmpdir/allowlist.json" "bridg"

  local output rc available transport kind warning_text
  output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
    QUEST_CLAUDE_BRIDGE_SCRIPT="$tmpdir/fake_bridge.py" \
    QUEST_PREFLIGHT_BG_CACHE_FILE="$tmpdir/claude_bg_cache.json" \
    QUEST_PREFLIGHT_CACHE_TTL_SECONDS=3600 \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>&1)
  rc=$?
  available=$(printf '%s' "$output" | jq -r '.available')
  transport=$(printf '%s' "$output" | jq -r '.transport')
  kind=$(printf '%s' "$output" | jq -r '.diagnostic.probe_result_kind')
  warning_text=$(printf '%s' "$output" | jq -r '.warning | join(" ")')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$available" = "false" ] &&
    [ "$transport" = "bridg" ] &&
    [ "$kind" = "invalid_transport_config" ] &&
    printf '%s' "$warning_text" | grep -q "Invalid claude_role_transport 'bridg'"
}

test_quest_preflight_invalid_transport_emits_valid_json_for_special_chars() {
  # The fail-closed payload must stay valid JSON even when the bad transport
  # value contains a quote/backslash — the value is JSON-encoded, not embedded
  # raw into the warning array.
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/bin"
  write_logged_in_claude "$tmpdir/bin/claude"
  write_success_bridge "$tmpdir/fake_bridge.py"
  # allowlist value: bad"q\z  (embedded double-quote and backslash)
  printf '{"claude_role_transport": "bad\\"q\\\\z"}\n' > "$tmpdir/allowlist.json"

  local output rc available kind
  output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
    QUEST_CLAUDE_BRIDGE_SCRIPT="$tmpdir/fake_bridge.py" \
    QUEST_PREFLIGHT_BG_CACHE_FILE="$tmpdir/claude_bg_cache.json" \
    QUEST_PREFLIGHT_CACHE_TTL_SECONDS=3600 \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>&1)
  rc=$?
  available=$(printf '%s' "$output" | jq -r '.available')
  kind=$(printf '%s' "$output" | jq -r '.diagnostic.probe_result_kind')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    printf '%s' "$output" | jq -e . >/dev/null 2>&1 &&
    [ "$available" = "false" ] &&
    [ "$kind" = "invalid_transport_config" ]
}

test_quest_preflight_resolves_helpers_by_absolute_path_from_foreign_cwd() {
  # Quest installed outside the target repo: invoke preflight by ABSOLUTE path
  # from a cwd with no scripts/ dir and WITHOUT helper-path overrides. The
  # script must resolve its helpers next to itself (SCRIPT_DIR), so
  # bridge_script_exists is true regardless of cwd. (Pre-fix: false.)
  local tmpdir bridge_exists
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/bin"
  write_logged_in_claude "$tmpdir/bin/claude"
  write_allowlist "$tmpdir/allowlist.json" "bridge"

  bridge_exists=$(cd "$tmpdir" && PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
    QUEST_PREFLIGHT_CACHE_FILE="$tmpdir/bridge_cache.json" \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>/dev/null \
    | jq -r '.checks.bridge_script_exists')
  rm -rf "$tmpdir"

  [ "$bridge_exists" = "true" ]
}

test_quest_preflight_resolves_helpers_through_symlinked_entrypoint() {
  # A symlinked entrypoint must still resolve helpers to the REAL install dir
  # (BASH_SOURCE points at the symlink; SCRIPT_DIR must follow it).
  local tmpdir bridge_exists
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/bin"
  write_logged_in_claude "$tmpdir/bin/claude"
  write_allowlist "$tmpdir/allowlist.json" "bridge"
  ln -s "$PREFLIGHT_SCRIPT" "$tmpdir/bin/preflight_link.sh"

  bridge_exists=$(cd "$tmpdir" && PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
    QUEST_PREFLIGHT_CACHE_FILE="$tmpdir/bridge_cache.json" \
    "$tmpdir/bin/preflight_link.sh" --orchestrator codex 2>/dev/null \
    | jq -r '.checks.bridge_script_exists')
  rm -rf "$tmpdir"

  [ "$bridge_exists" = "true" ]
}

test_quest_preflight_reports_missing_probe_helper_diagnostic() {
  # A missing probe helper yields an explicit diagnostic, not a blank message.
  local tmpdir kind msg
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/bin"
  write_logged_in_claude "$tmpdir/bin/claude"
  write_success_bridge "$tmpdir/fake_bridge.py"
  write_allowlist "$tmpdir/allowlist.json" "bridge"

  local output
  output=$(PATH="$tmpdir/bin:$PATH" \
    QUEST_ALLOWLIST_FILE="$tmpdir/allowlist.json" \
    QUEST_CLAUDE_BRIDGE_SCRIPT="$tmpdir/fake_bridge.py" \
    QUEST_CLAUDE_PROBE_SCRIPT="$tmpdir/does_not_exist_probe.py" \
    QUEST_PREFLIGHT_CACHE_FILE="$tmpdir/bridge_cache.json" \
    "$PREFLIGHT_SCRIPT" --orchestrator codex 2>/dev/null)
  kind=$(printf '%s' "$output" | jq -r '.diagnostic.probe_result_kind')
  msg=$(printf '%s' "$output" | jq -r '.diagnostic.probe_message')
  rm -rf "$tmpdir"

  [ "$kind" = "preflight_invocation_error" ] &&
    printf '%s' "$msg" | grep -q "does_not_exist_probe.py"
}

run_test test_quest_preflight_resolves_helpers_by_absolute_path_from_foreign_cwd
run_test test_quest_preflight_resolves_helpers_through_symlinked_entrypoint
run_test test_quest_preflight_reports_missing_probe_helper_diagnostic
run_test test_quest_preflight_caches_successful_codex_bridge_probe
run_test test_quest_preflight_uses_cached_success_when_live_probe_fails
run_test test_quest_preflight_does_not_use_cached_success_for_non_auth_probe_failure
run_test test_quest_preflight_auto_prefers_background_agent_when_probe_succeeds
run_test test_quest_preflight_auto_blocks_instead_of_downgrading_to_bridge
run_test test_quest_preflight_reports_bg_prompt_not_consumed
run_test test_quest_preflight_forced_background_agent_blocks_without_bridge_fallback
run_test test_quest_preflight_rejects_invalid_transport_config
run_test test_quest_preflight_invalid_transport_emits_valid_json_for_special_chars

echo ""
echo "Tests run: $TESTS_RUN"
echo "Passed:    $TESTS_PASSED"
echo "Failed:    $TESTS_FAILED"

if [ $TESTS_FAILED -ne 0 ]; then
  exit 1
fi
