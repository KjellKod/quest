# Consumer CI ownership — issue #185

Status: Complete

## Acceptance criteria

- Fresh installs omit the CI reviewer; generic review skills remain installed.
- Current-installer upgrades preserve legacy CI files and sidecars exactly,
  release the reviewer's checksum ownership, and leave it alone on later runs.
- Interactive, unattended, forced, and preview paths preserve consumer policy.
- Source validation permits the source-only reviewer but forbids distributing
  it or `.github` entries; unrelated framework validation and cleanup remain.

## Steps

- [x] Preservation regressions — done. Reused the full installer network
  fixture and PTY harness. Manifest, strict-validation, and pristine-copy
  tests failed before the fix without changing test expectations afterward.
- [x] Distribution and cleanup — done. Exact-path ownership release and
  literal strict-validation exclusion; no consumer migration or new flags.
- [x] Documentation and verification — done. Setup/ownership guidance,
  120 Python tests, 72 shell runtime tests, strict manifest validation,
  shell syntax checks, Black, and whitespace checks passed.

## Decisions and review

- Existing CI reviewer files become consumer-owned without edits, deletion,
  replacement, or sidecar cleanup. Keep the source copy for Quest-local use.
- Current installer is required: accept self-update or download it. User
  explicitly excluded old-installer compatibility work from this change.
- Codex self-review and Claude independent plan review identified stale-file
  deletion and strict-validation hazards. Retain interactive/sentinel/repeat
  upgrade tests as issue acceptance coverage despite Claude's matrix concern.
- Consumer prompts and validators define CI policy; generic prose is optional
  guidance. This is documented precedence, not a new executable policy engine.
- Issue #184 remains separate. No consumer repository changes are authorized.

## Risks and validation

- Legacy pristine-file deletion: real installer transition regressions.
- Validator accidentally reclaiming the skill: exact-path and sibling tests.
- Continued policy coupling: documented consumer-owned surfaces and byte-level
  preservation checks, without tests requiring matching policy prose.

The temporary-consumer preview, interactive upgrade, checksum release, and
subsequent upgrade scenarios are automated with the real installer and PTY
harness; no live consumer repository was modified.

## Verification

- `python3 -m pytest tests/unit/test_quest_manifest.py tests/integration/test_consumer_ci_ownership.py -q`: 56 passed.
- `python3 -m pytest tests/integration/test_quest_effort_install.py tests/integration/test_codex_installed_distribution.py tests/unit/test_source_python_formatting.py -q`: 64 passed.
- `bash tests/test-quest-runtime.sh`: 72 passed.
- Strict manifest validation, `black --check .`, shell syntax, and
  `git diff --check` passed. Python commands used the local `.venv`.

## PR review follow-up

Cubic identified that protected snapshots omitted permission modes and that
the distributed catalog still advertised the source-only skill. Added failing
regressions, extended snapshots with `lstat().st_mode` for every protected path,
and removed the catalog entry. The source skill remains in the Quest repo.
