#!/bin/bash
# Quest wrong-location guardrail: PreToolUse branch/dir context emitter.
#
# Prints exactly one line to stdout in the form:
#   [quest-context] branch=<name|short-sha|no-branch|no-git> dir=<path>
#
# Purpose: surface the current git branch and working directory before every
# Edit/Write tool call so users notice when they are about to edit on the
# wrong branch or in the wrong directory.
#
# Contract:
#   - Observational only. Always exits 0. Never blocks the wrapped tool call.
#   - Single newline-terminated line on stdout. No stderr noise.
#   - Works in git repos, non-git directories, and detached-HEAD checkouts.
#   - Pure shell. No dependency on jq, python, or repo helpers.

set -u

branch="no-git"
raw_dir="$(pwd 2>/dev/null || printf '%s' '?')"
# Defend the single-line stdout contract: collapse embedded LF/CR (legal in
# POSIX path components, fatal for a one-line emitter) into spaces using
# bash parameter expansion. No external commands — when ``git`` is absent
# because PATH is restricted, ``tr`` or other coreutils can be too; the
# hook must remain self-contained on the shell builtin path.
dir="${raw_dir//$'\n'/ }"
dir="${dir//$'\r'/ }"

if command -v git >/dev/null 2>&1; then
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        # symbolic-ref --short fails on detached HEAD; fall back to short SHA.
        if name=$(git symbolic-ref --short -q HEAD 2>/dev/null) && [ -n "$name" ]; then
            branch="$name"
        else
            sha=$(git rev-parse --short=7 HEAD 2>/dev/null || true)
            if [ -n "$sha" ]; then
                branch="$sha"
            else
                branch="no-branch"
            fi
        fi
    fi
fi

printf '[quest-context] branch=%s dir=%s\n' "$branch" "$dir"
exit 0
