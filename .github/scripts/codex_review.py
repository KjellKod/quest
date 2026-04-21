#!/usr/bin/env python3
"""Codex CI Review -- extracted from codex-ci-review.yml heredocs."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

# --- Shared utilities ---

VALID_SEVERITIES = {"blocker", "must-fix", "should-fix"}
DEEP_CI_EXTENSIONS = {".py", ".sh", ".js", ".ts"}
DEEP_CI_EXCLUDED_SEGMENTS = {
    "docs",
    "ideas",
    "generated",
    "vendor",
    "build",
    "dist",
    "node_modules",
}
DEEP_CI_LOCKFILES = {
    "package-lock.json",
    "npm-shrinkwrap.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "pipfile.lock",
}
DEEP_CI_MAX_CHANGES = 2000
DEEP_CI_MAX_FILE_CHARS = 20000
DEEP_CI_MAX_TOTAL_CHARS = 60000
DEEP_CI_MAX_FILES = 3
PROMPT_PLACEHOLDER_RE = re.compile(r"\{(PLACEHOLDER_[A-Z_]+)\}")


def normalize_severity(value):
    """Return normalized severity string or None."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if normalized in VALID_SEVERITIES else None


def escape_github_command_field(value):
    """Escape special chars for GitHub Actions workflow commands."""
    if value is None:
        return ""
    text = str(value)
    return (
        text.replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
        .replace(":", "%3A")
        .replace(",", "%2C")
    )


# --- Subcommand: gather-context ---


def _normalize_path_info(changed_file):
    """Return normalized PR file metadata for a path or gh ``files`` entry."""
    if isinstance(changed_file, str):
        return {"path": changed_file}
    if not isinstance(changed_file, dict):
        return {"path": ""}

    path = changed_file.get("path") or changed_file.get("filename") or changed_file.get("file")
    info = dict(changed_file)
    info["path"] = path or ""
    return info


def _path_segments(path):
    return [segment.lower() for segment in Path(path).parts if segment not in ("", ".")]


def _is_deleted_file(file_info):
    status_values = [
        file_info.get("status"),
        file_info.get("changeType"),
        file_info.get("change_type"),
    ]
    return any(str(value).lower() in {"removed", "deleted", "delete"} for value in status_values if value)


def _is_large_by_metadata(file_info, max_chars_per_file=DEEP_CI_MAX_FILE_CHARS):
    size = file_info.get("size")
    if isinstance(size, int) and size > max_chars_per_file:
        return True

    changes = file_info.get("changes")
    if isinstance(changes, int) and changes > DEEP_CI_MAX_CHANGES:
        return True

    additions = file_info.get("additions")
    deletions = file_info.get("deletions")
    if isinstance(additions, int) and isinstance(deletions, int):
        return additions + deletions > DEEP_CI_MAX_CHANGES

    return False


def is_deep_ci_candidate(path, file_info=None):
    """Return True when a changed file is eligible for Deep CI whole-file review."""
    if not isinstance(path, str) or not path:
        return False

    info = _normalize_path_info(file_info or {"path": path})
    if _is_deleted_file(info) or _is_large_by_metadata(info):
        return False

    lower_path = path.lower()
    name = Path(lower_path).name
    suffix = Path(lower_path).suffix
    if suffix not in DEEP_CI_EXTENSIONS:
        return False
    if name in DEEP_CI_LOCKFILES or ".lock." in name:
        return False
    if name.endswith(".min.js") or name.endswith(".min.ts") or ".min." in name:
        return False
    if any(segment in DEEP_CI_EXCLUDED_SEGMENTS for segment in _path_segments(lower_path)):
        return False

    return True


def select_deep_ci_files(changed_files, max_files=DEEP_CI_MAX_FILES):
    """Select a deterministic, path-sorted subset of Deep CI candidate paths."""
    candidates = []
    seen = set()
    for changed_file in changed_files:
        info = _normalize_path_info(changed_file)
        path = info["path"]
        if path in seen:
            continue
        if is_deep_ci_candidate(path, info):
            candidates.append(path)
            seen.add(path)

    return sorted(candidates)[:max_files]


def _deep_ci_omitted_note(path, reason):
    return {
        "path": path,
        "content": "",
        "omitted": True,
        "reason": reason,
    }


def markdown_code_fence(content):
    """Return a backtick fence longer than any run inside content."""
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", content)), default=0)
    return "`" * max(3, longest + 1)


