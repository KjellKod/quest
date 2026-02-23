# Installing Quest for Codex (What I Did Exactly)

## Why Quest Was Not Showing Up
Quest was installed in a repository (`.agents/skills/quest`) but **not** in Codex's global skills directory (`~/.codex/skills`).

Codex only lists globally installed skills from `~/.codex/skills` (plus system skills), so repo-local files alone may not appear in available skills.

## Exact Checks I Ran

1. Verified Quest existed in repo-local location:
```bash
ls -la /Users/kjell/ws/extra/internal-slack-automation-platform/.agents/skills/quest
sed -n '1,220p' /Users/kjell/ws/extra/internal-slack-automation-platform/.agents/skills/quest/SKILL.md
```

2. Verified global Codex skills did **not** include Quest yet:
```bash
ls -la /Users/kjell/.codex/skills
find /Users/kjell/.codex/skills -maxdepth 3 -type f -name 'SKILL.md' | sort
```

At that point only `.system` skills were present globally.

## Exact Install Command I Ran
First attempt (direct script execution) failed with permission/executable issue:
```bash
/Users/kjell/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo KjellKod/quest \
  --path .agents/skills/quest \
  --name quest
```

Successful command (run via Python):
```bash
python3 /Users/kjell/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo KjellKod/quest \
  --path .agents/skills/quest \
  --name quest
```

Installer output:
- `Installed quest to /Users/kjell/.codex/skills/quest`

## Verification I Ran After Install
```bash
ls -la /Users/kjell/.codex/skills
ls -la /Users/kjell/.codex/skills/quest
sed -n '1,80p' /Users/kjell/.codex/skills/quest/SKILL.md
```

Confirmed:
- `~/.codex/skills/quest/SKILL.md` exists
- `name: quest` is present in the installed skill file

## Final Required Step
Restart Codex so it reloads skills.

If Quest still does not appear after restart, re-check:
- `~/.codex/skills/quest/SKILL.md` exists
- the file has valid frontmatter with `name: quest`

## Status
reference
