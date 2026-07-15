# Quest Journal: Source-repository Python formatting

- Quest ID: `source-python-formatting_2026-07-14__1723`
- Slug: source-python-formatting
- Completed: 2026-07-15
- Mode: workflow
- Quality: Gold
- Celebration: [`celebrations/source-python-formatting_2026-07-15.md`](celebrations/source-python-formatting_2026-07-15.md)
- Outcome: Implement Workstream D — Source-repository Python formatting from `ideas/2026-07-11-quest-hardening.md`. Preconditions and workflow requirements: - Workstreams A, B, and C must each have a merged P...

## What Shipped

**Problem:** Quest's source repository does not declare a formatter dependency, provide mandatory contributor hook setup, or enforce Python formatting in CI. Current contributor instructions install a recommended symlink in `.git/hooks`; changing the installed validator to add Black would leak so...

## Files Changed

- `.quest/source-python-formatting_2026-07-14__1723/phase_01_plan/plan.md`
- `.quest/source-python-formatting_2026-07-14__1723/phase_01_plan/arbiter_verdict.md.next`
- `.quest/source-python-formatting_2026-07-14__1723/phase_01_plan/review_findings.json.next`
- `.quest/source-python-formatting_2026-07-14__1723/phase_01_plan/review_plan-reviewer-a.md`
- `.quest/source-python-formatting_2026-07-14__1723/phase_01_plan/review_plan-reviewer-b.md`
- `.quest/source-python-formatting_2026-07-14__1723/phase_02_implementation/pr_description.md`
- `.quest/source-python-formatting_2026-07-14__1723/phase_02_implementation/builder_feedback_discussion.md`
- `.quest/source-python-formatting_2026-07-14__1723/phase_03_review/review_code-reviewer-a.md`
- `.quest/source-python-formatting_2026-07-14__1723/phase_03_review/review_findings_code-reviewer-a.json`
- `.quest/source-python-formatting_2026-07-14__1723/phase_03_review/review_code-reviewer-b.md`
- `.quest/source-python-formatting_2026-07-14__1723/phase_03_review/review_findings_code-reviewer-b.json`
- `.quest/source-python-formatting_2026-07-14__1723/phase_03_review/review_arbiter_verdict.md.next`
- `.quest/source-python-formatting_2026-07-14__1723/phase_03_review/review_findings.json.next`

## Iterations

- Plan iterations: 2
- Fix iterations: 0

## Agents

- **The Judge** (arbiter):
- **The Implementer** (builder):

## Quest Brief

Implement Workstream D — Source-repository Python formatting from
`ideas/2026-07-11-quest-hardening.md`.

Preconditions and workflow requirements:

- Workstreams A, B, and C must each have a merged PR.
- Start from updated `main` containing PRs #149, #150, and #152.
- Their roadmap rows must be `[done]` with PR links.
- Use an isolated worktree.
- Do not modify Candid Talent Edge.
- Follow the complete full Quest workflow and approval gates: routing, plan,
  dual plan review, arbiter, presentation and explicit approval,
  implementation, dual code review, fixes, validation, commit approval, push
  approval, draft PR creation, and lifecycle/archive follow-up.

Intent and policy correction:

- Python formatting is mandatory policy for the Quest source repository. It
  must never be installed into or enforced in consumer repositories.
- Correct Workstream D roadmap language during implementation: do not describe
  the Quest source hook as optional or recommended.
- Quest contributors must configure this repository with
  `git config core.hooksPath .githooks`.
- Git cannot propagate `core.hooksPath` automatically through a clone, so
  document it as required contributor setup and configure it in the isolated
  worktree for validation.
- CI is the authoritative, non-bypassable formatting gate.

Implementation scope:

- Add a pinned Black development dependency for the Quest source repository.
- Add Black configuration to `pyproject.toml`.
- Format the Quest source Python files with that configuration.
- Update `.github/workflows/test-python.yml` to install the pinned Black version
  and run `python3 -m black --check .`.
- Add an executable, versioned `.githooks/pre-commit` for the Quest source
  repository.
- Update `CONTRIBUTING.md` so configuring `core.hooksPath` to `.githooks` is
  required Quest contributor setup, replacing the current recommended
  source-repository hook instructions.

Hook behavior:

- The hook is check-only and never rewrites files during `git commit`.
- It runs the existing Quest configuration validation and then
  `python3 -m black --check .`.
- Preserve the source repository's existing configuration-validation
  protection when moving contributors from `.git/hooks` to `.githooks`.
- If Black is missing or formatting fails, print clear remediation commands for
  installing the pinned development dependency and running
  `python3 -m black .`.
- Handle invocation from subdirectories by resolving the repository root.
- Keep the implementation small and shell-portable.

