<!-- quest-id: direct-cli-guidance_2026-03-22__1052 -->
<!-- style: celebration -->
<!-- quality-tier: Platinum -->
<!-- date: 2026-03-22 -->
<!-- journal: ../direct-cli-guidance_2026-03-22.md -->
<!-- origin: step7-original -->

# Quest Celebration: Direct CLI Guidance

```text
██████╗ ██╗██████╗ ███████╗ ██████╗████████╗
██╔══██╗██║██╔══██╗██╔════╝██╔════╝╚══██╔══╝
██║  ██║██║██████╔╝█████╗  ██║        ██║   
██║  ██║██║██╔══██╗██╔══╝  ██║        ██║   
██████╔╝██║██║  ██║███████╗╚██████╗   ██║   
╚═════╝ ╚═╝╚═╝  ╚═╝╚══════╝ ╚═════╝   ╚═╝

 ██████╗██╗     ██╗
██╔════╝██║     ██║
██║     ██║     ██║
██║     ██║     ██║
╚██████╗███████╗██║
 ╚═════╝╚══════╝╚═╝

 ██████╗ ██╗   ██╗██╗██████╗  █████╗ ███╗   ██╗ ██████╗███████╗
██╔════╝ ██║   ██║██║██╔══██╗██╔══██╗████╗  ██║██╔════╝██╔════╝
██║  ███╗██║   ██║██║██║  ██║███████║██╔██╗ ██║██║     █████╗  
██║   ██║██║   ██║██║██║  ██║██╔══██║██║╚██╗██║██║     ██╔══╝  
╚██████╔╝╚██████╔╝██║██████╔╝██║  ██║██║ ╚████║╚██████╗███████╗
 ╚═════╝  ╚═════╝ ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝╚══════╝
```

---

## What Started This

Add guidance to skill docs that GitHub CLI commands should be invoked directly (not wrapped in `bash -lc`) so that persistent permission prefixes like `["gh","api"]` and `["gh","pr"]` match correctly. Wrapping defeats prefix matching and causes repeated permission prompts during quest orchestration.

## Achievements

- [BUG] **Gremlin Slayer** — Tackled 4 review findings
- [TEST] **Battle Tested** — Survived 2 reviews
- [SOLO] **Solo Adventurer** — Completed quest with a single companion
- [WIN] **Quest Complete** — All phases finished successfully

## Impact Metrics

- Review findings addressed: **4**
- Review rounds completed: **2**
- Plan iterations: **1**
- Fix iterations: **0**

## Handoff & Reliability

- Handoffs parsed: 0
- Reviewer handoffs: 0
- Fixer handoffs: 0
- Review findings tracked: 4
- Reliability signal: high

## Carry-Over Findings

- No carry-over findings this round; nothing was inherited from earlier quests and nothing needs to be saved for the next one.

## 🏆 Quality Tier: Platinum

QUALITY SCORE
----------------------------------------
  [████████████████████] 100% (Grade: A)


## Quest Quote

> "The proposed wording is clear, minimal, and explains the WHY (permission prefix matching)"
>
> — Review finding

## Victory Narrative

Add guidance to skill docs that GitHub CLI commands should be invoked directly (not wrapped in `bash -lc`) so that persistent permission prefixes like `["gh","api"]` and `["gh","pr"]` match correctly. Wrapping defeats prefix matching and causes repeated permission prompts during quest orchestration. The quest finished with 1 plan iteration(s), 0 fix loop(s), and a persisted celebration artifact that future readers can open directly from the journal.
