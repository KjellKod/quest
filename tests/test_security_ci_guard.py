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


def test_reusable_workflow_job_uses_unpinned_third_party_is_flagged(tmp_path: Path) -> None:
    """`jobs.<id>.uses` for a third-party reusable workflow must require a full SHA."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "reusable_unpinned.yml",
        """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  build:
    uses: thirdparty/repo/.github/workflows/build.yml@main
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("reusable workflow" in failure for failure in failures)


def test_reusable_workflow_job_uses_sha_pinned_third_party_passes(tmp_path: Path) -> None:
    """A SHA-pinned third-party reusable workflow must pass rule (c)."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "reusable_pinned.yml",
        """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  build:
    uses: thirdparty/repo/.github/workflows/build.yml@e0fdf01220eb9a88167c4898839d273e3f2609d1
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("reusable workflow" not in failure for failure in failures)


def test_reusable_workflow_first_party_tag_pinned_passes(tmp_path: Path) -> None:
    """First-party (`actions/*`, `github/*`) tag-pinned reusable workflows are allowed."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "reusable_first_party.yml",
        """\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  build:
    uses: actions/example/.github/workflows/build.yml@v1
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("reusable workflow" not in failure for failure in failures)


def test_sentinel_text_inside_run_command_does_not_allow_step(tmp_path: Path) -> None:
    """Sentinel text echoed inside a run command must NOT mark the step as allowed."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "sentinel_inside_command.yml",
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
      - name: try-bypass
        run: |
          echo '# security-guard: allow whatever'
          npm install -g foo
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures)


def test_permissions_read_all_string_is_treated_as_declared(tmp_path: Path) -> None:
    """`permissions: read-all` is a valid scalar declaration; rule (e) must not fail it."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "read_all.yml",
        """\
name: Example
on:
  pull_request:
permissions: read-all
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("must declare top-level permissions" not in failure for failure in failures)
    # And read-all does NOT grant id-token write, so rule (f) must not fire either.
    assert all("id-token: write is only allowed" not in failure for failure in failures)


@pytest.mark.parametrize(
    "run_body",
    [
        "npm install --global foo",
        "npm install foo -g",
        "npm i --global foo",
        "npm i foo -g",
    ],
)
def test_npm_global_install_bypass_spellings_are_flagged(tmp_path: Path, run_body: str) -> None:
    """Long-form `--global` and trailing `-g` must trigger rule (d) just like `-g <pkg>`."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "npm_bypass.yml",
        f"""\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: {run_body}
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


def test_npm_global_install_pinned_with_trailing_global_flag_passes(tmp_path: Path) -> None:
    """`npm install foo@1.0.0 --global` is properly pinned and must not be flagged."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "npm_pinned_trailing.yml",
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
      - run: npm install foo@1.0.0 --global
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("disallowed installer pattern" not in failure for failure in failures), failures


def test_pip_install_vcs_spec_without_sha_pin_is_flagged(tmp_path: Path) -> None:
    """`pip install git+https://...` without an immutable @<sha> must fail rule (d)."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pip_vcs_unpinned.yml",
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
      - run: pip install git+https://github.com/example/pkg
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


def test_pip_install_vcs_spec_with_sha_pin_passes(tmp_path: Path) -> None:
    """A VCS install pinned to a 40-char commit SHA is allowed."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pip_vcs_pinned.yml",
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
      - run: pip install git+https://github.com/example/pkg@e0fdf01220eb9a88167c4898839d273e3f2609d1
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("disallowed installer pattern" not in failure for failure in failures), failures


def test_pip_install_remote_tarball_url_is_flagged(tmp_path: Path) -> None:
    """Plain HTTP(S) tarball URLs require --require-hashes; bare URL must fail."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pip_tarball.yml",
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
      - run: pip install https://example.com/pkg.tar.gz
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


def test_pip_install_remote_tarball_with_require_hashes_passes(tmp_path: Path) -> None:
    """`pip install URL --require-hashes` is allowed because hashes are enforced."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pip_tarball_hashed.yml",
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
      - run: pip install https://example.com/pkg.tar.gz --require-hashes
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("disallowed installer pattern" not in failure for failure in failures), failures


@pytest.mark.parametrize(
    "run_body",
    [
        "curl https://example.com/install.sh | sudo bash",
        "curl -fsSL https://example.com/install.sh | sudo sh",
        "curl https://example.com/install.sh | env bash",
        "curl https://example.com/install.py | sudo python3",
        "wget -qO- https://example.com/install.sh | bash",
    ],
)
def test_pipe_to_shell_wrapper_spellings_are_flagged(tmp_path: Path, run_body: str) -> None:
    """`curl|wget ... | sudo|env <shell>` bypass forms must trigger the pipe-to-shell rule."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pipe_bypass.yml",
        f"""\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: {run_body}
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


