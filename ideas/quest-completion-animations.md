---
title: Quest Completion Animation System
purpose: ASCII art animations and celebration displays for completed quests
audience: Quest orchestrators and AI agents
status: draft
---

# Quest Completion Animation System

## Overview

Make quest completion feel like an achievement, not just a checkbox. ASCII animations, progress bars, and end credits create memorable conclusions to multi-agent workflows.

## Philosophy

> "Shipping should feel like a celebration, not a status update."

- **Visual**: ASCII art > plain text
- **Animated**: Progress bars > static lists  
- **Playful**: Gremlin battles > dry summaries
- **Configurable**: Choose your celebration level

## Configuration

### In `.ai/allowlist.json` or `.quest/config.json`:

```json
{
  "quest_completion": {
    "enabled": true,
    "animation_style": "epic",
    "show_end_credits": true,
    "show_progress_bars": true,
    "ascii_art": true,
    "emoji_density": "high"
  }
}
```

### Environment Variables:

```bash
QUEST_ANIMATIONS=1          # Enable/disable (0 = off)
QUEST_STYLE=epic            # minimal | standard | epic | silly
QUEST_CREDITS=1             # Show end credits (0 = skip)
```

## Animation Styles

### 1. Minimal
```
✅ Quest Complete: tool-tiering
📦 25 tools | 🧪 47 tests | 🚀 Merged
```

### 2. Standard
```
╔════════════════════════════════════╗
║      🏆 QUEST COMPLETE 🏆          ║
║                                    ║
║  Tool Tiering & Dynamic Discovery  ║
║                                    ║
║  ✅ 25 Tools  ✅ 47 Tests  ✅ Merged║
╚════════════════════════════════════╝
```

### 3. Epic (Full Production)
- Multi-phase progress bars
- ASCII art battles
- Gremlin eviction ceremony
- Scrolling end credits
- Achievement unlocks

### 4. Silly
- Maximum emojis
- Ridiculous metaphors
- Dancing ASCII characters
- Over-the-top celebrations

## Animation Library

### Progress Bar Builder

```python
def show_phase_progress(phase: str, percent: int, detail: str):
    """Display animated progress bar for quest phases."""
    filled = "█" * (percent // 10)
    empty = "░" * (10 - (percent // 10))
    print(f"   {phase:20} [{filled}{empty}] {percent}% - {detail}")

# Usage:
show_phase_progress("Planning", 100, "Dual reviews complete")
show_phase_progress("Building", 100, "25 tools created")
show_phase_progress("Testing", 100, "47 tests passing")
show_phase_progress("Review", 100, "All issues fixed")
show_phase_progress("Merge", 100, "SHIPPED! 🚀")
```

### ASCII Art Templates

#### Trophy Stand
```
              🏆
             /|\
            / | \
           /  |  \
          / TIER  \
         /  TOOLS   \
        /______________\
        |   COMPLETE   |
        |     {N}      |
        |    TOOLS     |
        |______________|
```

#### Gremlin Battle
```
              /\_/\
             ( o.o )      << The Code Gremlin
              > ^ <
               
              🔥 ATTACK! 🔥
    
           ⚔️       🛡️
          /|\      /|\
           |        |
          / \      / \
    
    🗡️  /      🐛💥      \  🗡️
       /                    \
      Human    +    AI Agents
```

#### Gremlin Farm (Retirement)
```
            🦋      🦋
      🌻  🐛→🏡  🌻
          🌳  🦋  🌳
    
    "Happy gremlin in retirement"
    (Bug-free since {date})
```

#### Rocket Launch
```
              🚀
           ========
          |  SHIP  |
          |   IT   |
           ========
            🔥🔥🔥🔥
    ```

### End Credits Template

```
╔════════════════════════════════════════════════════════════╗
║                      🎬  THE END  🎬                         ║
║                                                            ║
║              A QUEST PRODUCTION                            ║
║                                                            ║
║         "{quest_name}"                                    ║
║                                                            ║
╚════════════════════════════════════════════════════════════╝

🎭  STARRING  🎭

   {human_name} .................. The Vision Keeper
   {ai_model} .................... The Implementer
   {planner_model} ............... The Planner
   {reviewer_model} ............. The Reviewer

🎬  CREW  🎬

   GitHub API ................. Comment Threader
   GitHub Actions ............. CI Guardian
   {test_framework} ............ Truth Teller
   {lint_tool} ................. Style Enforcer

🏆  SPECIAL ACHIEVEMENTS  🏆

   🐛 "Gremlin Slayer" - Found and fixed {N} edge cases
   🧪 "Test Champion" - {N} tests, 100% pass rate
   🚀 "Ship It" - PR #{N} merged
   📝 "Playbook Pioneer" - Evolved review style
   
💜  FAMOUS LAST WORDS  💜

   "{memorable_quote}"
   
   — {ai_model}, {context}

═══════════════════════════════════════════════════════════

         QUESTS COMPLETED: {total}
         GREMLINS EVICTED: {bugs_fixed}
         USERS MADE HAPPY: ∞

═══════════════════════════════════════════════════════════

🦋 ...and the gremlin lived happily ever after
     on a farm, chasing butterflies. 🦋

THE END. REALLY. FIN. 💜
```

