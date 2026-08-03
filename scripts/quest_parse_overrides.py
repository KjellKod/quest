#!/usr/bin/env python3
"""Parse a Quest orchestration override submission from standard input."""

from __future__ import annotations

import json
import sys

from quest_runtime.orchestration import (
    OverrideParseError,
    normalize_override_input,
    parse_override_input,
)


def main() -> int:
    normalizations: list[str] = []
    try:
        normalized, normalizations = normalize_override_input(sys.stdin.read())
        overrides = parse_override_input(normalized)
    except OverrideParseError as exc:
        print(
            json.dumps(
                {"ok": False, "error": str(exc), "normalizations": normalizations},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    payload = {
        "ok": True,
        "normalizations": normalizations,
        "overrides": [
            {"role": override.role, "model": override.model} for override in overrides
        ],
    }
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
