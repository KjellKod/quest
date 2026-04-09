#!/usr/bin/env bash
# Test harness for Quest runtime helper scripts
# Run: bash tests/test-quest-runtime.sh

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
STATE_SCRIPT="$REPO_ROOT/scripts/quest_state.py"
STARTUP_BRANCH_SCRIPT="$REPO_ROOT/scripts/quest_startup_branch.py"
CLAUDE_RUNNER="$REPO_ROOT/scripts/quest_claude_runner.py"
CLAUDE_PROBE="$REPO_ROOT/scripts/quest_claude_probe.py"

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

init_git_repo() {
  local dir="$1"
  git init -b main "$dir" >/dev/null 2>&1 || {
    git init "$dir" >/dev/null 2>&1 || return 1
    git -C "$dir" checkout -b main >/dev/null 2>&1 || return 1
  }
  git -C "$dir" config user.name "Quest Test" >/dev/null 2>&1 || return 1
  git -C "$dir" config user.email "quest-test@example.com" >/dev/null 2>&1 || return 1
  printf 'seed\n' > "$dir/README.md"
  git -C "$dir" add README.md >/dev/null 2>&1 || return 1
  git -C "$dir" commit -m "init" >/dev/null 2>&1 || return 1
}

write_allowlist() {
  local dir="$1"
  local branch_mode="$2"
  mkdir -p "$dir/.ai"
  cat > "$dir/.ai/allowlist.json" <<EOF
{
  "quest_startup": {
    "branch_mode": "$branch_mode",
    "branch_prefix": "quest/",
    "worktree_root": ".worktrees/quest"
  }
}
EOF
}