## Implementation

### Shell Script Version

```bash
#!/usr/bin/env bash
# quest-celebrate.sh

QUEST_NAME="$1"
STYLE="${QUEST_STYLE:-standard}"
SHOW_CREDITS="${QUEST_CREDITS:-1}"

if [ "$QUEST_ANIMATIONS" = "0" ]; then
    echo "✅ Quest Complete: $QUEST_NAME"
    exit 0
fi

case "$STYLE" in
    minimal)
        echo "✅ Quest Complete: $QUEST_NAME"
        ;;
    standard)
        cat << 'ASCII'
╔════════════════════════════════════╗
║      🏆 QUEST COMPLETE 🏆          ║
╚════════════════════════════════════╝
ASCII
        ;;
    epic)
        # Show full animation sequence
        show_phase_progress() {
            local phase="$1"
            local percent="$2"
            local detail="$3"
            local filled=$((percent / 10))
            local empty=$((10 - filled))
            printf "   %-20s [" "$phase"
            printf '%*s' "$filled" '' | tr ' ' '█'
            printf '%*s' "$empty" '' | tr ' ' '░'
            printf "] %3d%% - %s\n" "$percent" "$detail"
        }
        
        echo "🎬 QUEST COMPLETION SEQUENCE"
        sleep 0.3
        show_phase_progress "Planning" 100 "Dual reviews"
        sleep 0.3
        show_phase_progress "Building" 100 "Tools created"
        sleep 0.3
        show_phase_progress "Testing" 100 "All passing"
        sleep 0.3
        show_phase_progress "Review" 100 "Issues fixed"
        sleep 0.3
        show_phase_progress "Merge" 100 "SHIPPED! 🚀"
        
        if [ "$SHOW_CREDITS" = "1" ]; then
            show_end_credits
        fi
        ;;
esac
```

### Python Version

```python
#!/usr/bin/env python3
"""Quest completion animation system."""

import os
import time
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class QuestStats:
    name: str
    tools: int
    tests: int
    bugs_fixed: int
    pr_number: int
    duration_hours: float

class QuestAnimator:
    def __init__(self, style: str = "standard", show_credits: bool = True):
        self.style = style
        self.show_credits = show_credits
        self.enabled = os.getenv("QUEST_ANIMATIONS", "1") == "1"
    
    def celebrate(self, stats: QuestStats) -> None:
        if not self.enabled:
            print(f"✅ Quest Complete: {stats.name}")
            return
        
        if self.style == "epic":
            self._epic_celebration(stats)
        elif self.style == "standard":
            self._standard_celebration(stats)
        else:
            self._minimal_celebration(stats)
    
    def _epic_celebration(self, stats: QuestStats) -> None:
        phases = [
            ("Planning", 100, "Dual reviews complete"),
            ("Building", 100, f"{stats.tools} tools created"),
            ("Testing", 100, f"{stats.tests} tests passing"),
            ("Review", 100, f"{stats.bugs_fixed} gremlins evicted"),
            ("Merge", 100, "SHIPPED! 🚀"),
        ]
        
        print("\n    🎬 QUEST COMPLETION SEQUENCE\n")
        for phase, pct, detail in phases:
            self._show_progress_bar(phase, pct, detail)
            time.sleep(0.3)
        
        print("\n    " + "═" * 50)
        print("    " + " 🏆  QUEST COMPLETE!  🏆 ".center(50))
        print("    " + "═" * 50 + "\n")
        
        if self.show_credits:
            self._show_end_credits(stats)
    
    def _show_progress_bar(self, phase: str, percent: int, detail: str) -> None:
        filled = "█" * (percent // 10)
        empty = "░" * (10 - (percent // 10))
        print(f"       {phase:12} [{filled}{empty}] {percent}% - {detail}")
    
    def _show_end_credits(self, stats: QuestStats) -> None:
        credits = f"""
    ╔════════════════════════════════════════════════════════════╗
    ║                      🎬  THE END  🎬                         ║
    ║                                                            ║
    ║              "{stats.name}"                                 ║
    ║                                                            ║
    ║         🎭  STARRING  🎭                                    ║
    ║                                                            ║
    ║            You  +  AI Collaborators                        ║
    ║                                                            ║
    ║         🏆  {stats.tools} Tools  |  {stats.tests} Tests  🏆         ║
    ║                                                            ║
    ╚════════════════════════════════════════════════════════════╝
    
        🦋  ...and the gremlins lived happily ever after  🦋
        """
        print(credits)

# Usage
if __name__ == "__main__":
    stats = QuestStats(
        name="Tool Tiering & Dynamic Discovery",
        tools=25,
        tests=47,
        bugs_fixed=2,
        pr_number=23,
        duration_hours=14.0,
    )
    
    animator = QuestAnimator(style="epic", show_credits=True)
    animator.celebrate(stats)
```

