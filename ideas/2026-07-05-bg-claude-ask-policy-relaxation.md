# Ask-Policy Relaxation for Background Claude Roles

Date: 2026-07-05
Status: `proposed`
Predecessor: `ideas/archive/quest-needs-human-resume-relay.md` — items 0–6
(the full same-session relay) shipped in PR #142; this document carries the
one unresolved item (item 7).

## The situation

The relay machinery is fully built and tested (PR #142): a background Claude
role that writes a `needs_human` handoff parks its session, the question
reaches the human, the answer resumes the SAME conversation
(`quest_claude_runner.py --resume`), the parked id persists and chains through
`quest_state.py --parked-bg-session`, and lifecycle guards protect the parked
session from every sweep. The pipe exists; the faucet is still labeled
"don't use."

Quest role instructions bias hard against entering the relay: agent files and
prompt contracts say "make explicit assumptions and proceed," and the bg
runner's completion-protocol text permits asking only when the agent
"genuinely cannot proceed." Nothing deliberately defines when a background
Claude role SHOULD ask.

## Proposal

1. **Define the asking criteria** (the policy decision — needs the human's
   sign-off). Proposed starting set — a bg Claude role writes `needs_human`
   when, and only when:
   - the ambiguity is destructive or hard to reverse (deleting/overwriting
     user data, force-pushes, schema drops);
   - the choice involves accounts, credentials, billing, or external
     publication;
   - it is a genuine product/design decision the brief and plan do not answer
     and both options are expensive to redo.
   Everything else stays "make explicit assumptions and document them."
2. **Write the scoped permission into the Claude role agent files**
   (`.skills/quest/agents/planner.md`, `builder.md`, `fixer.md`, reviewers as
   applicable), with the criteria above verbatim. Codex roles stay strictly
   non-interactive (unchanged contract).
3. **Pin it**: a dispatch-guardrails assertion that the agent files carry the
   scoped ask-policy text, so it cannot silently regress to blanket
   "never ask."
4. **Watch the measurement gate** (inherited from the predecessor):
   `quest_complete.py` prints the needs_human rollup across
   `.quest/archive/*/logs/` (baseline at relaxation time: 0 occurrences in 1
   status-instrumented quest of 57 archived). After relaxation, the rollup
   answers whether roles ask usefully or over-ask; the 3-question cap in the
   workflow relay loop bounds the damage of an over-asker either way.

## Why deferred out of PR #142

How chatty agents may be with the human's time is a taste/policy call, not a
correctness fix — it deserved its own decision rather than riding into a
hardening PR. The mechanism shipped; this is the switch.
