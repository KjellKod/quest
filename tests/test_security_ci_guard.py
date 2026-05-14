"""Tests for .github/scripts/security_ci_guard.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_module():
    module_path = _repo_root() / ".github" / "scripts" / "security_ci_guard.py"
    spec = importlib.util.spec_from_file_location("security_ci_guard", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_workflow(tmp_path: Path, name: str, text: str) -> Path:
    workflow_path = tmp_path / name
    workflow_path.write_text(text, encoding="utf-8")
    return workflow_path


def test_workflow_yaml_on_key_coerced_to_bool_is_normalized(tmp_path: Path) -> None:
    """YAML 1.1 parses bare `on:` as Python True; the loader must restore the string key."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "workflow.yml",
        """\
name: Example
on:
  pull_request:
    branches: [main]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
""",
    )

    view = module.load_workflow_view(workflow_path)
    assert "pull_request" in view.triggers


def test_sentinel_does_not_leak_to_next_step(tmp_path: Path) -> None:
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "workflow.yml",
        """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  job-one:
    runs-on: ubuntu-latest
    steps:
      - name: allowed-step
        run: |
          # security-guard: allow migration bootstrap
          npm install -g foo
      - name: blocked-step
        run: npm install -g bar
  job-two:
    runs-on: ubuntu-latest
    steps:
      - name: blocked-in-second-job
        run: npm install -g baz
""",
    )

    failures = module.scan_workflow(workflow_path)
    assert len([f for f in failures if "disallowed installer pattern" in f]) == 2
    assert any("blocked-step" in failure for failure in failures)
    assert any("blocked-in-second-job" in failure for failure in failures)


def test_non_step_run_key_does_not_shift_sentinel_mapping(tmp_path: Path) -> None:
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "workflow.yml",
        """\
name: Example
on:
  pull_request:
permissions:
  contents: read
defaults:
  run:
    shell: bash
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - name: allowed-step
        run: |
          # security-guard: allow temporary bootstrap
          npm install -g foo
      - name: should-fail
        run: npm install -g bar
""",
    )

    failures = module.scan_workflow(workflow_path)
    installer_failures = [f for f in failures if "disallowed installer pattern" in f]
    assert len(installer_failures) == 1
    assert "should-fail" in installer_failures[0]


def test_defaults_run_mapping_does_not_leak_sentinel_to_next_step(tmp_path: Path) -> None:
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "workflow.yml",
        """\
name: Example
on:
  pull_request:
permissions:
  contents: read
defaults:
  run:
    shell: bash
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: |
          npm install -g foo@1.0.0
          # security-guard: allow temporary bootstrap
      - run: npm install -g bar
""",
    )

    failures = module.scan_workflow(workflow_path)
    installer_failures = [f for f in failures if "disallowed installer pattern" in f]
    assert len(installer_failures) == 1
    assert "unnamed step" in installer_failures[0]


def test_validate_quest_config_has_no_npm_node_ajv_tokens() -> None:
    content = (_repo_root() / ".github" / "workflows" / "validate-quest-config.yml").read_text(
        encoding="utf-8"
    )
    lowered = content.lower()
    assert "npm" not in lowered
    assert "node" not in lowered
    assert "ajv" not in lowered
    assert "setup-node" not in lowered


def test_rule_npm_view_metadata_call_does_not_trigger_installer_rule(tmp_path: Path) -> None:
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "workflow.yml",
        """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - name: metadata-only
        run: npm view @openai/codex version
""",
    )

    assert module.scan_workflow(workflow_path) == []


@pytest.mark.parametrize(
    ("name", "content", "allowed", "expected_fragment"),
    [
        (
            "pull_request_target_fail.yml",
            """\
name: Example
on:
  pull_request_target:
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
            False,
            "pull_request_target requires",
        ),
        (
            "pull_request_target_allow.yml",
            """\
# security-guard: allow pull_request_target migration-only check
name: Example
on:
  pull_request_target:
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
            True,
            "pull_request_target requires",
        ),
    ],
)
def test_rule_pull_request_target_sentinel(
    tmp_path: Path,
    name: str,
    content: str,
    allowed: bool,
    expected_fragment: str,
) -> None:
    module = _load_module()
    workflow_path = _write_workflow(tmp_path, name, content)
    failures = module.scan_workflow(workflow_path)
    if allowed:
        assert all(expected_fragment not in failure for failure in failures)
    else:
        assert any(expected_fragment in failure for failure in failures)


