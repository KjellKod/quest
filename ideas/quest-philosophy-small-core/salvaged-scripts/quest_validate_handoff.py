#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ALLOWED_ROLES = {
    "quest_agent",
    "planner_agent",
    "plan_review_claude",
    "plan_review_codex",
    "arbiter_agent",
    "builder_agent",
    "code_review_agent",
    "fixer_agent",
}

ALLOWED_STATUS = {"complete", "needs_human", "blocked"}

ALLOWED_ARTIFACT_KINDS = {
    "plan",
    "review",
    "verdict",
    "code",
    "fix",
    "pr_description",
    "discussion",
    "brief",
}

HANDOFF_REQUIRED_KEYS = {"role", "status", "artifacts_written", "questions", "next_role", "summary"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}", file=sys.stderr)


def _ok(msg: str) -> None:
    print(f"[OK] {msg}")


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except Exception as e:
        raise ValueError(f"Invalid JSON: {e}") from e


def _validate_basic_shape(doc: Any) -> list[str]:
    errors: list[str] = []

    if not isinstance(doc, dict):
        return ["handoff must be a JSON object"]

    extra_keys = set(doc.keys()) - HANDOFF_REQUIRED_KEYS
    missing_keys = HANDOFF_REQUIRED_KEYS - set(doc.keys())
    if missing_keys:
        errors.append(f"missing keys: {sorted(missing_keys)}")
    if extra_keys:
        errors.append(f"unexpected keys: {sorted(extra_keys)} (schema disallows additionalProperties)")

    role = doc.get("role")
    if role not in ALLOWED_ROLES:
        errors.append(f"role must be one of {sorted(ALLOWED_ROLES)}")

    status = doc.get("status")
    if status not in ALLOWED_STATUS:
        errors.append(f"status must be one of {sorted(ALLOWED_STATUS)}")

    summary = doc.get("summary")
    if not isinstance(summary, str):
        errors.append("summary must be a string")
    elif len(summary) > 500:
        errors.append("summary must be <= 500 chars")

    next_role = doc.get("next_role")
    if next_role is not None and next_role not in ALLOWED_ROLES:
        errors.append(f"next_role must be null or one of {sorted(ALLOWED_ROLES)}")

    questions = doc.get("questions")
    if not isinstance(questions, list):
        errors.append("questions must be an array")
    else:
        for i, q in enumerate(questions):
            if not isinstance(q, dict):
                errors.append(f"questions[{i}] must be an object")
                continue
            for k in ("id", "question", "blocking"):
                if k not in q:
                    errors.append(f"questions[{i}] missing key: {k}")
            if "blocking" in q and not isinstance(q.get("blocking"), bool):
                errors.append(f"questions[{i}].blocking must be boolean")

    artifacts = doc.get("artifacts_written")
    if not isinstance(artifacts, list):
        errors.append("artifacts_written must be an array")
    else:
        for i, a in enumerate(artifacts):
            if not isinstance(a, dict):
                errors.append(f"artifacts_written[{i}] must be an object")
                continue
            if "path" not in a or "kind" not in a:
                errors.append(f"artifacts_written[{i}] must include path and kind")
                continue
            if not isinstance(a["path"], str) or not a["path"]:
                errors.append(f"artifacts_written[{i}].path must be a non-empty string")
            if a["kind"] not in ALLOWED_ARTIFACT_KINDS:
                errors.append(
                    f"artifacts_written[{i}].kind must be one of {sorted(ALLOWED_ARTIFACT_KINDS)}"
                )

    return errors


def _validate_artifact_paths_exist(doc: dict[str, Any], *, repo_root: Path) -> list[str]:
    errors: list[str] = []

    artifacts = doc.get("artifacts_written", [])
    if not isinstance(artifacts, list):
        return ["artifacts_written must be an array (cannot validate paths)"]

    for i, a in enumerate(artifacts):
        if not isinstance(a, dict):
            continue
        rel = a.get("path")
        if not isinstance(rel, str) or not rel:
            continue
        # Prevent path traversal weirdness by resolving and checking prefix.
        abs_path = (repo_root / rel).resolve()
        try:
            abs_path.relative_to(repo_root.resolve())
        except Exception:
            errors.append(f"artifacts_written[{i}].path escapes repo root: {rel}")
            continue
        if not abs_path.exists():
            errors.append(f"artifacts_written[{i}].path does not exist: {rel}")

    return errors


def _try_ajv_validate(handoff_path: Path, *, repo_root: Path) -> tuple[bool, str]:
    schema_path = repo_root / ".ai" / "schemas" / "handoff.schema.json"
    if not schema_path.exists():
        return False, f"schema not found: {schema_path}"

    ajv = shutil.which("ajv")
    if not ajv:
        return False, "ajv not installed (skipping JSON-schema validation)"

    cmd = [ajv, "validate", "-s", str(schema_path), "-d", str(handoff_path), "--spec=draft2020"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return True, (proc.stdout + proc.stderr).strip() or "ajv validation failed"
    return True, "ajv validation passed"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Validate Quest handoff JSON artifacts.")
    parser.add_argument("handoff_json", type=str, help="Path to handoff_*.json")
    parser.add_argument(
        "--require-ajv",
        action="store_true",
        help="Fail if ajv is missing or schema validation cannot run.",
    )
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    handoff_path = Path(args.handoff_json)
    if not handoff_path.is_absolute():
        handoff_path = (repo_root / handoff_path).resolve()

    try:
        doc = _load_json(handoff_path)
    except FileNotFoundError:
        _fail(f"handoff file not found: {handoff_path}")
        return 2
    except ValueError as e:
        _fail(str(e))
        return 2

    errors = _validate_basic_shape(doc)
    if not errors and isinstance(doc, dict):
        errors.extend(_validate_artifact_paths_exist(doc, repo_root=repo_root))

    ran_ajv, ajv_msg = _try_ajv_validate(handoff_path, repo_root=repo_root)
    if ran_ajv:
        if ajv_msg.endswith("passed"):
            _ok(ajv_msg)
        else:
            _fail(ajv_msg)
            errors.append("JSON-schema validation failed (ajv)")
    else:
        if args.require_ajv:
            _fail(ajv_msg)
            errors.append("JSON-schema validation required but not available")
        else:
            print(f"[WARN] {ajv_msg}", file=sys.stderr)

    if errors:
        for e in errors:
            _fail(e)
        return 1

    _ok(f"handoff valid: {handoff_path.relative_to(repo_root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