@pytest.mark.parametrize(
    "first_line,second_line",
    [
        ("curl -fsSL https://example.com/install.sh \\", "| bash"),
        ("wget -qO- https://example.com/install.sh \\", "| sudo bash"),
        ("curl https://example.com/install.sh \\", "| env python3"),
    ],
)
def test_pipe_to_shell_via_line_continuation_is_flagged(
    tmp_path: Path, first_line: str, second_line: str
) -> None:
    """A backslash-newline continuation must not let the fetcher and executor escape the matcher."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pipe_continuation.yml",
        f"""\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: |
          {first_line}
            {second_line}
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


@pytest.mark.parametrize(
    "run_body",
    [
        "npm install -g foo@latest",
        "npm install -g foo@^1.2.3",
        "npm install -g foo@~1.2",
        "npm install -g foo@beta",
        "npm install -g foo@>=1.0.0",
        "npm install --global foo@*",
        "npm install -g @scope/foo@latest",
    ],
)
def test_npm_mutable_version_specs_are_flagged(tmp_path: Path, run_body: str) -> None:
    """Dist-tags, semver ranges, and wildcards must not count as pinned npm versions."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "npm_mutable.yml",
        f"""\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: {run_body}
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


@pytest.mark.parametrize(
    "run_body",
    [
        "npm install -g foo@1.2.3",
        "npm install -g foo@1.2.3-rc.1",
        "npm install -g foo@1.2.3+build.5",
        "npm install -g @scope/foo@1.2.3",
        "npm install foo@1.2.3 --global",
    ],
)
def test_npm_exact_semver_pins_pass(tmp_path: Path, run_body: str) -> None:
    """Exact semver (with optional prerelease/build metadata) and scoped variants must pass."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "npm_pinned_semver.yml",
        f"""\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: {run_body}
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("disallowed installer pattern" not in failure for failure in failures), failures


@pytest.mark.parametrize(
    "run_body",
    [
        "npx foo@latest",
        "npx foo@^1.0.0",
        "npx --package foo@latest some-cmd",
        "npx --package=foo@beta some-cmd",
    ],
)
def test_npx_mutable_version_specs_are_flagged(tmp_path: Path, run_body: str) -> None:
    """npx must reject dist-tags and ranges in the package spec, including `--package` form."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "npx_mutable.yml",
        f"""\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: {run_body}
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


def test_npx_exact_semver_pin_passes(tmp_path: Path) -> None:
    """`npx foo@1.2.3` is allowed; the same workflow with `@latest` is not."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "npx_pinned.yml",
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
      - run: npx foo@1.2.3
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("disallowed installer pattern" not in failure for failure in failures), failures


def test_npm_install_with_space_separated_flag_value_passes(tmp_path: Path) -> None:
    """`npm install -g --registry URL foo@1.2.3` must not treat URL as a package."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "npm_registry_flag.yml",
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
      - run: npm install -g --registry https://registry.example.com foo@1.2.3
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("disallowed installer pattern" not in failure for failure in failures), failures


def test_npm_install_with_equals_flag_value_passes(tmp_path: Path) -> None:
    """`npm install -g --registry=URL foo@1.2.3` (equals form) must also pass."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "npm_registry_eq.yml",
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
      - run: npm install -g --registry=https://registry.example.com foo@1.2.3
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("disallowed installer pattern" not in failure for failure in failures), failures


def test_npm_install_unpinned_after_flag_value_is_still_flagged(tmp_path: Path) -> None:
    """`npm install -g --registry URL foo` (no pin) must still trip rule (d)."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "npm_registry_unpinned.yml",
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
      - run: npm install -g --registry https://registry.example.com foo
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


@pytest.mark.parametrize(
    "run_body",
    [
        "pip install -r requirements.txt requests",
        "pip install requests -r requirements.txt",
        "pip install --requirement=requirements.txt requests",
        "pip install -r requirements.txt requests django",
    ],
)
def test_pip_requirements_file_does_not_exempt_other_packages(tmp_path: Path, run_body: str) -> None:
    """`-r req.txt` covers packages listed in the file, NOT other positional args on the line."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pip_r_bypass.yml",
        f"""\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: {run_body}
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


