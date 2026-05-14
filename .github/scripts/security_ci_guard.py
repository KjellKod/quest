#!/usr/bin/env python3

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode


WORKFLOW_DIR = Path(".github/workflows")
TRUSTED_AUTHOR = "KjellKod"
TRUSTED_AUTHOR_SNIPPETS = {
    f"github.event.pull_request.user.login == '{TRUSTED_AUTHOR}'",
    f'github.event.pull_request.user.login == "{TRUSTED_AUTHOR}"',
}
SAME_REPO_SNIPPET = "github.event.pull_request.head.repo.full_name == github.repository"
BASE_SHA_SNIPPET = "ref: ${{ github.event.pull_request.base.sha }}"
SECRET_BEARING_SNIPPETS = (
    "OPENAI_API_KEY",
    "secrets.OPENAI_API_KEY",
    "pull-requests: write",
    "issues: write",
)
BROAD_WRITE_SNIPPETS = (
    "contents: write",
    "actions: write",
    "packages: write",
    "deployments: write",
    "attestations: write",
    "checks: write",
)
SENTINEL_INLINE_RE = re.compile(r"#\s*security-guard:\s*allow\b")
SENTINEL_LINE_RE = re.compile(r"^\s*#\s*security-guard:\s*allow\b")
PULL_REQUEST_TARGET_SENTINEL_RE = re.compile(
    r"^\s*#\s*security-guard:\s*allow\s+pull_request_target\b",
    re.MULTILINE,
)
RUN_LINE_RE = re.compile(r"^(?P<indent>\s*)(?:-\s*)?run:\s*(?P<tail>.*)$")
ACTION_REF_RE = re.compile(r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)@(?P<ref>\S+)$")
FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
TRUSTED_ACTION_OWNERS = {"actions", "github"}
ID_TOKEN_ALLOWLIST = {".github/workflows/deploy-dashboard.yml"}


@dataclass(frozen=True)
class StepView:
    name: str
    uses: str | None
    run: str | None
    has_allow_sentinel: bool


@dataclass(frozen=True)
class JobView:
    name: str
    permissions: Mapping[str, str]
    steps: tuple[StepView, ...]


@dataclass(frozen=True)
class WorkflowView:
    path: Path
    raw_text: str
    triggers: frozenset[str]
    permissions: Mapping[str, str]
    jobs: Mapping[str, JobView]


def _normalize_yaml_root(raw_data: object) -> dict[str, object]:
    """Coerce the YAML 1.1 `on:` key from `True` back to `"on"` if needed."""
    if not isinstance(raw_data, dict):
        return {}

    normalized: dict[str, object] = {}
    for key, value in raw_data.items():
        if key is True and "on" not in raw_data:
            normalized["on"] = value
            continue
        if isinstance(key, str):
            normalized[key] = value
    return normalized


def _as_string_mapping(raw_data: object) -> dict[str, str]:
    if not isinstance(raw_data, dict):
        return {}

    mapping: dict[str, str] = {}
    for key, value in raw_data.items():
        if isinstance(key, str):
            mapping[key] = str(value)
    return mapping


def _parse_triggers(on_value: object) -> frozenset[str]:
    if isinstance(on_value, str):
        return frozenset({on_value})
    if isinstance(on_value, list):
        return frozenset(item for item in on_value if isinstance(item, str))
    if isinstance(on_value, dict):
        return frozenset(key for key in on_value if isinstance(key, str))
    return frozenset()


def _parse_steps(raw_steps: object) -> tuple[StepView, ...]:
    if not isinstance(raw_steps, list):
        return ()

    steps: list[StepView] = []
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            continue

        name_obj = raw_step.get("name")
        uses_obj = raw_step.get("uses")
        run_obj = raw_step.get("run")
        run_text = run_obj if isinstance(run_obj, str) else None
        steps.append(
            StepView(
                name=name_obj if isinstance(name_obj, str) else "",
                uses=uses_obj if isinstance(uses_obj, str) else None,
                run=run_text,
                has_allow_sentinel=run_text is not None and SENTINEL_INLINE_RE.search(run_text) is not None,
            )
        )
    return tuple(steps)


