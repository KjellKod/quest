#!/usr/bin/env python3
"""Check Quest-managed files against .quest-checksums.

This is a repo-local maintenance helper. It is intentionally not part of the
Quest installer manifest.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check Quest-managed files against .quest-checksums.",
    )
    parser.add_argument(
        "repo",
        nargs="?",
        default=".",
        help="Repository root to check (default: current directory).",
    )
    return parser.parse_args()


def resolve_repo_managed_path(root: Path, relpath: str) -> Path | None:
    try:
        candidate = (root / relpath).resolve(strict=False)
        candidate.relative_to(root)
    except (OSError, RuntimeError, ValueError):
        return None
    return candidate


def main() -> int:
    args = parse_args()
    root = Path(args.repo).resolve()
    checksums = root / ".quest-checksums"

    if not checksums.exists():
        print(f"missing .quest-checksums: {checksums}")
        return 2

    drift: list[tuple[str, str]] = []
    for raw in checksums.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            expected, relpath = raw.split("  ", 1)
        except ValueError:
            drift.append((raw, "malformed entry"))
            continue

        path = resolve_repo_managed_path(root, relpath)
        if path is None:
            drift.append((relpath, "unsafe path"))
            continue
        if not path.exists():
            drift.append((relpath, "missing file"))
            continue

        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            drift.append((relpath, actual))

    if drift:
        print("DRIFT")
        for relpath, detail in drift:
            print(f"{relpath}\t{detail}")
        return 1

    print("OK: no checksum drift")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
