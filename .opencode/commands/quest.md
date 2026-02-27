---
description: Run Quest multi-agent orchestration - plan, review, build, and fix features with human approval gates
agent: quest
---

Load and execute the Quest orchestration skill. Use the skill tool to load: quest

Quest is a structured multi-agent workflow with these phases:
1. Intake - understand the quest brief
2. Planning - create implementation plan
3. Dual Review - Claude + second model review independently  
4. Arbiter - synthesize reviews, decide approve/iterate
5. Human Gate - you approve before building
6. Build - implement the plan
7. Code Review Loop - review, fix, re-review until approved

Current quest directory: .quest/

If the user provides a quest ID (format: name_YYYY-MM-DD__HHMM), resume from that quest's state.