## Integration with Quest Workflow

### At Archive Time

```python
# In quest orchestrator, after archiving:

from quest_animations import QuestAnimator, QuestStats

stats = QuestStats(
    name=quest.slug,
    tools=count_deliverables(),
    tests=count_tests(),
    bugs_fixed=len(review_issues_resolved),
    pr_number=pr.number,
    duration_hours=(completed_at - created_at).total_seconds() / 3600,
)

animator = QuestAnimator(
    style=os.getenv("QUEST_STYLE", "epic"),
    show_credits=os.getenv("QUEST_CREDITS", "1") == "1"
)

animator.celebrate(stats)
```

## Examples in Action

### Minimal (CI environments, quick mode)
```
✅ Quest Complete: tool-tiering
📦 25 tools | 🧪 47 tests | 🚀 PR #23 merged
```

### Standard (Default)
```
╔════════════════════════════════════╗
║      🏆 QUEST COMPLETE 🏆          ║
║                                    ║
║  Tool Tiering & Dynamic Discovery  ║
║                                    ║
║  ✅ 25 Tools  ✅ 47 Tests          ║
║  ✅ PR #23 Merged                  ║
╚════════════════════════════════════╝
```

### Epic (Full Experience)
```
🎬 QUEST COMPLETION SEQUENCE

   Planning   [██████████] 100% - Dual reviews complete
   Building   [██████████] 100% - 25 tools created
   Testing    [██████████] 100% - 47 tests passing
   Review     [██████████] 100% - 2 gremlins evicted
   Merge      [██████████] 100% - SHIPPED! 🚀

══════════════════════════════════════════════════
           🏆  QUEST COMPLETE!  🏆
══════════════════════════════════════════════════

[ASCII trophy art]
[End credits scroll]

🦋 ...and the gremlin lived happily ever after 🦋
```

## Future Enhancements

- [ ] Sound effects (terminal bell sequences)
- [ ] Animated ASCII (frame-by-frame)
- [ ] Custom themes (holidays, milestones)
- [ ] Slack/Discord webhook integration
- [ ] Screenshot-friendly "victory cards"
- [ ] Achievement badges system

## Related

- `pr-inline-commenting-playbook.md` - Review comment style guide
- `quest-workflow.md` - Full quest orchestration
- `agent-personas.md` - AI voice and tone guidelines

---

*"Shipping should feel like a celebration."* 🎉

---

## 💡 Adjusting End Credits

> **Want to customize the end credits for your quest?**
>
> Edit the configuration in your project:
> - **File**: `.ai/allowlist.json` or `.quest/config.json`
> - **Key**: `quest_completion.show_end_credits`
> - **Env**: `QUEST_CREDITS=0` to skip, `QUEST_CREDITS=1` to show
>
> Or set per-quest in: `.quest/<quest_id>/config.json`
>
> The end credits template is in the **End Credits Template** section above.
> Modify the ASCII art, achievements, or famous quotes to match your team's style!


---

## 🔧 Terminal Compatibility Notes

### The Problem
Some terminals don't render Unicode block characters (█ ░) properly. They show as:
- Placeholder boxes (like in your screenshot)
- Question marks
- Nothing at all

### The Solution: Universal ASCII

Replace fancy blocks with simple characters that work everywhere:

```bash
# BEFORE (fancy, but may break):
filled="█" * (percent // 10)
empty="░" * (10 - (percent // 10))

# AFTER (universal, always works):
filled="=" * (percent // 10)
empty="-" * (10 - (percent // 10))
```

### Cross-Platform Progress Bar

```
# Universal version (works everywhere):
[====------] 40% - Building...
[========--] 80% - Almost there...
[==========] 100% - Complete!

# Instead of:
[████░░░░░░] 40% - Building...
[████████░░] 80% - Almost there...
[██████████] 100% - Complete!
```

