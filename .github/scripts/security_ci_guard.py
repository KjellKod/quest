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
SECRET_TOKEN_RAW_SNIPPETS = (
    "OPENAI_API_KEY",
    "secrets.OPENAI_API_KEY",
)
SECRET_BEARING_SCOPES = frozenset({"pull-requests", "issues"})
BROAD_WRITE_SCOPES = frozenset({
    "contents",
    "actions",
    "packages",
    "deployments",
    "attestations",
    "checks",
})
# `permissions: write-all` is a scalar shortcut that grants every scope as write.
# Mirror that structurally so every downstream permission check (id-token rule,
# broad-write rule, secret-bearing rule) sees the implied grants. `read-all` is
# the complementary shortcut and must count as an explicit declaration.
WRITE_ALL_SCOPES = (
    "actions",
    "attestations",
    "checks",
    "contents",
    "deployments",
    "id-token",
    "issues",
    "packages",
    "pages",
    "pull-requests",
    "repository-projects",
    "security-events",
    "statuses",
)
READ_ALL_SCOPES = tuple(scope for scope in WRITE_ALL_SCOPES if scope != "id-token")
SENTINEL_INLINE_RE = re.compile(r"#\s*security-guard:\s*allow\b")
SENTINEL_LINE_RE = re.compile(r"^\s*#\s*security-guard:\s*allow\b")


def _has_unquoted_inline_sentinel(text: str) -> bool:
    """True iff `text` carries a `# security-guard: allow` sentinel outside any
    quoted string. Treats single quotes as fully literal and double quotes as
    backslash-escaping per POSIX shell rules. Avoids depending on `shlex.split`
    because it raises on unbalanced quotes, which appear regularly in real
    `run:` bodies (e.g. apostrophes inside echo messages)."""
    in_single = False
    in_double = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_single:
            if ch == "'":
                in_single = False
        elif in_double:
            if ch == "\\" and i + 1 < len(text):
                i += 2
                continue
            if ch == '"':
                in_double = False
        else:
            if ch == "'":
                in_single = True
            elif ch == '"':
                in_double = True
            elif ch == "#":
                # Unquoted `#` starts a real shell comment; check the
                # remainder of the line for the sentinel and stop scanning
                # — anything after this `#` is the comment body.
                return SENTINEL_INLINE_RE.match(text[i:]) is not None
        i += 1
    return False
PULL_REQUEST_TARGET_SENTINEL_RE = re.compile(
    r"^\s*#\s*security-guard:\s*allow\s+pull_request_target\b",
    re.MULTILINE,
)
RUN_LINE_RE = re.compile(r"^(?P<indent>\s*)(?:-\s*)?run:\s*(?P<tail>.*)$")
ACTION_REF_RE = re.compile(r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)@(?P<ref>\S+)$")
REUSABLE_WORKFLOW_REF_RE = re.compile(
    r"^(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)/(?P<path>[A-Za-z0-9_./-]+\.ya?ml)@(?P<ref>\S+)$"
)
DOCKER_DIGEST_REF_RE = re.compile(r"^docker://[^\s@]+@sha256:[0-9a-f]{64}$")
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
    uses: str | None


