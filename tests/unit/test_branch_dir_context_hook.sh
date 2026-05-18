#!/usr/bin/env bash
# Tests for .claude/hooks/branch-dir-context.sh
#
# Covers (plan §7.1):
#   1. test_hook_in_git_repo_emits_branch
#   2. test_hook_in_non_git_dir_emits_no_git
#   3. test_hook_in_detached_head_emits_short_sha_or_no_branch
#   4. test_hook_never_blocks_tool_call
#   5. test_hook_emits_exactly_one_line
#
# Runner contract: prints "PASS:" / "FAIL:" lines; exits 0 only when every
# test passes.

set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HOOK="$REPO_ROOT/.claude/hooks/branch-dir-context.sh"

failures=0

assert_equal() {
    local label="$1" expected="$2" actual="$3"
    if [ "$expected" = "$actual" ]; then
        printf 'PASS: %s\n' "$label"
    else
        printf 'FAIL: %s\n  expected: %s\n  actual:   %s\n' "$label" "$expected" "$actual"
        failures=$((failures + 1))
    fi
}

assert_match() {
    local label="$1" pattern="$2" actual="$3"
    if printf '%s' "$actual" | grep -Eq "$pattern"; then
        printf 'PASS: %s\n' "$label"
    else
        printf 'FAIL: %s\n  pattern: %s\n  actual:  %s\n' "$label" "$pattern" "$actual"
        failures=$((failures + 1))
    fi
}

# ---------------------------------------------------------------------------
# 1. Git repo -> emits a non-empty branch name and exit 0.
# ---------------------------------------------------------------------------
test_hook_in_git_repo_emits_branch() {
    local tmpdir
    tmpdir=$(mktemp -d)
    (
        cd "$tmpdir" || exit 1
        git init -q -b main-test-branch . >/dev/null 2>&1 || git init -q . >/dev/null 2>&1
        # Ensure we are on a named branch even if git defaults differ.
        git checkout -q -b main-test-branch >/dev/null 2>&1 || true
        # An initial commit is not required; symbolic-ref reads HEAD regardless.
        output=$(bash "$HOOK")
        ec=$?
        echo "$ec"
        echo "$output"
    ) > /tmp/branch_dir_context_test_1.out 2>/dev/null
    local exit_code branch_line
    exit_code=$(sed -n '1p' /tmp/branch_dir_context_test_1.out)
    branch_line=$(sed -n '2p' /tmp/branch_dir_context_test_1.out)
    assert_equal "test_hook_in_git_repo_emits_branch: exit 0" "0" "$exit_code"
    assert_match "test_hook_in_git_repo_emits_branch: format" \
        '^\[quest-context\] branch=[^[:space:]]+ dir=[^[:space:]]+$' \
        "$branch_line"
    assert_match "test_hook_in_git_repo_emits_branch: non-empty branch" \
        '^\[quest-context\] branch=.+ dir=' "$branch_line"
    rm -rf "$tmpdir" /tmp/branch_dir_context_test_1.out
}

# ---------------------------------------------------------------------------
# 2. Non-git dir -> emits "no-git" and exit 0.
# ---------------------------------------------------------------------------
test_hook_in_non_git_dir_emits_no_git() {
    local tmpdir
    tmpdir=$(mktemp -d)
    output=$(cd "$tmpdir" && bash "$HOOK")
    local ec=$?
    assert_equal "test_hook_in_non_git_dir_emits_no_git: exit 0" "0" "$ec"
    assert_match "test_hook_in_non_git_dir_emits_no_git: branch=no-git" \
        '^\[quest-context\] branch=no-git dir=' "$output"
    rm -rf "$tmpdir"
}

