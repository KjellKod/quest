"""Generate compatibility defaults from .ai/allowlist.json; --check detects drift.

Run in the Quest source repository after editing its model policy. Installed
repos may customize their allowlist without regenerating shipped fallbacks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BEGIN = "# BEGIN GENERATED MODEL DEFAULTS"
END = "# END GENERATED MODEL DEFAULTS"


def sync(root: Path, *, check: bool) -> bool:
    allowlist = json.loads((root / ".ai/allowlist.json").read_text())
    models = allowlist["models"]
    if (
        not isinstance(models, dict)
        or not models
        or not all(
            isinstance(role, str) and isinstance(model, str) and model.strip()
            for role, model in models.items()
        )
    ):
        raise ValueError("allowlist models must contain nonempty model strings")
    fallback = allowlist["codex_fallback_model"]
    if (
        not isinstance(fallback, str)
        or not fallback.strip()
        or fallback.startswith(("claude", "gemini"))
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
