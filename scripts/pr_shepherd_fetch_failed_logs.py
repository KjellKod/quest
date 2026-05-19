#!/usr/bin/env python3
"""Fetch and bound failed GitHub Actions logs for PR shepherding."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, text=True, capture_output=True)


def _bounded(text: str, *, head: int, tail: int) -> list[str]:
    lines = text.splitlines()
    if len(lines) <= head + tail:
        return lines
    return lines[:head] + [f"... truncated {len(lines) - head - tail} lines ..."] + lines[-tail:]


def _source_label(*, check_name: str, job_name: str, run_id: str) -> str:
    for value in (check_name, job_name):
        if value.strip():
            return value.strip()
    return f"run-{run_id}"


def _record_from_lines(
    *,
    run_id: str,
    lines: list[str],
    check_name: str = "",
    job_name: str = "",
    raw_log_url: str = "",
) -> dict[str, Any]:
    body = "\n".join(lines)
    label = _source_label(check_name=check_name, job_name=job_name, run_id=run_id)
    return {
        "source_kind": "failed_log_summary",
        "source_label": label,
        "activity_state": "active",
        "author": "",
        "author_kind": "automation",
        "path": "ci/log",
        "line": None,
        "body_excerpt": body[:2000],
        "url": raw_log_url,
        "raw_log_url": raw_log_url,
        "run_id": run_id,
        "check_name": check_name,
        "job_name": job_name,
    }


def build_payload(
    *,
    run_id: str,
    result: subprocess.CompletedProcess[str],
    head: int,
    tail: int,
    check_name: str = "",
    job_name: str = "",
    raw_log_url: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": run_id,
        "ok": result.returncode == 0,
        "records": [],
        "unavailable": [],
    }
    if result.returncode == 0:
        lines = _bounded(result.stdout, head=head, tail=tail)
        payload["lines"] = lines
        payload["records"].append(
            _record_from_lines(
                run_id=run_id,
                lines=lines,
                check_name=check_name,
                job_name=job_name,
                raw_log_url=raw_log_url,
            )
        )
    else:
        reason = "log_unavailable"
        message = (result.stderr or result.stdout)[:500]
        payload["unavailable_reason"] = reason
        payload["message"] = message
        payload["unavailable"].append(
            {
                "source_kind": "failed_log_summary",
                "unavailable_reason": reason,
                "run_id": run_id,
                "check_name": check_name,
                "job_name": job_name,
                "raw_log_url": raw_log_url,
                "message": message,
            }
        )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="GitHub Actions run id")
    parser.add_argument("--head", type=int, default=40)
    parser.add_argument("--tail", type=int, default=80)
    parser.add_argument("--check-name", default="")
    parser.add_argument("--job-name", default="")
    parser.add_argument("--raw-log-url", default="")
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = _run(["gh", "run", "view", args.run_id, "--log-failed"])
    payload = build_payload(
        run_id=args.run_id,
        result=result,
        head=args.head,
        tail=args.tail,
        check_name=args.check_name,
        job_name=args.job_name,
        raw_log_url=args.raw_log_url,
    )
    encoded = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