test_quest_state_updates_phase_and_timestamp() {
  local tmpdir
  tmpdir=$(mktemp -d)
  cat > "$tmpdir/state.json" <<EOF
{
  "quest_id": "test_quest",
  "slug": "test",
  "phase": "plan",
  "status": "pending",
  "quest_mode": "solo",
  "plan_iteration": 0,
  "fix_iteration": 0,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
EOF

  local output
  output=$(python3 "$STATE_SCRIPT" --quest-dir "$tmpdir" --phase plan_reviewed --status complete --plan-iteration 1 2>&1)
  local rc=$?
  local phase status iter updated
  phase=$(jq -r '.phase' "$tmpdir/state.json")
  status=$(jq -r '.status' "$tmpdir/state.json")
  iter=$(jq -r '.plan_iteration' "$tmpdir/state.json")
  updated=$(jq -r '.updated_at' "$tmpdir/state.json")
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$phase" = "plan_reviewed" ] &&
    [ "$status" = "complete" ] &&
    [ "$iter" = "1" ] &&
    [ "$updated" != "2026-01-01T00:00:00Z" ] &&
    echo "$output" | grep -q '"phase": "plan_reviewed"'
}

test_quest_claude_runner_polls_handoff_and_logs_runtime() {
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/logs"
  cat > "$tmpdir/fake_bridge.py" <<'EOF'
#!/usr/bin/env python3
import json
import pathlib
import sys

args = sys.argv[1:]
prompt_file = pathlib.Path(args[args.index("--prompt-file") + 1])
argv_log = prompt_file.parent / "argv.json"
argv_log.write_text(json.dumps(args), encoding="utf-8")

if prompt_file.name == "prompt.txt":
    review_path = prompt_file.parent / "review.md"
    handoff_path = prompt_file.parent / "handoff.json"
    review_path.write_text("review body\n", encoding="utf-8")
    handoff_path.write_text(
        json.dumps(
            {
                "status": "complete",
                "artifacts": [str(review_path)],
                "next": "arbiter",
                "summary": "ok",
            }
        ),
        encoding="utf-8",
    )
    print("---HANDOFF---")
    print("STATUS: complete")
    print(f"ARTIFACTS: {review_path}")
    print("NEXT: arbiter")
    print("SUMMARY: ok")
else:
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
  chmod +x "$tmpdir/fake_bridge.py"
  cat > "$tmpdir/prompt.txt" <<EOF
Write your review to: $tmpdir/review.md
Write handoff file to: $tmpdir/handoff.json
EOF

  local output rc args_log log_line source
  output=$(python3 "$CLAUDE_RUNNER" \
    --quest-dir "$tmpdir" \
    --phase plan_review \
    --agent plan-reviewer-a \
    --iter 1 \
    --prompt-file "$tmpdir/prompt.txt" \
    --handoff-file "$tmpdir/handoff.json" \
    --bridge-script "$tmpdir/fake_bridge.py" \
    --cwd "$REPO_ROOT" 2>&1)
  rc=$?
  args_log=$(cat "$tmpdir/argv.json")
  log_line=$(cat "$tmpdir/logs/context_health.log")
  source=$(printf '%s' "$output" | jq -r '.source')
  local repo_root_escaped tmpdir_escaped
  repo_root_escaped=$(printf '%s' "$REPO_ROOT")
  tmpdir_escaped=$(printf '%s' "$tmpdir")
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    printf '%s' "$args_log" | grep -q 'bypassPermissions' &&
    printf '%s' "$args_log" | grep -q "$repo_root_escaped" &&
    printf '%s' "$args_log" | grep -q "$tmpdir_escaped" &&
    printf '%s' "$log_line" | grep -q 'runtime=claude' &&
    printf '%s' "$log_line" | grep -q 'source=' &&
    ([ "$source" = "handoff_json" ] || [ "$source" = "text_fallback" ])
}

test_quest_claude_probe_requires_real_artifacts() {
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/logs"
  cat > "$tmpdir/fake_bridge.py" <<'EOF'
#!/usr/bin/env python3
import json
import pathlib
import sys

args = sys.argv[1:]
prompt_file = pathlib.Path(args[args.index("--prompt-file") + 1])
argv_log = prompt_file.parent / "argv.json"
argv_log.write_text(json.dumps(args), encoding="utf-8")

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
  chmod +x "$tmpdir/fake_bridge.py"

  local output rc args_log probe_artifact probe_handoff source
  output=$(python3 "$CLAUDE_PROBE" \
    --quest-dir "$tmpdir" \
    --model claude-opus-4-6 \
    --bridge-script "$tmpdir/fake_bridge.py" \
    --cwd "$REPO_ROOT" 2>&1)
  rc=$?
  args_log=$(cat "$tmpdir/logs/bridge_probe/argv.json")
  probe_artifact=$(cat "$tmpdir/logs/bridge_probe/probe_artifact.txt")
  probe_handoff=$(jq -r '.summary' "$tmpdir/logs/bridge_probe/probe_handoff.json")
  source=$(printf '%s' "$output" | jq -r '.source')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$probe_artifact" = "ok" ] &&
    [ "$probe_handoff" = "probe ok" ] &&
    printf '%s' "$args_log" | grep -q 'bypassPermissions' &&
    printf '%s' "$args_log" | grep -q 'bridge_probe' &&
    [ "$source" = "handoff_json" ]
}

test_quest_state_transition_valid() {
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  touch "$tmpdir/phase_01_plan/review_plan-reviewer-a.md"
  cat > "$tmpdir/state.json" <<EOF
{
  "quest_id": "test_quest",
  "slug": "test",
  "phase": "plan_reviewed",
  "status": "complete",
  "quest_mode": "solo",
  "plan_iteration": 1,
  "fix_iteration": 0,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
EOF

  local output rc phase updated
  output=$(python3 "$STATE_SCRIPT" --quest-dir "$tmpdir" --transition presenting --status in_progress 2>&1)
  rc=$?
  phase=$(jq -r '.phase' "$tmpdir/state.json")
  updated=$(jq -r '.updated_at' "$tmpdir/state.json")
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$phase" = "presenting" ] &&
    [ "$updated" != "2026-01-01T00:00:00Z" ]
}

test_quest_state_transition_invalid_leaves_state_unchanged() {
  local tmpdir
  tmpdir=$(mktemp -d)
  cat > "$tmpdir/state.json" <<EOF
{
  "quest_id": "test_quest",
  "slug": "test",
  "phase": "building",
  "status": "in_progress",
  "quest_mode": "workflow",
  "plan_iteration": 1,
  "fix_iteration": 0,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
EOF

  local output rc phase updated
  output=$(python3 "$STATE_SCRIPT" --quest-dir "$tmpdir" --transition building 2>&1)
  rc=$?
  phase=$(jq -r '.phase' "$tmpdir/state.json")
  updated=$(jq -r '.updated_at' "$tmpdir/state.json")
  rm -rf "$tmpdir"

  [ "$rc" -eq 1 ] &&
    [ "$phase" = "building" ] &&
    [ "$updated" = "2026-01-01T00:00:00Z" ]
}

test_quest_state_transition_rejects_plan_reviewed_to_building() {
  local tmpdir
  tmpdir=$(mktemp -d)
  mkdir -p "$tmpdir/phase_01_plan"
  touch "$tmpdir/phase_01_plan/plan.md"
  echo '{"status":"complete","next":"builder","summary":"approved"}' > "$tmpdir/phase_01_plan/handoff_arbiter.json"
  cat > "$tmpdir/state.json" <<EOF
{
  "quest_id": "test_quest",
  "slug": "test",
  "phase": "plan_reviewed",
  "status": "complete",
  "quest_mode": "workflow",
  "plan_iteration": 1,
  "fix_iteration": 0,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-01T00:00:00Z"
}
EOF

  local output rc phase
  output=$(python3 "$STATE_SCRIPT" --quest-dir "$tmpdir" --transition building 2>&1)
  rc=$?
  phase=$(jq -r '.phase' "$tmpdir/state.json")
  rm -rf "$tmpdir"

  [ "$rc" -eq 1 ] &&
    [ "$phase" = "plan_reviewed" ] &&
    echo "$output" | grep -qi "rejected"
}

test_quest_startup_branch_defaults_to_branch_checkout() {
  local tmpdir
  tmpdir=$(mktemp -d)
  init_git_repo "$tmpdir" || return 1
  mkdir -p "$tmpdir/.ai"
  echo '{}' > "$tmpdir/.ai/allowlist.json"

  local output rc branch status branch_mode requested_mode
  output=$(python3 "$STARTUP_BRANCH_SCRIPT" --repo-root "$tmpdir" --allowlist "$tmpdir/.ai/allowlist.json" --slug startup-branch 2>&1)
  rc=$?
  branch=$(git -C "$tmpdir" branch --show-current)
  status=$(printf '%s' "$output" | jq -r '.status')
  branch_mode=$(printf '%s' "$output" | jq -r '.branch_mode')
  requested_mode=$(printf '%s' "$output" | jq -r '.requested_branch_mode')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$branch" = "quest/startup-branch" ] &&
    [ "$status" = "created" ] &&
    [ "$branch_mode" = "branch" ] &&
    [ "$requested_mode" = "branch" ]
}

test_quest_startup_branch_skips_when_already_on_feature_branch() {
  local tmpdir
  tmpdir=$(mktemp -d)
  init_git_repo "$tmpdir" || return 1
  write_allowlist "$tmpdir" "branch"
  git -C "$tmpdir" checkout -b feature/existing >/dev/null 2>&1 || return 1

  local output rc branch status branch_mode
  output=$(python3 "$STARTUP_BRANCH_SCRIPT" --repo-root "$tmpdir" --allowlist "$tmpdir/.ai/allowlist.json" --slug startup-branch 2>&1)
  rc=$?
  branch=$(git -C "$tmpdir" branch --show-current)
  status=$(printf '%s' "$output" | jq -r '.status')
  branch_mode=$(printf '%s' "$output" | jq -r '.branch_mode')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$branch" = "feature/existing" ] &&
    [ "$status" = "skipped" ] &&
    [ "$branch_mode" = "none" ]
}

test_quest_startup_branch_blocks_dirty_default_branch_checkout() {
  local tmpdir
  tmpdir=$(mktemp -d)
  init_git_repo "$tmpdir" || return 1
  write_allowlist "$tmpdir" "branch"
  printf 'dirty\n' >> "$tmpdir/README.md"

  local output rc branch status message
  output=$(python3 "$STARTUP_BRANCH_SCRIPT" --repo-root "$tmpdir" --allowlist "$tmpdir/.ai/allowlist.json" --slug startup-branch 2>&1)
  rc=$?
  branch=$(git -C "$tmpdir" branch --show-current)
  status=$(printf '%s' "$output" | jq -r '.status')
  message=$(printf '%s' "$output" | jq -r '.message')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$branch" = "main" ] &&
    [ "$status" = "blocked" ] &&
    echo "$message" | grep -qi "dirty"
}

test_quest_startup_branch_creates_worktree() {
  local tmpdir
  tmpdir=$(mktemp -d)
  init_git_repo "$tmpdir" || return 1
  write_allowlist "$tmpdir" "worktree"

  # Create .quest/ in repo root so the symlink has a target
  mkdir -p "$tmpdir/.quest"

  local output rc main_branch status branch_mode worktree_path worktree_branch quest_link
  output=$(python3 "$STARTUP_BRANCH_SCRIPT" --repo-root "$tmpdir" --allowlist "$tmpdir/.ai/allowlist.json" --slug startup-worktree 2>&1)
  rc=$?
  main_branch=$(git -C "$tmpdir" branch --show-current)
  status=$(printf '%s' "$output" | jq -r '.status')
  branch_mode=$(printf '%s' "$output" | jq -r '.branch_mode')
  worktree_path=$(printf '%s' "$output" | jq -r '.worktree_path')
  worktree_branch=$(git -C "$worktree_path" branch --show-current 2>/dev/null)
  quest_link="$worktree_path/.quest"
  local has_symlink=false
  [ -L "$quest_link" ] && has_symlink=true
  git -C "$tmpdir" worktree remove "$worktree_path" --force >/dev/null 2>&1 || true
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$main_branch" = "main" ] &&
    [ "$status" = "created" ] &&
    [ "$branch_mode" = "worktree" ] &&
    [ "$worktree_branch" = "quest/startup-worktree" ] &&
    [ "$has_symlink" = "true" ]
}

test_quest_startup_branch_none_mode_leaves_main_checked_out() {
  local tmpdir
  tmpdir=$(mktemp -d)
  init_git_repo "$tmpdir" || return 1
  write_allowlist "$tmpdir" "none"

  local output rc branch status branch_mode requested_mode
  output=$(python3 "$STARTUP_BRANCH_SCRIPT" --repo-root "$tmpdir" --allowlist "$tmpdir/.ai/allowlist.json" --slug startup-none 2>&1)
  rc=$?
  branch=$(git -C "$tmpdir" branch --show-current)
  status=$(printf '%s' "$output" | jq -r '.status')
  branch_mode=$(printf '%s' "$output" | jq -r '.branch_mode')
  requested_mode=$(printf '%s' "$output" | jq -r '.requested_branch_mode')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$branch" = "main" ] &&
    [ "$status" = "skipped" ] &&
    [ "$branch_mode" = "none" ] &&
    [ "$requested_mode" = "none" ]
}

test_quest_startup_branch_invalid_allowlist_returns_blocked_contract() {
  local tmpdir
  tmpdir=$(mktemp -d)
  init_git_repo "$tmpdir" || return 1
  mkdir -p "$tmpdir/.ai"
  printf '{ invalid json\n' > "$tmpdir/.ai/allowlist.json"

  local output rc status branch_mode requested_mode message
  output=$(python3 "$STARTUP_BRANCH_SCRIPT" --repo-root "$tmpdir" --allowlist "$tmpdir/.ai/allowlist.json" --slug startup-bad 2>&1)
  rc=$?
  status=$(printf '%s' "$output" | jq -r '.status')
  branch_mode=$(printf '%s' "$output" | jq -r '.branch_mode')
  requested_mode=$(printf '%s' "$output" | jq -r '.requested_branch_mode')
  message=$(printf '%s' "$output" | jq -r '.message')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$status" = "blocked" ] &&
    [ "$branch_mode" = "none" ] &&
    [ "$requested_mode" = "branch" ] &&
    echo "$message" | grep -qi "failed"
}

run_test test_quest_state_updates_phase_and_timestamp
run_test test_quest_state_transition_valid
run_test test_quest_state_transition_invalid_leaves_state_unchanged
run_test test_quest_state_transition_rejects_plan_reviewed_to_building
run_test test_quest_startup_branch_defaults_to_branch_checkout
run_test test_quest_startup_branch_skips_when_already_on_feature_branch
run_test test_quest_startup_branch_blocks_dirty_default_branch_checkout
run_test test_quest_startup_branch_creates_worktree
run_test test_quest_startup_branch_none_mode_leaves_main_checked_out
run_test test_quest_startup_branch_invalid_allowlist_returns_blocked_contract
run_test test_quest_claude_runner_polls_handoff_and_logs_runtime
run_test test_quest_claude_probe_requires_real_artifacts

echo ""
echo "Tests run: $TESTS_RUN"
echo "Passed: $TESTS_PASSED"
echo "Failed: $TESTS_FAILED"

if [ "$TESTS_FAILED" -eq 0 ]; then
  exit 0
else
  exit 1
fi
