#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import re
from pathlib import Path


REQUIRED_HEADING_SUBSTRINGS = {
    "overview": "overview",
    "approach": "approach",
    "file_changes": "file changes",
    "test_strategy": "test strategy",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)


def _ok(msg: str) -> None:
    print(f"[OK] {msg}")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_headings(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        m = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
        if not m:
            continue
        headings.append(m.group(1).strip().lower())
    return headings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Lint a Quest plan markdown for required sections.")
    parser.add_argument("plan_md", type=str, help="Path to plan.md")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    plan_path = Path(args.plan_md)
    if not plan_path.is_absolute():
        plan_path = (repo_root / plan_path).resolve()

    if not plan_path.exists():
        _fail(f"plan not found: {plan_path}")
        return 2

    text = _read_text(plan_path)
    headings = _extract_headings(text)

    errors: list[str] = []

    for key, needle in REQUIRED_HEADING_SUBSTRINGS.items():
        if not any(needle in h for h in headings):
            errors.append(f"missing required section (heading contains): {needle}")

    if "quest_brief.md" not in text:
        errors.append("plan should reference the quest brief (expected to contain 'quest_brief.md')")

    if errors:
        for e in errors:
            _fail(e)
        return 1

    _ok(f"plan lint passed: {plan_path.relative_to(repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