@pytest.mark.parametrize(
    ("name", "content", "allowed", "expected_fragment"),
    [
        (
            "third_party_unpinned.yml",
            """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: openai/codex-action@v1
""",
            False,
            "third-party action",
        ),
        (
            "third_party_pinned.yml",
            """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: openai/codex-action@e0fdf01220eb9a88167c4898839d273e3f2609d1
""",
            True,
            "third-party action",
        ),
    ],
)
def test_rule_third_party_sha_pinning(
    tmp_path: Path,
    name: str,
    content: str,
    allowed: bool,
    expected_fragment: str,
) -> None:
    module = _load_module()
    workflow_path = _write_workflow(tmp_path, name, content)
    failures = module.scan_workflow(workflow_path)
    if allowed:
        assert all(expected_fragment not in failure for failure in failures)
    else:
        assert any(expected_fragment in failure for failure in failures)


@pytest.mark.parametrize(
    ("name", "failing_workflow", "passing_workflow", "expected_fragment"),
    [
        (
            "installer_hygiene",
            """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - name: unpinned-install
        run: pip install requests
""",
            """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - name: pinned-install
        run: pip install requests==2.32.3
""",
            "disallowed installer pattern",
        ),
        (
            "top_level_permissions",
            """\
name: Example
on:
  pull_request:
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
            """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
            "must declare top-level permissions",
        ),
        (
            "id_token_allowlist",
            """\
name: Example
on:
  push:
    branches: [main]
permissions:
  contents: read
  id-token: write
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
            """\
name: Example
on:
  push:
    branches: [main]
permissions:
  contents: read
  id-token: write
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
            "id-token: write is only allowed",
        ),
    ],
)
def test_rule_fixtures_b_to_f(
    tmp_path: Path,
    monkeypatch,
    name: str,
    failing_workflow: str,
    passing_workflow: str,
    expected_fragment: str,
) -> None:
    module = _load_module()
    failing_path = _write_workflow(tmp_path, f"{name}_failing.yml", failing_workflow)
    passing_path = _write_workflow(tmp_path, f"{name}_passing.yml", passing_workflow)

    if name == "id_token_allowlist":
        monkeypatch.setattr(module, "ID_TOKEN_ALLOWLIST", {str(passing_path)})

    failing = module.scan_workflow(failing_path)
    passing = module.scan_workflow(passing_path)
    assert any(expected_fragment in failure for failure in failing)
    assert all(expected_fragment not in failure for failure in passing)


def test_cli_output_matches_legacy_format_on_failure(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    """CLI output must remain `workflow security guard failed:` plus `- <path>:` bullets."""
    module = _load_module()
    workflows = tmp_path / "workflows"
    workflows.mkdir()

    failing = workflows / "failing.yml"
    failing.write_text(
        """\
name: Failing
on:
  pull_request:
    branches: [main]
permissions:
  contents: write
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "WORKFLOW_DIR", workflows)

    assert module.main() == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "workflow security guard failed:"
    assert lines[1].startswith("- ")
    assert lines[1].startswith(f"- {failing}:")


def test_existing_workflows_pass_guard() -> None:
    """All on-disk workflows must pass the guard after this commit lands."""
    module = _load_module()
    failures = []
    for workflow_path in sorted((_repo_root() / ".github" / "workflows").glob("*.y*ml")):
        failures.extend(module.scan_workflow(workflow_path))
    assert failures == []


def test_permissions_write_all_string_triggers_id_token_rule(tmp_path: Path) -> None:
    """`permissions: write-all` grants id-token write implicitly; rule (f) must catch it."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "write_all.yml",
        """\
name: Example
on:
  push:
    branches: [main]
permissions: write-all
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("id-token: write is only allowed" in failure for failure in failures)


def test_unparseable_uses_reference_fails_closed(tmp_path: Path) -> None:
    """A `uses:` value that doesn't match owner/repo@ref must fail the SHA-pin rule."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "uses_unparseable.yml",
        """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: some-weird-bare-name
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("third-party action" in failure for failure in failures)


def test_pip_install_mixed_pinned_and_unpinned_is_flagged(tmp_path: Path) -> None:
    """`pip install foo==1.0 bar` must fail rule (d): every positional package needs `==`."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pip_mixed.yml",
        """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: pip install foo==1.0 bar
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures)
    assert any("pip install" in failure for failure in failures)


def test_pip3_install_unpinned_is_flagged(tmp_path: Path) -> None:
    """The pip-install matcher must also catch versioned `pip3 install` invocations."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pip3_unpinned.yml",
        """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: pip3 install requests
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures)


def test_pip_install_with_requirements_file_passes(tmp_path: Path) -> None:
    """`pip install -r requirements.txt` is an explicit safe mode and must not be flagged."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pip_requirements.yml",
        """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: pip install -r requirements.txt
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("disallowed installer pattern" not in failure for failure in failures)