def _mapping_node_get(node: MappingNode, key: str) -> object | None:
    for raw_key, raw_value in node.value:
        if isinstance(raw_key, ScalarNode) and raw_key.value == key:
            return raw_value
    return None


def _step_run_has_allow_sentinel(
    lines: list[str],
    *,
    step_start_line: int,
    step_end_line: int,
    run_key_line: int,
) -> bool:
    """Evaluate sentinels within one parsed step's own `run` context."""
    if run_key_line >= len(lines):
        return False

    line = lines[run_key_line]
    match = RUN_LINE_RE.match(line)
    if not match:
        return False

    indent = len(match.group("indent"))
    tail = match.group("tail").strip()
    sentinel_above = False

    previous = run_key_line - 1
    while previous >= step_start_line and not lines[previous].strip():
        previous -= 1
    if previous >= step_start_line and SENTINEL_LINE_RE.match(lines[previous]):
        previous_indent = len(lines[previous]) - len(lines[previous].lstrip(" "))
        sentinel_above = previous_indent >= indent

    sentinel_in_block = False
    if tail.startswith("|") or tail.startswith(">"):
        body_index = run_key_line + 1
        while body_index < len(lines) and body_index < step_end_line:
            body_line = lines[body_index]
            body_stripped = body_line.strip()
            if body_stripped:
                body_indent = len(body_line) - len(body_line.lstrip(" "))
                if body_indent <= indent:
                    break
                if SENTINEL_LINE_RE.match(body_line):
                    sentinel_in_block = True
                    break
            body_index += 1

    return sentinel_above or sentinel_in_block or SENTINEL_INLINE_RE.search(tail) is not None


def _extract_job_step_sentinel_flags(raw_text: str) -> dict[str, list[bool]]:
    """Return one sentinel flag per parsed step for each job."""
    lines = raw_text.splitlines()
    root = yaml.compose(raw_text)
    if not isinstance(root, MappingNode):
        return {}

    raw_jobs = _mapping_node_get(root, "jobs")
    if not isinstance(raw_jobs, MappingNode):
        return {}

    job_step_sentinel_flags: dict[str, list[bool]] = {}
    for raw_job_name, raw_job_body in raw_jobs.value:
        if not isinstance(raw_job_name, ScalarNode) or not isinstance(raw_job_body, MappingNode):
            continue

        raw_steps = _mapping_node_get(raw_job_body, "steps")
        if not isinstance(raw_steps, SequenceNode):
            continue

        step_flags: list[bool] = []
        for raw_step in raw_steps.value:
            if not isinstance(raw_step, MappingNode):
                continue
            run_key_line: int | None = None
            for raw_step_key, _ in raw_step.value:
                if isinstance(raw_step_key, ScalarNode) and raw_step_key.value == "run":
                    run_key_line = raw_step_key.start_mark.line
                    break
            if run_key_line is None:
                step_flags.append(False)
                continue
            step_flags.append(
                _step_run_has_allow_sentinel(
                    lines,
                    step_start_line=raw_step.start_mark.line,
                    step_end_line=raw_step.end_mark.line,
                    run_key_line=run_key_line,
                )
            )
        job_step_sentinel_flags[raw_job_name.value] = step_flags
    return job_step_sentinel_flags


def _with_step_sentinels(
    steps: tuple[StepView, ...],
    sentinel_flags: list[bool],
) -> tuple[StepView, ...]:
    updated: list[StepView] = []

    for index, step in enumerate(steps):
        has_allow_sentinel = step.has_allow_sentinel
        if index < len(sentinel_flags):
            has_allow_sentinel = has_allow_sentinel or sentinel_flags[index]
        updated.append(
            StepView(
                name=step.name,
                uses=step.uses,
                run=step.run,
                has_allow_sentinel=has_allow_sentinel,
            )
        )
    return tuple(updated)


