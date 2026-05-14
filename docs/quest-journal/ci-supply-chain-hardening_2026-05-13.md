# Quest Journal: CI/CD Supply-Chain Hardening

- Quest ID: `ci-supply-chain-hardening_2026-05-12__2109`
- Slug: ci-supply-chain-hardening
- Completed: 2026-05-13
- Mode: workflow
- Quality: Silver
- Celebration: [`celebrations/ci-supply-chain-hardening_2026-05-13.md`](celebrations/ci-supply-chain-hardening_2026-05-13.md)
- Outcome: Planned YAML for `.github/workflows/security.yml` (`workflow-guard` job): ```yaml workflow-guard: runs-on: ubuntu-latest steps: - name: Checkout repository uses: actions/checkout@v4

## What Shipped

Planned YAML for `.github/workflows/security.yml` (`workflow-guard` job):
```yaml
  workflow-guard:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

## Files Changed

- `/Users/kjell/ws/extra/worktrees/quest-ci-review-security/.quest/ci-supply-chain-hardening_2026-05-12__2109/phase_01_plan/plan.md`
- `/Users/kjell/ws/extra/worktrees/quest-ci-review-security/.quest/ci-supply-chain-hardening_2026-05-12__2109/phase_01_plan/handoff.json`
- `.quest/ci-supply-chain-hardening_2026-05-12__2109/phase_01_plan/arbiter_verdict.md`
- `.quest/ci-supply-chain-hardening_2026-05-12__2109/phase_01_plan/review_findings.json`
- `.quest/ci-supply-chain-hardening_2026-05-12__2109/phase_01_plan/review_backlog.json`
- `.quest/ci-supply-chain-hardening_2026-05-12__2109/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/ci-supply-chain-hardening_2026-05-12__2109/phase_01_plan/review_plan-reviewer-b.md`
- `/Users/kjell/ws/extra/worktrees/quest-ci-review-security/.quest/ci-supply-chain-hardening_2026-05-12__2109/phase_02_implementation/build_report.md`
- `.quest/ci-supply-chain-hardening_2026-05-12__2109/phase_03_review/review_code-reviewer-a.md`
- `.quest/ci-supply-chain-hardening_2026-05-12__2109/phase_03_review/review_findings_code-reviewer-a.json`
- `.quest/ci-supply-chain-hardening_2026-05-12__2109/phase_03_review/review_code-reviewer-b.md`
- `.quest/ci-supply-chain-hardening_2026-05-12__2109/phase_03_review/review_findings_code-reviewer-b.json`
- `.quest/ci-supply-chain-hardening_2026-05-12__2109/phase_03_review/review_fix_feedback_discussion.md`
- `.github/scripts/security_ci_guard.py`
- `tests/test_security_ci_guard.py`

## Iterations

- Plan iterations: 2
- Fix iterations: 2

## Agents

- **The Judge** (arbiter): 

## Quest Brief

CI/CD supply-chain hardening: remove the npm path, harden workflow permissions, and extend security_ci_guard.py so the patterns we just audited can't regress.

Context: this quest follows a CI/CD security review (branch quest-ci-review-security, off origin/main). The review confirmed the repo has no package.json / npm publish path; the only npm-registry footprint is `npm install -g ajv-cli` in validate-quest-config.yml, and that workflow has no explicit permissions block. The guard at .github/scripts/security_ci_guard.py catches pull_request_target+checkout but is silent on several adjacent patterns.

### Scope (code-only — repo settings changes are out of scope and will be done separately via `gh api`)

**1. Replace ajv-cli with check-jsonschema in `.github/workflows/validate-quest-config.yml`:**
- Remove `actions/setup-node@v4`, `Install jq`, and `npm install -g ajv-cli` steps.
- Remove the apt install of jq if no remaining step needs it (verify with grep before deleting).
- Add `actions/setup-python@v5` with `python-version: '3.12'`.
- Install check-jsonschema with a pinned version: `python3 -m pip install check-jsonschema==<latest-stable>` (planner picks current pin; record in plan).
- Replace the `ajv validate ...` step with: `check-jsonschema --schemafile .ai/schemas/allowlist.schema.json .ai/allowlist.json`
- Verify check-jsonschema supports JSON Schema draft 2020-12 against `.ai/schemas/allowlist.schema.json` (confirm in plan).
- Add top-level `permissions: contents: read` to the workflow.

