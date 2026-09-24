"""Generate compatibility defaults from .ai/allowlist.json; --check detects drift.

Run in the Quest source repository after editing its model policy. Installed
repos may customize their allowlist without regenerating shipped fallbacks.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from quest_runtime.orchestration import (
    CANONICAL_ROLES,
    CLAUDE_EFFORT_LEVELS,
    runtime_for_model,
    validate_effort,
)

BEGIN = "# BEGIN GENERATED MODEL DEFAULTS"
END = "# END GENERATED MODEL DEFAULTS"

# Claude-led Claude roles dispatch through native `Task(...)`, which reads
# effort from subagent frontmatter rather than from orchestration.json. Mapping
# each agent file to the role it serves lets the allowlist stay authoritative
# for that path too. The reviewer files serve the Claude-side slot (A); slot B
# is the Codex slot and is configured through the runner.
AGENT_FILE_ROLES: dict[str, str] = {
    "planner.md": "planner",
    "plan-reviewer.md": "plan-reviewer-a",
    "arbiter.md": "arbiter",
    "builder.md": "builder",
    "code-reviewer.md": "code-reviewer-a",
    "review-arbiter.md": "review-arbiter",
    "fixer.md": "fixer",
}


_EFFORT_KEY = re.compile(r"""^\s*(?:"effort"|'effort'|effort)\s*:""")


def _with_effort(text: str, level: str) -> str:
    """Set `effort:` in a subagent file's YAML frontmatter, preserving the rest."""
    if not text.startswith("---\n"):
        raise ValueError("subagent file has no YAML frontmatter")
    end = text.index("\n---\n", 3)
    lines = text[4:end].split("\n")
    # Drop every spelling of the key, not just the one we emit: a quoted
    # `"effort": low` left behind would win under YAML's last-key-wins and
    # silently pin the opposite level.
    kept = []
    nested_content = False
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            kept.append(line)
            continue
        if line[:1].isspace() and nested_content:
            kept.append(line)
            continue
        if not line[:1].isspace():
            # A block scalar or nested mapping belongs to the preceding field.
            # Its indented text is not a top-level dispatch setting.
            _, separator, value = line.partition(":")
            value = value.split(" #", 1)[0].strip()
            nested_content = bool(separator) and (
                not value or value.startswith(("|", ">"))
            )
        if not _EFFORT_KEY.match(line):
            kept.append(line)
    # Keep it adjacent to `model:`, the other generated dispatch control.
    anchor = next(
        (i for i, line in enumerate(kept) if line.startswith("model:")), len(kept) - 1
    )
    kept.insert(anchor + 1, f"effort: {level}")
    return "---\n" + "\n".join(kept) + text[end:]


def sync(root: Path, *, check: bool) -> bool:
    allowlist = json.loads((root / ".ai/allowlist.json").read_text())
    models = allowlist["models"]
    if (
        not isinstance(models, dict)
        or set(models) != set(CANONICAL_ROLES)
        or not all(
            isinstance(model, str) and model.strip() and model == model.strip()
            for role, model in models.items()
        )
    ):
        raise ValueError(
            "allowlist models must contain all canonical roles with nonempty, trimmed model strings"
        )
    effort = allowlist["effort"]
    if not isinstance(effort, dict) or set(effort) != set(CANONICAL_ROLES):
        raise ValueError("allowlist effort must contain all canonical roles")
    for role, level in effort.items():
        validate_effort(role, level)
        if (
            runtime_for_model(models[role]) == "claude"
            and level not in CLAUDE_EFFORT_LEVELS
        ):
            raise ValueError(f"Unsupported Claude effort for {role}: {level!r}")
    fallback = allowlist["codex_fallback_model"]
    if (
        not isinstance(fallback, str)
        or not fallback.strip()
        or fallback != fallback.strip()
        or runtime_for_model(fallback) != "codex"
    ):
        raise ValueError("codex_fallback_model must be a Codex model ID")
    runtime = root / "scripts/quest_runtime/orchestration.py"
    original = runtime.read_text()
    start = original.index(BEGIN)
    end = original.index(END, start) + len(END)
    generated = (
        BEGIN
        + " (edit .ai/allowlist.json, then run scripts/quest_sync_model_defaults.py)\n"
        + "DEFAULT_MODELS: dict[str, str] = "
        + "{\n"
        + "".join(
            f"    {json.dumps(role)}: {json.dumps(model)},\n"
            for role, model in models.items()
        )
        + "}"
        + "\n"
        + "DEFAULT_EFFORT: dict[str, str] = "
        + "{\n"
        + "".join(
            f"    {json.dumps(role)}: {json.dumps(effort[role])},\n" for role in models
        )
        + "}"
        + "\n"
        + "CODEX_NATIVE_FALLBACK_MODEL = "
        + json.dumps(fallback)
        + "\n"
        + END
    )
    updates = {runtime: original[:start] + generated + original[end:]}
    # OpenCode's static agent definitions cannot read the allowlist themselves.
    # Preserve its provider prefix and permissions while generating role policy.
    opencode = root / ".opencode/opencode.json"
    config = json.loads(opencode.read_text())
    config["agent"]["quest"].pop("model", None)
    for role, model in models.items():
        config["agent"][role]["model"] = "opencode/" + model
    updates[opencode] = json.dumps(config, indent=2) + "\n"
    # Claude subagent frontmatter: the only effort control on the
    # Claude-led -> Claude path, since native Task() reads the agent file.
    # Documented but unverified on Claude Code 2.1.280 — an invalid value there
    # raises no warning and low-vs-max showed no token separation, unlike the
    # `claude --effort` flag. Emitted anyway: it is free and forward-compatible.
    for filename, role in AGENT_FILE_ROLES.items():
        agent_file = root / ".claude/agents" / filename
        if not agent_file.exists():
            continue
        updates[agent_file] = _with_effort(agent_file.read_text(), effort[role])
    clean = True
    for path, content in updates.items():
        if path.read_text() == content:
            continue
        clean = False
        if check:
            print(f"Stale generated model defaults: {path.relative_to(root)}")
        else:
            path.write_text(content)
            print(f"Updated {path.relative_to(root)}")
    return clean or not check


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return 0 if sync(Path(__file__).resolve().parents[1], check=args.check) else 1


if __name__ == "__main__":
    raise SystemExit(main())
