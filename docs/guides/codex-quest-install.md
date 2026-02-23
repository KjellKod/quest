# Installing Quest for Codex

## Why Quest May Not Show Up
Quest installed in a repository (`.agents/skills/quest`) is not automatically visible in Codex's global skill list. Codex discovers global skills from `~/.codex/skills` (plus system skills).

## Install Steps

1. Verify Quest exists in repo-local location:
```bash
ls -la .agents/skills/quest/SKILL.md
```

2. Install to global Codex skills:
```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo KjellKod/quest \
  --path .agents/skills/quest \
  --name quest
```

3. Verify installation:
```bash
ls -la ~/.codex/skills/quest/SKILL.md
```

4. Restart Codex so it reloads skills.

## Troubleshooting
If Quest still does not appear after restart, check:
- `~/.codex/skills/quest/SKILL.md` exists
- The file has valid frontmatter with `name: quest`
- Direct script execution may fail with permission issues — use `python3` prefix