### Recommended: Create a Script File

Instead of chaining `echo` commands (which shows the messy commands), create a proper script:

```bash
#!/usr/bin/env bash
# celebrate.sh - Quest completion animation

clear

echo ""
echo "    ============================================"
echo "           QUEST COMPLETE!"
echo "    ============================================"
echo ""

# Phase 1
echo "    [====------] 40% Planning..."
sleep 0.3
echo "    [========--] 80% Building..."
sleep 0.3
echo "    [==========] 100% Complete!"
sleep 0.5

echo ""
echo "    Trophy:"
echo "        T"
echo "       /|\\"
echo "      / | \\"
echo "     /  |  \\"
echo "    ==========="
echo ""
```

Then run it:
```bash
./celebrate.sh
```

Not:
```bash
echo '...' && sleep 0.3 && echo '...'  # Messy!
```

### Block Letter Titles

The celebration renders quest names as big ASCII block letters inside a bordered box. Each character is 5 rows tall and 5 columns wide, with 1 column of space between letters.

**Example — "HELLO" in block letters:**

```
#   # ##### #     #      ### 
#   # #     #     #     #   #
##### ###   #     #     #   #
#   # #     #     #     #   #
#   # ##### ##### #####  ### 
```

**Width calculation:** Each letter = 5 chars wide + 1 space = 6 chars per letter. So:
- 5 letters (HELLO) = 5 × 6 - 1 = **29 chars**
- 11 letters max fit in an 80-column box (80 - 10 border padding = 70 usable, 70 ÷ 6 = 11)

**When the name is too wide (>11 characters):** The script extracts the first 1-2 words from the quest slug and renders them on separate lines:

```
+==============================================================================+
|                          ✨ QUEST COMPLETE ✨                                  |
|                                                                              |
|                           #   #  ###  #   # #####                            |
|                           ##  # #   # ## ## #                                |
|                           # # # ##### # # # ###                              |
|                           #  ## #   # #   # #                                |
|                           #   # #   # #   # #####                            |
|                     ####  #####  ####  ###  #     #   #                      |
|                     #   # #     #     #   # #     #   #                      |
|                     ####  ###    ###  #   # #     #   #                      |
|                     #  #  #         # #   # #     #   #                      |
|                     #   # ##### ####   ###  #####  ###                       |
|                                                                              |
+==============================================================================+
```

**Rules:**
- Word 1: first word of slug, max 5 chars (e.g., "NAME" from "name-resolution")
- Word 2: second word of slug, max 6 chars (e.g., "RESOLU" from "name-resolution")
- Each word gets its own line of block letters
- If the slug has only one word, only one line renders

### Emoji Compatibility

Some emojis also break in certain terminals. Safe alternatives:

| Fancy | Universal |
|-------|-----------|
| 🏆 | [TROPHY] or just "WIN" |
| 🎉 | *** or !!! |
| ✅ | [OK] or [DONE] |
| 🐛 | [BUG] or just text "Gremlin" |
| 🚀 | >> or "LAUNCH" |

### The "Safe Mode" Template

```bash
#!/usr/bin/env bash
# safe-celebrate.sh - Works on ANY terminal

QUEST_NAME="${1:-Quest}"

clear
echo ""
echo "========================================"
echo "       QUEST COMPLETE: $QUEST_NAME"
echo "========================================"
echo ""

echo "Phase 1: Planning     [====------] 40%"
sleep 0.3
echo "Phase 2: Building     [========--] 80%"
sleep 0.3
echo "Phase 3: Testing      [==========] 100%"
sleep 0.3
echo "Phase 4: Review       [==========] 100%"
sleep 0.3
echo "Phase 5: Merge        [==========] DONE!"
sleep 0.5

echo ""
echo "========================================"
echo "           [TROPHY]"
echo "           COMPLETE!"
echo "========================================"
echo ""
echo "The gremlin has retired to a nice farm."
echo ""
```

### Testing Your Animation

Before shipping, test in:
1. Your terminal (iTerm, Terminal, etc.)
2. VS Code integrated terminal
3. CI logs (GitHub Actions, etc.)
4. Plain text output (redirect to file)

If it looks good in all 4, it's universal!

---

## Quick Fix for This Quest

Want to replay the celebration with clean formatting? Use this simplified version:

