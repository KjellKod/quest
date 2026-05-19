#!/usr/bin/env python3
"""Annotate findings with deterministic in_diff/unknown scope evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


HUNK_RE = re.compile(r"@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@")


def _changed_lines(diff_text: str) -> dict[str, set[int]]:
    changed: dict[str, set[int]] = {}
    current_path = ""
    old_path = ""
    old_line = 0
    new_line = 0
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current_path = ""
            old_path = ""
            old_line = 0
            new_line = 0
            continue
        if line.startswith("--- a/"):
            old_path = line[len("--- a/") :]
            continue
        if line.startswith("+++ b/"):
            current_path = line[len("+++ b/") :]
            changed.setdefault(current_path, set())
            continue
        if line == "+++ /dev/null":
            current_path = old_path
            if current_path:
                changed.setdefault(current_path, set())
            continue
        match = HUNK_RE.match(line)
        if match:
            old_line = int(match.group("old_start"))
            new_line = int(match.group("new_start"))
            continue
        if not current_path or line.startswith("\\"):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            changed.setdefault(current_path, set()).add(new_line)
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            old_line += 1
        else:
            old_line += 1
            new_line += 1
    return changed


def _load_diff(args: argparse.Namespace) -> str:
    if args.diff_file:
        return Path(args.diff_file).read_text(encoding="utf-8")
    if args.pr:
        result = subprocess.run(["gh", "pr", "diff", str(args.pr), "--patch"], check=False, text=True, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout).strip())
        return result.stdout
    raise ValueError("one of --diff-file or --pr is required")


def annotate(findings: list[dict[str, Any]], diff_text: str) -> list[dict[str, Any]]:
    changed = _changed_lines(diff_text)
    annotated: list[dict[str, Any]] = []
    for finding in findings:
        item = dict(finding)
        path = str(item.get("path") or "")
        line = item.get("line")
        if isinstance(line, int) and not isinstance(line, bool) and line in changed.get(path, set()):
            item["scope"] = "in_diff"
            item["scope_reason"] = f"{path}:{line} overlaps a changed diff line."
        else:
            item["scope"] = "unknown"
            item["scope_reason"] = "No deterministic changed-line overlap found."
        annotated.append(item)
    return annotated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--findings", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diff-file")
    parser.add_argument("--pr")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    findings = json.loads(Path(args.findings).read_text(encoding="utf-8"))
    if not isinstance(findings, list):
        raise ValueError("--findings must contain a JSON list")
    annotated = annotate(findings, _load_diff(args))
    Path(args.output).write_text(json.dumps(annotated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "count": len(annotated), "output": args.output}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
