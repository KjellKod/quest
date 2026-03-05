#!/usr/bin/env bash
set -euo pipefail

# Experimental bridge: Codex context -> Claude CLI (`claude -p`)
# Intended for ideas/prototyping only.

PROMPT=""
PROMPT_FILE=""
OUTPUT_FORMAT="json"
MODEL=""
TIMEOUT_SECONDS="90"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt)
      PROMPT="${2:-}"
      shift 2
      ;;
    --prompt-file)
      PROMPT_FILE="${2:-}"
      shift 2
      ;;
    --output-format)
      OUTPUT_FORMAT="${2:-json}"
      shift 2
      ;;
    --model)
      MODEL="${2:-}"
      shift 2
      ;;
    --timeout)
      TIMEOUT_SECONDS="${2:-90}"
      shift 2
      ;;
    -h|--help)
      cat <<'EOF'
Usage: codex_calls_claude.sh [options]

Options:
  --prompt <text>        Prompt text
  --prompt-file <path>   Prompt from file ('-' for stdin)
  --output-format <fmt>  text|json (default: json)
  --model <name>         Optional Claude model override
  --timeout <seconds>    Optional timeout (default: 90)
EOF
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -n "$PROMPT" && -n "$PROMPT_FILE" ]]; then
  echo "Use either --prompt or --prompt-file, not both" >&2
  exit 2
fi

if [[ -z "$PROMPT" ]]; then
  if [[ -n "$PROMPT_FILE" ]]; then
    if [[ "$PROMPT_FILE" == "-" ]]; then
      PROMPT="$(cat)"
    else
      PROMPT="$(<"$PROMPT_FILE")"
    fi
  else
    if [[ -t 0 ]]; then
      echo "No prompt provided. Use --prompt/--prompt-file or pipe stdin." >&2
      exit 2
    fi
    PROMPT="$(cat)"
  fi
fi

if [[ -z "${PROMPT//[[:space:]]/}" ]]; then
  echo "Prompt is empty." >&2
  exit 2
fi

CMD=(claude -p "$PROMPT" --output-format "$OUTPUT_FORMAT")
if [[ -n "$MODEL" ]]; then
  CMD+=(--model "$MODEL")
fi

if command -v gtimeout >/dev/null 2>&1; then
  gtimeout "$TIMEOUT_SECONDS" "${CMD[@]}"
elif command -v timeout >/dev/null 2>&1; then
  timeout "$TIMEOUT_SECONDS" "${CMD[@]}"
else
  "${CMD[@]}"
fi
