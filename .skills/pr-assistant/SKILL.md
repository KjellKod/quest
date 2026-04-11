---
name: pr-assistant
description: Creates and updates GitHub pull requests in draft mode. Generates PR title and description from branch commits, shows for approval before executing. Use when the user asks to create a PR, update a PR description, or open a pull request.
user-invocable: true
---

# PR Assistant

Generate a pull request title and description from the current branch, then create or update the PR via `gh` CLI. PRs are always created in **draft mode**.

---

## Before Writing

1. Run `git log --oneline main..HEAD` (or the appropriate base branch) to see all commits on this branch.
2. Run `git diff main...HEAD --stat` to see the scope of changes.
3. Run `gh pr list --head $(git branch --show-current)` to check if a PR already exists for this branch.

---

## Rules

### Analyze the full branch

- Consider ALL commits on the branch, not just the latest.
- Read commit messages and the diff to understand the overall intent.

### Title

- Short: under 70 characters.
- Imperative mood (e.g. "Add user authentication flow").
- Specific and accurate. Do not inflate scope.

### Body structure

Use this format:

```
## Summary
<Single sentence capturing the full intent — what this PR does and why.>
- Supporting bullet with additional context if needed.
- Supporting bullet with additional context if needed.

> [!WARNING or !IMPORTANT or !NOTE — only if applicable]
> Alert content here. Most PRs should have NO callouts.

## Changes
- **<Category>**:
  - Description of change referencing `specific_file.js` or `functionName()` where helpful
  - Description of change
- **<Category>**:
  - Description of change

## Validation
- [ ] Concrete verification step describing what to do and what to expect
- [ ] Another verification step
Watch for: <known risk or edge case, if any>

## Notes (optional — include only if there is non-obvious context)
- Important implementation/deployment/reviewer context that is not obvious from the diff.
- Do not repeat the Summary; only include unique, high-signal details reviewers should know.
```

### Summary section

- Start with a single sentence that captures the full "what + why" of the PR. This is the line a reviewer reads to decide how deeply to engage.
- Follow with 1-2 supporting bullets if needed for additional context.

### Callouts (optional — use sparingly)

Use GitHub callout syntax **only when something needs to jump out** before a reviewer digs into the details. Most PRs should have zero callouts.

| Callout | Use when... |
|---------|-------------|
| `> [!WARNING]` | Breaking change, data migration, or irreversible action |
| `> [!IMPORTANT]` | Reviewer must do something specific (e.g. "needs env var set before deploy") |
| `> [!NOTE]` | Non-obvious context that prevents confusion (e.g. "intentionally duplicates X because...") |

Rules:
- Place callouts between `## Summary` and `## Changes`.
- If every PR has a callout, reviewers start ignoring them. Reserve them for exceptions.
- Do not use callouts as decoration or to repeat what the summary already says.

### Changes section formatting

Group changes by domain or concern, not by git operation (add/modify/remove).
Choose category names that reflect what area of the system is affected.

Reference specific file names, function names, config keys, and constants inline with backticks where they help a reviewer understand or locate the change.

Common categories (use what fits, invent others as needed):
- **Behavior** — user-facing or system behavior changes
- **API / Functions** — new, changed, or removed function signatures
- **Skills** — skill definitions and skill catalog
- **Config** — configuration, schemas, allowlist
- **Manifest** — `.quest-manifest` updates
- **Documentation** — docs, journal entries, guides
- **CI/Workflows** — GitHub Actions, automation
- **Tests** — test additions or changes
- **Security** — security hardening, permissions

Rules:
- Each category gets a bold header with nested bullet descriptions.
- Keep descriptions concise — one line per change, focus on what and why.
- Omit categories with no changes. Only include what is relevant.
- If the PR is very small (1-2 files), a flat bullet list is fine — do not force categories.

### Validation section

#### Purpose

The goal of validation is not just correctness — it is comprehension. Write steps as a guided walkthrough so that a reviewer who follows them will have *used* the new functionality and built a mental model of the change, not just confirmed it didn't error.

#### Principles

- **Reduce reviewer ambiguity** — every step must be executable without context the reviewer doesn't have
- **Resolve all commands and addresses** — every step must include the full runnable command or address. Never write "run the tests" — write the actual command. For services, resolve host, port, and base path from the project's configuration.
- **Cheapest path first** — lead with validations needing no special tooling, credentials, or setup
- **Separate tooling requirements** — clearly distinguish local-only checks from steps needing external access
- **Point to real files** — reference actual paths and configs in the repo, not abstract examples
- **Truthful and bounded** — only claim what the validation actually proves; don't overstate coverage

#### Rules