**2. SHA-pin the third-party action in `.github/workflows/codex-ci-review.yml`:**
- Replace `openai/codex-action@v1` with `openai/codex-action@<full-40-char-sha>  # v1.x.y` where the SHA matches the latest v1 release.
- Add a brief comment with the version tag for future Dependabot review.
- Do NOT SHA-pin first-party `actions/*` in this quest.

**3. Extend `.github/scripts/security_ci_guard.py` with these rules (refactor to YAML-parsed structure before adding rules):**

a. **Refactor:** Parse each workflow with PyYAML into a structured dict; build a small typed view (triggers, top-level permissions, jobs, per-job permissions, steps with uses/run). Keep the public CLI surface (exit code, stdout format) backwards compatible.

b. **Rule:** Fail if any workflow uses `pull_request_target` at all, unless the file has a sentinel comment `# security-guard: allow pull_request_target` with rationale. (Today no workflow uses it; rule is preventative.)

c. **Rule:** Fail if any `uses:` references a third-party action (owner not in `{actions, github}`) without a 40-char SHA pin. Allow tag-pinned first-party actions for now.

d. **Rule:** Fail if any step `run:` in a PR-triggered workflow contains:
   - `npm install -g` or `npm i -g` without a version pin (`@<ver>`)
   - `npx ` without `--package @<ver>` or `@<ver>` in the package spec
   - `pip install` without `==`, `-r <file>`, or `--require-hashes`
   - `pipx install` without `==`
   - `curl ... | sh` or `curl ... | bash` (pipe-to-shell)
   
   Allow exact-line exceptions via `# security-guard: allow <reason>` comment on the same step. Whitelist the existing gitleaks versioned-URL line in `security.yml` via this mechanism.

e. **Rule:** Fail if any workflow triggered by `pull_request` has no top-level `permissions:` block. Defense in depth — repo default is `read`, but explicit is enforceable.

f. **Rule:** Fail if any workflow declares `id-token: write` outside an explicit allowlist (initially: `.github/workflows/deploy-dashboard.yml`). Allowlist lives at the top of the guard script.

**4. Add `.github/dependabot.yml` watching the github-actions ecosystem:**
- Weekly schedule on Mondays.
- Target branch: main.
- Group: all github-actions updates into a single PR per week.
- `open-pull-requests-limit: 5`.
- Do NOT add the `npm` ecosystem (repo has no package.json after step 1).

**5. Add `.github/workflows/codex-version-drift.yml` as a tracking-only signal for the Codex CLI npm package.**

**PLANNER MUST FIRST DECIDE** whether this workflow is duplicative of the SHA pin on `openai/codex-action@<sha>`:
- WebFetch `action.yml` / README at `github.com/openai/codex-action` to determine whether the action self-bundles `@openai/codex` or fetches it at runtime.
- If self-bundled: SKIP this workflow entirely and document why in the plan. The github-actions Dependabot watch covers drift.
- If runtime-fetched (or ambiguous): proceed with the workflow.

If proceeding:
- Triggers: `schedule: cron: '0 12 * * 1'` (Monday noon UTC) plus `workflow_dispatch`.
- Top-level permissions: `contents: read, issues: write`.
- Add a checked-in `.github/codex-cli-version.txt` seeded at quest build time with the current `npm view @openai/codex version` output.
- Workflow steps:
  a. Checkout (`actions/checkout@<sha>` or tag — first-party, tag OK for now).
  b. `npm view @openai/codex version` → write to `/tmp/latest_version`.
  c. Read `.github/codex-cli-version.txt` → `/tmp/pinned_version`.
  d. If they differ: use `gh issue list --search "in:title [codex-drift]"` to find an existing tracking issue with a deterministic title like `[codex-drift] Codex CLI drift: <pinned> → <latest>`. If found, update body via `gh issue edit`. If not found, create with `gh issue create`. Idempotent.
  e. If versions match: no-op (exit 0).
