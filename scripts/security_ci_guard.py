#!/usr/bin/env python3

from __future__ import annotations

from pathlib import Path


WORKFLOW_DIR = Path(".github/workflows")
TRUSTED_AUTHOR_SNIPPETS = {
    "github.event.pull_request.user.login == 'KjellKod'",
    'github.event.pull_request.user.login == "KjellKod"',
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


def uses_pull_request_event(text: str) -> bool:
    return "pull_request:" in text


def uses_pull_request_target(text: str) -> bool:
    return "pull_request_target:" in text


def uses_checkout(text: str) -> bool:
    return "actions/checkout@" in text


def is_secret_bearing(text: str) -> bool:
    return any(snippet in text for snippet in SECRET_BEARING_SNIPPETS)


def has_trusted_author_gate(text: str) -> bool:
    return any(snippet in text for snippet in TRUSTED_AUTHOR_SNIPPETS)


def scan_workflow(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    failures: list[str] = []

    if not (uses_pull_request_event(text) or uses_pull_request_target(text)):
        return failures

    if uses_pull_request_target(text) and uses_checkout(text):
        failures.append(
            f"{path}: pull_request_target must not be combined with actions/checkout on PR code."
        )

    if not uses_pull_request_event(text):
        return failures

    if any(snippet in text for snippet in BROAD_WRITE_SNIPPETS):
        failures.append(f"{path}: PR workflow requests overly broad write permissions.")

    if not is_secret_bearing(text):
        return failures

    if "permissions:" not in text:
        failures.append(
            f"{path}: secret-bearing PR workflow must declare explicit permissions."
        )
    if "environment:" not in text:
        failures.append(
            f"{path}: secret-bearing PR workflow must use an environment gate."
        )
    if not has_trusted_author_gate(text):
        failures.append(
            f"{path}: secret-bearing PR workflow must gate execution to KjellKod."
        )
    if SAME_REPO_SNIPPET not in text:
        failures.append(
            f"{path}: secret-bearing PR workflow must require same-repo PRs."
        )
    if uses_checkout(text) and BASE_SHA_SNIPPET not in text:
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
