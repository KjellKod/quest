# Public repo hardening — quest (drafted 2026-06-01)

## Why

very GitHub Actions reference should be pinned to a
full-length commit SHA rather than a floating tag. A tag like `@v6` can be silently
repointed by an upstream (or a compromised upstream) to malicious code; a 40-char SHA
cannot. The sibling repo **sketch2md** already completed this pass (all 18 of its
`uses:` are SHA-pinned with `# vX.Y.Z` comments) and is the model to copy here.

## Current state

All Actions in `.github/workflows/*` are **tag-pinned**, not SHA-pinned:

- `actions/checkout@v6`
- `actions/setup-python@v6`
- `actions/upload-pages-artifact@v5`
- `actions/deploy-pages@v5`
- `actions/github-script@v9`

Spread across these workflow files:

- `codex-ci-review.yml`
- `deploy-dashboard.yml`
- `pr-body-gate.yml`
- `security.yml`
- `test-python.yml`
- `validate-quest-config.yml`

All are first-party `actions/*` (no third-party actions), so realistic risk is low —
but tag-repointing is still possible, so SHA-pinning closes it. Because everything is
tag-pinned, the "Require actions to be pinned to a full-length commit SHA" repo setting
is **NOT safe to enable yet**: turning it on now would break ALL workflows.

## What to do

1. For each `uses:` tag, resolve the tag to its current commit SHA and rewrite it,
   keeping the version as a comment. For example:

   ```bash
   gh api repos/actions/checkout/git/ref/tags/v6 --jq .object.sha
   ```

   Then: `uses: actions/checkout@<40-char-sha> # v6`.
   Note: if the tag points to an annotated tag object, dereference it to the
   underlying commit before pinning.
2. Do this on a dedicated branch + PR, get CI green, then merge.
3. THEN enable Settings → Actions → General → "Require actions to be pinned to a
   full-length commit SHA".

## Watch out

- `deploy-dashboard.yml` drives the GitHub Pages deploy
  (`upload-pages-artifact` + `deploy-pages`). Give it a careful CI run before merge so
  the dashboard deploy still works after re-pinning.

## Related public-readiness settings (checklist, mirrors sketch2md Phase 6.1)

These are repo **Settings**, applied at/around the public flip — NOT code changes.
Documentation/checklist only here:

- [ ] Require approval for first-time contributor Actions runs (only appears once the
      repo is public).
- [ ] Default `GITHUB_TOKEN` permissions = read-only.
- [ ] No fork-PR access to secrets.
- [ ] Protect `main` with required CI status checks.

---

Drafted idea — not yet scheduled. Precedent: sketch2md PR #27 / its Phase 6.1.
