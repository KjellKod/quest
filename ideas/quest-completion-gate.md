# Quest Completion Gate: When Is a Quest Really Done?

## What

Decide whether Quest needs an explicit completion gate, and if so, what triggers it.

## Context

Today, a quest is marked `complete` when code reviews pass (Step 7). The human approved the plan before build, and reviewers approved the code after build. But there's a gap between "reviews passed" and "this is actually done" — the hardening phase happens outside the quest lifecycle.

In practice, the human workflow is front-loaded and back-loaded:
- **Planning:** Review the plan, read arbiter trade-offs, sometimes override.
- **Build/review:** Runs largely on its own.
- **Hardening:** Validate the MVP, understand how the plan was realized, spot improvements. This is where v2 ideas and small adjustments come from.

The question: should the quest stay open during hardening, or is "reviews passed" the right completion point?

## Options

### Option A: Current behavior (quest closes at review approval)

**Pro:**
- Clean lifecycle: plan → build → review → done.
- Hardening is a separate concern. A v2 quest captures follow-up work with its own plan and review cycle.
- No ambiguous "open but not really active" state.
- The quest fulfilled its acceptance criteria — that's what "done" means.

**Con:**
- Journal entry and archive happen before hardening insights exist. The journal captures what was planned and built, not what was learned.
- No formal link between the quest and its hardening/v2 follow-up.

### Option B: Quest closes when the PR is merged

**Pro:**
- Natural completion signal — the work is in main, it shipped.
- Hardening happens between "reviews passed" and "PR merged," so insights feed back before the quest closes.
- The journal entry captures a more complete picture.
- PR merge is an observable event (GitHub webhook, `gh pr view --json state`).

**Con:**
- Quest stays in limbo if the PR sits unmerged. The `.quest/` dir stays in root instead of archive.
- Couples Quest to GitHub (currently Quest is git-aware but not GitHub-dependent).
- What if there's no PR? (manual commits, or work committed directly to main.)
- Adds a new state (`merged`? `shipped`?) to an already-sufficient state machine.

### Option C: Soft close + hardening tag

**Pro:**
- Quest marks `complete` at review approval (current behavior).
- A new optional `hardening` tag or journal annotation links follow-up work back to the original quest.
- Journal entry gets updated when hardening finishes or v2 quest is created.
- No new gates, no new state — just better breadcrumbs.

**Con:**
- Relies on discipline to add the annotation (same "trust the process" gap Quest tries to close).
- Could be over-engineering for something that works fine informally.

## Recommendation

Lean toward **Option A** (current behavior) with elements of **Option C** (better breadcrumbs). The quest lifecycle is clean and well-defined. Hardening is valuable but it's a different activity — it deserves its own quest if it produces changes, or a journal annotation if it's just validation.

The PR-merge trigger (Option B) is appealing but introduces coupling and edge cases that don't justify the benefit.

## Status

idea