- No version pinning is added to codex-ci-review.yml. Watcher, not enforcer.
- Verify guard rule 3d does not false-positive on `npm view` (metadata-only, no install). Add unit test covering that case.

### Acceptance Criteria

- `validate-quest-config.yml` has no `npm`, `node`, or `ajv` references.
- `python3 -m pytest tests/test_security_ci_guard.py -v` passes locally and in CI.
- `python3 .github/scripts/security_ci_guard.py` exits 0 against current workflows after sentinels added.
- All required status checks (`validate`, `secret-scan`, `workflow-guard`, `test`, `pr-body-gate`) still pass on the PR.
- `codex-ci-review.yml` still triggers on author=KjellKod same-repo PRs.

### Out of Scope (separate work, do NOT include in this quest)

- Repo settings changes: Actions allowlist, `sha_pinning_required` toggle, fork-PR approval policy, legacy `allow_force_pushes` flip.
- Gitleaks checksum verification.
- SHA-pinning of first-party `actions/*`.
- Switching the AI review step's checkout strategy.
- Watching `npm` or `pip` ecosystems in Dependabot.
- Pinning the codex CLI version in `codex-ci-review.yml` itself.

### Notes for the Planner

- **Pin choice for check-jsonschema:** pick the latest stable release as of plan time; record exact version in plan and quote PyPI URL in PR description.
- **Pin choice for openai/codex-action:** resolve `v1` tag at plan time via `gh api repos/openai/codex-action/git/ref/tags/v1` (or matching `git/refs/tags`) and use the dereferenced commit SHA. Record both SHA and human version.
- **Commit ordering:** ship the guard YAML-parsing refactor as the first commit so subsequent rule commits are reviewable diffs against structured code.

### Workspace

This quest runs in the existing worktree at `/Users/kjell/ws/extra/worktrees/quest-ci-review-security` on branch `quest-ci-review-security`, created from `origin/main` @ `45b4ab7`.

## Findings Left For Future Quests

- Count: **1**
- Codex drift issue selection can update the wrong open issue when multiple `[codex-drift]` issues exist.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- Full celebration: [`celebrations/ci-supply-chain-hardening_2026-05-13.md`](celebrations/ci-supply-chain-hardening_2026-05-13.md)
- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/ci-supply-chain-hardening_2026-05-13.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "workflow",
  "agents": [
    {
      "name": "arbiter",
      "model": "",
      "role": "The Judge"
    }
  ],
  "achievements": [
    {
      "icon": "[BUG]",
      "title": "Gremlin Slayer",
      "desc": "Tackled 13 review findings"
    },
    {
      "icon": "[TEST]",
      "title": "Battle Tested",
      "desc": "Survived 5 reviews"
    },
    {
      "icon": "[PLAN]",
      "title": "Plan Perfectionist",
      "desc": "Iterated plan 2 times"
    },
    {
      "icon": "[WIN]",
      "title": "Quest Complete",
      "desc": "All phases finished successfully"
    }
  ],
  "metrics": [
    {
      "icon": "📊",
      "label": "Plan iterations: 2"
    },
    {
      "icon": "🔧",
      "label": "Fix iterations: 2"
    },
    {
      "icon": "📝",
      "label": "Review findings: 5"
    }
  ],
  "quality": {
    "tier": "Silver",
    "grade": "S"
  },
  "inherited_findings_used": {
    "count": 0,
    "summaries": []
  },
  "findings_left_for_future_quests": {
    "count": 1,
    "summaries": [
      "Codex drift issue selection can update the wrong open issue when multiple `[codex-drift]` issues exist."
    ]
  },
  "test_count": null,
  "tests_added": null,
  "files_changed": 15
}
```
<!-- celebration-data-end -->
