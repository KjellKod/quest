---
name: celebrate
description: Play a quest completion celebration animation. Use when the user invokes /celebrate, asks to celebrate a quest, or when a quest reaches the complete/archived state.
---

# Skill: Celebrate

Play a rich, visually stunning celebration for a completed quest.

## When to Use

- User types `/celebrate` or `/celebrate <quest-id>`
- User asks to "celebrate", "play celebration", or "show the celebration" for a quest
- Quest workflow reaches Step 7 (complete) and user chooses to celebrate
- User points to a quest archive path or journal entry and asks to celebrate it

## Process

### Step 1: Resolve the Quest Source

If the user provides an argument:
1. If it's a full path (starts with `/` or `.`), use it directly
2. If it looks like a quest ID (e.g., `name-resolution_2026-03-04__1954`), look in:
   - `.quest/<id>/` (active quest)
   - `.quest/archive/<id>/` (archived quest)
   - `docs/quest-journal/` for a matching filename (journaled quest)
3. If it's a short name (e.g., `name-resolution`), find the best match in:
   - `.quest/archive/`
   - `docs/quest-journal/` (match by filename prefix)

If no argument is provided:
- Find the most recently modified quest in `.quest/archive/`
- If no archive, find the most recent entry in `docs/quest-journal/` (by filename date)

### Step 2: Read the Quest Artifacts

**From a quest directory** (`.quest/` or `.quest/archive/`):
- `state.json` — plan_iterations, fix_iterations, phase history, current_phase
- `quest_brief.md` — quest name, risk level, scope, acceptance criteria
- `phase_01_plan/handoff_arbiter.json` — arbiter verdict and summary
- `phase_01_plan/handoff.json` — planner summary
- `phase_02_implementation/handoff.json` — builder summary, files changed
- `phase_03_review/handoff_code-reviewer-a.json` — reviewer verdict
- `phase_03_review/handoff_code-reviewer-b.json` — reviewer verdict
- `phase_03_review/handoff_fixer.json` — fixer summary, what was fixed, test counts

**From a journal entry** (`docs/quest-journal/*.md`):
1. Look for a `celebration_data` JSON block between `<!-- celebration-data-start -->` and `<!-- celebration-data-end -->` markers
2. If found: use the structured data (agents, achievements, metrics, quality tier, quote, victory narrative)
3. If not found (legacy entries): "wing it" from the markdown text — read the sections for iterations, files changed, outcome, and the "what started it" quote. Improvise achievements and metrics from context.

### Step 3: Generate the Celebration as Rich Markdown

**IMPORTANT: Write the celebration directly as your response text. Do NOT run a script. Do NOT wrap the entire celebration in a code block. The UI renders agent markdown beautifully, but ASCII/block-letter title art must be emitted as plain text lines rather than markdown headers or list items.**

You have all the data from the artifacts. Now **create your own celebration**. Be creative. Make it feel like an achievement, not a status report.

**Required sections** (present them however you like):
- Quest name and ID
- Starring cast with role-specialized labels and model tags (inline):
  - `plan-reviewer-a [Model] ........ The A Plan Critic`
  - `plan-reviewer-b [Model] ........ The B Plan Critic`
  - `code-reviewer-a [Model] ........ The A Code Critic`
  - `code-reviewer-b [Model] ........ The B Code Critic`
- Achievements — specific to what happened in this quest
- Impact metrics — domain-specific, not generic file counts
- Handoff & reliability snapshot (handoffs parsed, reviewer/fixer handoffs, findings tracked, stability signal)
- Quality tier — named, from the full honest scale (see below)
- A quote from the actual quest (arbiter verdict, reviewer summary, fixer handoff)
- Victory narrative — what this quest proved or demonstrated (or survival narrative for rough ones)

**Use markdown richly:**
- `#` and `##` headers (they render big and bold)
- `**bold**` for emphasis
- `>` blockquotes for the quote
- Celebration Emojis generously (⭐️ 🏆 🎯 💎 📊 🔧 🧪 ✨ 🔒 📚 ⚡️ 🫡  🥇💪  🎉 🚀 🎮)
- Scary Emojis as needed (👺 👿 🦠 🐛 👹 👾 😈 💩 💀 ⛈️ )
- Neutral Emojis to emphesize either celebration or scary (🌪️ 🔥  ⚙️  🔧)
- `---` horizontal rules for visual separation
- Tables if they help present the data

**ASCII/block-letter title rules:**
- Emit block-letter rows as plain text lines only.
- Do **not** prefix block-letter rows with `#`, `-`, `>`, or any other markdown marker.
- Keep the title art contiguous with no blank separator inserted inside the rows.
- After the title art, leave one normal blank line before the rest of the celebration.

**Do NOT:**
- Put too many characters on one line of block letters — max ~5 letters per line, break long names across multiple lines (one word per block, like the HELLO/WORLD example)
- Wrap the entire celebration in a code block (kills the rich rendering)
- Prefix ASCII title art with markdown header markers such as `#`
- Use generic achievements like "Quest Complete" or "Battle Tested"
- Use generic metrics like "Files Changed: 22" or "Agents Involved: 0"
- Use fallback quotes like "Shipping should feel like a celebration"
- Follow a rigid template — reimagine the presentation each time