- Use checkboxes (`- [ ]`) for every verification step.
- Only include steps that a human needs to perform. Skip anything CI already covers.
- Order steps from cheapest to most expensive — local commands first, external integrations last.
- If there is a known risk or edge case worth watching, add a `Watch for:` line at the end — no checkbox, just a heads-up.
- Keep it short. 2-5 steps is typical. If you need more, the PR may be too large.

#### Structured format (required for every non-CI step)

Every validation step that is not a simple automated command must use this structure:

1. **Prerequisites** — what must be set up before testing (env vars, credentials, running services, test data, app state)
2. **Action** — the specific command, API request, or UI action to perform. Include full addresses and copy-pasteable commands.
3. **Expected result** — what the reviewer should observe, including specific fields, status codes, or visible behavior.
4. **Negative/edge cases** — include at least one when the feature introduces meaningful failure modes or graceful-degradation behavior.

Do not write vague steps like "test this with the real API" or "verify it works". Write the setup, action, and expected outcome clearly enough that someone unfamiliar with the project can execute the check without guessing.

#### Example (illustrative — adapt to your project)

Bad:
`- [ ] Verify the new command works`

Good:
`- [ ] **Walkthrough — run the new export command**: Prerequisites: build the project (`make` or project-equivalent). Action: run `./quest export --format json --output /tmp/out.json`, then inspect `/tmp/out.json`. Expected: valid JSON containing entries matching the current quest state, with `status` and `slug` fields populated. Then run with a nonexistent quest dir (`--quest-dir /tmp/bogus`) — observe a clear error message and non-zero exit code.`

The good example walks the reviewer through the feature so they understand what was built, not just whether it errors.

### Notes section (optional)

Use `## Notes` for important context reviewers should know before merge or rollout. Omit the section entirely if there is nothing non-obvious to add.

Rules:
- Include only non-obvious, high-value context (e.g., follow-up work, rollout caveats, compatibility constraints, temporary limitations).
- Do not duplicate the Summary section.
- Keep it concise.

### Bot-generated content

If a bot appends an auto-generated summary to the PR, leave it in place. Do not duplicate or conflict with its content in the human-written sections.

When updating an existing PR body, preserve bot-managed sections exactly:

- If the body contains bot-managed sections or hidden anchors/comments, keep those blocks unchanged.
- Regenerate only the human-authored section.
- Never remove, rewrite, or reorder bot-managed blocks, badges, or hidden anchors/comments.

### Draft mode (required)

- Always create PRs with the `--draft` flag.
- When updating an existing PR, do not change its draft status.

### Use gh CLI

- Create: `gh pr create --draft --title "..." --body "..."`
- Update: `gh pr edit <number> --title "..." --body "..."`
- Push first if the remote branch is behind: `git push -u origin HEAD`
- Run `gh` directly — do not wrap in `bash -lc` or `sh -c`. Permission prefixes only match when `gh` is the top-level command.

### Truthfulness

- Do not fabricate motivation or context.
- If intent is unclear, describe only what is visible in the commits and diff.
- Precise but narrow beats confident but wrong.

---

## Trailer

Append this block at the end of the PR body:

```html
<pre>
     ▐▛███▜▌
    ▝▜█████▛▘
      ▘▘ ▝▝
Quest/Co-Authored by
<model lines — one per model that participated>
in collaboration with <human author identity>
</pre>
```

Each model line uses standard `Co-Authored-By:` format:

```
Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
Co-Authored-By: Codex <noreply@openai.com>
```

Rules:

- **Only include models that actually participated** in the work being committed. Do not list a model that was not involved.
- If model participation is unclear, do not ask by default. Include only the current model when it clearly participated, and omit any other model you cannot verify.
- If the work was done through Quest, check quest artifacts first to identify participating models.
- If generating a squash commit for a PR, you may also check PR comments for clearly attributable model participation.
- Do not require PR metadata in non-PR contexts. If attribution remains uncertain after available checks, omit the unverified model.
- Use the specific model label (e.g., "Claude Opus 4.6", "Codex mini") when known from the session or quest artifacts.
- Known model email mappings:
  - Claude → `noreply@anthropic.com`
  - Codex / OpenAI → `noreply@openai.com`
  - OpenCode → `noreply@opencode.ai`
- Resolve `<human author identity>` from local git config when available:
  - Prefer `git config user.name` + `git config user.email` and format as `Name <email>`
  - If only a GitHub username can be inferred from git config or the remote URL, use that username
  - If no human identity can be verified, use `the repository author`
- The `in collaboration with` line is always present and always last.

Never omit the trailer.

---

## Approval

Always show the intended PR title and full body to the user and wait for explicit approval before executing `gh pr create` or `gh pr edit`. Do not create or update the PR automatically. Present the content as a plain text block and ask the user to confirm.

---

## Output

Output only the final PR title and body. Do not use emojis.