# ---------------------------------------------------------------------------
# 3. Detached HEAD -> emits short SHA or "no-branch" and exit 0.
# ---------------------------------------------------------------------------
test_hook_in_detached_head_emits_short_sha_or_no_branch() {
    local tmpdir
    tmpdir=$(mktemp -d)
    (
        cd "$tmpdir" || exit 1
        git init -q . >/dev/null 2>&1
        # Disable any host-level commit signing — sandbox CI environments may
        # configure git to sign every commit, which fails without credentials.
        git -c commit.gpgsign=false -c user.email=t@x -c user.name=t \
            commit --allow-empty -q -m init >/dev/null 2>&1
        # Detach HEAD by checking out the commit by SHA. --detach forces
        # detached state even when the SHA matches a current branch tip.
        sha=$(git rev-parse HEAD)
        git checkout -q --detach "$sha" >/dev/null 2>&1
        output=$(bash "$HOOK")
        ec=$?
        echo "$ec"
        echo "$output"
    ) > /tmp/branch_dir_context_test_3.out 2>/dev/null
    local exit_code branch_line
    exit_code=$(sed -n '1p' /tmp/branch_dir_context_test_3.out)
    branch_line=$(sed -n '2p' /tmp/branch_dir_context_test_3.out)
    assert_equal "test_hook_in_detached_head_emits_short_sha_or_no_branch: exit 0" "0" "$exit_code"
    # Branch token is either 7-40 hex chars OR the literal "no-branch".
    assert_match "test_hook_in_detached_head_emits_short_sha_or_no_branch: format" \
        '^\[quest-context\] branch=([0-9a-f]{7,40}|no-branch) dir=' \
        "$branch_line"
    rm -rf "$tmpdir" /tmp/branch_dir_context_test_3.out
}

# ---------------------------------------------------------------------------
# 4. Never blocks even when git is unavailable (PATH manipulation).
# ---------------------------------------------------------------------------
test_hook_never_blocks_tool_call() {
    # Simulate git unavailable by using a sanitized PATH that contains no
    # `git` binary. We invoke bash via an absolute path so the launcher
    # itself does not need a PATH lookup.
    local stub_dir bash_path
    stub_dir=$(mktemp -d)
    bash_path=$(command -v bash)
    output=$(PATH="$stub_dir" "$bash_path" "$HOOK" 2>/dev/null)
    local ec=$?
    assert_equal "test_hook_never_blocks_tool_call: exit 0 with sanitized PATH" "0" "$ec"
    assert_match "test_hook_never_blocks_tool_call: branch=no-git" \
        '^\[quest-context\] branch=no-git dir=' "$output"
    rm -rf "$stub_dir"
}

# ---------------------------------------------------------------------------
# 5. Emits exactly one newline-terminated line and no stderr.
# ---------------------------------------------------------------------------
test_hook_emits_exactly_one_line() {
    local tmpdir
    tmpdir=$(mktemp -d)
    local stdout_file stderr_file
    stdout_file=$(mktemp)
    stderr_file=$(mktemp)
    (cd "$tmpdir" && bash "$HOOK") >"$stdout_file" 2>"$stderr_file"
    local ec=$?
    assert_equal "test_hook_emits_exactly_one_line: exit 0" "0" "$ec"
    local line_count
    line_count=$(wc -l < "$stdout_file" | tr -d ' ')
    assert_equal "test_hook_emits_exactly_one_line: one stdout line" "1" "$line_count"
    local stderr_bytes
    stderr_bytes=$(wc -c < "$stderr_file" | tr -d ' ')
    assert_equal "test_hook_emits_exactly_one_line: empty stderr" "0" "$stderr_bytes"
    rm -rf "$tmpdir" "$stdout_file" "$stderr_file"
}

# Run all tests.
test_hook_in_git_repo_emits_branch
test_hook_in_non_git_dir_emits_no_git
test_hook_in_detached_head_emits_short_sha_or_no_branch
test_hook_never_blocks_tool_call
test_hook_emits_exactly_one_line

if [ "$failures" -ne 0 ]; then
    printf '\n%d test(s) failed\n' "$failures" >&2
    exit 1
fi

printf '\nAll branch-dir-context.sh hook tests passed.\n'
exit 0
