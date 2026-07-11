#!/usr/bin/env python3
"""Parse a Quest orchestration override submission from standard input."""

from __future__ import annotations

import json
import sys

from quest_runtime.orchestration import OverrideParseError, parse_override_input


def main() -> int:
    try:
        overrides = parse_override_input(sys.stdin.read())
    except OverrideParseError as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, sort_keys=True),
            file=sys.stderr,
        )
        return 2

    payload = {
        "ok": True,
        "overrides": [
            {"role": override.role, "model": override.model}
            for override in overrides
        ],
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
