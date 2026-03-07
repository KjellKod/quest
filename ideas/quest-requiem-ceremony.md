# Idea: Quest Requiem Ceremony

## Problem

When a quest is abandoned, it just... stops. No closure, no reflection. The celebration script marks completed quests with fanfare, but abandoned quests get nothing — even though they often produce real value (research, plans, lessons learned).

## Concept

A **requiem** — the counterpart to the celebration. But also a celebration in its own right: a celebration of *discovery*. Many paths we try lead to wisdom and better approaches in the future. We learn and get strengthened by the missteps. An abandoned quest isn't a failure — it's proof that we explored, questioned, and chose a better direction.

Same terminal animation dynamics (ASCII art, progressive reveal, metrics), reframed for reflection and discovery.

## Tone

- A celebration of learning, not of delivery
- Respectful and warm, not mournful
- Reflective — honoring the journey, not just the destination
- Acknowledges what was discovered and what made us stronger
- Brief — shorter than a completion celebration, but not dismissive

## Animation Structure

```
  ╔══════════════════════════════════════════════╗
  ║              QUEST REQUIEM                   ║
  ╚══════════════════════════════════════════════╝

  The quest rests here. Not every path leads forward.
  Some lead to wisdom.

  ┌─────────────────────────────────────────────┐
  │                                             │
  │          <quest slug>                       │
  │                                             │
  │     Born:      <created_at>                 │
  │     Rested:    <abandoned_at>               │
  │     Phase:     <last phase reached>         │
  │     Reached:   ██████░░░░░░░░░░  N%         │
  │                                             │
  └─────────────────────────────────────────────┘

  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄ EPITAPH ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄

  "<one-line summary from quest brief or abandon reason>"

  ┄┄┄┄┄┄┄┄┄┄┄┄ WHAT REMAINS ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄

  N artifacts preserved
  N agents contributed
  N plan iterations completed

  ┄┄┄┄┄┄┄┄┄┄┄ WHY WE TURNED BACK ┄┄┄┄┄┄┄┄┄┄┄

  "<abandon reason — documented by the agent from
    the conversation that led to abandonment>"

  ┄┄┄┄┄┄┄┄┄┄┄ WHAT WE DISCOVERED ┄┄┄┄┄┄┄┄┄┄┄┄

  Auto-extracted highlights from the quest journey:
  - User feedback moments (where we course-corrected)
  - Arbiter verdicts (what got refined)
  - Key decisions made along the way

  Example:
  > "KISS wins: SQLite was overkill, JSONL is enough"
  > "Plans are cheap, building prematurely is expensive"

  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄

          The quest sleeps in the archive.
       Its ideas may wake in another quest.

     Not every path leads to the destination.
       Some lead to the better question.

            N
            |
            |     *
       .----+----/
      /     |  /   \
     /      |/      \
 W--+-------+-------+--E
     \      |      /
      \     |     /
       '----+----'
            |
            |
            S

      *                                *
     /|\                             / | \
    / | \                           /| | |\
   // | \\                         //| | |\\
      |              - - - >     ///| | | |\\\
      |                         ////| | | |\\\\
      |                        /////| | | |\\\\\
                                    | | |
                                    | | |

   planted                        rooted

  ══════════════════════════════════════════════
```

## Parallels to Celebration

| Celebration            | Requiem                                          |
|------------------------|--------------------------------------------------|
| Achievement unlocked   | Epitaph (what was attempted)                     |
| Files changed          | What remains (artifacts preserved)               |
| Tests passed           | What we discovered (from feedback + verdicts)    |
| Credits roll           | Agents who contributed                           |
| Confetti / fireworks   | Single candle / quiet fade                       |
| Progress: 100%         | Progress bar: where the journey reached          |
| "Quest complete!"      | "A celebration of discovery"                     |
| Next steps             | "Its ideas may wake in another quest"            |
| —                      | Why we turned back (agent-documented narrative)  |

## Agent Responsibility: Document the "Why"

When a quest is abandoned, the orchestrating agent MUST write a structured abandon summary before triggering the requiem. This is not optional — the requiem draws from it.

The agent documents from the actual conversation:
1. **Why it was abandoned** — the real reason, in the user's words or spirit
2. **Key turning points** — moments where direction changed (user feedback, plan revisions, realizations)
3. **What we now know** — concrete insights that didn't exist before the quest started

Written to: `.quest/<id>/abandon_summary.md`

```markdown
## Why We Turned Back
<1-2 sentences capturing the real reason>

## Turning Points
- <moment 1: what happened and what it revealed>
- <moment 2: ...>

## What We Now Know
- <insight 1>
- <insight 2>
```

This is what makes the requiem meaningful — it's not generic platitudes, it's the actual story of what we tried and what we learned.

## Data Sources

All auto-extractable from the quest directory:
- `state.json` — phase reached, iterations, created/updated timestamps
- `quest_brief.md` — one-line summary for epitaph
- `abandon_summary.md` — agent-written narrative of why and what was learned (NEW)
- `phase_01_plan/user_feedback.md` — user corrections (turning points)
- `phase_01_plan/arbiter_verdict.md` — what was refined
- `logs/context_health.log` — agent count
- `phase_*/` directories — artifact count

## Progress Bar Mapping

| Last Phase Reached      | Percentage |
|-------------------------|------------|
| plan (no approval)      | 20%        |
| plan_reviewed           | 35%        |
| presenting              | 40%        |
| presentation_complete   | 45%        |
| building                | 60%        |
| reviewing               | 80%        |
| fixing                  | 90%        |

## Implementation

- New script: `scripts/quest_requiem/quest-requiem.sh`
- Mirror `quest_celebrate` structure but simpler (fewer frames, no confetti)
- Called from workflow Step 8 (Abandon) after archiving
- Same `--quest-dir` interface as celebrate
- Fire-and-forget: `bash scripts/quest_requiem/quest-requiem.sh --quest-dir .quest/archive/<id> || true`

## Depends On

- `quest-abandon-flow.md` — the abandon mechanics (Step 8) that would trigger this

## Scope

Small — one bash script, ~200 LOC, no dependencies beyond what celebrate already uses.
