---
title: Per-Quest Orchestration Override
purpose: Let each quest pick its own model assignments without changing the repo allowlist, by promoting the per-quest snapshot to authoritative and adding a confirm/override step during quest startup.
audience:
  - quest-users
  - quest-maintainers
scope: Quest startup (post-classification, pre-folder-creation) plus the source-of-truth for model dispatch during a quest.
status: proposed
date: 2026-05-18
related:
  - .skills/quest/SKILL.md
  - .skills/quest/delegation/workflow.md
  - .ai/allowlist.json
  - scripts/quest_preflight.sh
  - scripts/quest_startup_branch.py
origin:
  - PR #116 review feedback (Codex flagged that an all-Claude pin in `.ai/allowlist.json` was scoped per-quest but committed globally; would change repo defaults for every checkout)
---

# Per-Quest Orchestration Override

## Motivation

PR #116 surfaced a real friction:

- The user wanted **this one quest** to run all-Claude (no Codex).
- The only place to set that today is `.ai/allowlist.json` `models.*`, which is shared repo config.
- Editing the repo allowlist for one quest creates two problems: (1) the change rides into `main` if it gets committed, switching defaults for everyone; (2) if the user *doesn't* commit it, they have to remember to revert after the quest closes.

We already snapshot the allowlist into `.quest/<id>/logs/allowlist_snapshot.json` at quest startup (`SKILL.md` Step 3.7 step 8). That snapshot is informational today — workflow.md and role dispatch still read from `.ai/allowlist.json`. The snapshot is a record, not the source of truth.

This proposal flips that: **the snapshot becomes the source of truth for the active quest**, and a small confirm/override step at startup lets the user customize it per quest without touching the repo file.

## Proposal (user-stated design, restated)

After Step 2b (preflight) and Step 3 (route selection — solo/workflow) but before Quest Folder Creation:

1. Present the current orchestration (model per role, from `.ai/allowlist.json`).
2. Ask: do you want to customize model assignments for this quest?
3. If **yes** → collect overrides, validate against availability, write the resulting `models` block into the per-quest snapshot before folder creation finishes.
4. If **no** → copy the unmodified allowlist into the per-quest snapshot anyway.
5. From that point on, every role dispatch in `workflow.md` reads from the per-quest snapshot, not from `.ai/allowlist.json`. The repo file is consulted only as the default source at startup.

## Sketch of the user prompt

```
Quest orchestration for `<slug>` (full quest):

  planner           gpt-5.5
  plan-reviewer-a   claude
  plan-reviewer-b   gpt-5.5
  arbiter           claude
  builder           gpt-5.5
  code-reviewer-a   claude
  code-reviewer-b   gpt-5.5
  fixer             gpt-5.5

Customize for this quest only? [y/N]
```

If `y`, present a tight chooser (one role at a time, or a single line shorthand like `planner=claude, builder=claude, all-reviewers=claude`).

Any overrides are validated against the preflight result. If the user picks `codex` for a role but Codex MCP isn't available, reject the override with the same warning text the preflight already prints.

## Feasibility analysis

### Where today's allowlist is consulted

Spot check before writing this doc:
- `.skills/quest/SKILL.md` — Step 3.7 reads `quest_id_format`; the snapshot step is already there.
- `.skills/quest/delegation/workflow.md` — every role-invocation site reads `models.<role>` from "the allowlist" without specifying which file. Today that's `.ai/allowlist.json`.
- `scripts/quest_validate-quest-state.sh` — likely doesn't consult `models.*`, only artifact paths and phase transitions. Worth auditing.
- `.claude/hooks/enforce-allowlist.sh` — enforces `role_permissions` (file_write, bash). Independent of `models.*`. Doesn't need to change.

The dispatch surface is concentrated in `workflow.md`. Switching the read source is mechanically small: replace prose "read `models.<role>` from `.ai/allowlist.json`" with "read `models.<role>` from `.quest/<id>/logs/allowlist_snapshot.json`" everywhere it appears. That's an edit, not a refactor.

The agents themselves don't independently read the allowlist — they read what the orchestrator hands them. So the per-quest override is a routing-time choice, not an agent-time choice. That's the key simplifying property: only the orchestrator and `workflow.md` need to learn the new source-of-truth.

### Where the design interacts with other startup steps

