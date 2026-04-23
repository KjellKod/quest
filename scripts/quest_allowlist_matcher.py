#!/usr/bin/env python3
"""Quest allowlist matcher for bash commands.

Rejected metacharacters for non-exact matches: &&, ||, ;, |, &, `, $(),
>(, <(, >, >>, 2>, <, \n, \r. Non-exact find commands also reject
execution/write primaries such as -exec and -delete; non-exact rg commands
reject preprocessor flags. Exact-match allowlist entries still work for
commands that intentionally need these forms.
"""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

BLOCKED_METACHARACTERS = (
    "&&",
    "||",
    ";",
    "|",
    "&",
    "`",
    "$(",
    ">(",
    "<(",
    ">>",
    ">",
    "2>",
    "<",
    "\n",
    "\r",
)
EXACT_ONLY_BARE_ENTRIES = {"bash", "python", "python3"}
BLOCKED_FIND_ACTIONS = {
    "-delete",
    "-exec",
    "-execdir",
    "-fprint",
    "-fprint0",
    "-fls",
    "-fprintf",
    "-ok",
    "-okdir",
}
BLOCKED_RG_FLAGS = {"--pre", "--pre-glob"}


def contains_blocked_shell_metacharacters(command: str) -> bool:
    return any(token in command for token in BLOCKED_METACHARACTERS)


def shell_tokens(command: str) -> list[str] | None:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return None


def command_basename(command_tokens: list[str]) -> str:
    if not command_tokens:
        return ""
    return Path(command_tokens[0]).name


def executable_token_matches(command_token: str, entry_token: str) -> bool:
    if command_token == entry_token:
        return True
    if "/" in entry_token:
        return False
    command_path = Path(command_token)
    if command_path.is_absolute():
        return command_path.name == entry_token
    return False


def contains_blocked_find_action(command_tokens: list[str]) -> bool:
    if command_basename(command_tokens) != "find":
        return False
    return any(token in BLOCKED_FIND_ACTIONS for token in command_tokens[1:])


def contains_blocked_rg_flag(command_tokens: list[str]) -> bool:
    if command_basename(command_tokens) != "rg":
        return False
    return any(
        token in BLOCKED_RG_FLAGS
        or any(token.startswith(f"{flag}=") for flag in BLOCKED_RG_FLAGS)
        for token in command_tokens[1:]
    )


def token_prefix_matches(command_tokens: list[str], entry: str) -> bool:
    entry_tokens = shell_tokens(entry)
    if entry_tokens is None:
        return False
    if not entry_tokens:
        return False
    if (
        len(entry_tokens) == 1
        and entry_tokens[0] in EXACT_ONLY_BARE_ENTRIES
        and command_tokens != entry_tokens
    ):
        return False
    if len(command_tokens) < len(entry_tokens):
        return False
    if not executable_token_matches(command_tokens[0], entry_tokens[0]):
        return False
    return command_tokens[1 : len(entry_tokens)] == entry_tokens[1:]


def is_bash_command_allowed(command: str, allowed_entries: list[str]) -> tuple[bool, str]:
    if command in allowed_entries:
        return True, "exact_match"

    if contains_blocked_shell_metacharacters(command):
        return False, "blocked_metacharacter"

    command_tokens = shell_tokens(command)
    if command_tokens is None:
        return False, "invalid_shell_syntax"

    if contains_blocked_find_action(command_tokens):
        return False, "blocked_find_action"

    if contains_blocked_rg_flag(command_tokens):
        return False, "blocked_rg_flag"

    for entry in allowed_entries:
        if token_prefix_matches(command_tokens, entry):
            return True, "token_prefix_match"

    return False, "no_match"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quest bash allowlist matcher")
    parser.add_argument("--command", required=True, help="Raw command string to evaluate")
    parser.add_argument(
        "--allow",
        required=True,
        help="JSON array of allowlist entries (strings)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    try:
        parsed_entries = json.loads(args.allow)
    except json.JSONDecodeError:
        print("invalid_allowlist_json", file=sys.stderr)
        return 2

    if not isinstance(parsed_entries, list) or not all(
        isinstance(item, str) for item in parsed_entries
    ):
        print("invalid_allowlist_entries", file=sys.stderr)
        return 2

    allowed, reason = is_bash_command_allowed(args.command, parsed_entries)
    if allowed:
        return 0

    print(reason, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