@dataclass(frozen=True)
class WorkflowView:
    path: Path
    raw_text: str
    triggers: frozenset[str]
    permissions: Mapping[str, str]
    permissions_declared: bool
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
    if isinstance(raw_data, str):
        if raw_data == "write-all":
            return {scope: "write" for scope in WRITE_ALL_SCOPES}
        if raw_data == "read-all":
            return {scope: "read" for scope in READ_ALL_SCOPES}
        return {}
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
                has_allow_sentinel=False,
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

    return sentinel_above or sentinel_in_block or _has_unquoted_inline_sentinel(tail)


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
            job_uses_obj = raw_job.get("uses")
            jobs[job_name] = JobView(
                name=job_name,
                permissions=_as_string_mapping(raw_job.get("permissions")),
                steps=steps,
                uses=job_uses_obj if isinstance(job_uses_obj, str) else None,
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
            uses=job.uses,
        )

    return WorkflowView(
        path=path,
        raw_text=raw_text,
        triggers=_parse_triggers(workflow.get("on")),
        permissions=_as_string_mapping(workflow.get("permissions")),
        permissions_declared=workflow.get("permissions") is not None,
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


def _permissions_grant_any(perms: Mapping[str, str], scopes: frozenset[str], value: str) -> bool:
    return any(perms.get(scope) == value for scope in scopes)


def _workflow_grants_any_write(workflow: WorkflowView, scopes: frozenset[str]) -> bool:
    if _permissions_grant_any(workflow.permissions, scopes, "write"):
        return True
    return any(
        _permissions_grant_any(job.permissions, scopes, "write")
        for job in workflow.jobs.values()
    )


def is_secret_bearing(workflow: WorkflowView) -> bool:
    if any(snippet in workflow.raw_text for snippet in SECRET_TOKEN_RAW_SNIPPETS):
        return True
    return _workflow_grants_any_write(workflow, SECRET_BEARING_SCOPES)


def has_broad_write_permissions(workflow: WorkflowView) -> bool:
    return _workflow_grants_any_write(workflow, BROAD_WRITE_SCOPES)


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
    if uses.startswith("./"):
        return True
    if uses.startswith("docker://"):
        return DOCKER_DIGEST_REF_RE.match(uses) is not None
    match = ACTION_REF_RE.match(uses) or REUSABLE_WORKFLOW_REF_RE.match(uses)
    if not match:
        return False
    owner = match.group("owner").lower()
    if owner in TRUSTED_ACTION_OWNERS:
        return True
    return FULL_SHA_RE.match(match.group("ref")) is not None


# Exact semver pin: `1.2.3` with optional `-prerelease` and `+build` metadata. No ranges, no dist-tags.
_NPM_EXACT_SEMVER_RE = re.compile(
    r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)

# npm install/npx flags whose value lives in the *next* token (space separated).
# Skipped as a pair so the value isn't misclassified as a package spec — e.g.
# `npm install -g --registry https://registry.example.com foo@1.2.3` must not
# treat the registry URL as an unpinned package.
_NPM_FLAGS_WITH_VALUE = frozenset({
    "--registry",
    "--prefix",
    "--cache",
    "--userconfig",
    "--globalconfig",
    "--proxy",
    "--https-proxy",
    "--ca",
    "--cafile",
    "--cert",
    "--key",
    "--user-agent",
    "--workspace",
    "-w",
    "--workspaces",
    "--loglevel",
    "--script-shell",
    "--tag",
    "--save-prefix",
    "-C",
    "--prefix-dir",
})


def _npm_package_spec_is_immutable(spec: str) -> bool:
    """True only if `spec` is `<name>@<exact-semver>` or `<name>@<40-char-sha>`."""
    # Scoped packages start with `@scope/name` — strip the leading `@scope/` before splitting on the version separator.
    body = spec
    if body.startswith("@"):
        slash_idx = body.find("/")
        if slash_idx == -1:
            return False
        body = body[slash_idx + 1 :]
    if "@" not in body:
        return False
    _, _, version = body.rpartition("@")
    if not version:
        return False
    if FULL_SHA_RE.match(version):
        return True
    return _NPM_EXACT_SEMVER_RE.match(version) is not None


def _is_npm_global_install_unpinned(line: str) -> bool:
    if re.search(r"\bnpm\s+(?:install|i)\b", line) is None:
        return False
    if not re.search(r"(?:\s|^)(?:-g|--global)(?:\s|$)", line):
        return False
    args_match = re.search(r"\bnpm\s+(?:install|i)\b(.*)$", line)
    if not args_match:
        return False
    args_str = args_match.group(1).split("#", 1)[0]
    tokens = args_str.split()
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("-"):
            # `--flag=value` is one token; nothing more to skip.
            if "=" in token:
                i += 1
                continue
            # `--flag value` — drop both tokens so the value isn't misread as a package.
            if token in _NPM_FLAGS_WITH_VALUE:
                i += 2
                continue
            i += 1
            continue
        if not _npm_package_spec_is_immutable(token):
            return True
        i += 1
    return False


def _is_npx_unpinned(line: str) -> bool:
    if re.search(r"\bnpx\b", line) is None:
        return False
    args_match = re.search(r"\bnpx\b(.*)$", line)
    if not args_match:
        return True
    args_str = args_match.group(1).split("#", 1)[0]
    tokens = args_str.split()
    i = 0
    package_specs: list[str] = []
    while i < len(tokens):
        token = tokens[i]
        if token in {"--package", "-p"}:
            if i + 1 < len(tokens):
                package_specs.append(tokens[i + 1])
                i += 2
                continue
            i += 1
            continue
        if token.startswith("--package="):
            package_specs.append(token.split("=", 1)[1])
            i += 1
            continue
        if token.startswith("-"):
            i += 1
            continue
        # Without --package/-p, the first positional is the package spec
        # to invoke. When --package was already used, that positional is
        # the command name inside the pinned package and is not a spec
        # we need to re-check for pinning.
        if not package_specs:
            package_specs.append(token)
        break
    if not package_specs:
        return True
    return not all(_npm_package_spec_is_immutable(spec) for spec in package_specs)


_PIP_FLAGS_WITH_VALUE = frozenset(
    {
        "-c",
        "--constraint",
        "-i",
        "--index-url",
        "--extra-index-url",
        "-f",
        "--find-links",
        "--target",
        "-t",
        "--prefix",
        "--root",
        "--platform",
        "--python-version",
        "--implementation",
        "--abi",
        "--src",
        "--cache-dir",
        "--no-binary",
        "--only-binary",
        "--proxy",
        "--cert",
        "--client-cert",
        "--trusted-host",
        "--timeout",
        "-r",
        "--requirement",
    }
)


_PIP_VCS_SCHEME_RE = re.compile(r"^(?:git|hg|svn|bzr)\+", re.IGNORECASE)
_PIP_HTTP_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def _is_pip_install_unpinned(line: str) -> bool:
    match = re.search(r"\b(?:python3?\s+-m\s+)?pip[0-9.]*\s+install\b(.*)$", line)
    if match is None:
        return False
    args_str = match.group(1)
    # `--require-hashes` allows everything (every distribution must carry a hash).
    if re.search(r"(?:^|\s)--require-hashes(?:\s|$)", args_str):
        return False
    args_str = args_str.split("#", 1)[0]
    tokens = args_str.split()
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith("-"):
            # `--requirement=req.txt` is a single token; nothing more to skip.
            if "=" in token:
                i += 1
                continue
            if token in _PIP_FLAGS_WITH_VALUE:
                i += 2
                continue
            i += 1
            continue
        # VCS specs (git+https://..., hg+...) — require an @<ref> pin to a 40-char SHA-like ref.
        if _PIP_VCS_SCHEME_RE.match(token):
            at_idx = token.rfind("@")
            scheme_end = token.find("://")
            if at_idx <= scheme_end:
                return True
            ref = token[at_idx + 1 :]
            # Strip any egg / subdirectory suffix introduced with `#`.
            ref = ref.split("#", 1)[0]
            if not FULL_SHA_RE.match(ref):
                return True
            i += 1
            continue
        # Direct HTTP(S) tarball/wheel URLs — require either an inline hash fragment or `--require-hashes` (handled above).
        if _PIP_HTTP_URL_RE.match(token):
            return True
        # Local paths and file: specs are out of scope for supply-chain pinning.
        if token.startswith((".", "/", "file:")) or "://" in token:
            i += 1
            continue
        if "==" not in token and "===" not in token:
            return True
        i += 1
    return False


def _is_pipx_install_unpinned(line: str) -> bool:
    match = re.search(r"\bpipx\s+install\s+([^\s#]+)", line)
    if not match:
        return False
    package_spec = match.group(1)
    if package_spec.startswith("@"):
        return "@" not in package_spec[1:]
    return "==" not in package_spec


_PIPE_TO_SHELL_FETCHER_RE = re.compile(r"\b(?:curl|wget|fetch)\b[^\n|]*\|")
# The executor must be the actual command being run at the start of a pipe-stage
# command, optionally behind a `sudo`/`env`/`exec` wrapper and/or an absolute
# path. Anchoring this way prevents false positives where shell-name words
# appear only in quoted arguments (e.g. `| echo "Use python here"`).
#
# Wrapper handling:
#   * An inline env-var assignment prefix (`FOO=bar BAZ=qux <wrapper-or-exec>`).
#   * `sudo`/`env`/`exec` wrappers, repeated, each with optional flags. Flag
#     tokens include short flags that take a value in the next token
#     (`-u root`), short flags that don't (`-i`), long flags (`--user=root`),
#     and env-style assignments (`FOO=bar`).
_PIPE_TO_SHELL_EXECUTOR_RE = re.compile(
    r"^\s*"
    r"(?:\S+=\S*\s+)*"
    r"(?:(?:sudo|env|exec)(?:\s+-\S+(?:\s+\S+)?|\s+\S+=\S*)*\s+)*"
    r"(?:/\S*/)?"
    r"(?:sh|bash|zsh|ksh|dash|ash|fish|python[0-9.]*|perl|ruby|node)\b"
)
# Split each pipe stage on shell command separators so chained commands like
# `tar xzf - && python install.py` still trip the rule on the executed
# component rather than depending on an unanchored substring match.
_SHELL_CMD_SEPARATOR_RE = re.compile(r"&&|\|\||;")


def _is_pipe_to_shell(line: str) -> bool:
    if _PIPE_TO_SHELL_FETCHER_RE.search(line) is None:
        return False
    # Inspect every pipe stage after the fetcher; flag if any stage executes a shell-like interpreter.
    stages = line.split("|")
    if len(stages) < 2:
        return False
    for stage in stages[1:]:
        for command in _SHELL_CMD_SEPARATOR_RE.split(stage):
            if _PIPE_TO_SHELL_EXECUTOR_RE.match(command):
                return True
    return False


def _join_shell_continuations(body: str) -> list[str]:
    """Collapse trailing-backslash shell line continuations into single logical lines."""
    joined: list[str] = []
    buffer = ""
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        # A trailing backslash continues the next line, but `\\` (escaped) does not.
        if line.endswith("\\") and not line.endswith("\\\\"):
            buffer += line[:-1] + " "
            continue
        joined.append(buffer + line)
        buffer = ""
    if buffer:
        joined.append(buffer)
    return joined


def _check_installer_line(line: str) -> str | None:
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


def _find_unpinned_installer_line(step: StepView) -> str | None:
    if step.run is None:
        return None
    logical_lines = [
        raw for raw in _join_shell_continuations(step.run) if raw.strip()
    ]
    # Single-logical-line steps may rely on a sentinel sourced from outside the
    # body (a YAML comment above the run key, or a trailing comment that YAML
    # stripped during parsing). Trust the AST-derived flag only for those.
    if step.has_allow_sentinel:
        non_sentinel_lines = [
            line for line in logical_lines if not SENTINEL_LINE_RE.match(line.strip())
        ]
        if len(non_sentinel_lines) <= 1:
            return None

    next_line_exempt = False
    for raw_line in logical_lines:
        line = raw_line.strip()
        # Pure sentinel-comment line: annotate the next non-blank command line.
        if SENTINEL_LINE_RE.match(line):
            next_line_exempt = True
            continue
        # Trailing inline sentinel on the same line as the command.
        # Must be a real shell comment, not the sentinel string embedded
        # inside a quoted argument to the command.
        if not line.startswith("#") and _has_unquoted_inline_sentinel(line):
            next_line_exempt = False
            continue
        if next_line_exempt:
            next_line_exempt = False
            continue
        reason = _check_installer_line(line)
        if reason:
            return reason
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
        if job.uses and not _is_pinned_third_party_action(job.uses):
            failures.append(
                f"{path}: third-party reusable workflow '{job.uses}' must be pinned to a full 40-character commit SHA."
            )
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

    if has_broad_write_permissions(workflow):
        failures.append(f"{path}: PR workflow requests overly broad write permissions.")

    if not workflow.permissions_declared:
        failures.append(f"{path}: PR workflow must declare top-level permissions.")

    for job in workflow.jobs.values():
        for step in job.steps:
            reason = _find_unpinned_installer_line(step)
            if reason:
                step_name = step.name or "unnamed step"
                failures.append(f"{path}: {step_name} uses disallowed installer pattern ({reason}).")

    if not is_secret_bearing(workflow):
        return failures

    if not workflow.permissions_declared:
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
