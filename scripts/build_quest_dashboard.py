#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from quest_dashboard.loaders import DashboardDataError, load_dashboard_data
from quest_dashboard.render import render_dashboard


DEFAULT_OUTPUT = Path("docs") / "dashboard" / "index.html"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a static Quest Dashboard HTML page from repo quest data."
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Repository root path. Defaults to the current repository root.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Output HTML path (absolute or relative to --repo-root).",
    )
    parser.add_argument(
        "--github-url",
        default=None,
        help="GitHub repo URL for journal links (e.g. https://github.com/owner/repo). Auto-detected from git remote if not provided.",
    )
    return parser.parse_args(argv)


def resolve_repo_root(repo_root_arg: str | None) -> Path:
    if repo_root_arg:
        return Path(repo_root_arg).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def resolve_output_path(repo_root: Path, output_arg: str) -> Path:
    candidate = Path(output_arg).expanduser()
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def detect_github_url(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, cwd=repo_root, timeout=5,
        )
        remote = result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ""
    # Convert git@github.com:owner/repo.git -> https://github.com/owner/repo
    m = re.match(r"git@github\.com:(.+?)(?:\.git)?$", remote)
    if m:
        return f"https://github.com/{m.group(1)}"
    # Already HTTPS
    m = re.match(r"(https://github\.com/[^/]+/[^/]+?)(?:\.git)?$", remote)
    if m:
        return m.group(1)
    return ""


def build_dashboard(repo_root: Path, output_path: Path, github_base_url: str = "") -> tuple[int, int, list[str]]:
    data = load_dashboard_data(repo_root=repo_root)
    html = render_dashboard(data=data, output_path=output_path, repo_root=repo_root, github_base_url=github_base_url)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    return len(data.active_quests), len(data.completed_quests), data.warnings


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo_root = resolve_repo_root(args.repo_root)
    output_path = resolve_output_path(repo_root=repo_root, output_arg=args.output)

    github_url = args.github_url or detect_github_url(repo_root)

    try:
        active_count, completed_count, warnings = build_dashboard(
            repo_root=repo_root,
            output_path=output_path,
            github_base_url=github_url,
        )
    except DashboardDataError as exc:
        print(f"Build failed: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        reason = exc.strerror or "filesystem error"
        print(f"Build failed: could not write output file ({reason}).", file=sys.stderr)
        return 3

    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)

    print(
        f"Dashboard built: {output_path} "
        f"(active={active_count}, completed={completed_count})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