```bash
clear
echo ""
echo "==========================================="
echo "      TOOL TIERING QUEST COMPLETE!"
echo "==========================================="
echo ""
echo "Phase 1: Planning     [==========] Done"
echo "Phase 2: Building     [==========] 25 tools"
echo "Phase 3: Testing      [==========] 47 tests pass"
echo "Phase 4: Review       [==========] 2 gremlins fixed"
echo "Phase 5: Merge        [==========] PR #23 merged!"
echo ""
echo "==========================================="
echo "           TROPHY"
echo "          /|\\"
echo "         / | \\"
echo "        /  |  \\"
echo "       / 25 |  \\"
echo "      /TOOLS|   \\"
echo "     ================="
echo "==========================================="
echo ""
echo "The gremlin is happy on a farm."
echo "The code is merged."
echo "You are awesome."
echo ""
echo "*** THE END ***"
echo ""
```

Run it: `bash celebrate.sh`

---

## ✅ CORRECTED: Animation Format

### The Problem (What We Did Wrong)

**DON'T chain long commands:**
```bash
echo '...' && sleep 0.3 && echo '...' && sleep 0.2 && echo '...'
# ^ This wraps messily and shows raw commands
```

**DO use heredocs:**
```bash
cat << 'ANIMATION'
Phase 1: Planning     [████████░░] 80% - Dual reviews
Phase 2: Building     [██████████] 100% - 25 tools
Phase 3: Testing      [██████████] 100% - 47 tests pass
ANIMATION
```

### Key Rule: One Line Per Phase

Keep each status line short enough to not wrap:

```
Phase 1: Planning     [████████░░] 80% - Dual reviews
Phase 2: Building     [██████████] 100% - 25 tools
Phase 3: Testing      [██████████] 100% - 47 tests pass
Phase 4: Review       [██████████] 100% - 2 gremlins fixed
Phase 5: Merge        [██████████] 100% - PR #23 merged!
```

NOT:
```
Phase 1: Planning     [█     <- wrapping here breaks it!
██░░░░░░░] 80% - Dual reviews
```

### Corrected Full Script

```bash
#!/usr/bin/env bash
# celebrate.sh

clear

cat << 'EOF'

===========================================
      TOOL TIERING QUEST COMPLETE!
===========================================

Phase 1: Planning     [========--] 80%
Phase 2: Building     [==========] 100% - 25 tools
Phase 3: Testing      [==========] 100% - 47 tests
Phase 4: Review       [==========] 100% - 2 bugs fixed
Phase 5: Merge        [==========] 100% - PR merged!

===========================================
              TROPHY
             /|\\
            / | \\
           /  |  \\
          / 25|TOOLS \\n         =================
===========================================

The gremlin is happy on a farm.
The code is merged.

*** THE END ***

EOF
```

**Key fixes:**
- One line per phase (no wrapping)
- Block chars (█ ░) work fine!
- Heredoc keeps formatting clean
- No visible command chains

---

## ⏱️ Animation Speed & Timing

Control how fast the celebration plays. Different contexts need different speeds.

### 3 Speed Modes

| Mode | Use Case | Total Time | Feel |
|------|----------|------------|------|
| `--fast` | CI, logs, parallel jobs | ~1 second | Snappy, invisible |
| `default` | Normal completion | ~7 seconds | Sweet spot |
| `--slow` | Demos, milestones, Fridays | ~15-20 seconds | Cinematic, celebratory |

### Timing Breakdown (Default Mode)

```python
# Progress bar animation
for i in range(10):
    render_bar(i * 10)
    time.sleep(0.1)        # 100ms - visible but snappy

# Between phases
sleep(0.3)                  # 300ms - moment to breathe

# Trophy reveal
sleep(0.5)                  # 500ms - dramatic pause

# End credits scroll
for line in credits:
    print(line)
    time.sleep(0.05)        # 50ms/line - movie crawl speed
```

### Configuration

#### Environment Variables
```bash
export QUEST_SPEED=fast        # CI mode
export QUEST_SPEED=slow        # Cinematic mode
export QUEST_SCROLL=0.1        # Custom seconds per line
export QUEST_PAUSE=0.5         # Custom phase pause (seconds)
```

#### Command Line Flags
```bash
quest-celebrate --speed=fast          # Quick mode
quest-celebrate --speed=slow          # Slow mode
quest-celebrate --no-scroll           # Static only
quest-celebrate --scroll-speed=0.2    # Custom crawl speed
```

#### JSON Config
```json
{
  "quest_completion": {
    "enabled": true,
    "animation_speed": "default",
    "scroll_speed_seconds": 0.05,
    "phase_pause_seconds": 0.3,
    "show_progress_bars": true,
    "show_end_credits": true
  }
}
```

### Auto-Detection (Smart Defaults)

System automatically switches to `--fast` or static if:
- `CI=true` (GitHub Actions, Travis, etc.)
- `TERM=dumb` (basic terminal)
- Output piped: `| less` or `> file`
- `QUEST_ANIMATIONS=0` explicitly set