def fetch_deep_ci_files(
    repo,
    head_sha,
    selected_files,
    max_chars_per_file=DEEP_CI_MAX_FILE_CHARS,
    max_total_chars=DEEP_CI_MAX_TOTAL_CHARS,
):
    """Fetch selected PR-head full files as read-only Deep CI snapshots.

    Over-cap and unavailable files are omitted entirely from the whole-file pass.
    """
    snapshots = []
    total_chars = 0
    for path in selected_files:
        encoded_path = quote(path, safe="/")
        cmd = [
            "gh",
            "api",
            "-H",
            "Accept: application/vnd.github.raw",
            f"repos/{repo}/contents/{encoded_path}?ref={head_sha}",
        ]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() or exc.stdout.strip() or "unable to fetch current PR-head file"
            snapshots.append(_deep_ci_omitted_note(path, f"unavailable: {detail}"))
            continue

        content = result.stdout
        if len(content) > max_chars_per_file:
            snapshots.append(
                _deep_ci_omitted_note(
                    path,
                    f"current file size exceeds {max_chars_per_file} chars",
                )
            )
            continue
        if total_chars + len(content) > max_total_chars:
            snapshots.append(
                _deep_ci_omitted_note(
                    path,
                    f"Deep CI total content cap exceeds {max_total_chars} chars",
                )
            )
            continue

        total_chars += len(content)
        snapshots.append({"path": path, "content": content, "omitted": False, "reason": ""})

    return snapshots


def render_deep_ci_context(snapshots, selected_files=None):
    """Render Deep CI snapshots and omission notes as prompt markdown."""
    if not snapshots:
        return "No eligible changed code files selected for Deep CI whole-file review.\n"

    rendered = []
    selected_count = len(selected_files or snapshots)
    rendered.append(
        f"Selected {selected_count} changed code file(s) for bounded Deep CI whole-file review."
    )
    for snapshot in snapshots:
        path = snapshot["path"]
        if snapshot.get("omitted"):
            rendered.append(
                "## "
                + path
                + "\n"
                + f"Skipped Deep CI whole-file review for {path} because {snapshot['reason']}."
            )
            continue
        content = snapshot["content"].rstrip()
        fence = markdown_code_fence(content)
        rendered.append(f"## {path}\n{fence}\n{content}\n{fence}")

    return "\n\n".join(rendered).strip() + "\n"


