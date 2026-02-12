# User Feedback on Quest Experience

## Purpose
This document captures real-world user feedback about the Quest workflow to identify UX improvements and missing features. Feedback will be continuously added here, then analyzed to prioritize improvements.

---

## Feedback Items

### 1. Cost & Complexity Estimation (First-Class Citizen)

**What users want:**
- Upfront cost/LOE (Level of Effort) estimates BEFORE the building phase starts
- Clear complexity labels: **Big**, **Small**, **Medium**, **Easy**, **Hard**
- Risk assessment and phase complexity prominently displayed

**Current state:**
- Some estimation exists but it's not prominent enough
- Users can miss the information or it's not clearly called out

**User quote:**
> "We already get this now to some extent but we would like to make it a first-class citizen and really call out big, small, medium, easy, etc. The complexity is important to call out too."

**Impact:** HIGH - Users need to understand commitment before starting a build

---

### 2. Agent-Driven Pause Recommendations for Large Builds

**What users want:**
- For large builds with multiple phases and risks, the agent should **proactively recommend pausing**
- Agent should suggest: "Put the finished plan in the ideas folder, then break it into separate quests—one per phase"
- Each phase becomes its own detailed implementation plan that gets built step-by-step

**Current state:**
- Agent doesn't automatically recognize when a quest is too large/risky to tackle in one go
- No built-in mechanism to suggest phased approach

**User quote:**
> "If it's a large build with multiple phases and maybe with risk, the agent should call out itself that the suggestion is that we should pause here, put our finished plan, and put it in the ideas folder. Then you start a new quest with each phase as its input to break down into a more detailed implementation plan and implement it step by step."

**Impact:** HIGH - Prevents overwhelming builds, improves success rate

---

### 3. Phase Transition Clarity & Status Awareness

**What happened:**
- User missed the end of Phase 1 completion
- There was a prompt waiting: "Questions about this phase? Or changes you'd like to request? (continue/question/change)"
- User came back the next morning unsure what the status was
- Had to ask for status update to understand where things stood

**Current gap:**
- Phase transitions aren't obvious when user steps away
- No persistent "current status" indicator visible when resuming
- Easy to lose context between sessions

**User quote:**
> "I somehow missed the end of Phase 1 and prompt waiting for next steps [...] came back this morning and wasn't sure what was up. Asked status and picked up."

**Impact:** MEDIUM - Causes confusion and lost time when resuming work

---

### 4. Plan File Navigation & Quick Summary Access

**What happened:**
- After finding the plan files, user felt **overwhelmed**
- Didn't know where to start reading
- Needed a way to get a **quick summary** with suggested edits and questions

**Current gap:**
- Plan files exist but there's no executive summary or "start here" guide
- No quick way to see: "What was planned? What's the status? What needs my attention?"
- Too much detail without a roadmap for navigating it

**User quote:**
> "After a bit found the plan files and it's a bit overwhelming where to start, need to learn a way to get a quick summary and suggested edits and questions."

**Impact:** MEDIUM-HIGH - Reduces plan review effectiveness, creates friction

---

### 5. Cost/LOE in Build Kickoff Summary

**What happened:**
- User gave go-ahead to start the build
- Agent shared: "This is a large build (6 phases, ~100 files). I'll build it phase by phase, starting with Phase 1."
- User's first thought: "This would be nice to include in the summary if possible to give an estimate of the cost/LOE. If it's there I just missed it."

**Current state:**
- Build summary mentions size (phases, files) but may not clearly show cost/effort estimate
- Information might be there but not prominent

**User quote:**
> "Gave the go ahead to start the build - it kicked off and shared this first thought was this would nice to include in the summary if possible to give an estimate of the cost/LOE. if its there I just missed it"

**Impact:** MEDIUM - Relates to feedback item #1, reinforces need for prominent cost info

---

### 6. Default Full Permission Mode for Quest Workflow