### The "Goldilocks" Philosophy

> Not Matrix-falling-code fast.
> Not PowerPoint-transition slow.
> **Star Wars crawl speed**: readable, moving, engaging.

**Default timing rationale:**
- **100ms** per progress bar tick = "I can see it moving"
- **300ms** between phases = "Okay, next part"
- **500ms** trophy reveal = "Dramatic moment"
- **50ms/line** credits = "I can read it, but it's flowing"

Total: ~7 seconds — enough to feel rewarding, not enough to annoy.

### Per-Quest Override

Create `.quest/<quest_id>/celebration.conf`:
```
# This quest was epic - make it special
SPEED=slow
TROPHY_ART=epic
CUSTOM_QUOTE="Waiting forever is what I do..."
```

---

## V2 Retrospective (2026-03-05)

### What V2 Got Wrong

The V2 implementation built generic scaffolding that reads quest artifacts but produces **thin, generic output**. Compared to the orchestrator-generated celebration from the name-resolution quest (screenshot), our V2 is visibly worse:

1. **Block letters didn't render** for the quest title — fell back to a plain banner
2. **"Agents Involved: 0"** — handoff files use varying field names and the reader didn't find them
3. **Generic achievements** ("Quest Complete", "Battle Tested") vs the old specific ones ("Two-Gate Survivor", "KISS Champion", "Zero Regression")
4. **No domain-specific metrics** — showed "Files Changed: 16" instead of "20 tools enhanced", "Security model preserved", "20/20 tests passing"
5. **No quality label** — showed a percentage bar instead of "PLATINUM" badge
6. **Fallback quote** — "Shipping should feel like a celebration" instead of a real reflective quote from the quest
7. **No Victory Unlocked narrative** — the old one had a paragraph summarizing what the quest demonstrated
8. **Minimal/standard styles are "nothing"** — barely any output

---

## Core Principle

> **The agent with context should produce the data, not a script guessing after the fact.**

The celebration script is fundamentally doing archaeology — digging through `state.json`, `quest_brief.md`, handoff files, trying to reconstruct what happened. And it shows: "Agents Involved: 0", generic achievements, fallback quotes. It's guessing.

Compare that to when the orchestrator celebrates directly. It has full context — it read the arbiter verdict, the code reviews, the quest brief. It knows it was 20 tools, 20/20 tests, that the arbiter broke a tie with binding directives, that the fixer resolved all blockers in one pass. The celebration is specific and meaningful because the agent has the context.

A post-hoc script can never reconstruct that semantic understanding. It can count files and parse JSON, but it can't know that the achievement was surviving an arbiter tie-break. It can't generate "KISS Champion" because it doesn't understand what was built or why it matters.

### The Architecture

```
Layer 1: DATA (orchestrator, has context)
  → At completion, reads quest artifacts that already exist
  → Generates celebration.json with achievements, metrics, quotes
  → Has full semantic understanding of what happened and why it matters

Layer 2: RENDERING (celebrate script, no context needed)
  → Reads celebration.json
  → Renders it beautifully: block letters, progress bars, emojis, credits
  → Handles markdown wrapping, terminal detection, animation speed
```

The script becomes a pure rendering engine. All the intelligence is in the data, produced by the agent that actually lived through the quest.

### The Artifacts Already Have Everything

The quest archive already contains rich data. No separate write-at-each-phase step is needed — the orchestrator just reads what's already there at completion time:

| Artifact | What it gives the celebration |
|----------|-------------------------------|
| `state.json` | plan_iterations, fix_iterations, phase history, timeline |
| `quest_brief.md` | quest name, risk level, scope, acceptance criteria |
| `handoff_arbiter.json` | verdict, summary (e.g., "signature contradiction resolved via 6 binding builder directives") |
| `handoff_fixer.json` | files changed list, summary (e.g., "Fixed all 4 user blockers"), test count |
| `handoff_code-reviewer-*.json` | final verdict, review summary |
| `user_findings.md` | what the human caught — material for achievements |
| `review_code-reviewer-*.md` | detailed findings with resolution status |
| `arbiter_verdict.md` | whether arbiter overrode reviewers, binding directives |
| `pr_description.md` | PR number, what shipped |

From these, the orchestrator can generate:
- "Two-Gate Survivor" — it read the arbiter verdict and knows there was a tie-break
- "20/20 Vision" — it parsed the fixer handoff summary mentioning test counts
- "KISS Champion" — it read the review and knows no unnecessary complexity was added
- "One-Shot Fixer" — it sees fix_iterations=1 in state.json

**A script can count files. Only an agent with context can understand meaning.**