| Step | Today | After this proposal |
|---|---|---|
| 2b Preflight | Reads `.ai/allowlist.json` to know which models are required (Codex MCP + Claude bridge availability). | Still uses `.ai/allowlist.json` as the *default* for preflight. Override step runs **after** preflight so the user can opt out of an unavailable model entirely — but if they pick a model that the preflight said is unavailable, we must re-validate. |
| 3 Route selection | Solo / full / manual. | Unchanged. |
| 3.5 Quest Folder Creation | Snapshots allowlist as record. | Snapshot becomes authoritative. Override-or-copy step happens here. |
| 3.7 Step 1.5 (workflow) | Reads `models.<role>` from `.ai/allowlist.json`. | Reads from `.quest/<id>/logs/allowlist_snapshot.json` (or a sibling `.quest/<id>/orchestration.json` if we want to keep the snapshot read-only as a historical record and edit a separate file). |

### Two storage-shape options

**Option A — overwrite the snapshot in place.** Use `.quest/<id>/logs/allowlist_snapshot.json` as the active config. Pro: one source of truth. Con: the snapshot is no longer a "what was the repo config at quest start" record — it's the chosen config. We lose the historical baseline unless we copy the original first.

**Option B — separate snapshot and active config.** Keep `.quest/<id>/logs/allowlist_snapshot.json` as the read-only record of the repo allowlist at quest start. Add `.quest/<id>/orchestration.json` with the active `models` block (and only that block). The orchestrator reads `orchestration.json`. The two files agree when the user didn't override; differ when they did. Pro: preserves both the baseline and the choice. Con: two files.

**Recommendation: Option B.** Cheap, explicit, and the journal/celebration can show both ("you started with X, ran with Y"). It also keeps the snapshot's existing semantics intact, avoiding a behavior change to a file other tooling may already read.

### Edge cases worth thinking through

- **Codex unavailable, user picks Codex for a role.** Reject and re-prompt with the preflight warning. Do not silently fall back.
- **Solo-mode override.** In solo mode, only Reviewer A + planner + builder + arbiter + fixer matter; reviewer B and code-reviewer B are skipped. The override chooser should grey-out (or omit) roles that won't run in this quest's mode.
- **Auto-approve gates.** If `auto_approve_phases.plan_refinement` is set (per repo policy), the chooser should still surface — overriding a model is a different decision than approving a plan iteration.
- **Resume.** When a user resumes a quest by ID (`/quest <id>`), they should NOT see the chooser. The chosen orchestration is locked at quest start.
- **Reading allowlist from agents.** Some role prompts pass a model name (e.g., `mcp__codex__codex(model: <models.plan-reviewer-b>)`). The orchestrator computes this string from the active config before invocation; agents don't read the file. No change to agent behavior.
- **Schema validation.** The chosen `models` block should be validated against the same schema the allowlist uses today. Reject typos like `claud` or `gpt-5.5.1` before they reach a role.

### Is it useful?

Yes. Concrete user value:

- **No more allowlist ping-pong.** The PR #116 friction (edit, run quest, forget to revert, ship to main, code reviewer catches it, revert) goes away.
- **Quest-level experimentation.** Try "all Claude" or "Codex builder + Claude reviewers" for one quest without affecting team defaults.
- **Captured intent.** The journal and celebration already read quest artifacts. With orchestration in the artifact, completion records show exactly which model played each role for that quest.
- **Smaller blast radius for risky configs.** A maintainer can dogfood an experimental model on a low-risk quest without forcing the same config on every quest started by every contributor that day.

### Is it feasible?

Yes, with a small caveat.

- **Mechanically small.** Snapshot file already exists; dispatch sites are concentrated in `workflow.md`; the UI is a single confirm-then-optional-edit prompt.
- **Caveat: prompt fatigue.** Every quest start gains one extra question. Mitigation: default to **N** (use repo allowlist). A single Enter keystroke skips. Resume invocations don't ask at all.
- **Caveat: rollout discipline.** Has to land *together* — the source-of-truth swap and the chooser must ship in one PR. If we ship the swap without the chooser, every quest reads the snapshot but has no way to differ from the repo file (no value gained). If we ship the chooser without the swap, the chooser is decoration.

### Honest counter-position

If we squint hard: does this feature pull its weight?

- A team that wants different models per quest **already** has a path — edit `.ai/allowlist.json`, run the quest, revert. That works. It's friction, not a blocker.
- A startup chooser adds a question to every quest. Even with a default-skip, users will read it once or twice and then automate-tab past it.
- The PR #116 friction is real but rare — only when somebody wants a non-default config for one quest. Most quests will use the default.

