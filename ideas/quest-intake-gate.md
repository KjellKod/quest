# Quest Intake Gate + Progressive Exploration Budget

## What
Make `/quest` reliably:

1. Ask **2–3 targeted clarifying questions** when the initial input is thin (and **block planning** until answered).
2. Stay **thorough by default** while avoiding “wandering repo exploration” via **progressive, timeboxed** discovery and **caching**.

## Why
Current behavior can diverge from the intended spec:

- The spec/docs claim “thin input → Quest asks clarifying questions first” (e.g. `README.md`, `docs/guides/quest_analysis.md`), but in practice the orchestrator can proceed directly to planning without asking.
- Repo exploration can dominate early latency. Some exploration is good, but repeated “inventory-style” scanning is wasted work and increases variance.

Root cause: Quest is largely **instruction-driven** (Claude Code skill + role docs). The only hard “ask the human” loop that’s consistently modeled is the **handoff Q&A** pattern (`STATUS: needs_human`), but intake questions are not currently enforced by **state + artifacts + a strict output contract**.

## Approach

### A) Enforce intake as a real gate (state + artifacts + contract)
Add an explicit, resumable intake stage that must complete before planning:

- **State**
  - Extend `.quest/<id>/state.json` to include a phase like `intake` (or `intake_questions`), and a `status` that can be `blocked` until answers arrive.
  - Update routing so `/quest <id>` resumes into intake when unanswered questions exist.

- **Artifacts**
  - Create `.quest/<id>/phase_00_intake/` with:
    - `intake_handoff.json` (structured “quest_agent handoff”)
    - `intake_answers.md` (creator answers, append-only)
    - Optional: `intake_notes.md` (assumptions/decision log)

- **Contract**
  - Make the Quest Agent speak the same “handoff language” as other roles (see `.ai/schemas/handoff.schema.json`):
    - On thin input: `status: needs_human` with a **`questions[]` array** (IDs + blocking=true).
    - On rich input: `status: complete` with `artifacts_written` including the quest brief.
  - This turns “ask questions” from a suggestion into the **only allowed output shape** for thin input.

Implementation touchpoints (future changes):
- `.ai/roles/quest_agent.md` (expand output contract to support multiple questions and `needs_human`)
- `.skills/quest/SKILL.md` Step 1 (treat intake Q&A as a gate, write intake artifacts, set state accordingly)
- Optionally extend `.ai/schemas/handoff.schema.json` to allow/encode intake metadata (input quality, assumptions).

### B) Thin vs rich classification (deterministic + explainable)
Use a simple, explainable rubric (not “magic”):

- **Thin** signals (any 2 is enough to trigger Q&A):
  - Very short prompt (e.g. < ~15 words)
  - No file paths / no referenced doc / no ticket
  - No definition of done (no acceptance criteria, no “should/when/verify”)
  - No stated scope (“where in the app/codebase”)

- **Rich** signals:
  - At least two of: intent/why, scope boundaries, constraints, acceptance criteria, referenced doc/ticket.

Store the classification result in `phase_00_intake/intake_handoff.json` so it’s auditable.

### C) Question picker (2 by default; 3 only when needed)
Make question selection predictable:

- Default to **Acceptance Criteria + Scope** (fastest to unblock planning).
- Ask a third only if risk is high without it (unclear intent, likely constraints, or tricky edge cases).

Example mappings:
- “add dark mode” → ask (1) ACs (where/toggle/persistence) (2) scope (which screens/components).
- “fix login bug” → ask (1) repro steps + expected behavior (2) acceptance criteria (test expectations), and maybe (3) environment constraints if relevant.

### D) Fast intake override (speed when the user wants it)
Support an explicit “go fast” mode without making it the default:

- Accept `/quest --fast ...` (or equivalent “fast/just run with it” phrasing).
- In fast mode:
  - Ask **0–1** question (only if absolutely necessary), then proceed.
  - Record assumptions explicitly in the quest brief (so reviews have a spec to enforce).

This aligns with keeping Quest opinionated and thorough by default, while letting experienced users opt out of friction.

### E) Progressive exploration budget + caching (reduce wasted scans)
Target the main sources of exploration latency:

- **Planner exploration is explicitly required today** (`.ai/roles/planner_agent.md` says “Explore the codebase…”). Keep it, but make it **targeted** and **repeatable**:
  - Generate a one-time per-quest `repo_overview.md` (or `repo_map.md`) early (after intake), then reuse it across plan iterations.
  - Timebox discovery: prefer top-level `ls` + a few targeted `rg` searches over directory-by-directory browsing.

- Improve “starting context” so agents don’t need to rediscover basics:
  - Expand `.ai/context_digest.md` to include the actual repo’s key directories, entry points, and “how to run tests”.

### F) Acceptance criteria (behavioral)
1. Thin input triggers **at least 2** clarifying questions and does **not** run planning until answered.
2. Rich input triggers **at most 1** “last call” question (optional) and proceeds.
3. `--fast` mode proceeds with explicit assumptions and minimal/no questions.
4. Resume (`/quest <id>`) reliably continues from intake without losing pending questions/answers.
5. Planner iterations reuse cached `repo_overview.md` and avoid repeating broad repo scans.

## Status
idea

