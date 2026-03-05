#!/usr/bin/env python3
"""Thin bridge: Codex context -> Claude CLI (`claude -p`).

This script is intended for experiments/prototyping in the ideas/ area.
It shells out to Claude CLI and returns either plain text or structured JSON.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Call Claude CLI from a Codex-driven shell workflow."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--prompt", help="Prompt text")
    source.add_argument(
        "--prompt-file", help="Read prompt from file (or '-' for stdin)"
    )

    parser.add_argument(
        "--output-format",
        choices=["text", "json"],
        default="json",
        help="Claude output format (default: json)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=90.0,
        help="Command timeout seconds (default: 90)",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Optional Claude model override (passed through if provided)",
    )
    parser.add_argument(
        "--json-wrap",
        action="store_true",
        help="Wrap result in a stable JSON envelope",
    )
    return parser.parse_args(argv)


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt is not None:
        prompt = args.prompt
    elif args.prompt_file:
        if args.prompt_file == "-":
            prompt = sys.stdin.read()
        else:
            prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            raise ValueError("No prompt provided. Use --prompt/--prompt-file or stdin.")
        prompt = sys.stdin.read()

    prompt = prompt.strip()
    if not prompt:
        raise ValueError("Prompt is empty.")
    return prompt


def run_claude(
    prompt: str, output_format: str, timeout: float, model: str
) -> dict[str, Any]:
    cmd = ["claude", "-p", prompt, "--output-format", output_format]
    if model:
        cmd.extend(["--model", model])

    try:
        cp = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "status": "ok" if cp.returncode == 0 else "error",
            "exit_code": cp.returncode,
            "stdout": cp.stdout,
            "stderr": cp.stderr,
            "command": cmd,
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "exit_code": 127,
            "stdout": "",
            "stderr": "claude CLI not found in PATH",
            "command": cmd,
        }
    except subprocess.TimeoutExpired as err:
        return {
            "status": "timeout",
            "exit_code": 124,
            "stdout": (err.stdout or ""),
            "stderr": f"Timed out after {timeout}s",
            "command": cmd,
        }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        prompt = read_prompt(args)
    except (ValueError, OSError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 2

    result = run_claude(prompt, args.output_format, args.timeout, args.model)

    if args.json_wrap:
        payload = {
            "status": result["status"],
            "exit_code": result["exit_code"],
            "stderr": result["stderr"].strip(),
            "response": result["stdout"].strip(),
        }
        print(json.dumps(payload, ensure_ascii=True))
    else:
        if result["stdout"]:
            print(result["stdout"], end="")
        if result["status"] != "ok":
            msg = result["stderr"].strip() or f"claude exited {result['exit_code']}"
            print(msg, file=sys.stderr)

    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