### What This Means In Practice

At Step 7 (quest completion), the orchestrator:
1. Reads the key artifacts (state.json, handoffs, reviews, brief)
2. Writes `celebration.json` with rich, context-aware data
3. Calls the celebrate script which renders it beautifully

No incremental writes during the quest. No new ceremony at each phase transition. Just one smart read at the end by the agent that has full context.

**Why `celebration.json` and not just inline output from the orchestrator:** The celebration must be **replayable**. You should be able to run `/celebrate name-resolution_2026-03-04__1954` six months later in a fresh session with zero context. The orchestrator distills its context into a file. The file is the permanent record. The script renders it on demand, anytime, anywhere.

### Optional: PR Comments & Quotes

If the quest involved PR review (PR shepherd flow), the orchestrator may also have:
- Remarkable reviewer comments worth quoting
- Our best responses that show insight
- CI drama (failed, fixed, green)

These are optional — if present, they enrich the celebration. If not (no PR, or PR not yet merged), the celebration is still great without them.

### Celebration Data File Schema

```json
{
  "quest_name": "Name Resolution",
  "quest_id": "name-resolution_2026-03-04__1954",
  "completed_at": "2026-03-05T00:30:00Z",
  
  "title_display": "NAME RESOLUTION",
  
  "achievements": [
    {"icon": "⭐", "title": "Two-Gate Survivor", "description": "Plan survived dual review"},
    {"icon": "⭐", "title": "One-Shot Fixer", "description": "All blockers resolved in 1 pass"},
    {"icon": "⭐", "title": "20/20 Vision", "description": "Perfect test coverage"}
  ],
  
  "impact_metrics": [
    {"icon": "📊", "label": "20 tools enhanced"},
    {"icon": "🔒", "label": "Security model preserved"},
    {"icon": "🧪", "label": "20/20 tests passing"},
    {"icon": "📝", "label": "Docs updated (README + OPS)"},
    {"icon": "⚡", "label": "Medium-risk quest → Zero incidents"}
  ],
  
  "quality": {
    "score": 100,
    "label": "PLATINUM",
    "icon": "💎"
  },
  
  "agents": [
    {"name": "planner", "model": "claude-opus-4-6", "role_title": "The Architect"},
    {"name": "builder", "model": "gpt-5.3-codex", "role_title": "The Implementer"},
    {"name": "code-reviewer-a", "model": "claude-opus-4-6", "role_title": "The Critic"},
    {"name": "fixer", "model": "claude-opus-4-6", "role_title": "The Surgeon"}
  ],
  
  "quote": {
    "text": "The planner, reviewers, and fixer executed the Quest workflow with precision and discipline.",
    "attribution": "Quest System"
  },
  
  "victory_narrative": "Your quest demonstrated the full power of the multi-agent workflow:\n- Rigorous planning with arbiter intervention\n- Systematic issue detection through dual review\n- Focused, efficient fixes\n- Production-ready delivery",
  
  "pr": {
    "number": 42,
    "ci_status": "green",
    "comments_posted": 3,
    "review_comments_received": 1
  }
}
```

---

## Completed (2026-03-05, `celebration` branch)

### Agent-First Celebration — THE KEY BREAKTHROUGH

The celebrate skill tells the agent: **read the artifacts, then write the celebration yourself as rich markdown. Do not run a script.**

```
PRIMARY PATH (agent in UI — confirmed working in OpenCode):
  1. Agent reads quest artifacts (state.json, handoffs, reviews, brief)
  2. Agent generates celebration as rich markdown (headers, emojis, bold, blockquotes)
  3. UI renders it beautifully — big headers, colorful emojis, proper spacing
  4. Agent has context → specific achievements, domain metrics, real quotes

FALLBACK PATH (no agent available — terminal, CI):
  1. Script reads quest artifacts
  2. Script outputs celebration wrapped in code fences
  3. Renders as monospace code block (acceptable, not amazing)
```

**Why this works:** A script produces flat text in a code block — small, monospace, same-weight. An agent produces markdown that the UI renders richly. The difference is dramatic. The skill is a creative brief, not a rigid template — the agent reimagines the celebration each time, emphasizing what was remarkable about *this specific* quest.

**Confirmed:** OpenCode renders agent-generated celebrations beautifully with rich markdown. This is the primary path going forward.

### Celebrate Skill — Registered Across All Platforms