def load_workflow_view(path: Path) -> WorkflowView:
    raw_text = path.read_text(encoding="utf-8")
    parsed_yaml = yaml.safe_load(raw_text)
    workflow = _normalize_yaml_root(parsed_yaml)

    raw_jobs = workflow.get("jobs")
    jobs: dict[str, JobView] = {}
    if isinstance(raw_jobs, dict):
        for job_name, raw_job in raw_jobs.items():
            if not isinstance(job_name, str) or not isinstance(raw_job, dict):
                continue
            steps = _parse_steps(raw_job.get("steps"))
            jobs[job_name] = JobView(
                name=job_name,
                permissions=_as_string_mapping(raw_job.get("permissions")),
                steps=steps,
            )

    job_step_sentinel_flags = _extract_job_step_sentinel_flags(raw_text)
    updated_jobs: dict[str, JobView] = {}
    for job_name, job in jobs.items():
        sentinel_flags = job_step_sentinel_flags.get(job_name, [])
        steps = _with_step_sentinels(job.steps, sentinel_flags)
        updated_jobs[job_name] = JobView(
            name=job.name,
            permissions=job.permissions,
            steps=steps,
        )

    return WorkflowView(
        path=path,
        raw_text=raw_text,
        triggers=_parse_triggers(workflow.get("on")),
        permissions=_as_string_mapping(workflow.get("permissions")),
        jobs=updated_jobs,
    )


def uses_pull_request_event(workflow: WorkflowView) -> bool:
    return "pull_request" in workflow.triggers or "pull_request:" in workflow.raw_text


def uses_pull_request_target(workflow: WorkflowView) -> bool:
    return "pull_request_target" in workflow.triggers or "pull_request_target:" in workflow.raw_text


def uses_checkout(workflow: WorkflowView) -> bool:
    for job in workflow.jobs.values():
        for step in job.steps:
            if step.uses and step.uses.startswith("actions/checkout@"):
                return True
    return "actions/checkout@" in workflow.raw_text


def is_secret_bearing(workflow: WorkflowView) -> bool:
    return any(snippet in workflow.raw_text for snippet in SECRET_BEARING_SNIPPETS)


def has_trusted_author_gate(workflow: WorkflowView) -> bool:
    return any(snippet in workflow.raw_text for snippet in TRUSTED_AUTHOR_SNIPPETS)


def _has_pull_request_target_sentinel(workflow: WorkflowView) -> bool:
    return PULL_REQUEST_TARGET_SENTINEL_RE.search(workflow.raw_text) is not None


def _contains_id_token_write(permissions: Mapping[str, str]) -> bool:
    return permissions.get("id-token") == "write"


def _is_id_token_allowlisted(path: Path) -> bool:
    path_posix = path.as_posix()
    if path_posix in ID_TOKEN_ALLOWLIST:
        return True
    return any(path_posix.endswith(f"/{entry}") for entry in ID_TOKEN_ALLOWLIST)


def _is_pinned_third_party_action(uses: str) -> bool:
    if uses.startswith("./") or uses.startswith("docker://"):
        return True
    match = ACTION_REF_RE.match(uses)
    if not match:
        return True
    owner = match.group("owner").lower()
    if owner in TRUSTED_ACTION_OWNERS:
        return True
    return FULL_SHA_RE.match(match.group("ref")) is not None


def _is_npm_global_install_unpinned(line: str) -> bool:
    match = re.search(r"\bnpm\s+(?:install|i)\s+-g\s+([^\s#]+)", line)
    if not match:
        return False
    package_spec = match.group(1)
    if package_spec.startswith("@"):
        return "@" not in package_spec[1:]
    return "@" not in package_spec


def _is_npx_unpinned(line: str) -> bool:
    if re.search(r"\bnpx\b", line) is None:
        return False
    if re.search(r"--package(?:=|\s+)[^\s@]+@[^\s]+", line):
        return False
    if re.search(r"--package(?:=|\s+)@[^\s]+/[^\s@]+@[^\s]+", line):
        return False
    if re.search(r"\bnpx(?:\s+--[^\s]+(?:=[^\s]+)?)*\s+[^\s@]+@[^\s]+", line):
        return False
    if re.search(r"\bnpx(?:\s+--[^\s]+(?:=[^\s]+)?)*\s+@[^\s]+/[^\s@]+@[^\s]+", line):
        return False
    return True