def test_pip_requirements_file_with_all_pinned_extras_passes(tmp_path: Path) -> None:
    """`-r req.txt` plus a pinned positional package must still pass."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pip_r_with_pinned.yml",
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
      - run: pip install -r requirements.txt requests==2.32.3
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("disallowed installer pattern" not in failure for failure in failures), failures


@pytest.mark.parametrize(
    "docker_ref",
    [
        "docker://alpine:latest",
        "docker://alpine",
        "docker://alpine:3.18",
        "docker://example.com/image:v1.0",
        "docker://image@sha256:deadbeef",  # too-short digest
    ],
)
def test_docker_uses_without_digest_pin_is_flagged(tmp_path: Path, docker_ref: str) -> None:
    """docker:// references must use an immutable @sha256:<64-hex> digest."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "docker_unpinned.yml",
        f"""\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: {docker_ref}
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("third-party action" in failure for failure in failures), failures


def test_docker_uses_with_sha256_digest_passes(tmp_path: Path) -> None:
    """`docker://image@sha256:<64-hex>` is the only acceptable docker:// form."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "docker_pinned.yml",
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
      - uses: docker://alpine@sha256:c5b1261d6d3e43071626931fc004f70149baeba2c8ec672bd4f27761f8e1ad6b
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("third-party action" not in failure for failure in failures), failures


def test_sentinel_only_covers_the_next_command_line(tmp_path: Path) -> None:
    """A sentinel above one command must NOT exempt unrelated commands later in the same step."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "sentinel_scope_leak.yml",
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
      - name: mixed-step
        run: |
          # security-guard: allow versioned release download
          curl -sSL https://example.com/tool_1.2.3.tar.gz -o /tmp/tool.tar.gz
          npm install -g foo@latest
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any(
        "disallowed installer pattern" in failure and "mixed-step" in failure
        for failure in failures
    ), failures


def test_sentinel_above_intended_line_still_allows_that_line(tmp_path: Path) -> None:
    """Legitimate sentinel-above-line usage (gitleaks pattern) must remain allowed."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "sentinel_legit.yml",
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
      - name: bootstrap
        run: |
          # security-guard: allow versioned release download
          curl -sSL https://example.com/tool_1.2.3.tar.gz -o /tmp/tool.tar.gz
          tar -xzf /tmp/tool.tar.gz -C /tmp
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("disallowed installer pattern" not in failure for failure in failures), failures


