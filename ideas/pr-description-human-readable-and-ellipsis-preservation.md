# Quest PR Body Standard: Human-Readable Summary + Ellipsis Preservation

## Problem
Quest-generated draft PR bodies are sometimes technically complete but inconsistent in readability and structure. On updates, bot-added Ellipsis sections may be accidentally overwritten if PR body updates are naive.

## Desired Outcome
All Quest-driven draft PRs should:
1. Lead with a concise, human-readable summary and actionable validation.
2. Preserve Ellipsis hidden add-ons exactly when present.
3. Keep human-authored content and bot-authored content clearly separated.

## Recommended Standard

### Human section (top)
Use a predictable reviewer-first layout:
- `## Summary` (what changed + why)
- `## Changes` (group by area/files)
- `## Validation` (command -> result)
- `## Notes` (risks/follow-ups)

### Bot section (bottom)
If Ellipsis markers exist, preserve the block exactly:
- Sentinel: `<!-- ELLIPSIS_HIDDEN -->`
- Keep everything from first sentinel to end unchanged during PR edits.
- Update only the human section above that sentinel block.

## Update Algorithm (safe)
1. Fetch current PR body.
2. Detect first `<!-- ELLIPSIS_HIDDEN -->` marker.
3. If found:
   - `human_part = body[0:marker_start]`
   - `bot_part = body[marker_start:end]`
   - regenerate only `human_part`
   - new body = `new_human_part + "\n\n" + bot_part`
4. If not found, update full body normally.

## Why This Improves Review Quality
- Reviewers quickly understand intent and risk without parsing full diff context.
- Validation is explicit and trustworthy.
- Bot-generated enhancement remains intact and continuously updated.

## Suggested Quest-Core Changes
- Add this behavior to `pr-assistant` skill as mandatory update rule.
- Add a small regression fixture: updating a PR body with Ellipsis markers must keep marker block byte-identical.
- In Quest completion flow, suggest using `pr-assistant` so this formatting is consistently applied.
