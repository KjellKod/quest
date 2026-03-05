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
