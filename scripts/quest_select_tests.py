"""CLI helper for selecting validation steps for one canonical finding."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from quest_runtime.pr_review_cycle import select_validation_steps

JsonObject = dict[str, object]


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finding", required=True, help="Path to single finding JSON object")
    parser.add_argument(
        "--repo-inventory",
        default=None,
        help="Optional repository inventory JSON object path",
    )
    parser.add_argument("--output", default=None, help="Optional output path for validation steps JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        finding_payload = _load_json(Path(args.finding))
        if not isinstance(finding_payload, dict):
            raise ValueError("finding JSON must be an object")

        repo_inventory: JsonObject | None = None
        if args.repo_inventory:
            inventory_payload = _load_json(Path(args.repo_inventory))
            if not isinstance(inventory_payload, dict):
                raise ValueError("repo inventory JSON must be an object")
            repo_inventory = inventory_payload

        validation_steps = select_validation_steps(
            finding_payload,
            repo_inventory=repo_inventory,
        )
        if args.output:
            _write_json(Path(args.output), validation_steps)
        print(json.dumps(validation_steps, sort_keys=True))
        return 0
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