def load_changed_file_metadata(path="/tmp/changed_files.json"):
    """Load gh PR file metadata, falling back to the legacy path list."""
    metadata_path = Path(path)
    if metadata_path.exists():
        try:
            loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("files"), list):
                return loaded["files"]
            if isinstance(loaded, list):
                return loaded
        except (json.JSONDecodeError, OSError):
            pass

    return [
        line.strip()
        for line in Path("/tmp/changed_files.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def fetch_head_files(repo, head_sha, changed_files, max_files=12, max_chars=12000):
    """Fetch file snapshots and return rendered markdown sections."""
    rendered = []
    for path in changed_files[:max_files]:
        encoded_path = quote(path, safe='/')
        cmd = [
            'gh', 'api',
            '-H', 'Accept: application/vnd.github.raw',
            f'repos/{repo}/contents/{encoded_path}?ref={head_sha}',
        ]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            content = result.stdout
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.strip() or exc.stdout.strip() or 'unable to fetch file snapshot'
            content = f'[unavailable: {detail}]'

        if len(content) > max_chars:
            content = content[:max_chars] + '\n... [truncated]\n'

        rendered.append(f'## {path}\n```\n{content.rstrip()}\n```')

    if len(changed_files) > max_files:
        rendered.append(
            f'## Additional changed files omitted\nOnly the first {max_files} changed files are included here for context. '
            'Use the diff as the source of truth for the full change set.'
        )

    return rendered


def gather_context():
    """Entry point for gather-context subcommand.

    Reads env: REPO.
    Reads: /tmp/pr_head_sha.txt, /tmp/changed_files.txt
    Writes: /tmp/pr_head_files.md
    """
    repo = os.environ['REPO']
    head_sha = Path('/tmp/pr_head_sha.txt').read_text(encoding='utf-8').strip()
    changed_files = [
        line.strip()
        for line in Path('/tmp/changed_files.txt').read_text(encoding='utf-8').splitlines()
        if line.strip()
    ]

    rendered = fetch_head_files(repo, head_sha, changed_files)
    Path('/tmp/pr_head_files.md').write_text('\n\n'.join(rendered).strip() + '\n', encoding='utf-8')

    changed_file_metadata = load_changed_file_metadata()
    selected_deep_ci_files = select_deep_ci_files(changed_file_metadata)
    deep_ci_snapshots = fetch_deep_ci_files(repo, head_sha, selected_deep_ci_files)
    deep_ci_context = render_deep_ci_context(deep_ci_snapshots, selected_deep_ci_files)
    Path('/tmp/deep_ci_files.md').write_text(deep_ci_context, encoding='utf-8')


# --- Subcommand: build-prompt ---


def build_review_prompt(template_text, replacements):
    """Replace prompt placeholders with gathered PR context in one template pass."""
    return PROMPT_PLACEHOLDER_RE.sub(
        lambda match: replacements.get(match.group(1), match.group(0)),
        template_text,
    )


def _read_text_if_exists(path):
    file_path = Path(path)
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8")


def build_prompt():
    """Entry point for build-prompt subcommand.

    Reads: prompt template and /tmp gathered context files.
    Writes: /tmp/review-prompt.md
    """
    template = Path(".github/codex-review-prompt.md").read_text(encoding="utf-8")
    prompt = build_review_prompt(
        template,
        {
            "PLACEHOLDER_PR_DESCRIPTION": _read_text_if_exists("/tmp/pr_description.txt"),
            "PLACEHOLDER_EXISTING_COMMENTS": _read_text_if_exists("/tmp/existing_comments.json"),
            "PLACEHOLDER_PR_HEAD_FILES": _read_text_if_exists("/tmp/pr_head_files.md"),
            "PLACEHOLDER_DEEP_CI_FILES": _read_text_if_exists("/tmp/deep_ci_files.md"),
            "PLACEHOLDER_DIFF": _read_text_if_exists("/tmp/pr.diff"),
        },
    )
    Path("/tmp/review-prompt.md").write_text(prompt, encoding="utf-8")


# --- Subcommand: post-review ---


def parse_review_output(raw):
    """Parse AI review JSON from raw text. Returns list or None.

    Tries four strategies in order:
    1. Direct JSON parse
    2. Strip all markdown fences then parse
    3. Extract from individual fenced code blocks
    4. Regex search for any JSON array in fence-stripped text
    """
    comments = None

    # Strategy 1: direct JSON parse
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            comments = parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: strip markdown fences
    if comments is None:
        stripped = re.sub(r'```[\w]*\n?', '', raw)
        try:
            parsed = json.loads(stripped.strip())
            if isinstance(parsed, list):
                comments = parsed
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3: extract from fenced code blocks
    if comments is None:
        for fence_match in re.finditer(r'```(?:json)?\s*\n(.*?)```', raw, re.DOTALL):
            try:
                parsed = json.loads(fence_match.group(1))
                if isinstance(parsed, list):
                    comments = parsed
                    break
            except (json.JSONDecodeError, ValueError):
                continue

    # Strategy 4: find any JSON array in fence-stripped text
    if comments is None:
        # Use the same stripped text from strategy 2
        stripped = re.sub(r'```[\w]*\n?', '', raw)
        for match in re.finditer(r'\[.*?\]', stripped, re.DOTALL):
            try:
                candidate = json.loads(match.group())
                if isinstance(candidate, list):
                    comments = candidate
                    break
            except (json.JSONDecodeError, ValueError):
                continue

    return comments


def is_valid_comment(c, severity_stats):
    """Validate and normalize a single comment dict in-place. Returns bool.

    Mutates ``c`` to set defaults (side) and normalize severity.
    Increments ``severity_stats["stripped"]`` when an invalid severity is removed.
    """
    if not isinstance(c, dict):
        return False
    if not (isinstance(c.get("path"), str) and c["path"]):
        return False
    if not (isinstance(c.get("body"), str) and c["body"]):
        return False
    try:
        c["line"] = int(c["line"])
    except (TypeError, ValueError):
        return False
    if c["line"] < 1:
        return False
    if c.get("side") not in ("LEFT", "RIGHT"):
        c["side"] = "RIGHT"
    severity = c.get("severity")
    if severity is None:
        return True
    normalized_severity = normalize_severity(severity)
    if normalized_severity is None:
        c.pop("severity", None)
        severity_stats["stripped"] += 1
    else:
        c["severity"] = normalized_severity
    return True


def extract_keywords(body):
    """Extract meaningful words (4+ chars) for fuzzy dedup matching."""
    words = set(re.findall(r'[a-z][a-z0-9_.-]{3,}', body.lower()))
    # Remove common filler words
    words -= {"this", "that", "with", "from", "have", "been", "should",
              "could", "would", "must", "which", "when", "into", "more",
              "than", "also", "only", "will", "does", "about", "because",
              "review", "automated", "openai", "codex", "comment", "file"}
    return words


def build_dedup_state(existing_comments):
    """Build dedup state from existing comments.

    Returns (resolved_locations, bot_commented_locations, bot_concerns).
    """
    bot_comment_ids = {}  # id -> {path, line}
    for ex in existing_comments:
        if ex.get("user") == "github-actions[bot]":
            bot_comment_ids[ex.get("id")] = {
                "path": ex.get("path"),
                "line": ex.get("line"),
            }

    resolved_locations = set()  # (path, line) tuples where human replied
    for ex in existing_comments:
        reply_to = ex.get("in_reply_to_id")
        if reply_to and ex.get("user") != "github-actions[bot]":
            parent = bot_comment_ids.get(reply_to)
            if parent:
                resolved_locations.add((parent["path"], parent.get("line")))

    # Also build set of (path, line) where bot already commented (any wording)
    bot_commented_locations = set()
    for ex in existing_comments:
        if ex.get("user") == "github-actions[bot]" and ex.get("path"):
            bot_commented_locations.add((ex["path"], ex.get("line")))

    bot_concerns = []  # list of {path, line, keywords}
    for ex in existing_comments:
        if ex.get("user") == "github-actions[bot]" and ex.get("body"):
            bot_concerns.append({
                "path": ex.get("path"),
                "line": ex.get("line"),
                "keywords": extract_keywords(ex["body"]),
            })

    return resolved_locations, bot_commented_locations, bot_concerns


def is_duplicate(new_comment, resolved_locations, bot_commented_locations, bot_concerns):
    """Check if comment is duplicate. Returns reason string or None."""
    new_path = new_comment.get("path", "")
    new_line = new_comment.get("line")

    # Hard block: human already replied on this exact location
    if (new_path, new_line) in resolved_locations:
        return "resolved"

    # Hard block: bot already commented on this exact path+line
    if (new_path, new_line) in bot_commented_locations:
        return "already-commented"

    # Fuzzy block: same path, high keyword overlap with existing bot comment
    new_kw = extract_keywords(new_comment.get("body", ""))
    for bc in bot_concerns:
        if bc["path"] != new_path:
            continue
        if not bc["keywords"] or not new_kw:
            continue
        overlap = len(new_kw & bc["keywords"])
        union = len(new_kw | bc["keywords"])
        if union > 0 and overlap / union > 0.4:
            return "similar-concern"

    return None


def post_comments(comments, repo, pr_number, commit_sha):
    """Post inline review comments via gh API. Returns (posted_count, failed_list)."""
    posted = 0
    failed = []

    for idx, c in enumerate(comments):
        severity = c.get("severity") or "none"
        print(
            f"[{idx}] posting path={escape_github_command_field(c['path'])} "
            f"line={escape_github_command_field(c['line'])} "
            f"side={escape_github_command_field(c.get('side', 'RIGHT'))} "
            f"severity={escape_github_command_field(severity)}"
        )
        payload = {
            "body": c["body"],
            "commit_id": commit_sha,
            "path": c["path"],
            "line": c["line"],
            "side": c.get("side", "RIGHT"),
        }

        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            json.dump(payload, tf)
            temp_path = tf.name

        result = subprocess.run(
            [
                "gh",
                "api",
                "-X",
                "POST",
                f"repos/{repo}/pulls/{pr_number}/comments",
                "--input",
                temp_path,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            posted += 1
        else:
            failed.append(
                {
                    "index": idx,
                    "path": c.get("path"),
                    "line": c.get("line"),
                    "side": c.get("side"),
                    "severity": severity,
                    "error": (result.stderr or result.stdout or "").strip(),
                }
            )

    return posted, failed


def post_fallback_review(repo, pr_number, num_candidates):
    """Post a fallback PR review comment when all inline posts fail."""
    fallback_payload = {
        "event": "COMMENT",
        "body": (
            "Automated review generated findings, but inline posting failed for all "
            f"{num_candidates} candidate comment(s). "
            "This is advisory-only by default; check workflow logs for details."
        ),
    }
    with tempfile.NamedTemporaryFile("w", delete=False) as tf:
        json.dump(fallback_payload, tf)
        fallback_path = tf.name

    fallback_result = subprocess.run(
        [
            "gh",
            "api",
            "-X",
            "POST",
            f"repos/{repo}/pulls/{pr_number}/reviews",
            "--input",
            fallback_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if fallback_result.returncode != 0:
        fallback_error = (
            fallback_result.stderr or fallback_result.stdout or "unknown error"
        ).strip()
        print(
            "::warning::Failed to post PR-visible fallback review comment: "
            + fallback_error[:500]
        )


def post_review():
    """Entry point for post-review subcommand.

    Reads env: REPO, PR_NUMBER, COMMIT_SHA, STRICT_INLINE_POSTING.
    Reads: /tmp/review-output.json, /tmp/existing_comments.json
    """
    raw = open("/tmp/review-output.json").read()

    comments = parse_review_output(raw)

    if comments is None:
        print("No review comments -- could not parse JSON array from output.")
        sys.exit(0)

    if not isinstance(comments, list) or not comments:
        print("No review comments.")
        sys.exit(0)

    severity_stats = {"stripped": 0}

    valid = [c for c in comments if is_valid_comment(c, severity_stats)]
    if not valid:
        print("No valid review comments after structural validation.")
        sys.exit(0)
    if len(valid) < len(comments):
        print(f"Filtered {len(comments) - len(valid)} malformed comment(s).")
    if severity_stats["stripped"]:
        print(
            f"Ignored invalid structured severity on {severity_stats['stripped']} comment(s); "
            "preserving body-based behavior."
        )
    comments = valid

    # --- Dedup: filter out already-discussed and resolved concerns ---
    existing = []
    try:
        existing = json.load(open("/tmp/existing_comments.json"))
    except Exception:
        pass

    resolved_locations, bot_commented_locations, bot_concerns = build_dedup_state(existing)

    before_count = len(comments)
    skipped = {"resolved": 0, "already-commented": 0, "similar-concern": 0}
    filtered = []
    for c in comments:
        reason = is_duplicate(c, resolved_locations, bot_commented_locations, bot_concerns)
        if reason:
            skipped[reason] = skipped.get(reason, 0) + 1
        else:
            filtered.append(c)
    comments = filtered
    total_skipped = before_count - len(comments)

    if total_skipped:
        parts = [f"{v} {k}" for k, v in skipped.items() if v > 0]
        print(f"Skipped {total_skipped} comment(s): {', '.join(parts)}.")

    if not comments:
        print("All comments were duplicates or already resolved. Nothing new to post.")
        sys.exit(0)

    repo = os.environ['REPO']
    pr_number = os.environ['PR_NUMBER']
    commit_sha = os.environ['COMMIT_SHA']

    print(f"Posting {len(comments)} new inline comment(s) against commit {commit_sha[:8]}.")

    posted, failed = post_comments(comments, repo, pr_number, commit_sha)

    print(f"Posted {posted} inline comment(s). Failed: {len(failed)}.")

    if failed:
        print("::warning::Some inline comments could not be posted (often invalid path/line).")
        for f in failed:
            print(
                f"::warning::[{escape_github_command_field(f['index'])}] "
                f"path={escape_github_command_field(f['path'])} "
                f"line={escape_github_command_field(f['line'])} "
                f"side={escape_github_command_field(f['side'])} "
                f"severity={escape_github_command_field(f['severity'])} "
                f"error={escape_github_command_field(f['error'][:500])}"
            )

    if posted == 0 and comments:
        strict = os.environ.get("STRICT_INLINE_POSTING", "false").lower() in (
            "1",
            "true",
            "yes",
        )
        print("::warning::No inline comments were posted; all candidate comments failed.")

        post_fallback_review(repo, pr_number, len(comments))

        if strict:
            print("::error::STRICT_INLINE_POSTING is enabled; failing job.")
            sys.exit(1)


# --- Main dispatch ---

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: codex_review.py <gather-context|build-prompt|post-review>", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "gather-context":
        gather_context()
    elif cmd == "build-prompt":
        build_prompt()
    elif cmd == "post-review":
        post_review()
    else:
        print(f"Unknown subcommand: {cmd}", file=sys.stderr)
        sys.exit(1)
