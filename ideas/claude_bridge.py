#!/usr/bin/env python3
"""Simple CLI bridge from Codex shell calls to Anthropic Messages API.

Examples:
  python3 scripts/claude_bridge.py --prompt "hello world"
  echo "hello world" | python3 scripts/claude_bridge.py --model claude-opus-4-1
  python3 scripts/claude_bridge.py --prompt-file prompt.txt --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
RETRIABLE_HTTP_CODES = {408, 409, 429, 500, 502, 503, 504}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Call Anthropic Messages API from a local CLI bridge."
    )
    prompt_group = parser.add_mutually_exclusive_group()
    prompt_group.add_argument(
        "--prompt",
        help="Prompt text. If omitted, read from stdin (pipe or redirect).",
    )
    prompt_group.add_argument(
        "--prompt-file",
        help="Read prompt text from a file path. Use '-' for stdin.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("CLAUDE_BRIDGE_MODEL", "claude-opus-4-1"),
        help="Anthropic model name. Default: claude-opus-4-1",
    )
    parser.add_argument(
        "--system",
        default=None,
        help="Optional system instruction.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Max output tokens. Default: 512",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="Optional sampling temperature.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP timeout in seconds. Default: 60",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retry count for retriable errors. Default: 2",
    )
    parser.add_argument(
        "--api-key-env",
        default="ANTHROPIC_API_KEY",
        help="Environment variable that stores API key. Default: ANTHROPIC_API_KEY",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON instead of plain text.",
    )
    return parser.parse_args(argv)


def read_prompt(args: argparse.Namespace) -> str:
    """Load prompt from --prompt, --prompt-file, or stdin."""
    if args.prompt is not None:
        prompt = args.prompt
    elif args.prompt_file:
        if args.prompt_file == "-":
            prompt = sys.stdin.read()
        else:
            with open(args.prompt_file, "r", encoding="utf-8") as handle:
                prompt = handle.read()
    else:
        if sys.stdin.isatty():
            raise ValueError(
                "No prompt provided. Use --prompt/--prompt-file or pipe stdin."
            )
        prompt = sys.stdin.read()

    if not prompt.strip():
        raise ValueError("Prompt is empty.")
    return prompt


def build_payload(args: argparse.Namespace, prompt: str) -> dict[str, Any]:
    """Build Anthropic Messages API payload."""
    payload: dict[str, Any] = {
        "model": args.model,
        "max_tokens": args.max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if args.system:
        payload["system"] = args.system
    if args.temperature is not None:
        payload["temperature"] = args.temperature
    return payload


def extract_error_message(body_text: str) -> str:
    """Parse API error payload; fallback to raw body."""
    try:
        parsed = json.loads(body_text)
        error = parsed.get("error", {})
        message = error.get("message")
        if message:
            return str(message)
    except json.JSONDecodeError:
        pass
    return body_text.strip() or "Unknown API error"


def call_anthropic(
    api_key: str,
    payload: dict[str, Any],
    timeout: float,
    retries: int,
) -> dict[str, Any]:
    """Call Anthropic Messages API with simple retry logic."""
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "content-type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": API_VERSION,
    }

    for attempt in range(retries + 1):
        request = urllib.request.Request(API_URL, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_text = response.read().decode("utf-8")
            parsed = json.loads(response_text)
            if not isinstance(parsed, dict):
                raise RuntimeError("Unexpected API response format.")
            return parsed
        except urllib.error.HTTPError as err:
            response_text = err.read().decode("utf-8", errors="replace")
            if err.code in RETRIABLE_HTTP_CODES and attempt < retries:
                time.sleep(2**attempt)
                continue
            message = extract_error_message(response_text)
            raise RuntimeError(f"Anthropic API HTTP {err.code}: {message}") from err
        except urllib.error.URLError as err:
            if attempt < retries:
                time.sleep(2**attempt)
                continue
            raise RuntimeError(f"Network error calling Anthropic API: {err.reason}") from err
        except json.JSONDecodeError as err:
            raise RuntimeError("Could not parse API JSON response.") from err

    raise RuntimeError("Failed after retries.")


def extract_text(response: dict[str, Any]) -> str:
    """Extract concatenated text blocks from Messages API response."""
    content = response.get("content", [])
    if not isinstance(content, list):
        return ""

    blocks: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str):
                blocks.append(text)
    return "".join(blocks).strip()


def print_output(response: dict[str, Any], text: str, as_json: bool) -> None:
    """Print either plain text or structured JSON."""
    if as_json:
        result = {
            "id": response.get("id"),
            "model": response.get("model"),
            "role": response.get("role"),
            "stop_reason": response.get("stop_reason"),
            "usage": response.get("usage"),
            "text": text,
        }
        print(json.dumps(result, ensure_ascii=True))
        return

    print(text)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    args = parse_args(argv)
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(
            f"Missing API key. Set environment variable: {args.api_key_env}",
            file=sys.stderr,
        )
        return 2

    try:
        prompt = read_prompt(args)
        payload = build_payload(args, prompt)
        response = call_anthropic(
            api_key=api_key,
            payload=payload,
            timeout=args.timeout,
            retries=max(0, args.retries),
        )
        text = extract_text(response)
        if not text:
            raise RuntimeError("API returned no text content.")
        print_output(response, text, as_json=args.json)
        return 0
    except (ValueError, OSError, RuntimeError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