But the savings *when* this matters (mis-shipped allowlist edits affecting team defaults, like the one Codex caught in PR #116) are large. One incident every few months still beats a one-keystroke prompt at every quest start. **Net: ship it, but make the default extremely cheap to confirm.**

## Implementation plan (recommended)

### Phase 1 — Source-of-truth swap + minimal chooser (one quest)

1. **Storage:** introduce `.quest/<id>/orchestration.json` with shape:
   ```json
   {
     "version": 1,
     "models": {
       "planner": "...",
       "plan-reviewer-a": "...",
       "plan-reviewer-b": "...",
       "arbiter": "...",
       "builder": "...",
       "code-reviewer-a": "...",
       "code-reviewer-b": "...",
       "fixer": "..."
     },
     "source": "default | overridden",
     "overridden_roles": [],
     "preflight_validated_at": "<ISO8601>"
   }
   ```
2. **Startup chooser:** add a new SKILL.md sub-step between "After route selection" and Quest Folder Creation that:
   - Displays the active `models` block (from `.ai/allowlist.json`).
   - Greys/omits roles unused in this quest mode.
   - Prompts `Customize for this quest only? [y/N]` (default N).
   - On N, writes `orchestration.json` with `source: "default"` and the unmodified block.
   - On Y, presents a short chooser. Validates each override against the preflight cache. Writes `orchestration.json` with `source: "overridden"` and `overridden_roles` populated.
3. **Dispatch swap:** rewrite every `workflow.md` reference to "read `models.<role>` from the allowlist" to "read `models.<role>` from `.quest/<id>/orchestration.json`". Cross-reference test asserts no remaining reads of `.ai/allowlist.json` `models.*` inside `workflow.md`.
4. **Validate-quest-state additions:** assert `orchestration.json` exists for every phase transition. Reject if `models.<active role>` is unset or invalid.
5. **Resume:** detect `orchestration.json`'s presence in `state.json`-adjacent files; never re-prompt on resume.
6. **Tests:**
   - Unit: chooser writes the snapshot correctly; defaults pass through; overrides validate; invalid model name rejected.
   - Unit: `validate-quest-state.sh` rejects missing `orchestration.json` at every phase.
   - Integration: workflow text references `orchestration.json` not `.ai/allowlist.json`.
   - Smoke: resume does not re-prompt.
7. **Docs:** SKILL.md, AGENTS.md, and the chooser help text.

### Phase 2 (optional, follow-up)

- Quick presets: `--orchestration claude-only`, `--orchestration codex-only`, `--orchestration mixed-defaults`.
- Per-user last-choice memory across quests (opt-in).
- Display the chosen orchestration in the celebration ("Cast roster" line).

## Open questions

1. **Confirm vs. silent.** Should the chooser run on every quest, or only when `.ai/allowlist.json` `models.*` has been touched recently (e.g., uncommitted change detected)? A "silent if defaults are clean" mode might cut prompt fatigue further. Risk: users don't realize they can override.
2. **One file or two?** Option B (separate `orchestration.json`) is recommended above but the simpler Option A (in-place snapshot) is defensible. Decision should be made before implementation.
3. **Schema location.** Does the `models` block deserve its own JSON schema in `.ai/schemas/orchestration.schema.json`, or do we share the existing allowlist schema and pin only the `models` subtree?
4. **Codex-led sessions.** When the orchestrator is Codex (not Claude), the chooser runs in the Codex runtime. The prompt experience may differ. Worth a spike before formalizing.

## Recommended quest prompt (when ready)

```text
/quest "Implement per-quest orchestration override.

Reference: ideas/2026-05-18-per-quest-orchestration-override.md

DELIVERABLES

1. Storage
   - Add `.quest/<id>/orchestration.json` writer to Quest Folder Creation.
   - Schema: { version, models, source, overridden_roles, preflight_validated_at }.

2. Startup chooser
   - New SKILL.md sub-step after route selection. Defaults to no-customization.
   - On customize=yes, validates each override against preflight availability.
   - Resume detects existing orchestration.json and never re-prompts.

3. Source-of-truth swap
   - Every workflow.md role-dispatch site reads from
     .quest/<id>/orchestration.json, not .ai/allowlist.json.
   - Contract test: no models.<role> reads of .ai/allowlist.json inside
     workflow.md after this change.

4. Validate-quest-state additions
   - Assert orchestration.json exists at every phase transition.
   - Reject if any required role's model is unset or invalid.

5. Tests
   - Chooser writes correct artifact for default and override paths.
   - Override validation rejects unavailable models with preflight reason.
   - Resume does not re-prompt.
   - Workflow text reads only from orchestration.json for models.*.

OUT OF SCOPE
- Per-user persistent preferences.
- Preset templates (claude-only / codex-only).
- Schema split into a dedicated orchestration schema.
- Changes to role_permissions or quest_completion sections of allowlist.

KILL CRITERIA
- Prompt fatigue evidence (users habitually accept without reading).
- Chooser raises false-positive validation errors for valid model names.
- workflow.md dispatch still reads .ai/allowlist.json for any role."
```
