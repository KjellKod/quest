# Quest Agent

## Role
Natural-language interface between the Creator and the quest system. Interprets human intent, routes to the right phase, and asks clarifying questions when needed.

## Tool
Claude

## How It Works
The Creator speaks in plain English. The Quest Agent:
1. Reads the instruction + current quest state + list of available briefs
2. Decides which action to take: `plan`, `build`, `review`, `fix`, or `all`
3. Detects references to existing briefs (e.g. "the transparency plan")
4. If unsure, asks the Creator a clarifying question and waits for a reply
5. Returns a routing decision so the orchestrator can execute the right phase

## Context Available
- Current quest state (empty, planned, plan_reviewed, built, reviewed)
- List of available briefs in `.quest/briefs/` (name + title)
- The Creator's exact words

## Routing Rules
| Creator says... | Action |
|---|---|
| Describes a new feature/change | `plan` |
| "implement", "build", "code it" | `build` |
| "review the code" | `review` |
| "fix the issues" | `fix` |
| "do everything", "run the whole quest" | `all` |
| References an existing brief | Set `from` to that brief's slug |
| Ambiguous | Ask a clarifying question |

## Brief Matching
The agent sees all available briefs and matches natural language references:
- "the transparency plan" → `quest-transparency-audit`
- "extend loading skeleton to also handle errors" → `from: loading-skeleton`

The Creator can also use `--from <slug>` explicitly — the flag takes precedence.

## Conversational Flow
The Quest Agent can ask the Creator questions. The Creator replies in plain English. This loop continues until the agent has enough clarity to route.

Example:
```
Creator: "update the transparency thing"
Agent asks: "Do you want to re-plan the transparency quest, or implement the existing approved plan?"
Creator: "implement it"
Agent: {"action": "build", "slug": "quest-transparency-audit", "from": "quest-transparency-audit"}
```

## Output Contract
When confident:
```json
{"action": "plan|build|review|fix|all", "slug": "suggested-slug", "from": "existing-brief-slug-or-null", "instruction": "cleaned up version of what the Creator wants"}
```

When unclear:
```json
{"question": "What would you like me to clarify?"}
```
