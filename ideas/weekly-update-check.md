# Weekly Update Check

## What
Quest automatically checks for updates once per week (or configurable interval) when a `/quest` command completes. If an update is available, it notifies the user and offers to run the installer.

## Why
- Users stay current with bug fixes and improvements without manual checking
- Non-intrusive: only triggers after quest completion, not during
- Opt-in update: user decides whether to apply
- Leverages existing checksum infrastructure (`checksums.txt`, `.quest-checksums`)
- "Set it and forget it" experience for adopters

## How It Works

### State Tracking
Store last check timestamp in `.quest-last-check`:
```
1707091200   # Unix timestamp of last successful check
```

### Check Logic (after quest completion)
1. Read `.quest-last-check` timestamp
2. If less than 7 days ago, skip (no network call)
3. Fetch upstream `checksums.txt` from `KjellKod/quest/main`
4. Compare checksum of upstream vs local `checksums.txt`
5. If different:
   ```
   Quest update available!
   Run: ./scripts/quest_installer.sh
   Or: ./scripts/quest_installer.sh --check (preview changes)
   ```
6. Update `.quest-last-check` with current timestamp

### Integration Point
Add to SKILL.md Step 7 (Complete) or as a new Step 8:
```bash
# Check for updates (non-blocking, after quest completes)
if [ -f "scripts/quest_installer.sh" ]; then
  LAST_CHECK_FILE=".quest-last-check"
  NOW=$(date +%s)
  WEEK=$((7 * 24 * 60 * 60))

  SHOULD_CHECK=true
  if [ -f "$LAST_CHECK_FILE" ]; then
    LAST_CHECK=$(cat "$LAST_CHECK_FILE")
    if [ $((NOW - LAST_CHECK)) -lt $WEEK ]; then
      SHOULD_CHECK=false
    fi
  fi

  if $SHOULD_CHECK; then
    UPSTREAM_HASH=$(curl -fsSL "https://raw.githubusercontent.com/KjellKod/quest/main/checksums.txt" 2>/dev/null | shasum -a 256 | cut -d' ' -f1)
    LOCAL_HASH=$(shasum -a 256 checksums.txt 2>/dev/null | cut -d' ' -f1)

    if [ "$UPSTREAM_HASH" != "$LOCAL_HASH" ]; then
      echo ""
      echo -n "Quest update available. Update now? [Y/n] "
      read -r response
      if [ "$response" != "n" ] && [ "$response" != "N" ]; then
        ./scripts/quest_installer.sh
      fi
    fi

    echo "$NOW" > "$LAST_CHECK_FILE"
  fi
fi
```

## Configuration Options

Could add to `.ai/allowlist.json`:
```json
{
  "update_check": {
    "enabled": true,
    "interval_days": 7,
    "auto_notify": true
  }
}
```

Or keep it simple with no configuration (always check weekly, always notify).

## Approach Options

### Option A: Check in SKILL.md (Recommended)
- Add check logic to Step 7 (Complete)
- Transparent: visible in skill definition
- Uses Bash tool, no new scripts needed

### Option B: Standalone script
- New `scripts/quest_check_update.sh`
- Called by SKILL.md or manually
- Cleaner separation, reusable outside quests

### Option C: Flag on installer
- `quest_installer.sh --check-update-available`
- Returns exit code 0 if update available, 1 if current
- SKILL.md calls this after completion

## Acceptance Criteria

1. After `/quest` completes successfully, check runs (if 7+ days since last)
2. Check is fast (single HTTP request, ~1 second)
3. No check during quest execution (only after completion)
4. User prompted: "Quest update available. Update now? [Y/n]"
5. If user accepts, installer runs inline
6. `.quest-last-check` updated after each check (even if no update)
7. `.quest-last-check` added to `.gitignore`
8. Works offline gracefully (network errors silently ignored)
9. Opt-out via `update_check.enabled: false` in allowlist

## Decisions

1. **Opt-out via allowlist**: Yes - add `update_check.enabled` to `.ai/allowlist.json` (default: true)
2. **Interactive prompt**: Yes - prompt user directly:
   ```
   Quest update available. Update now? [Y/n]
   ```
   If yes, run the installer inline.
3. **Gitignore `.quest-last-check`**: Yes - it's local state per machine

## Status
implemented