| Platform | Skill file | AGENTS.md | Trigger | Status |
|----------|-----------|-----------|---------|--------|
| Claude Code | `.claude/skills/celebrate/SKILL.md` → `.skills/celebrate/SKILL.md` | `.claude/AGENTS.md` | `/celebrate` | ✅ Confirmed working |
| Codex CLI | `.agents/skills/celebrate/SKILL.md` → `.skills/celebrate/SKILL.md` | `.codex/AGENTS.md` | `$celebrate` | ✅ Confirmed working (no autocomplete) |
| OpenCode | `.opencode/commands/celebrate.md` + `opencode.json` | N/A | `/celebrate` | ✅ Confirmed working |

### Celebrate Script Improvements (fallback path)

| File | Change |
|------|--------|
| `animations.py` | Block letter header from slug, gremlin battle, rocket launch, victory narrative, markdown wrapping, standard style overhaul |
| `ascii_art.py` | Achievements with `⭐️` aligned columns |
| `progress.py` | ASCII `=-` bars with emoji indicators (`🚀⚡🔄✅`), 4x slower animation |
| `terminal.py` | Non-interactive no longer forces safe mode |
| `config.py` | Safe mode only for CI or missing Unicode support |

### Integration

- ✅ Workflow Step 7 updated to use Python celebrate script
- ✅ `.quest-manifest` includes all celebrate files for installer
- ✅ `.skills/SKILLS.md` registry includes celebrate

### Learnings

1. **Agent-generated markdown >>> script output in code blocks.** The single most important insight. When the agent writes the celebration as response text, the UI renders rich markdown. When a script outputs text (even in code fences), it's a flat monospace block. The agent-first approach makes the script improvements largely moot for the primary use case.

2. **The skill is a creative brief, not a template.** The skill gives the agent structure (achievements, metrics, quality tier, quote) and principles (be specific, use domain metrics), but the agent reimagines the presentation each time. Every celebration is unique.

3. **Emoji > Unicode blocks.** Block characters (`█░`) break in many terminals. Emojis (`⭐️ 🏆 🎯 💎 📊`) render well everywhere. Simple `=` and `-` with emoji indicators beat fancy Unicode.

4. **Skill registration requires ALL platform touchpoints.** Skill file + thin redirects per platform + AGENTS.md entries + SKILLS.md + manifest + opencode.json. Missing any one = platform can't find it.

5. **Non-interactive ≠ dumb terminal.** The old heuristic disabled Unicode/emoji for any piped output. Modern terminals and AI agent UIs handle them fine.

6. **Speed matters.** Animations <1s feel like a glitch. ~7s default is the sweet spot for the script fallback path.

---

## Left to Do / Discuss

### `celebration.json` — Replayable Cache (V3)

**Status:** Not implemented. Still a good idea but lower priority now that the agent-first approach works.

**The case for it:** The celebration must be replayable. Running `/celebrate name-resolution_2026-03-04__1954` six months later in a fresh session means the agent has to re-read all the artifacts and re-generate everything. A `celebration.json` written at completion time would cache the orchestrator's context-aware data (specific achievements, domain metrics, quality tier, victory narrative, real quotes) so future celebrations are instant and consistent.

**The case against urgency:** The agent-first approach already works great. The agent reads artifacts and generates a celebration in ~15 seconds. The result is good because the artifacts contain rich data. `celebration.json` would make it faster and more consistent, but it's not blocking anything.

**If we do it:** The orchestrator writes `celebration.json` at Step 7 by reading the existing artifacts. The celebrate skill checks for this file first, and only falls back to reading raw artifacts if it's missing. Schema is defined above in this document.

### PR Comments & Quotes Enrichment

**Status:** Not implemented. Optional enrichment.

If the quest involved PR shepherd flow, remarkable reviewer comments and CI drama could enrich the celebration. But this depends on the PR shepherd integration capturing that data, which isn't in place yet. Low priority — celebrations are already good without it.

### `/celebrate` Autocomplete in Codex CLI

**Status:** Works but no autocomplete. Codex CLI doesn't seem to support autocomplete for skill-based commands. This is a Codex CLI limitation, not something we can fix. The command works when typed manually.

### Script `ascii_art.py` Polish

**Status:** Partially done. Achievements use `⭐️` with aligned columns. Trophy, rocket, impact metrics rendering, and quality tier labels are partially updated. This is low-priority polish for the fallback path — the agent-first primary path doesn't use the script at all.

### Validation Still Needed

1. **Codex CLI with terminal.py fix** — run `$celebrate` again and confirm emojis/block letters show up in the script fallback path
2. **Quest workflow auto-trigger** — complete a quest and confirm Step 7 runs the celebration
3. **Installer** — run `quest_installer.sh --check` to verify celebrate files are included
4. **OpenCode autocomplete** — `/celebrate` and `/quest` autocomplete may need OpenCode restart to pick up config changes