**Example of the kind of output that looks amazing** (but don't copy this — create your own based on what you read):

---

```
██╗  ██╗███████╗██╗     ██╗      ██████╗
██║  ██║██╔════╝██║     ██║     ██╔═══██╗
███████║█████╗  ██║     ██║     ██║   ██║
██╔══██║██╔══╝  ██║     ██║     ██║   ██║
██║  ██║███████╗███████╗███████╗╚██████╔╝
╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝ ╚═════╝

██╗    ██╗ ██████╗ ██████╗ ██╗     ██████╗
██║    ██║██╔═══██╗██╔══██╗██║     ██╔══██╗
██║ █╗ ██║██║   ██║██████╔╝██║     ██║  ██║
██║███╗██║██║   ██║██╔══██╗██║     ██║  ██║
╚███╔███╔╝╚██████╔╝██║  ██║███████╗██████╔╝
 ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═════╝
```

Break the text across **multiple lines** — max ~5 letters per line. Each word gets its own block, like "HELLO" on one line and "WORLD" on the next. For longer words, hyphenate: "RESOL-" on one line and "UTION" on the next. This keeps it readable without horizontal overflow.

 🎉 🎉 🎉 🎉  🙌  🎉 🎉 🎉 🎉  

## 🏆 Achievements Unlocked

⭐️ **Two-Gate Survivor** — Plan survived dual review
⭐️ **Arbiter's Blessing** — Tie-break directive approved
⭐️ **One-Shot Fixer** — All blockers resolved in 1 pass
⭐️ **20/20 Vision** — Perfect test coverage

## 🎯 Impact Metrics

📊 20 tools enhanced
🔒 Security model preserved
🧪 20/20 tests passing
📚 Docs updated (README + OPS)
⚡️ Medium-risk quest → Zero incidents

## 💎 Quest Quality Score: PLATINUM 💎

> "All critical issues from the previous review cycle have been properly addressed."
>
> — Code Reviewer A, final verdict

**Victory Unlocked!** 🎮

---

### Quality Tier Scale — The Full Honest Spectrum

The tier must be candid. Smooth quests get celebrated. Rough quests get acknowledged with humor and respect — they still shipped.

| Tier | Icon | Grade | Meaning | Criteria |
|------|------|-------|---------|----------|
| Diamond | 💎 | A+ | Flawless | Zero issues in first review, shipped clean |
| Platinum | 🏆 | A | Near-perfect | Minor issues, all fixed in one pass |
| Gold | 🥇 | B | Solid | Some issues, fixed cleanly |
| Silver | 🥈 | C | Workable | Multiple fix iterations but landed |
| Bronze | 🥉 | D | Rough | Got through, but bruised |
| Tin | 🥫 | D- | Dented | 3+ fix iterations, multiple plan revisions |
| Cardboard | 📦 | F (but passed) | Held together with tape | Barely survived, max iterations hit |
| Abandoned | 💀 | Incomplete | Never shipped | Quest was abandoned |

**Tone shifts per tier:**
- Diamond → full fireworks, "perfection exists"
- Platinum/Gold → warm celebration, real achievements
- Silver/Bronze → honest, "got there in the end", highlight what went right
- Tin → "dented but not broken", survivor humor
- Cardboard → "held together with tape and dreams. But it shipped. Respect."
- Abandoned → reflective, "lessons learned", no shame

### Key Principles

**Generate specific, context-aware content — not generic filler:**

- **Achievements must be specific.** Read the handoff summaries. If the arbiter broke a tie, that's "Two-Gate Survivor". If the fixer resolved all blockers in one pass, that's "One-Shot Fixer". If tests were 20/20, that's "20/20 Vision". If no unnecessary complexity was added, that's "KISS Champion". **Never use generic achievements like "Quest Complete" or "Battle Tested".**

- **Attach model attribution to achievements when possible.** Prefer dynamic labels from artifacts, e.g. `Gremlin Slayer (Codex)` or `Plan Perfectionist (KiMi K2.5)`.

- **Metrics must be domain-specific.** Read the fixer handoff for file counts, test counts, and what was built. "20 tools enhanced" is good. "Files Changed: 22" is bad. "Security model preserved" is good. "Agents Involved: 0" is bad.

- **Quality tier must be named.** Use the full honest scale above. If the quest struggled, say so — Tin and Cardboard are honest, not insults.

- **The quote must come from the quest.** Pull a real line from the arbiter verdict, reviewer summary, or fixer handoff. Not "Shipping should feel like a celebration."

- **Emojis render beautifully in markdown.** Use them generously: ⭐️ 🏆 🎯 💎 📊 🔧 🧪 🔒 📚 ⚡️ 🎊 🎉 🚀 🎮

## Examples

```
/celebrate
/celebrate name-resolution_2026-03-04__1954
/celebrate .quest/archive/celebrate-v2_2026-03-05__0643
/celebrate docs/quest-journal/celebrate-v2_2026-03-05.md
/celebrate celebrate-v2
```