Critical ownership boundary:

- `.githooks`, `pyproject.toml`, `CONTRIBUTING.md`, source-only dependency
  files, and `.github` workflows remain outside `.quest-manifest` and
  `.quest-checksums` ownership.
- Do not modify `scripts/quest_validate-quest-config.sh` hook installation
  behavior; it is part of the installed consumer surface.
- Do not add Black, formatting hooks, contributor policy, or source CI files to
  the Quest installer.
- Do not create or modify consumer-repository hooks.
- Validate an installed consumer topology, not only the Quest source checkout.

Focused tests:

- Assert the source hook exists, is executable, runs existing Quest validation,
  and invokes Black in check mode.
- Assert the hook contains no automatic Black formatting command.
- Assert its failure output gives the exact remediation command.
- Assert CI installs a pinned Black version and runs Black check mode.
- Assert `.githooks`, the source formatter dependency/configuration,
  `CONTRIBUTING.md`, and source CI remain outside `.quest-manifest` and checksum
  ownership.
- Build a temporary installed-consumer fixture and prove it receives no
  `.githooks` directory, Black dependency, formatter configuration, or
  formatting policy.
- Avoid brittle whole-file workflow or shell-script snapshots.

Manual validation:

- In a disposable Quest source clone or temporary worktree, configure
  `git config core.hooksPath .githooks`.
- Introduce an intentionally unformatted Python file and attempt a commit.
- Confirm the hook blocks the commit without modifying the file and prints the
  remediation command.
- Run `python3 -m black .`, retry, and confirm the hook passes.
- Confirm the existing Quest configuration validation still runs through the
  same hook.
- Install Quest into a clean temporary consumer repository and confirm no
  source formatting tooling or hook is installed.

Required validation:

- `python3 -m black --check .`
- `pytest -q` focused source-formatting and manifest/install-surface tests
- `python3 -m pytest tests/ -q`
- `bash tests/test-quest-runtime.sh`
- `bash tests/test-quest-preflight.sh`
- `bash tests/test-validate-quest-state.sh`
- `bash scripts/quest_validate-manifest.sh --strict`
- `bash scripts/quest_validate-quest-config.sh`
- `bash scripts/quest_validate-handoff-contracts.sh`
- `git diff --check`
- The repository's remaining formatting, lint, and security gates

Plan lifecycle and PR acceptance:

- Before implementation, change Workstream D from `[todo]` to `[ongoing]`.
- Do not alter completed A, B, or C PR records.
- Create the complete Workstream D draft PR.
- Once the PR exists, change D to `[done]` and record its PR number/link.
- Because A through D will then all be `[done]`, move the roadmap to
  `ideas/archive/2026-07-11-quest-hardening.md`.
- Update `ideas/README.md` by removing the active entry and adding a done-index
  entry linking the archived roadmap and PRs #149, #150, #152, and the new D PR.
- Commit and push the lifecycle/archive update to the same Workstream D PR.
- `[done]` means the PR exists; readiness and merge remain tracked on GitHub.
- Acceptance requires the A-through-D roadmap to be marked done and archived in
  the resulting PR.

Keep the change source-repository-only and minimal under KISS and YAGNI. Do not
introduce a formatting framework beyond Black, a small repository hook, the
required contributor setup, CI enforcement, and focused ownership tests.

## Carry-Over Findings

- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.

## Celebration

This journal embeds the celebration payload used by `/celebrate`.

- Full celebration: [`celebrations/source-python-formatting_2026-07-15.md`](celebrations/source-python-formatting_2026-07-15.md)
- [Jump to Celebration Data](#celebration-data)
- Replay locally: `/celebrate docs/quest-journal/source-python-formatting_2026-07-15.md`

## Celebration Data

<!-- celebration-data-start -->
```json
{
  "quest_mode": "workflow",
  "agents": [
    {
      "name": "arbiter",
      "model": "",
      "role": "The Judge",
      "transport": "background-agent"
    },
    {
      "name": "builder",
      "model": "",
      "role": "The Implementer"
    }
  ],
  "claude_transport_counts": {
    "background-agent": 8
  },
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
      "label": "Fix iterations: 0"
    },
    {
      "icon": "📝",
      "label": "Review rounds: 5"
    },
    {
      "icon": "🚌",
      "label": "Claude transport: background-agent ×8"
    }
  ],
  "quality": {
    "tier": "Gold",
    "grade": "G"
  },
  "inherited_findings_used": {
    "count": 0,
    "summaries": []
  },
  "findings_left_for_future_quests": {
    "count": 0,
    "summaries": []
  },
  "test_count": null,
  "tests_added": null,
  "files_changed": 13
}
```
<!-- celebration-data-end -->