def _is_pip_install_unpinned(line: str) -> bool:
    if re.search(r"\b(?:python3\s+-m\s+)?pip\s+install\b", line) is None:
        return False
    return not any(token in line for token in ("==", " -r ", "--require-hashes"))


def _is_pipx_install_unpinned(line: str) -> bool:
    match = re.search(r"\bpipx\s+install\s+([^\s#]+)", line)
    if not match:
        return False
    package_spec = match.group(1)
    if package_spec.startswith("@"):
        return "@" not in package_spec[1:]
    return "==" not in package_spec


def _is_pipe_to_shell(line: str) -> bool:
    return re.search(r"\bcurl\b[^\n|]*\|\s*(?:sh|bash)\b", line) is not None


def _find_unpinned_installer_line(step: StepView) -> str | None:
    if step.run is None:
        return None
    for raw_line in step.run.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _is_npm_global_install_unpinned(line):
            return "npm install -g without version pin"
        if _is_npx_unpinned(line):
            return "npx invocation without explicit version pin"
        if _is_pip_install_unpinned(line):
            return "pip install without pin or requirements file"
        if _is_pipx_install_unpinned(line):
            return "pipx install without == pin"
        if _is_pipe_to_shell(line):
            return "curl piped to shell"
    return None


def scan_workflow(path: Path) -> list[str]:
    workflow = load_workflow_view(path)
    failures: list[str] = []

    pr_event = uses_pull_request_event(workflow)
    pr_target = uses_pull_request_target(workflow)

    if pr_target and not _has_pull_request_target_sentinel(workflow):
        failures.append(
            f"{path}: pull_request_target requires '# security-guard: allow pull_request_target' sentinel."
        )

    for job in workflow.jobs.values():
        for step in job.steps:
            if not step.uses:
                continue
            if not _is_pinned_third_party_action(step.uses):
                failures.append(
                    f"{path}: third-party action '{step.uses}' must be pinned to a full 40-character commit SHA."
                )

    if _contains_id_token_write(workflow.permissions) and not _is_id_token_allowlisted(path):
        failures.append(f"{path}: id-token: write is only allowed for allowlisted workflows.")
    for job in workflow.jobs.values():
        if _contains_id_token_write(job.permissions) and not _is_id_token_allowlisted(path):
            failures.append(f"{path}: id-token: write is only allowed for allowlisted workflows.")

    if not pr_event:
        return failures

    if any(snippet in workflow.raw_text for snippet in BROAD_WRITE_SNIPPETS):
        failures.append(f"{path}: PR workflow requests overly broad write permissions.")

    if not workflow.permissions:
        failures.append(f"{path}: PR workflow must declare top-level permissions.")

    for job in workflow.jobs.values():
        for step in job.steps:
            if step.has_allow_sentinel:
                continue
            reason = _find_unpinned_installer_line(step)
            if reason:
                step_name = step.name or "unnamed step"
                failures.append(f"{path}: {step_name} uses disallowed installer pattern ({reason}).")

    if not is_secret_bearing(workflow):
        return failures

    if not workflow.permissions:
        failures.append(
            f"{path}: secret-bearing PR workflow must declare explicit permissions."
        )
    if "environment:" not in workflow.raw_text:
        failures.append(
            f"{path}: secret-bearing PR workflow must use an environment gate."
        )
    if not has_trusted_author_gate(workflow):
        failures.append(
            f"{path}: secret-bearing PR workflow must gate execution to KjellKod."
        )
    if SAME_REPO_SNIPPET not in workflow.raw_text:
        failures.append(
            f"{path}: secret-bearing PR workflow must require same-repo PRs."
        )
    if uses_checkout(workflow) and BASE_SHA_SNIPPET not in workflow.raw_text:
        failures.append(
            f"{path}: secret-bearing PR workflow must checkout the trusted base SHA, not PR head code."
        )

    return failures


def main() -> int:
    failures: list[str] = []
    for path in sorted(WORKFLOW_DIR.glob("*.y*ml")):
        failures.extend(scan_workflow(path))

    if not failures:
        print("workflow security guard passed")
        return 0

    print("workflow security guard failed:")
    for failure in failures:
        print(f"- {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