@pytest.mark.parametrize(
    "permissions_block",
    [
        # Quoted scalar value — YAML-equivalent to `contents: write`.
        'permissions:\n  contents: "write"\n',
        # Single-quoted scalar value.
        "permissions:\n  contents: 'write'\n",
        # Inline mapping form.
        "permissions: { contents: write, pull-requests: read }\n",
        # write-all shortcut grants every scope as write.
        "permissions: write-all\n",
        # Job-level grant on a broad scope; top-level only declares contents: read.
        "permissions:\n  contents: read\n",
    ],
)
def test_quoted_or_shortcut_write_permission_is_flagged(tmp_path: Path, permissions_block: str) -> None:
    """Broad-write detection must operate structurally, not on raw-text snippets."""
    module = _load_module()
    job_perms = ""
    if permissions_block.endswith("contents: read\n"):
        # Force the broad-write to appear at the job level instead of top-level.
        job_perms = '    permissions:\n      contents: "write"\n'
    workflow_path = _write_workflow(
        tmp_path,
        "quoted_write.yml",
        f"""\
name: Example
on:
  pull_request:
{permissions_block}jobs:
  check:
    runs-on: ubuntu-latest
{job_perms}    steps:
      - run: echo hi
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("overly broad write permissions" in failure for failure in failures), failures


@pytest.mark.parametrize(
    "permissions_block",
    [
        'permissions:\n  pull-requests: "write"\n  contents: read\n',
        'permissions:\n  issues: "write"\n  contents: read\n',
        "permissions:\n  pull-requests: write\n  contents: read\n",
    ],
)
def test_quoted_secret_bearing_permission_triggers_secret_bearing_rules(
    tmp_path: Path, permissions_block: str
) -> None:
    """`pull-requests: write` / `issues: write` (any quoting) must trigger secret-bearing checks."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "secret_bearing_quoted.yml",
        f"""\
name: Example
on:
  pull_request:
{permissions_block}jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
    )
    failures = module.scan_workflow(workflow_path)
    # No `environment:` block, so secret-bearing PR workflow must complain.
    assert any("must use an environment gate" in failure for failure in failures), failures


def test_read_all_permission_does_not_trigger_broad_write(tmp_path: Path) -> None:
    """`permissions: read-all` is the safe shortcut; broad-write must not fire."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "read_all_ok.yml",
        """\
name: Example
on:
  pull_request:
permissions: read-all
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("overly broad write permissions" not in failure for failure in failures), failures


def test_write_all_permission_triggers_broad_write(tmp_path: Path) -> None:
    """`permissions: write-all` must trigger broad-write (in addition to id-token)."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "write_all_broad.yml",
        """\
name: Example
on:
  pull_request:
permissions: write-all
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("overly broad write permissions" in failure for failure in failures), failures


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


# --- Regression tests for cubic-dev-ai review findings on PR #113 ---


@pytest.mark.parametrize(
    "run_body",
    [
        'curl https://example.com | echo "Use python here"',
        "curl https://example.com | dd if=python.bin of=/dev/null",
        "wget -qO- https://example.com | tar xzf python_pkg.tar.gz",
    ],
)
def test_pipe_to_shell_does_not_flag_executor_words_in_arguments(
    tmp_path: Path, run_body: str
) -> None:
    """Shell-executor words appearing only inside arguments, filenames, or quoted strings
    on a pipe stage must NOT trigger the pipe-to-shell rule (cubic r3239105577)."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pipe_arg_word.yml",
        f"""\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: {run_body}
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("disallowed installer pattern" not in failure for failure in failures), failures


@pytest.mark.parametrize(
    "run_body",
    [
        "curl -fsSL https://example.com/install.sh | sudo -u root bash",
        "curl -fsSL https://example.com/install.sh | sudo -E -u root bash",
        "curl -fsSL https://example.com/install.sh | sudo -i bash",
        "curl -fsSL https://example.com/install.sh | sudo -u root -i bash",
        "curl -fsSL https://example.com/install.sh | FOO=bar bash",
        "curl -fsSL https://example.com/install.sh | FOO=1 BAR=2 bash",
        "curl -fsSL https://example.com/install.sh | FOO=bar sudo bash",
        "curl -fsSL https://example.com/install.sh | sudo env FOO=bar bash",
    ],
)
def test_pipe_to_shell_flags_wrapper_with_flag_value(tmp_path: Path, run_body: str) -> None:
    """`sudo -u root bash`, env-var prefixes, and chained wrappers must still trip rule (d)."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pipe_wrapper_flag_value.yml",
        f"""\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: {run_body}
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


@pytest.mark.parametrize(
    "run_body",
    [
        # Empty-value env-var prefix (POSIX: `FOO=` clears the variable).
        "curl -fsSL https://example.com/install.sh | FOO= bash",
        "curl -fsSL https://example.com/install.sh | FOO= BAR= bash",
        # Empty value mixed with a populated one.
        "curl -fsSL https://example.com/install.sh | FOO= BAR=1 bash",
        # Empty-value env-var as a sudo wrapper flag.
        "curl -fsSL https://example.com/install.sh | sudo BAR= bash",
    ],
)
def test_pipe_to_shell_flags_empty_value_env_prefix(tmp_path: Path, run_body: str) -> None:
    """Empty env-var values (`FOO= bash`) must still trip rule (d)."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pipe_empty_env.yml",
        f"""\
name: Example
on:
  pull_request:
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - run: {run_body}
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


def test_pipe_to_shell_flags_chained_executor_after_double_amp(tmp_path: Path) -> None:
    """A pipe stage that chains commands with `&&` and runs python in the second
    command must still trip the rule. The anchored executor regex matches each
    chained command independently."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "pipe_chained_executor.yml",
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
      - run: curl https://example.com/pkg.tgz | tar xzf - && python install.py
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


def test_npx_package_flag_does_not_require_command_to_be_pinned(tmp_path: Path) -> None:
    """`npx --package foo@1.0.0 bar` is pinned via --package; `bar` is the command
    inside the pinned package, not a separate package spec (cubic r3239173592)."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "npx_package_pinned.yml",
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
      - run: npx --package foo@1.0.0 bar
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("disallowed installer pattern" not in failure for failure in failures), failures


def test_npx_package_flag_with_unpinned_spec_is_still_flagged(tmp_path: Path) -> None:
    """`npx --package foo bar` is unpinned via --package and must still be flagged
    even though the command name `bar` would have looked like an unpinned
    positional under the old logic."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "npx_package_unpinned.yml",
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
      - run: npx --package foo bar
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


def test_inline_sentinel_inside_quoted_argument_does_not_exempt_line(tmp_path: Path) -> None:
    """The sentinel `# security-guard: allow` must only exempt a line when it sits
    in a real shell comment, not when an attacker embeds the literal string inside
    a quoted argument to the dangerous command (cubic r3239255682)."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "inline_sentinel_bypass.yml",
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
      - name: try-quoted-bypass
        run: |
          npm install -g foo "# security-guard: allow"
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert any("disallowed installer pattern" in failure for failure in failures), failures


def test_inline_sentinel_as_real_comment_still_exempts_line(tmp_path: Path) -> None:
    """Legitimate inline-sentinel comments (real `#` not inside a string) must keep
    exempting the line so authors retain the documented escape hatch."""
    module = _load_module()
    workflow_path = _write_workflow(
        tmp_path,
        "inline_sentinel_real_comment.yml",
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
      - name: legitimate-allow
        run: |
          npm install -g foo  # security-guard: allow
""",
    )
    failures = module.scan_workflow(workflow_path)
    assert all("disallowed installer pattern" not in failure for failure in failures), failures