**What users want:**
- Quest should run in "full permission mode" by default
- No prompts for routine operations: creating slugs, directories, reading directories
- Should still ask for critical decisions like plan review
- All "natural steps" in the workflow should proceed automatically without permission requests

**Current state:**
- Quest asks for permission on many routine operations
- Creates friction and slows down the workflow
- Interrupts the flow for non-critical decisions

**Implementation questions:**
- Can this be done programmatically within the quest system?
- Or does it require users to start Claude in a specific mode/configuration?
- Need to determine what can be automated vs. what requires user configuration or documentation

**User quote:**
> "By default, it is in full permission mode. It doesn't ask if it can create a slug, if they can create directories, if you can read directories. It should just be able to do all of these things. [...] In this higher mode, it does need to ask, like, review the plan, I think. But everything, all the natural steps, I think, should be as they are."

**Impact:** HIGH - Reduces friction and improves workflow speed significantly

---

### 7. Exploration: Parallel Implementation Agents (RESEARCH)

**Research question:**
- Is it possible to run two implementation agents on the same branch simultaneously?
- Would they collaborate effectively and work faster?
- Or would they create conflicts and interfere with each other's work?

**Potential benefits:**
- Could speed up large builds by parallelizing work
- Multiple agents could tackle different files or phases

**Potential risks:**
- Git conflicts and merge issues
- Coordination overhead
- Agents working at cross-purposes

**Status:** Purely exploratory idea, needs investigation and prototyping

**Impact:** UNKNOWN - Requires feasibility research and experimentation

---

### 8. Exploration: Multiple Review Agents with Different Perspectives (RESEARCH)

**What users want to explore:**
- Add more review agents beyond the current setup
- Each reviewer focuses on a different perspective: security, performance, architecture, maintainability, etc.
- Arbiter would synthesize and reconcile feedback from multiple reviewers
- Could surface a wider range of issues and provide more comprehensive reviews

**Implementation questions:**
- Can this be done now just by prompting Claude differently in the review phase?
- Or does it require changes to the quest orchestration code?
- Should users be prompted to select which review perspectives they want?
- Or should there be sensible defaults with configuration file overrides?

**Design options:**
- **Prompt-based**: User selects review angles at review time
- **Default with config**: Pre-configured perspectives (e.g., security, performance, maintainability) that users can customize in a config file

**User quote:**
> "Can we add more review agents, and can the arbiter then work with more review agents and the collector feedback and so on? [...] We could have different angles on the review agents. Say security is one, for example, or we can even prompt the user if they should have different angles and viewpoints. Or another option is that we have a default that is to have different viewpoints, and we have to tell the user that this is a default. You can change it in the X, Y, C file."

**Status:** Exploratory idea, needs design and feasibility analysis

**Impact:** MEDIUM-HIGH - Could improve review quality and catch more issues

---

## Summary of Themes

| Theme | Priority | Description |
|-------|----------|-------------|
| **Cost Transparency** | HIGH | Make cost/LOE/complexity visible and prominent throughout the workflow |
| **Smart Pausing** | HIGH | Agent should recommend breaking large/risky builds into multiple quests |
| **Status Clarity** | MEDIUM | Better phase transition signals and resumption context |
| **Plan Navigation** | MEDIUM-HIGH | Quick summaries and guided navigation for plan review |
| **Permission Mode** | HIGH | Default full permission mode to reduce friction on routine operations |
| **Parallel Agents** | RESEARCH | Can multiple implementation agents work simultaneously on same branch? |
| **Multi-Perspective Review** | RESEARCH | Multiple review agents with different focuses (security, performance, etc.) |

---

## Next Steps

1. Continue collecting user feedback (add to this document)
2. Once feedback collection is complete, analyze and prioritize improvements
3. Create implementation plans for highest-impact UX improvements
4. Consider breaking improvements into separate quests based on theme

---

**Last Updated:** 2026-02-12
**Status:** Collecting feedback (ongoing)
