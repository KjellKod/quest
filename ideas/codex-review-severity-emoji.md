# Add severity color emoji to codex-review inline comments

Prepend colored circle emoji to each inline PR review comment based on severity level for quick visual scanning.

Mapping:

- 🔴 critical
- 🟠 high
- 🟡 medium
- 🔵 low
- 🟢 praise

Small change — add a `SEVERITY_EMOJI` dict and prepend the emoji to the comment body before posting.
