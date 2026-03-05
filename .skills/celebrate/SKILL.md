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
- User points to a quest archive path and asks to celebrate it

## Process

### Step 1: Resolve the Quest Directory

If the user provides an argument:
1. If it's a full path (starts with `/` or `.`), use it directly
2. If it looks like a quest ID (e.g., `name-resolution_2026-03-04__1954`), look in:
   - `.quest/<id>/` (active quest)
   - `.quest/archive/<id>/` (archived quest)
3. If it's a short name (e.g., `name-resolution`), find the best match in `.quest/archive/`

If no argument is provided:
- Find the most recently modified quest in `.quest/archive/` (or `.quest/` if no archive)

### Step 2: Read the Quest Artifacts

Read these files from the quest directory to understand what happened:
- `state.json` — plan_iterations, fix_iterations, phase history, current_phase
- `quest_brief.md` — quest name, risk level, scope, acceptance criteria
- `phase_01_plan/handoff_arbiter.json` — arbiter verdict and summary
- `phase_01_plan/handoff.json` — planner summary
- `phase_02_implementation/handoff.json` — builder summary, files changed
- `phase_03_review/handoff_code-reviewer-a.json` — reviewer verdict
- `phase_03_review/handoff_code-reviewer-b.json` — reviewer verdict
- `phase_03_review/handoff_fixer.json` — fixer summary, what was fixed, test counts

### Step 3: Generate the Celebration as Rich Markdown

**IMPORTANT: Write the celebration directly as your response text. Do NOT run a script. Do NOT wrap in code blocks. The UI renders agent markdown beautifully — big headers, colorful emojis, proper spacing. Use that.**

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
- Quality tier — named: Bronze, Silver, Gold, Platinum, Diamond
- A quote from the actual quest (arbiter verdict, reviewer summary, fixer handoff)
- Victory narrative — what this quest proved or demonstrated

**Use markdown richly:**
- `#` and `##` headers (they render big and bold)
- `**bold**` for emphasis
- `>` blockquotes for the quote
- Celebration Emojis generously (⭐️ 🏆 🎯 💎 📊 🔧 🧪 ✨ 🔒 📚 ⚡️ 🫡  🥇💪  🎉 🚀 🎮)
- Scary Emojis as needed (👺 👿 🦠 🐛 👹 👾 😈 💩 💀 ⛈️ )
- Neutral Emojis to emphesize either celebration or scary (🌪️ 🔥  ⚙️  🔧)
- `---` horizontal rules for visual separation
- Tables if they help present the data

**Do NOT:**
- Put too many characters on one line of block letters — max ~5 letters per line, break long names across multiple lines (one word per block, like the HELLO/WORLD example)
- Wrap the entire celebration in a code block (kills the rich rendering)
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

🎊 🎉 🎊 🎉 🎊 🎉 🎊 🎉 🎊 🎉 🎊 🎉 🎊 🎉 🎊

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

### Key Principles

**Generate specific, context-aware content — not generic filler:**

- **Achievements must be specific.** Read the handoff summaries. If the arbiter broke a tie, that's "Two-Gate Survivor". If the fixer resolved all blockers in one pass, that's "One-Shot Fixer". If tests were 20/20, that's "20/20 Vision". If no unnecessary complexity was added, that's "KISS Champion". **Never use generic achievements like "Quest Complete" or "Battle Tested".**

- **Attach model attribution to achievements when possible.** Prefer dynamic labels from artifacts, e.g. `Gremlin Slayer (Codex)` or `Plan Perfectionist (KiMi K2.5)`.

- **Metrics must be domain-specific.** Read the fixer handoff for file counts, test counts, and what was built. "20 tools enhanced" is good. "Files Changed: 22" is bad. "Security model preserved" is good. "Agents Involved: 0" is bad.

- **Quality tier must be named.** Based on your reading of the quest:
  - **Diamond** — zero issues in first review, shipped perfectly
  - **Platinum** — minor issues caught, all fixed in one pass
  - **Gold** — some issues, fixed cleanly
  - **Silver** — multiple fix iterations but got there
  - **Bronze** — got through but was rough

- **The quote must come from the quest.** Pull a real line from the arbiter verdict, reviewer summary, or fixer handoff. Not "Shipping should feel like a celebration."

- **Emojis render beautifully in markdown.** Use them generously: ⭐️ 🏆 🎯 💎 📊 🔧 🧪 🔒 📚 ⚡️ 🎊 🎉 🚀 🎮

## Examples

```
/celebrate
/celebrate name-resolution_2026-03-04__1954
/celebrate .quest/archive/celebrate-v2_2026-03-05__0643
```
