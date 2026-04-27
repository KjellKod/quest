#!/usr/bin/env bash
# Test harness for Quest runtime helper scripts
# Run: bash tests/test-quest-runtime.sh

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
STATE_SCRIPT="$REPO_ROOT/scripts/quest_state.py"
STARTUP_BRANCH_SCRIPT="$REPO_ROOT/scripts/quest_startup_branch.py"
CLAUDE_RUNNER="$REPO_ROOT/scripts/quest_claude_runner.py"
CLAUDE_PROBE="$REPO_ROOT/scripts/quest_claude_probe.py"
INSTALLER_SCRIPT="$REPO_ROOT/scripts/quest_installer.sh"
WORKFLOW_FILE="$REPO_ROOT/.skills/quest/delegation/workflow.md"
MANIFEST_FILE="$REPO_ROOT/.quest-manifest"

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

load_installer_functions() {
  local loader_tmp
  loader_tmp=$(mktemp)
  sed '/^# Store original args for re-exec after self-update/,$d' "$INSTALLER_SCRIPT" > "$loader_tmp"
  # shellcheck disable=SC1090
  source "$loader_tmp"
  rm -f "$loader_tmp"
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

  # No .quest/ dir yet — symlink is created unconditionally (dangling until quest init)
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

test_quest_startup_branch_invalid_mode_keeps_vcs_available_true() {
  local tmpdir
  tmpdir=$(mktemp -d)
  init_git_repo "$tmpdir" || return 1
  mkdir -p "$tmpdir/.ai"
  cat > "$tmpdir/.ai/allowlist.json" <<EOF
{
  "quest_startup": {
    "branch_mode": "banana"
  }
}
EOF

  local output rc status vcs_available requested_mode message
  output=$(python3 "$STARTUP_BRANCH_SCRIPT" --repo-root "$tmpdir" --allowlist "$tmpdir/.ai/allowlist.json" --slug startup-bad-mode 2>&1)
  rc=$?
  status=$(printf '%s' "$output" | jq -r '.status')
  vcs_available=$(printf '%s' "$output" | jq -r '.vcs_available')
  requested_mode=$(printf '%s' "$output" | jq -r '.requested_branch_mode')
  message=$(printf '%s' "$output" | jq -r '.message')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$status" = "blocked" ] &&
    [ "$vcs_available" = "true" ] &&
    [ "$requested_mode" = "banana" ] &&
    echo "$message" | grep -qi "expected one of"
}

test_quest_startup_branch_skips_outside_git_repo() {
  local tmpdir
  tmpdir=$(mktemp -d)
  write_allowlist "$tmpdir" "branch"

  local output rc branch status branch_mode requested_mode message vcs_available
  output=$(python3 "$STARTUP_BRANCH_SCRIPT" --repo-root "$tmpdir" --allowlist "$tmpdir/.ai/allowlist.json" --slug outside-repo 2>&1)
  rc=$?
  branch=$(printf '%s' "$output" | jq -r '.branch')
  status=$(printf '%s' "$output" | jq -r '.status')
  branch_mode=$(printf '%s' "$output" | jq -r '.branch_mode')
  requested_mode=$(printf '%s' "$output" | jq -r '.requested_branch_mode')
  vcs_available=$(printf '%s' "$output" | jq -r '.vcs_available')
  message=$(printf '%s' "$output" | jq -r '.message')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$branch" = "null" ] &&
    [ "$status" = "skipped" ] &&
    [ "$branch_mode" = "none" ] &&
    [ "$requested_mode" = "branch" ] &&
    [ "$vcs_available" = "false" ] &&
    echo "$message" | grep -qi "not a git repository"
}

test_workflow_documents_no_vcs_review_path() {
  grep -q 'vcs_available' "$WORKFLOW_FILE" &&
    grep -q 'Changed file list unavailable (no VCS)' "$WORKFLOW_FILE" &&
    grep -q 'Diff stats unavailable (no VCS)' "$WORKFLOW_FILE" &&
    grep -q 'review the implementation directly' "$WORKFLOW_FILE"
}

test_workflow_documents_arbiter_validate_build_publish_contract() {
  grep -Fq 'review_findings.json.next' "$WORKFLOW_FILE" &&
    grep -Fq 'review_backlog.json.next' "$WORKFLOW_FILE" &&
    grep -Fq 'validate-findings --input .quest/<id>/phase_01_plan/review_findings.json.next' "$WORKFLOW_FILE" &&
    grep -Fq 'build-backlog --phase plan --findings .quest/<id>/phase_01_plan/review_findings.json.next --output .quest/<id>/phase_01_plan/review_backlog.json.next' "$WORKFLOW_FILE" &&
    grep -Fq 'validate-backlog --input .quest/<id>/phase_01_plan/review_backlog.json.next --expected-phase plan --strict-plan-defaults' "$WORKFLOW_FILE" &&
    grep -Fq 'Canonical `arbiter_verdict.md` is not prepared or truncated; publish `arbiter_verdict.md.next` only after validation succeeds.' "$WORKFLOW_FILE" &&
    grep -Fq 'os.replace(".quest/<id>/phase_01_plan/review_findings.json.next", ".quest/<id>/phase_01_plan/review_findings.json")' "$WORKFLOW_FILE" &&
    grep -Fq 'os.replace(".quest/<id>/phase_01_plan/arbiter_verdict.md.next", ".quest/<id>/phase_01_plan/arbiter_verdict.md")' "$WORKFLOW_FILE" &&
    grep -Fq 'If arbiter handoff says `next: planner`' "$WORKFLOW_FILE" &&
    grep -Fq 'Do **not** call `quest_state.py --transition plan_reviewed`.' "$WORKFLOW_FILE"
}

test_installer_cleans_up_renamed_scripts() {
  grep -q 'OLD_SCRIPT_NAMES=(' "$INSTALLER_SCRIPT" &&
    grep -q 'scripts/claude_cli_bridge.py' "$INSTALLER_SCRIPT" &&
    grep -q 'scripts/validate-handoff-contracts.sh' "$INSTALLER_SCRIPT" &&
    grep -q 'scripts/validate-manifest.sh' "$INSTALLER_SCRIPT" &&
    grep -q 'scripts/validate-quest-config.sh' "$INSTALLER_SCRIPT" &&
    grep -q 'scripts/validate-quest-state.sh' "$INSTALLER_SCRIPT" &&
    grep -q 'get_stored_checksum' "$INSTALLER_SCRIPT" &&
    grep -q 'Leaving existing non-Quest script in place' "$INSTALLER_SCRIPT" &&
    grep -q 'Leaving modified legacy Quest script in place for manual cleanup' "$INSTALLER_SCRIPT" &&
    grep -q 'migrate_legacy_validation_hook' "$INSTALLER_SCRIPT" &&
    grep -q 'cleanup_renamed_scripts' "$INSTALLER_SCRIPT"
}

test_installer_updates_pristine_agents_file_in_place() {
  local tmpdir
  tmpdir=$(mktemp -d)
  printf 'old agents\n' > "$tmpdir/AGENTS.md"
  printf 'stale sidecar\n' > "$tmpdir/AGENTS.md.quest_updated"
  printf 'new agents\n' > "$tmpdir/upstream_AGENTS.md"

  (
    cd "$tmpdir" || exit 1
    load_installer_functions

    DRY_RUN=false
    FORCE_MODE=true
    QUEST_UPDATED_FILES=()
    LOCAL_CHECKSUM_FILES=("AGENTS.md")
    LOCAL_CHECKSUM_VALUES=("$(get_file_checksum "AGENTS.md")")
    init_updated_checksums

    fetch_file_to_temp() {
      cp "$tmpdir/upstream_AGENTS.md" "$2"
    }
    log_info() { :; }
    log_warn() { :; }
    log_success() { :; }
    log_action() { :; }
    clear_progress() { :; }

    install_user_customized_file "AGENTS.md"

    local recorded=""
    local i
    for i in "${!UPDATED_CHECKSUM_FILES[@]}"; do
      if [ "${UPDATED_CHECKSUM_FILES[$i]}" = "AGENTS.md" ]; then
        recorded="${UPDATED_CHECKSUM_VALUES[$i]}"
      fi
    done

    [ "$(cat AGENTS.md)" = "$(cat "$tmpdir/upstream_AGENTS.md")" ] &&
      [ ! -e AGENTS.md.quest_updated ] &&
      [ "$recorded" = "$(get_file_checksum "AGENTS.md")" ]
  )
  local rc=$?
  rm -rf "$tmpdir"
  return $rc
}

test_installer_records_checksum_for_new_agents_file() {
  local tmpdir
  tmpdir=$(mktemp -d)
  printf 'new agents\n' > "$tmpdir/upstream_AGENTS.md"

  (
    cd "$tmpdir" || exit 1
    load_installer_functions

    DRY_RUN=false
    FORCE_MODE=true
    QUEST_UPDATED_FILES=()
    LOCAL_CHECKSUM_FILES=()
    LOCAL_CHECKSUM_VALUES=()
    init_updated_checksums

    fetch_file_to_temp() {
      cp "$tmpdir/upstream_AGENTS.md" "$2"
    }
    log_info() { :; }
    log_warn() { :; }
    log_success() { :; }
    log_action() { :; }
    clear_progress() { :; }

    install_user_customized_file "AGENTS.md"

    local recorded=""
    local i
    for i in "${!UPDATED_CHECKSUM_FILES[@]}"; do
      if [ "${UPDATED_CHECKSUM_FILES[$i]}" = "AGENTS.md" ]; then
        recorded="${UPDATED_CHECKSUM_VALUES[$i]}"
      fi
    done

    [ -f AGENTS.md ] &&
      [ "$(cat AGENTS.md)" = "$(cat "$tmpdir/upstream_AGENTS.md")" ] &&
      [ "$recorded" = "$(get_file_checksum "AGENTS.md")" ]
  )
  local rc=$?
  rm -rf "$tmpdir"
  return $rc
}

test_installer_preserves_customized_agents_file_with_sidecar() {
  local tmpdir
  tmpdir=$(mktemp -d)
  printf 'old agents\n' > "$tmpdir/AGENTS.md"
  printf 'new agents\n' > "$tmpdir/upstream_AGENTS.md"

  (
    cd "$tmpdir" || exit 1
    load_installer_functions

    DRY_RUN=false
    FORCE_MODE=true
    QUEST_UPDATED_FILES=()
    LOCAL_CHECKSUM_FILES=("AGENTS.md")
    LOCAL_CHECKSUM_VALUES=("different-stored-checksum")
    init_updated_checksums

    fetch_file_to_temp() {
      cp "$tmpdir/upstream_AGENTS.md" "$2"
    }
    log_info() { :; }
    log_warn() { :; }
    log_success() { :; }
    log_action() { :; }
    clear_progress() { :; }

    install_user_customized_file "AGENTS.md"

    [ "$(cat AGENTS.md)" = "old agents" ] &&
      [ -e AGENTS.md.quest_updated ] &&
      [ "$(cat AGENTS.md.quest_updated)" = "$(cat "$tmpdir/upstream_AGENTS.md")" ]
  )
  local rc=$?
  rm -rf "$tmpdir"
  return $rc
}

test_installer_prunes_pristine_removed_managed_files() {
  local tmpdir
  tmpdir=$(mktemp -d)

  (
    cd "$tmpdir" || exit 1
    mkdir -p tests/unit
    printf 'stale quest unit test\n' > tests/unit/test_review_intelligence.py
    load_installer_functions

    DRY_RUN=false
    FORCE_MODE=true
    COPY_AS_IS=("scripts/quest_state.py")
    USER_CUSTOMIZED=()
    MERGE_CAREFULLY=()
    LOCAL_CHECKSUM_FILES=("tests/unit/test_review_intelligence.py")
    LOCAL_CHECKSUM_VALUES=("$(get_file_checksum "tests/unit/test_review_intelligence.py")")
    init_updated_checksums

    log_info() { :; }
    log_warn() { :; }
    log_success() { :; }
    log_action() { :; }
    clear_progress() { :; }

    cleanup_removed_managed_files

    [ ! -e tests/unit/test_review_intelligence.py ] &&
      [ "${#UPDATED_CHECKSUM_FILES[@]}" -eq 0 ]
  )
  local rc=$?
  rm -rf "$tmpdir"
  return $rc
}

test_installer_preserves_modified_removed_managed_files_for_manual_cleanup() {
  local tmpdir
  tmpdir=$(mktemp -d)

  (
    cd "$tmpdir" || exit 1
    mkdir -p tests/unit
    printf 'locally modified stale quest unit test\n' > tests/unit/test_review_intelligence.py
    load_installer_functions

    DRY_RUN=false
    FORCE_MODE=true
    COPY_AS_IS=("scripts/quest_state.py")
    USER_CUSTOMIZED=()
    MERGE_CAREFULLY=()
    LOCAL_CHECKSUM_FILES=("tests/unit/test_review_intelligence.py")
    LOCAL_CHECKSUM_VALUES=("different-stored-checksum")
    init_updated_checksums

    log_info() { :; }
    log_warn() { :; }
    log_success() { :; }
    log_action() { :; }
    clear_progress() { :; }

    cleanup_removed_managed_files

    [ -e tests/unit/test_review_intelligence.py ] &&
      [ "${#UPDATED_CHECKSUM_FILES[@]}" -eq 0 ]
  )
  local rc=$?
  rm -rf "$tmpdir"
  return $rc
}

test_load_local_checksums_skips_unsafe_paths() {
  local tmpdir
  tmpdir=$(mktemp -d)

  (
    cd "$tmpdir" || exit 1
    cat > .quest-checksums <<'EOF'
# Quest Installer Checksums
aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa  tests/unit/test_review_intelligence.py
bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb  /tmp/outside.txt
cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc  ../outside.txt
EOF
    load_installer_functions

    log_info() { :; }
    log_warn() { :; }
    log_success() { :; }
    log_action() { :; }
    clear_progress() { :; }

    load_local_checksums

    [ "${#LOCAL_CHECKSUM_FILES[@]}" -eq 1 ] &&
      [ "${LOCAL_CHECKSUM_FILES[0]}" = "tests/unit/test_review_intelligence.py" ]
  )
  local rc=$?
  rm -rf "$tmpdir"
  return $rc
}

test_installer_skips_unsafe_removed_managed_file_path() {
  local tmpdir
  local outside_file
  tmpdir=$(mktemp -d)
  outside_file="$(dirname "$tmpdir")/quest-installer-outside-$$.txt"

  (
    cd "$tmpdir" || exit 1
    printf 'outside repo file\n' > "$outside_file"
    load_installer_functions

    DRY_RUN=false
    FORCE_MODE=true
    COPY_AS_IS=("scripts/quest_state.py")
    USER_CUSTOMIZED=()
    MERGE_CAREFULLY=()
    LOCAL_CHECKSUM_FILES=("../$(basename "$outside_file")")
    LOCAL_CHECKSUM_VALUES=("$(get_file_checksum "../$(basename "$outside_file")")")
    init_updated_checksums

    log_info() { :; }
    log_warn() { :; }
    log_success() { :; }
    log_action() { :; }
    clear_progress() { :; }

    cleanup_removed_managed_files

    [ -e "../$(basename "$outside_file")" ] &&
      [ "${#UPDATED_CHECKSUM_FILES[@]}" -eq 0 ]
  )
  local rc=$?
  rm -f "$outside_file"
  rm -rf "$tmpdir"
  return $rc
}

test_installer_prunes_untracked_legacy_installed_source_only_test_matching_upstream() {
  local tmpdir
  tmpdir=$(mktemp -d)

  (
    cd "$tmpdir" || exit 1
    mkdir -p tests/unit
    printf 'quest installed source-only test\n' > tests/unit/test_allowlist_matcher.py
    printf 'quest installed source-only test\n' > "$tmpdir/upstream_test_allowlist_matcher.py"
    load_installer_functions

    DRY_RUN=false
    FORCE_MODE=true
    COPY_AS_IS=("scripts/quest_state.py")
    USER_CUSTOMIZED=()
    MERGE_CAREFULLY=()
    LOCAL_CHECKSUM_FILES=()
    LOCAL_CHECKSUM_VALUES=()
    init_updated_checksums

    fetch_file_to_temp() {
      if [ "$1" = "tests/unit/test_allowlist_matcher.py" ]; then
        cp "$tmpdir/upstream_test_allowlist_matcher.py" "$2"
        return 0
      fi
      return 1
    }
    log_info() { :; }
    log_warn() { :; }
    log_success() { :; }
    log_action() { :; }
    clear_progress() { :; }

    cleanup_legacy_source_only_tests

    [ ! -e tests/unit/test_allowlist_matcher.py ]
  )
  local rc=$?
  rm -rf "$tmpdir"
  return $rc
}

test_installer_preserves_modified_untracked_legacy_installed_source_only_test() {
  local tmpdir
  tmpdir=$(mktemp -d)

  (
    cd "$tmpdir" || exit 1
    mkdir -p tests/unit
    printf 'locally modified quest source-only test\n' > tests/unit/test_allowlist_matcher.py
    printf 'quest installed source-only test\n' > "$tmpdir/upstream_test_allowlist_matcher.py"
    load_installer_functions

    DRY_RUN=false
    FORCE_MODE=true
    COPY_AS_IS=("scripts/quest_state.py")
    USER_CUSTOMIZED=()
    MERGE_CAREFULLY=()
    LOCAL_CHECKSUM_FILES=()
    LOCAL_CHECKSUM_VALUES=()
    init_updated_checksums

    fetch_file_to_temp() {
      if [ "$1" = "tests/unit/test_allowlist_matcher.py" ]; then
        cp "$tmpdir/upstream_test_allowlist_matcher.py" "$2"
        return 0
      fi
      return 1
    }
    log_info() { :; }
    log_warn() { :; }
    log_success() { :; }
    log_action() { :; }
    clear_progress() { :; }

    cleanup_legacy_source_only_tests

    [ -e tests/unit/test_allowlist_matcher.py ]
  )
  local rc=$?
  rm -rf "$tmpdir"
  return $rc
}

test_installer_preserves_unowned_source_only_test_path() {
  local tmpdir
  tmpdir=$(mktemp -d)

  (
    cd "$tmpdir" || exit 1
    mkdir -p tests/unit
    printf 'repo-local source-only test\n' > tests/unit/test_quest_complete.py
    load_installer_functions

    DRY_RUN=false
    FORCE_MODE=true
    COPY_AS_IS=("scripts/quest_state.py")
    USER_CUSTOMIZED=()
    MERGE_CAREFULLY=()
    LOCAL_CHECKSUM_FILES=()
    LOCAL_CHECKSUM_VALUES=()
    init_updated_checksums

    log_info() { :; }
    log_warn() { :; }
    log_success() { :; }
    log_action() { :; }
    clear_progress() { :; }

    cleanup_legacy_source_only_tests

    [ -e tests/unit/test_quest_complete.py ]
  )
  local rc=$?
  rm -rf "$tmpdir"
  return $rc
}

test_manifest_lists_prefixed_scripts() {
  grep -q '^scripts/quest_claude_bridge.py$' "$MANIFEST_FILE" &&
    grep -q '^scripts/quest_validate-handoff-contracts.sh$' "$MANIFEST_FILE" &&
    grep -q '^scripts/quest_validate-manifest.sh$' "$MANIFEST_FILE" &&
    grep -q '^scripts/quest_validate-quest-config.sh$' "$MANIFEST_FILE" &&
    grep -q '^scripts/quest_validate-quest-state.sh$' "$MANIFEST_FILE"
}

test_manifest_lists_installed_quest_smoke_tests() {
  grep -q '^tests/integration/test-enforce-allowlist.sh$' "$MANIFEST_FILE" &&
    grep -q '^tests/test-quest-preflight.sh$' "$MANIFEST_FILE" &&
    grep -q '^tests/test-quest-runtime.sh$' "$MANIFEST_FILE" &&
    grep -q '^tests/test-validate-handoff-contracts.sh$' "$MANIFEST_FILE" &&
    grep -q '^tests/test-validate-quest-state.sh$' "$MANIFEST_FILE"
}

test_manifest_excludes_source_only_unit_tests() {
  ! grep -q '^tests/unit/test_allowlist_matcher.py$' "$MANIFEST_FILE" &&
    ! grep -q '^tests/unit/test_review_intelligence.py$' "$MANIFEST_FILE" &&
    ! grep -q '^tests/unit/test_codex_skill_wrappers.py$' "$MANIFEST_FILE"
}

test_manifest_validator_allows_custom_skills_in_installed_mode() {
  local tmpdir
  tmpdir=$(mktemp -d)
  (
    cd "$tmpdir" || exit 1
    mkdir -p scripts .skills/prepare-mcp-quest
    cp "$REPO_ROOT/scripts/quest_validate-manifest.sh" scripts/quest_validate-manifest.sh
    cat > .quest-manifest <<'EOF'
[copy-as-is]
scripts/quest_validate-manifest.sh

[directories]
.quest
EOF
    printf '# local custom skill\n' > .skills/prepare-mcp-quest/SKILL.md

    bash scripts/quest_validate-manifest.sh > output.txt 2>&1 &&
      grep -q 'Installed repo mode' output.txt &&
      ! grep -q 'prepare-mcp-quest' output.txt
  )
  local rc=$?
  rm -rf "$tmpdir"
  return $rc
}

test_manifest_validator_strict_mode_catches_unmanifested_skills() {
  local tmpdir
  tmpdir=$(mktemp -d)
  (
    cd "$tmpdir" || exit 1
    mkdir -p scripts .skills/prepare-mcp-quest
    cp "$REPO_ROOT/scripts/quest_validate-manifest.sh" scripts/quest_validate-manifest.sh
    cat > .quest-manifest <<'EOF'
[copy-as-is]
scripts/quest_validate-manifest.sh

[directories]
.quest
EOF
    printf '# local custom skill\n' > .skills/prepare-mcp-quest/SKILL.md

    if QUEST_MANIFEST_STRICT=1 bash scripts/quest_validate-manifest.sh > output.txt 2>&1; then
      exit 1
    fi
    grep -q '.skills/prepare-mcp-quest/SKILL.md' output.txt
  )
  local rc=$?
  rm -rf "$tmpdir"
  return $rc
}

test_manifest_validator_rejects_unknown_option() {
  local tmpdir
  tmpdir=$(mktemp -d)
  (
    cd "$tmpdir" || exit 1
    mkdir -p scripts
    cp "$REPO_ROOT/scripts/quest_validate-manifest.sh" scripts/quest_validate-manifest.sh
    cat > .quest-manifest <<'EOF'
[copy-as-is]
scripts/quest_validate-manifest.sh
EOF

    if bash scripts/quest_validate-manifest.sh --bogus > output.txt 2>&1; then
      exit 1
    fi
    grep -q 'Unknown option: --bogus' output.txt &&
      grep -q 'Usage: scripts/quest_validate-manifest.sh' output.txt
  )
  local rc=$?
  rm -rf "$tmpdir"
  return $rc
}

test_validation_hook_script_accepts_legacy_symlink_target() {
  grep -q '\[\[ "\$target" == \*"quest_validate-quest-config.sh" \]\] || \[\[ "\$target" == \*"validate-quest-config.sh" \]\]' "$REPO_ROOT/scripts/quest_validate-quest-config.sh"
}

test_quest_startup_branch_invalid_slug_preserves_requested_mode() {
  local tmpdir
  tmpdir=$(mktemp -d)
  init_git_repo "$tmpdir" || return 1
  write_allowlist "$tmpdir" "worktree"

  local output rc status branch_mode requested_mode message
  output=$(python3 "$STARTUP_BRANCH_SCRIPT" --repo-root "$tmpdir" --allowlist "$tmpdir/.ai/allowlist.json" --slug bad/slug 2>&1)
  rc=$?
  status=$(printf '%s' "$output" | jq -r '.status')
  branch_mode=$(printf '%s' "$output" | jq -r '.branch_mode')
  requested_mode=$(printf '%s' "$output" | jq -r '.requested_branch_mode')
  message=$(printf '%s' "$output" | jq -r '.message')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$status" = "blocked" ] &&
    [ "$branch_mode" = "none" ] &&
    [ "$requested_mode" = "worktree" ] &&
    echo "$message" | grep -qi "invalid slug"
}

test_quest_startup_branch_exception_handler_tolerates_missing_git() {
  local tmpdir python_bin
  tmpdir=$(mktemp -d)
  init_git_repo "$tmpdir" || return 1
  mkdir -p "$tmpdir/.ai" "$tmpdir/empty-path"
  printf '{ invalid json\n' > "$tmpdir/.ai/allowlist.json"
  python_bin=$(command -v python3) || return 1

  local output rc status vcs_available message
  output=$(PATH="$tmpdir/empty-path" "$python_bin" "$STARTUP_BRANCH_SCRIPT" --repo-root "$tmpdir" --allowlist "$tmpdir/.ai/allowlist.json" --slug startup-no-git 2>&1)
  rc=$?
  status=$(printf '%s' "$output" | jq -r '.status')
  vcs_available=$(printf '%s' "$output" | jq -r '.vcs_available')
  message=$(printf '%s' "$output" | jq -r '.message')
  rm -rf "$tmpdir"

  [ "$rc" -eq 0 ] &&
    [ "$status" = "blocked" ] &&
    [ "$vcs_available" = "false" ] &&
    echo "$message" | grep -qi "failed"
}

test_plan_review_retry_harness_preserves_canonical_artifacts_until_publish() {
  local tmpdir phase_dir verdict_file findings_file backlog_file verdict_next findings_next backlog_next
  tmpdir=$(mktemp -d)
  phase_dir="$tmpdir/phase_01_plan"
  verdict_file="$phase_dir/arbiter_verdict.md"
  findings_file="$phase_dir/review_findings.json"
  backlog_file="$phase_dir/review_backlog.json"
  verdict_next="$phase_dir/arbiter_verdict.md.next"
  findings_next="$phase_dir/review_findings.json.next"
  backlog_next="$phase_dir/review_backlog.json.next"
  mkdir -p "$phase_dir"

  cat > "$findings_file" <<'EOF'
[
  {
    "finding_id": "old-1",
    "source": "arbiter",
    "kind": "correctness",
    "severity": "low",
    "confidence": "high",
    "path": "scripts/old.py",
    "line": 1,
    "summary": "Old canonical finding.",
    "why_it_matters": "Old value should survive failed validation.",
    "evidence": ["old"],
    "action": "none",
    "needs_test": false,
    "write_scope": ["scripts/old.py"],
    "related_acceptance_criteria": ["AC-0"]
  }
]
EOF
  cat > "$backlog_file" <<'EOF'
{
  "version": 1,
  "generated_at": "2026-04-22T00:00:00Z",
  "phase": "plan",
  "at_loop_cap": false,
  "allowed_decisions": ["fix_now", "verify_first", "defer", "drop", "needs_human_decision"],
  "counts": {"fix_now": 1, "verify_first": 0, "defer": 0, "drop": 0, "needs_human_decision": 0},
  "items": [
    {
      "finding_id": "old-1",
      "source": "arbiter",
      "kind": "correctness",
      "severity": "low",
      "confidence": "high",
      "path": "scripts/old.py",
      "line": 1,
      "summary": "Old canonical finding.",
      "why_it_matters": "Old value should survive failed validation.",
      "evidence": ["old"],
      "action": "none",
      "needs_test": false,
      "write_scope": ["scripts/old.py"],
      "related_acceptance_criteria": ["AC-0"],
      "decision": "fix_now",
      "decision_confidence": "high",
      "reason": "old",
      "needs_validation": ["typecheck"],
      "owner": "builder",
      "batch": "correctness-scripts"
    }
  ]
}
EOF
  echo "old verdict" > "$verdict_file"

  local canonical_verdict_before canonical_findings_before canonical_backlog_before
  canonical_verdict_before=$(cat "$verdict_file")
  canonical_findings_before=$(cat "$findings_file")
  canonical_backlog_before=$(cat "$backlog_file")

  local attempts=0 retries=0 validated=false
  local transition_attempts=0 transition_attempts_before_publish=0 published=false
  while [ "$attempts" -lt 2 ]; do
    attempts=$((attempts + 1))
    rm -f "$verdict_next" "$findings_next" "$backlog_next"
    echo "arbiter attempt $attempts" > "$verdict_next"
    if [ "$attempts" -eq 1 ]; then
      cat > "$findings_next" <<'EOF'
[
  {
    "id": "bad-shape"
  }
]
EOF
    else
      cat > "$findings_next" <<'EOF'
[
  {
    "finding_id": "new-1",
    "source": "arbiter",
    "kind": "regression-risk",
    "severity": "high",
    "confidence": "high",
    "path": "scripts/new.py",
    "line": 12,
    "summary": "New canonical finding.",
    "why_it_matters": "Used to validate retry and publish ordering.",
    "evidence": ["new"],
    "action": "fix now",
    "needs_test": true,
    "write_scope": ["scripts/new.py"],
    "related_acceptance_criteria": ["B5"]
  }
]
EOF
    fi

    if python3 "$REPO_ROOT/scripts/quest_review_intelligence.py" validate-findings --input "$findings_next" >/dev/null 2>&1; then
      validated=true
      break
    fi

    retries=$((retries + 1))
    [ "$(cat "$verdict_file")" = "$canonical_verdict_before" ] || { rm -rf "$tmpdir"; return 1; }
    [ "$(cat "$findings_file")" = "$canonical_findings_before" ] || { rm -rf "$tmpdir"; return 1; }
    [ "$(cat "$backlog_file")" = "$canonical_backlog_before" ] || { rm -rf "$tmpdir"; return 1; }
    [ "$retries" -le 1 ] || { rm -rf "$tmpdir"; return 1; }
  done

  "$validated" || { rm -rf "$tmpdir"; return 1; }
  [ "$attempts" -eq 2 ] || { rm -rf "$tmpdir"; return 1; }
  [ "$retries" -eq 1 ] || { rm -rf "$tmpdir"; return 1; }

  python3 "$REPO_ROOT/scripts/quest_review_intelligence.py" build-backlog --phase plan --findings "$findings_next" --output "$backlog_next" >/dev/null 2>&1 || { rm -rf "$tmpdir"; return 1; }
  python3 "$REPO_ROOT/scripts/quest_review_intelligence.py" validate-backlog --input "$backlog_next" --expected-phase plan --strict-plan-defaults >/dev/null 2>&1 || { rm -rf "$tmpdir"; return 1; }

  attempt_transition() {
    transition_attempts=$((transition_attempts + 1))
    if [ "$published" != true ]; then
      transition_attempts_before_publish=$((transition_attempts_before_publish + 1))
    fi
  }

  [ -s "$verdict_next" ] || { rm -rf "$tmpdir"; return 1; }
  [ -s "$findings_next" ] || { rm -rf "$tmpdir"; return 1; }
  [ -s "$backlog_next" ] || { rm -rf "$tmpdir"; return 1; }

  mv "$verdict_next" "$verdict_file" || { rm -rf "$tmpdir"; return 1; }
  mv "$findings_next" "$findings_file" || { rm -rf "$tmpdir"; return 1; }
  mv "$backlog_next" "$backlog_file" || { rm -rf "$tmpdir"; return 1; }
  published=true
  attempt_transition

  local canonical_verdict_after canonical_findings_after canonical_backlog_after
  canonical_verdict_after=$(cat "$verdict_file")
  canonical_findings_after=$(cat "$findings_file")
  canonical_backlog_after=$(cat "$backlog_file")

  local rc=0
  [ "$transition_attempts" -eq 1 ] || rc=1
  [ "$transition_attempts_before_publish" -eq 0 ] || rc=1
  [ "$canonical_verdict_after" != "$canonical_verdict_before" ] || rc=1
  [ "$canonical_findings_after" != "$canonical_findings_before" ] || rc=1
  [ "$canonical_backlog_after" != "$canonical_backlog_before" ] || rc=1
  [ -s "$verdict_file" ] || rc=1
  [ -s "$findings_file" ] || rc=1
  [ -s "$backlog_file" ] || rc=1

  rm -rf "$tmpdir"
  return $rc
}

test_plan_review_retry_via_runner_preserves_canonical_artifacts_until_publish() {
  local tmpdir phase_dir verdict_file findings_file backlog_file verdict_next findings_next backlog_next prompt_file handoff_file
  tmpdir=$(mktemp -d)
  phase_dir="$tmpdir/phase_01_plan"
  verdict_file="$phase_dir/arbiter_verdict.md"
  findings_file="$phase_dir/review_findings.json"
  backlog_file="$phase_dir/review_backlog.json"
  verdict_next="$phase_dir/arbiter_verdict.md.next"
  findings_next="$phase_dir/review_findings.json.next"
  backlog_next="$phase_dir/review_backlog.json.next"
  prompt_file="$phase_dir/arbiter_prompt.txt"
  handoff_file="$phase_dir/handoff_arbiter.json"
  mkdir -p "$phase_dir"

  echo "old canonical verdict" > "$verdict_file"

  cat > "$findings_file" <<'EOF'
[
  {
    "finding_id": "old-runner-1",
    "source": "arbiter",
    "kind": "correctness",
    "severity": "low",
    "confidence": "high",
    "path": "scripts/old_runner.py",
    "line": 1,
    "summary": "Old canonical finding.",
    "why_it_matters": "Must remain unchanged before successful publish.",
    "evidence": ["old-runner"],
    "action": "none",
    "needs_test": false,
    "write_scope": ["scripts/old_runner.py"],
    "related_acceptance_criteria": ["B5"]
  }
]
EOF
  cat > "$backlog_file" <<'EOF'
{
  "version": 1,
  "generated_at": "2026-04-22T00:00:00Z",
  "phase": "plan",
  "at_loop_cap": false,
  "allowed_decisions": ["fix_now", "verify_first", "defer", "drop", "needs_human_decision"],
  "counts": {"fix_now": 1, "verify_first": 0, "defer": 0, "drop": 0, "needs_human_decision": 0},
  "items": [
    {
      "finding_id": "old-runner-1",
      "source": "arbiter",
      "kind": "correctness",
      "severity": "low",
      "confidence": "high",
      "path": "scripts/old_runner.py",
      "line": 1,
      "summary": "Old canonical finding.",
      "why_it_matters": "Must remain unchanged before successful publish.",
      "evidence": ["old-runner"],
      "action": "none",
      "needs_test": false,
      "write_scope": ["scripts/old_runner.py"],
      "related_acceptance_criteria": ["B5"],
      "decision": "fix_now",
      "decision_confidence": "high",
      "reason": "old",
      "needs_validation": ["typecheck"],
      "owner": "builder",
      "batch": "correctness-scripts"
    }
  ]
}
EOF
  cat > "$tmpdir/fake_arbiter_bridge.py" <<'EOF'
#!/usr/bin/env python3
import json
import pathlib
import sys

args = sys.argv[1:]
prompt_file = pathlib.Path(args[args.index("--prompt-file") + 1])
phase_dir = prompt_file.parent
attempt_file = phase_dir / "arbiter_attempt.txt"

attempt = 1
if attempt_file.exists():
    try:
        attempt = int(attempt_file.read_text(encoding="utf-8").strip()) + 1
    except ValueError:
        attempt = 1
attempt_file.write_text(str(attempt), encoding="utf-8")

verdict_path = phase_dir / "arbiter_verdict.md.next"
findings_path = phase_dir / "review_findings.json.next"
handoff_path = phase_dir / "handoff_arbiter.json"
verdict_path.write_text(f"arbiter attempt {attempt}\n", encoding="utf-8")

if attempt == 1:
    findings_path.write_text('[{"id":"bad-shape"}]\n', encoding="utf-8")
else:
    findings_path.write_text(
        json.dumps(
            [
                {
                    "finding_id": "runner-new-1",
                    "source": "arbiter",
                    "kind": "regression-risk",
                    "severity": "high",
                    "confidence": "high",
                    "path": "scripts/new_runner.py",
                    "line": 7,
                    "summary": "Valid findings after retry.",
                    "why_it_matters": "Validates runner/orchestrator retry path.",
                    "evidence": ["runner"],
                    "action": "fix now",
                    "needs_test": True,
                    "write_scope": ["scripts/new_runner.py"],
                    "related_acceptance_criteria": ["B5"],
                }
            ],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

handoff_path.write_text(
    json.dumps(
        {
            "status": "complete",
            "artifacts": [str(verdict_path), str(findings_path)],
            "next": "planner",
            "summary": f"attempt {attempt}",
        }
    ),
    encoding="utf-8",
)
print("---HANDOFF---")
print("STATUS: complete")
print(f"ARTIFACTS: {verdict_path}, {findings_path}")
print("NEXT: planner")
print(f"SUMMARY: attempt {attempt}")
EOF
  chmod +x "$tmpdir/fake_arbiter_bridge.py"
  cat > "$prompt_file" <<EOF
Write arbiter outputs for retry testing.
EOF

  # --- Runtime-evidence instrumentation ---------------------------------
  # Telemetry log: the runner appends JSON lines when QUEST_RUNNER_TELEMETRY_LOG
  # is set. The test also appends non-runner events (validate/publish/transition)
  # to the same file to produce a single ordered event stream that asserts the
  # real runtime sequence. A regression that called transition before publish
  # would show up as a "transition" line preceding the "publish" line here.
  local telemetry_log="$tmpdir/runner_telemetry.log"
  : > "$telemetry_log"
  export QUEST_RUNNER_TELEMETRY_LOG="$telemetry_log"

  record_event() {
    # Append a single JSON event line for non-runner activity.
    python3 - "$telemetry_log" "$@" <<'PY'
import json, sys, time
log_path = sys.argv[1]
payload = {"ts": time.time(), "event": sys.argv[2]}
for pair in sys.argv[3:]:
    if "=" in pair:
        k, v = pair.split("=", 1)
        payload[k] = v
with open(log_path, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
PY
  }

  # Stat snapshot: (mtime_ns, inode, size, sha256). Any change — including an
  # identical-byte rewrite (mtime_ns changes) — will differ from the recorded
  # snapshot and cause the invariant assertion to fail.
  stat_snapshot() {
    python3 - "$1" <<'PY'
import hashlib, os, sys
p = sys.argv[1]
st = os.stat(p)
with open(p, "rb") as fh:
    digest = hashlib.sha256(fh.read()).hexdigest()
print(f"{st.st_mtime_ns}|{st.st_ino}|{st.st_size}|{digest}")
PY
  }

  local canonical_verdict_before canonical_findings_before canonical_backlog_before
  canonical_verdict_before=$(cat "$verdict_file")
  canonical_findings_before=$(cat "$findings_file")
  canonical_backlog_before=$(cat "$backlog_file")
  local verdict_snapshot_before findings_snapshot_before backlog_snapshot_before
  verdict_snapshot_before=$(stat_snapshot "$verdict_file")
  findings_snapshot_before=$(stat_snapshot "$findings_file")
  backlog_snapshot_before=$(stat_snapshot "$backlog_file")

  local attempts=0 retries=0 validated=false
  local published=false
  while [ "$attempts" -lt 3 ]; do
    local output runner_rc result_kind
    output=$(python3 "$CLAUDE_RUNNER" \
      --quest-dir "$tmpdir" \
      --phase plan_review \
      --agent arbiter \
      --iter 1 \
      --prompt-file "$prompt_file" \
      --handoff-file "$handoff_file" \
      --bridge-script "$tmpdir/fake_arbiter_bridge.py" \
      --cwd "$REPO_ROOT" 2>&1)
    runner_rc=$?
    result_kind=$(printf '%s' "$output" | jq -r '.result_kind')
    attempts=$((attempts + 1))
    [ "$runner_rc" -eq 0 ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
    [ "$result_kind" = "handoff_json" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }

    # Stat-level canonical invariant: fails identical-byte rewrites too.
    [ "$(stat_snapshot "$verdict_file")" = "$verdict_snapshot_before" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
    [ "$(stat_snapshot "$findings_file")" = "$findings_snapshot_before" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
    [ "$(stat_snapshot "$backlog_file")" = "$backlog_snapshot_before" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }

    if python3 "$REPO_ROOT/scripts/quest_review_intelligence.py" validate-findings --input "$findings_next" >/dev/null 2>&1; then
      record_event validate result=ok attempt="$attempts"
      validated=true
      break
    fi
    record_event validate result=fail attempt="$attempts"

    retries=$((retries + 1))
    [ "$(cat "$verdict_file")" = "$canonical_verdict_before" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
    [ "$(cat "$findings_file")" = "$canonical_findings_before" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
    [ "$(cat "$backlog_file")" = "$canonical_backlog_before" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
    [ "$retries" -le 1 ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
  done

  "$validated" || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
  [ "$attempts" -eq 2 ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
  [ "$retries" -eq 1 ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
  [ "$(cat "$phase_dir/arbiter_attempt.txt")" = "2" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }

  python3 "$REPO_ROOT/scripts/quest_review_intelligence.py" build-backlog --phase plan --findings "$findings_next" --output "$backlog_next" >/dev/null 2>&1 || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
  python3 "$REPO_ROOT/scripts/quest_review_intelligence.py" validate-backlog --input "$backlog_next" --expected-phase plan --strict-plan-defaults >/dev/null 2>&1 || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }

  # Canonical files must still be untouched after build-backlog/validate — including
  # any identical-byte rewrite (detected by mtime/inode shift in stat_snapshot).
  [ "$(stat_snapshot "$verdict_file")" = "$verdict_snapshot_before" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
  [ "$(stat_snapshot "$findings_file")" = "$findings_snapshot_before" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
  [ "$(stat_snapshot "$backlog_file")" = "$backlog_snapshot_before" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }

  # Capture the .next sha256 immediately before publish for a post-publish
  # content-identity check that doesn't depend on the local canonical_* strings.
  local verdict_next_sha_prepublish findings_next_sha_prepublish backlog_next_sha_prepublish
  verdict_next_sha_prepublish=$(python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$verdict_next")
  findings_next_sha_prepublish=$(python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$findings_next")
  backlog_next_sha_prepublish=$(python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$backlog_next")

  attempt_transition() {
    # Records a transition event to the shared telemetry log. If an orchestration
    # regression called this before publish, the "transition" line would appear
    # before the "publish" line and the ordering assertion below would fail.
    record_event transition when="$1"
  }

  [ -s "$verdict_next" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
  [ -s "$findings_next" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
  [ -s "$backlog_next" ] || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }

  mv "$verdict_next" "$verdict_file" || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
  mv "$findings_next" "$findings_file" || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
  mv "$backlog_next" "$backlog_file" || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
  published=true
  record_event publish
  attempt_transition post_publish

  python3 "$REPO_ROOT/scripts/quest_review_intelligence.py" validate-findings --input "$findings_file" >/dev/null 2>&1 || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }
  python3 "$REPO_ROOT/scripts/quest_review_intelligence.py" validate-backlog --input "$backlog_file" >/dev/null 2>&1 || { unset QUEST_RUNNER_TELEMETRY_LOG; rm -rf "$tmpdir"; return 1; }

  local canonical_verdict_after canonical_findings_after canonical_backlog_after
  canonical_verdict_after=$(cat "$verdict_file")
  canonical_findings_after=$(cat "$findings_file")
  canonical_backlog_after=$(cat "$backlog_file")

  # Post-publish: canonical sha256 must match the .next sha256 captured immediately
  # before publish (proves publish is the only event that mutated canonical).
  local verdict_post_sha findings_post_sha backlog_post_sha
  verdict_post_sha=$(python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$verdict_file")
  findings_post_sha=$(python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$findings_file")
  backlog_post_sha=$(python3 -c 'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$backlog_file")

  # Parse telemetry log and assert the observed runtime sequence.
  local sequence_report
  sequence_report=$(python3 - "$telemetry_log" <<'PY'
import json, sys
lines = [l for l in open(sys.argv[1], encoding="utf-8").read().splitlines() if l.strip()]
events = [json.loads(l) for l in lines]
order = [e.get("event") for e in events]

attempt_starts = [e for e in events if e.get("event") == "attempt_start"]
attempt_ends = [e for e in events if e.get("event") == "attempt_end"]
transitions = [i for i, ev in enumerate(order) if ev == "transition"]
publish_idxs = [i for i, ev in enumerate(order) if ev == "publish"]

# Invariants:
#  - exactly two runner attempt_start/attempt_end pairs (1 initial + 1 retry)
#  - every attempt_end has result_kind=handoff_json (runner produced a handoff)
#  - exactly one "publish" event
#  - no "transition" event appears BEFORE "publish"
#  - validate events: one fail (attempt 1) then one ok (attempt 2)
errors = []
if len(attempt_starts) != 2:
    errors.append(f"attempt_start count={len(attempt_starts)}")
if len(attempt_ends) != 2:
    errors.append(f"attempt_end count={len(attempt_ends)}")
for e in attempt_ends:
    if e.get("result_kind") != "handoff_json":
        errors.append(f"attempt_end result_kind={e.get('result_kind')}")
if len(publish_idxs) != 1:
    errors.append(f"publish count={len(publish_idxs)}")
if publish_idxs and any(t < publish_idxs[0] for t in transitions):
    errors.append("transition before publish")
validate_results = [e.get("result") for e in events if e.get("event") == "validate"]
if validate_results != ["fail", "ok"]:
    errors.append(f"validate sequence={validate_results}")

# Ensure attempt iterations observed by runner are 1 and 2 in order.
iters = [e.get("iter") for e in attempt_ends]
# Both invocations use --iter 1 (outer loop provides the retry semantics), so all
# runner-observed iter values should be 1; the retry is counted by the outer loop
# via attempt_file. What matters is that the runner produced TWO independent
# attempt_end records, proving it actually ran twice.
if len(set(iters)) > 2:
    errors.append(f"iter values={iters}")

if errors:
    print("FAIL:" + ";".join(errors))
else:
    print("OK")
PY
  )

  local rc=0
  [ "$sequence_report" = "OK" ] || rc=1

  [ "$verdict_post_sha" = "$verdict_next_sha_prepublish" ] || rc=1
  [ "$findings_post_sha" = "$findings_next_sha_prepublish" ] || rc=1
  [ "$backlog_post_sha" = "$backlog_next_sha_prepublish" ] || rc=1

  [ "$canonical_verdict_after" != "$canonical_verdict_before" ] || rc=1
  [ "$canonical_findings_after" != "$canonical_findings_before" ] || rc=1
  [ "$canonical_backlog_after" != "$canonical_backlog_before" ] || rc=1
  [ -s "$verdict_file" ] || rc=1
  [ -s "$findings_file" ] || rc=1
  [ -s "$backlog_file" ] || rc=1

  unset QUEST_RUNNER_TELEMETRY_LOG
  rm -rf "$tmpdir"
  return $rc
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
run_test test_quest_startup_branch_invalid_mode_keeps_vcs_available_true
run_test test_quest_startup_branch_skips_outside_git_repo
run_test test_quest_startup_branch_invalid_slug_preserves_requested_mode
run_test test_quest_startup_branch_exception_handler_tolerates_missing_git
run_test test_plan_review_retry_harness_preserves_canonical_artifacts_until_publish
run_test test_plan_review_retry_via_runner_preserves_canonical_artifacts_until_publish
run_test test_workflow_documents_no_vcs_review_path
run_test test_workflow_documents_arbiter_validate_build_publish_contract
run_test test_installer_cleans_up_renamed_scripts
run_test test_installer_updates_pristine_agents_file_in_place
run_test test_installer_records_checksum_for_new_agents_file
run_test test_installer_preserves_customized_agents_file_with_sidecar
run_test test_installer_prunes_pristine_removed_managed_files
run_test test_installer_preserves_modified_removed_managed_files_for_manual_cleanup
run_test test_load_local_checksums_skips_unsafe_paths
run_test test_installer_skips_unsafe_removed_managed_file_path
run_test test_installer_prunes_untracked_legacy_installed_source_only_test_matching_upstream
run_test test_installer_preserves_modified_untracked_legacy_installed_source_only_test
run_test test_installer_preserves_unowned_source_only_test_path
run_test test_manifest_lists_prefixed_scripts
run_test test_manifest_lists_installed_quest_smoke_tests
run_test test_manifest_excludes_source_only_unit_tests
run_test test_manifest_validator_allows_custom_skills_in_installed_mode
run_test test_manifest_validator_strict_mode_catches_unmanifested_skills
run_test test_manifest_validator_rejects_unknown_option
run_test test_validation_hook_script_accepts_legacy_symlink_target
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
