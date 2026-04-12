#!/usr/bin/env python3
"""Thin bridge: Codex context -> Claude CLI (`claude --print`).

This script shells out to Claude CLI and returns either plain text or
structured JSON for non-interactive orchestration flows.
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
    # NOTE: This default is duplicated in scripts/quest_claude_runner.py.
    # If you change it here, update it there too.
    parser.add_argument(
        "--timeout",
        type=float,
        default=1800.0,
        help="Command timeout seconds (default: 1800)",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Optional Claude model override (passed through if provided)",
    )
    parser.add_argument(
        "--system-prompt",
        default="",
        help="Optional system prompt passed through to Claude CLI.",
    )
    parser.add_argument(
        "--append-system-prompt",
        default="",
        help="Optional appended system prompt passed through to Claude CLI.",
    )
    parser.add_argument(
        "--permission-mode",
        choices=[
            "acceptEdits",
            "bypassPermissions",
            "default",
            "dontAsk",
            "plan",
            "auto",
        ],
        default="default",
        help="Claude CLI permission mode (default: default).",
    )
    parser.add_argument(
        "--max-budget-usd",
        type=float,
        default=None,
        help="Optional Claude CLI max budget for the call.",
    )
    parser.add_argument(
        "--add-dir",
        action="append",
        default=[],
        help="Additional directories to allow tool access to. Repeatable.",
    )
    parser.add_argument(
        "--allowed-tools",
        default="",
        help="Optional allowed tools list passed through to Claude CLI.",
    )
    parser.add_argument(
        "--disallowed-tools",
        default="",
        help="Optional disallowed tools list passed through to Claude CLI.",
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
    prompt: str,
    output_format: str,
    timeout: float,
    model: str,
    system_prompt: str,
    append_system_prompt: str,
    permission_mode: str,
    max_budget_usd: float | None,
    add_dirs: list[str],
    allowed_tools: str,
    disallowed_tools: str,
) -> dict[str, Any]:
    cmd = ["claude", "--print", prompt, "--output-format", output_format]
    if model:
        cmd.extend(["--model", model])
    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])
    if append_system_prompt:
        cmd.extend(["--append-system-prompt", append_system_prompt])
    if permission_mode != "default":
        cmd.extend(["--permission-mode", permission_mode])
    if max_budget_usd is not None:
        cmd.extend(["--max-budget-usd", str(max_budget_usd)])
    for add_dir in add_dirs:
        cmd.extend(["--add-dir", add_dir])
    if allowed_tools:
        cmd.extend(["--allowed-tools", allowed_tools])
    if disallowed_tools:
        cmd.extend(["--disallowed-tools", disallowed_tools])

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

    result = run_claude(
        prompt=prompt,
        output_format=args.output_format,
        timeout=args.timeout,
        model=args.model,
        system_prompt=args.system_prompt,
        append_system_prompt=args.append_system_prompt,
        permission_mode=args.permission_mode,
        max_budget_usd=args.max_budget_usd,
        add_dirs=args.add_dir,
        allowed_tools=args.allowed_tools,
        disallowed_tools=args.disallowed_tools,
    )

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
