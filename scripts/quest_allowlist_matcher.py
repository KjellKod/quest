#!/usr/bin/env python3
"""Quest allowlist matcher for bash commands.

Rejected metacharacters for non-exact matches: &&, ||, ;, |, &, `, $(),
>(, <(, >, >>, 2>, <, \n, \r. Exact-match allowlist entries still work
for commands that legitimately need redirection.
"""

from __future__ import annotations

import argparse
import json
import sys

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


def contains_blocked_shell_metacharacters(command: str) -> bool:
    return any(token in command for token in BLOCKED_METACHARACTERS)


def token_prefix_matches(command: str, entry: str) -> bool:
    command_tokens = command.split()
    entry_tokens = entry.split()
    if not entry_tokens:
        return False
    if (
        len(entry_tokens) == 1
        and entry_tokens[0] in EXACT_ONLY_BARE_ENTRIES
        and command.strip() != entry_tokens[0]
    ):
        return False
    if len(command_tokens) < len(entry_tokens):
        return False
    return command_tokens[: len(entry_tokens)] == entry_tokens


def is_bash_command_allowed(command: str, allowed_entries: list[str]) -> tuple[bool, str]:
    if command in allowed_entries:
        return True, "exact_match"

    if contains_blocked_shell_metacharacters(command):
        return False, "blocked_metacharacter"

    for entry in allowed_entries:
        if token_prefix_matches(command, entry):
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
