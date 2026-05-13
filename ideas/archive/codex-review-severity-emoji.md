# Add severity color emoji to codex-review inline comments

> Superseded by `ideas/2026-05-04-ci-review-allowlist-quality-roadmap.md`.
> Keep this file as historical source material; do not implement directly.

Prepend colored circle emoji to each inline PR review comment based on severity level for quick visual scanning.

Mapping:

- 🔴 critical
- 🟠 high
- 🟡 medium
- 🔵 low
- 🟢 praise

Small change — add a `SEVERITY_EMOJI` dict and prepend the emoji to the comment body before posting.
