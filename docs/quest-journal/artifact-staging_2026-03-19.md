# Stage Artifacts Before Runtime Fallback

- PR: #74
- Merged: 2026-03-19
- Outcome: Artifact preparation is now explicit and happens before role execution, not during.

## What Shipped

- **Explicit artifact staging**: Quest prepares all required artifacts (brief, plan, reviews) in the workspace before dispatching a role, rather than assuming the role will find them.
- **Tighter runtime fallback**: Fallback retries no longer re-prepare artifacts -- they reuse what was already staged.
- **Workspace-local artifacts**: Artifacts stay within the quest workspace directory, keeping sandboxed runs self-contained.

## Why It Matters

Roles were sometimes failing because artifacts were not yet written when execution started. Making staging explicit eliminates that race condition and makes fallback retries cheaper and more predictable.
