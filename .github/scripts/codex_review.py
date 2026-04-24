#!/usr/bin/env python3
"""Codex CI Review -- extracted from codex-ci-review.yml heredocs."""

import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
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
DEEP_CI_CHUNK_CONTEXT_LINES = 100
DEEP_CI_MAX_CHUNKS_PER_FILE = 4
DEEP_CI_MAX_CHUNK_CHARS = 12000
DEEP_CI_MAX_FETCH_CHARS = 200000
DEEP_CI_REASON_EXCLUDED_PATH_SEGMENT = "excluded-path-segment"
DEEP_CI_REASON_LOCKFILE = "lockfile"
DEEP_CI_REASON_MINIFIED_FILE = "minified-file"
DEEP_CI_REASON_UNSUPPORTED_EXTENSION = "unsupported-extension"
DEEP_CI_REASON_DELETED_FILE = "deleted-file"
DEEP_CI_REASON_METADATA_TOO_LARGE = "metadata-too-large"
DEEP_CI_REASON_FETCH_TOO_LARGE = "fetch-too-large"
DEEP_CI_REASON_TOTAL_CAP_EXHAUSTED = "total-cap-exhausted"
DEEP_CI_REASON_NO_CHANGED_LINE_RANGES = "no-changed-line-ranges"
DEEP_CI_REASON_CHUNK_CAP_EXHAUSTED = "chunk-cap-exhausted"
DEEP_CI_REASON_UNAVAILABLE = "unavailable"
DEEP_CI_MANIFEST_VERSION = 1
DEEP_CI_MANIFEST_PATH = "/tmp/deep_ci_context_manifest.json"
PROMPT_PLACEHOLDER_RE = re.compile(r"\{(PLACEHOLDER_[A-Z_]+)\}")


def _utc_now():
    return datetime.now(timezone.utc)


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
    del max_chars_per_file  # metadata size no longer disqualifies chunk fallback candidates
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


def _classify_skip_reason(path, file_info):
    """Return a stable reason ID when a path is filtered out before selection."""
    if not isinstance(path, str) or not path:
        return None

    info = _normalize_path_info(file_info or {"path": path})
    if _is_deleted_file(info):
        return DEEP_CI_REASON_DELETED_FILE
    if _is_large_by_metadata(info):
        return DEEP_CI_REASON_METADATA_TOO_LARGE

    lower_path = path.lower()
    name = Path(lower_path).name
    suffix = Path(lower_path).suffix
    if name in DEEP_CI_LOCKFILES or ".lock." in name:
        return DEEP_CI_REASON_LOCKFILE
    if suffix not in DEEP_CI_EXTENSIONS:
        return DEEP_CI_REASON_UNSUPPORTED_EXTENSION
    if name.endswith(".min.js") or name.endswith(".min.ts") or ".min." in name:
        return DEEP_CI_REASON_MINIFIED_FILE
    if any(segment in DEEP_CI_EXCLUDED_SEGMENTS for segment in _path_segments(lower_path)):
        return DEEP_CI_REASON_EXCLUDED_PATH_SEGMENT
    return None


def _deep_ci_omitted_note(path, reason):
    return {
        "path": path,
        "mode": "skipped",
        "content": "",
        "chunks": [],
        "char_count": 0,
        "line_count": 0,
        "changed_line_ranges": [],
        "omitted": True,
        "reason": reason,
    }


def markdown_code_fence(content):
    """Return a backtick fence longer than any run inside content."""
    longest = max((len(match.group(0)) for match in re.finditer(r"`+", content)), default=0)
    return "`" * max(3, longest + 1)


def _merge_ranges(ranges):
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda value: (value[0], value[1]))
    merged = [sorted_ranges[0]]
    for start, end in sorted_ranges[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def parse_changed_line_ranges(diff_text):
    """Return path->right-side changed line ranges from a unified diff."""
    if not isinstance(diff_text, str) or not diff_text.strip():
        return {}

    per_path = {}
    current_path = None
    current_line = None
    pending_start = None
    pending_end = None
    hunk_re = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")

    def flush_pending():
        nonlocal pending_start, pending_end
        if current_path is None or pending_start is None or pending_end is None:
            pending_start = None
            pending_end = None
            return
        per_path.setdefault(current_path, []).append((pending_start, pending_end))
        pending_start = None
        pending_end = None

    for raw_line in diff_text.splitlines():
        line = raw_line.rstrip("\n")

        if current_line is None and line.startswith("+++ "):
            flush_pending()
            marker = line[4:]
            if marker == "/dev/null":
                current_path = None
            elif marker.startswith("b/"):
                current_path = marker[2:]
            else:
                current_path = marker
            current_line = None
            continue

        if line.startswith("diff --git "):
            flush_pending()
            current_line = None
            continue

        hunk_match = hunk_re.match(line)
        if hunk_match:
            flush_pending()
            current_line = int(hunk_match.group(1))
            continue

        if current_path is None or current_line is None:
            continue

        if line.startswith("+"):
            if pending_start is None:
                pending_start = current_line
            pending_end = current_line
            current_line += 1
            continue

        if line.startswith("-") and not line.startswith("---"):
            flush_pending()
            continue

        if line.startswith(" "):
            flush_pending()
            current_line += 1
            continue

        if line.startswith("\\"):
            continue

        flush_pending()

    flush_pending()

    return {path: _merge_ranges(ranges) for path, ranges in per_path.items() if ranges}


def build_line_windows(
    ranges,
    line_count,
    context_lines=DEEP_CI_CHUNK_CONTEXT_LINES,
    max_chunks=DEEP_CI_MAX_CHUNKS_PER_FILE,
    include_omitted=False,
):
    """Expand and merge line windows around changed ranges with deterministic caps."""
    if not ranges or line_count < 1:
        return {"included": [], "omitted": []} if include_omitted else []

    expanded = []
    for start, end in ranges:
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        if start < 1 or end < start:
            continue
        changed_start = max(1, min(start, line_count))
        changed_end = max(changed_start, min(end, line_count))
        expanded.append(
            {
                "start_line": max(1, changed_start - context_lines),
                "end_line": min(line_count, changed_end + context_lines),
                "changed_ranges": [(changed_start, changed_end)],
                "changed_line_count": changed_end - changed_start + 1,
            }
        )

    if not expanded:
        return {"included": [], "omitted": []} if include_omitted else []

    expanded.sort(key=lambda item: (item["start_line"], item["end_line"]))
    merged = [expanded[0]]
    for window in expanded[1:]:
        current = merged[-1]
        if window["start_line"] <= current["end_line"] + 1:
            current["end_line"] = max(current["end_line"], window["end_line"])
            current["changed_ranges"].extend(window["changed_ranges"])
            current["changed_ranges"] = _merge_ranges(current["changed_ranges"])
            current["changed_line_count"] = sum(
                (range_end - range_start + 1)
                for range_start, range_end in current["changed_ranges"]
            )
        else:
            merged.append(window)

    omitted = []
    if len(merged) > max_chunks:
        ranked = sorted(
            merged,
            key=lambda item: (
                -item["changed_line_count"],
                item["start_line"],
                item["end_line"],
            ),
        )[:max_chunks]
        ranked_ids = {id(item) for item in ranked}
        omitted = [item for item in merged if id(item) not in ranked_ids]
        merged = sorted(ranked, key=lambda item: (item["start_line"], item["end_line"]))

    if include_omitted:
        return {"included": merged, "omitted": omitted}

    return merged


def extract_line_chunk(content, start, end):
    """Extract a one-based inclusive line range from content."""
    lines = content.splitlines()
    if not lines:
        return ""
    start_line = max(1, start)
    end_line = min(len(lines), end)
    if end_line < start_line:
        return ""
    return "\n".join(lines[start_line - 1 : end_line])


def _text_len(lines):
    if not lines:
        return 0
    return sum(len(line) for line in lines) + max(0, len(lines) - 1)


def fit_chunk_to_char_cap(chunk, changed_lines, cap=DEEP_CI_MAX_CHUNK_CHARS):
    """Trim a chunk to cap while preserving changed lines when possible."""
    start_line = int(chunk.get("start_line", 1))
    end_line = int(chunk.get("end_line", start_line))
    content = chunk.get("content", "")
    lines = content.splitlines()
    if not lines:
        return {
            "start_line": start_line,
            "end_line": end_line,
            "content": "",
            "changed_lines_included": [],
            "changed_lines_omitted": sorted(changed_lines),
        }

    absolute_lines = list(range(start_line, start_line + len(lines)))
    changed = sorted(line for line in changed_lines if line in set(absolute_lines))

    if _text_len(lines) <= cap:
        return {
            "start_line": start_line,
            "end_line": end_line,
            "content": content,
            "changed_lines_included": changed,
            "changed_lines_omitted": [],
        }

    first_changed_idx = 0
    last_changed_idx = len(lines) - 1
    if changed:
        first_changed_idx = max(0, changed[0] - start_line)
        last_changed_idx = min(len(lines) - 1, changed[-1] - start_line)

    keep_start = 0
    keep_end = len(lines) - 1
    while (
        keep_start <= keep_end
        and _text_len(lines[keep_start : keep_end + 1]) > cap
        and (keep_start < first_changed_idx or keep_end > last_changed_idx)
    ):
        if keep_start < first_changed_idx:
            keep_start += 1
        if _text_len(lines[keep_start : keep_end + 1]) > cap and keep_end > last_changed_idx:
            keep_end -= 1

    kept_lines = lines[keep_start : keep_end + 1]
    if _text_len(kept_lines) > cap:
        keep_start = first_changed_idx
        selected = []
        current_len = 0
        for candidate in lines[keep_start:]:
            addition = len(candidate) + (1 if selected else 0)
            if selected and current_len + addition > cap:
                break
            if not selected and addition > cap:
                selected = [candidate[:cap]]
                current_len = len(selected[0])
                break
            selected.append(candidate)
            current_len += addition
        kept_lines = selected
        keep_end = keep_start + len(kept_lines) - 1

    kept_content = "\n".join(kept_lines)
    new_start = start_line + keep_start
    new_end = start_line + keep_end if kept_lines else new_start - 1
    included = [line for line in changed if new_start <= line <= new_end]
    omitted = [line for line in changed if line not in included]
    return {
        "start_line": new_start,
        "end_line": new_end,
        "content": kept_content,
        "changed_lines_included": included,
        "changed_lines_omitted": omitted,
    }


def _metadata_size_exceeds_hard_cap(file_info, max_fetch_chars):
    """Return True when PR file metadata reports a size exceeding the hard cap.

    Treat any missing or non-integer size field as "unknown size, proceed to
    fetch" so the post-fetch safeguard remains the backstop. GitHub's PR
    files endpoint does not guarantee a byte-size field, so we check a small
    allowlist of plausible keys that callers may populate (``size``,
    ``byteSize``, ``char_count``). The function never disqualifies a file
    based on line-count proxies like ``changes`` -- those are covered by
    ``_is_large_by_metadata`` during candidate selection, not the hard-cap
    pre-fetch guard.
    """
    if not isinstance(file_info, dict):
        return False
    for field in ("size", "byteSize", "char_count"):
        value = file_info.get(field)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value > max_fetch_chars:
            return True
    return False


def fetch_deep_ci_files(
    repo,
    head_sha,
    selected_files,
    changed_line_ranges=None,
    max_chars_per_file=DEEP_CI_MAX_FILE_CHARS,
    max_total_chars=DEEP_CI_MAX_TOTAL_CHARS,
    max_fetch_chars=DEEP_CI_MAX_FETCH_CHARS,
    context_lines=DEEP_CI_CHUNK_CONTEXT_LINES,
    max_chunks_per_file=DEEP_CI_MAX_CHUNKS_PER_FILE,
    max_chunk_chars=DEEP_CI_MAX_CHUNK_CHARS,
    file_metadata=None,
):
    """Fetch selected PR-head full/chunked files as read-only Deep CI snapshots."""
    snapshots = []
    total_chars = 0
    changed_line_ranges = changed_line_ranges or {}
    metadata_by_path = {}
    if isinstance(file_metadata, dict):
        metadata_by_path = file_metadata
    elif isinstance(file_metadata, list):
        for entry in file_metadata:
            info = _normalize_path_info(entry)
            path = info.get("path")
            if path:
                metadata_by_path[path] = info

    for path in selected_files:
        metadata = metadata_by_path.get(path) or {}
        # Pre-fetch guard: if PR metadata already tells us the file exceeds
        # the hard fetch cap, skip the gh api call entirely. This preserves
        # the F1 visibility behavior (rendered as Mode: skipped with a
        # hard-cap reason) without pulling the full body first.
        if _metadata_size_exceeds_hard_cap(metadata, max_fetch_chars):
            snapshots.append(
                _deep_ci_omitted_note(
                    path,
                    f"file exceeds Deep CI hard fetch cap of {max_fetch_chars} chars",
                )
            )
            continue

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
        line_count = len(content.splitlines())
        # Backstop: if metadata lacked a size field (or the size was under
        # the cap but the real file exceeds it), skip with the same reason
        # string as the pre-fetch path so downstream rendering is uniform.
        if len(content) > max_fetch_chars:
            snapshots.append(
                _deep_ci_omitted_note(
                    path,
                    f"file exceeds Deep CI hard fetch cap of {max_fetch_chars} chars",
                )
            )
            continue

        if len(content) <= max_chars_per_file:
            if total_chars + len(content) > max_total_chars:
                snapshots.append(_deep_ci_omitted_note(path, "total-cap-exhausted"))
                continue
            total_chars += len(content)
            snapshots.append(
                {
                    "path": path,
                    "mode": "full",
                    "content": content,
                    "chunks": [],
                    "char_count": len(content),
                    "line_count": line_count,
                    "changed_line_ranges": changed_line_ranges.get(path, []),
                    "omitted": False,
                    "reason": "",
                }
            )
            continue

        ranges = changed_line_ranges.get(path, [])
        if not ranges:
            snapshots.append(
                _deep_ci_omitted_note(path, "no changed-line ranges found for oversized file")
            )
            continue

        window_plan = build_line_windows(
            ranges,
            line_count,
            context_lines=context_lines,
            max_chunks=max_chunks_per_file,
            include_omitted=True,
        )
        windows = window_plan["included"]
        chunk_cap_omitted_windows = [
            {"start_line": window["start_line"], "end_line": window["end_line"]}
            for window in window_plan["omitted"]
        ]
        if not windows:
            snapshots.append(
                _deep_ci_omitted_note(path, "no changed-line ranges found for oversized file")
            )
            continue

        chunks = []
        total_cap_omitted_windows = []
        for idx, window in enumerate(windows):
            start_line = window["start_line"]
            end_line = window["end_line"]
            changed_lines = []
            for range_start, range_end in window["changed_ranges"]:
                changed_lines.extend(range(range_start, range_end + 1))
            changed_lines = sorted(set(changed_lines))
            raw_chunk = {
                "start_line": start_line,
                "end_line": end_line,
                "content": extract_line_chunk(content, start_line, end_line),
            }
            fitted_chunk = fit_chunk_to_char_cap(
                raw_chunk,
                changed_lines,
                cap=max_chunk_chars,
            )
            chunk_content = fitted_chunk["content"]
            if not chunk_content:
                continue
            chunk_chars = len(chunk_content)
            if total_chars + chunk_chars > max_total_chars:
                # Total cap reached mid-file: record every remaining planned
                # window (including this one) so rendering can surface the
                # dropped ranges explicitly rather than silently truncating.
                total_cap_omitted_windows = [
                    {"start_line": w["start_line"], "end_line": w["end_line"]}
                    for w in windows[idx:]
                ]
                break
            total_chars += chunk_chars
            chunks.append(
                {
                    "start_line": fitted_chunk["start_line"],
                    "end_line": fitted_chunk["end_line"],
                    "content": chunk_content,
                    "changed_lines": changed_lines,
                    "changed_lines_included": fitted_chunk["changed_lines_included"],
                    "changed_lines_omitted": fitted_chunk["changed_lines_omitted"],
                }
            )

        if not chunks:
            snapshots.append(_deep_ci_omitted_note(path, "total-cap-exhausted"))
            continue

        snapshots.append(
            {
                "path": path,
                "mode": "chunked",
                "content": "",
                "chunks": chunks,
                "char_count": len(content),
                "line_count": line_count,
                "changed_line_ranges": ranges,
                "chunk_cap_omitted_windows": chunk_cap_omitted_windows,
                "total_cap_omitted_windows": total_cap_omitted_windows,
                "omitted": False,
                "reason": (
                    f"full file exceeded {max_chars_per_file} chars; only changed-line windows are included"
                ),
            }
        )

    return snapshots


def _coerce_manifest_ranges(ranges):
    normalized = []
    for value in ranges or []:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            continue
        start, end = value
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        normalized.append((start, end))
    return sorted(normalized, key=lambda item: (item[0], item[1]))


def _coerce_manifest_windows(windows):
    normalized = []
    for window in windows or []:
        if not isinstance(window, dict):
            continue
        start = window.get("start_line")
        end = window.get("end_line")
        if not isinstance(start, int) or not isinstance(end, int):
            continue
        normalized.append({"start_line": start, "end_line": end})
    return sorted(normalized, key=lambda item: (item["start_line"], item["end_line"]))


def _map_fetch_omission_reason(reason):
    text = str(reason or "").strip().lower()
    if text.startswith("file exceeds deep ci hard fetch cap"):
        return DEEP_CI_REASON_FETCH_TOO_LARGE
    if text.startswith("total-cap-exhausted"):
        return DEEP_CI_REASON_TOTAL_CAP_EXHAUSTED
    if text.startswith("no changed-line ranges"):
        return DEEP_CI_REASON_NO_CHANGED_LINE_RANGES
    if text.startswith("chunk-cap-exhausted"):
        return DEEP_CI_REASON_CHUNK_CAP_EXHAUSTED
    if text.startswith("unavailable:"):
        return DEEP_CI_REASON_UNAVAILABLE
    if text in {
        DEEP_CI_REASON_FETCH_TOO_LARGE,
        DEEP_CI_REASON_TOTAL_CAP_EXHAUSTED,
        DEEP_CI_REASON_NO_CHANGED_LINE_RANGES,
        DEEP_CI_REASON_CHUNK_CAP_EXHAUSTED,
        DEEP_CI_REASON_UNAVAILABLE,
        DEEP_CI_REASON_EXCLUDED_PATH_SEGMENT,
        DEEP_CI_REASON_LOCKFILE,
        DEEP_CI_REASON_MINIFIED_FILE,
        DEEP_CI_REASON_UNSUPPORTED_EXTENSION,
        DEEP_CI_REASON_DELETED_FILE,
        DEEP_CI_REASON_METADATA_TOO_LARGE,
    }:
        return text
    return DEEP_CI_REASON_UNAVAILABLE


def _normalize_file_metadata(changed_files, file_metadata=None):
    metadata_by_path = {}
    all_paths = []
    seen = set()

    for entry in changed_files or []:
        info = _normalize_path_info(entry)
        path = info.get("path") or ""
        if not path:
            continue
        if path not in seen:
            all_paths.append(path)
            seen.add(path)
        metadata_by_path[path] = info

    if isinstance(file_metadata, dict):
        for raw_path, raw_info in file_metadata.items():
            info = _normalize_path_info(raw_info if isinstance(raw_info, dict) else {"path": raw_path})
            path = info.get("path") or raw_path
            if not path:
                continue
            if path not in seen:
                all_paths.append(path)
                seen.add(path)
            metadata_by_path[path] = info
    elif isinstance(file_metadata, list):
        for entry in file_metadata:
            info = _normalize_path_info(entry)
            path = info.get("path") or ""
            if not path:
                continue
            if path not in seen:
                all_paths.append(path)
                seen.add(path)
            metadata_by_path[path] = info

    return all_paths, metadata_by_path


def build_deep_ci_manifest(
    repo,
    head_sha,
    changed_files,
    changed_line_ranges=None,
    file_metadata=None,
    *,
    source=None,
    budget=None,
    clock=_utc_now,
    fetch=fetch_deep_ci_files,
):
    """Build canonical metadata-only Deep CI manifest for this review run."""
    if isinstance(changed_files, dict) and isinstance(changed_files.get("files"), list):
        changed_files = changed_files["files"]
    elif not isinstance(changed_files, list):
        changed_files = changed_files or []

    changed_line_ranges = changed_line_ranges or {}
    source = source or {}
    budget = budget or {}

    max_files = int(budget.get("max_files", DEEP_CI_MAX_FILES))
    max_total_chars = int(budget.get("max_total_chars", DEEP_CI_MAX_TOTAL_CHARS))
    max_file_chars = int(budget.get("max_file_chars", DEEP_CI_MAX_FILE_CHARS))
    max_fetch_chars = int(budget.get("max_fetch_chars", DEEP_CI_MAX_FETCH_CHARS))
    max_chunks_per_file = int(budget.get("max_chunks_per_file", DEEP_CI_MAX_CHUNKS_PER_FILE))
    max_chunk_chars = int(budget.get("max_chunk_chars", DEEP_CI_MAX_CHUNK_CHARS))
    context_lines = int(budget.get("context_lines", DEEP_CI_CHUNK_CONTEXT_LINES))

    _, metadata_by_path = _normalize_file_metadata(changed_files, file_metadata)
    selected_files = select_deep_ci_files(changed_files or [], max_files=max_files)
    selected_set = set(selected_files)
    omitted_candidates_by_path = {}

    for path in sorted(metadata_by_path):
        if path in selected_set:
            continue
        info = metadata_by_path.get(path) or {"path": path}
        reason = _classify_skip_reason(path, info)
        if reason is None and is_deep_ci_candidate(path, info):
            reason = DEEP_CI_REASON_TOTAL_CAP_EXHAUSTED
        if reason:
            omitted_candidates_by_path[path] = {
                "path": path,
                "mode": "skipped",
                "reason": reason,
            }

    snapshots = fetch(
        repo,
        head_sha,
        selected_files,
        changed_line_ranges=changed_line_ranges,
        max_chars_per_file=max_file_chars,
        max_total_chars=max_total_chars,
        max_fetch_chars=max_fetch_chars,
        context_lines=context_lines,
        max_chunks_per_file=max_chunks_per_file,
        max_chunk_chars=max_chunk_chars,
        file_metadata=file_metadata,
    )

    files = []
    used_total_chars = 0
    for snapshot in snapshots:
        path = snapshot.get("path")
        if not path:
            continue

        mode = snapshot.get("mode", "skipped")
        if snapshot.get("omitted") or mode == "skipped":
            omitted_candidates_by_path[path] = {
                "path": path,
                "mode": "skipped",
                "reason": _map_fetch_omission_reason(snapshot.get("reason", "")),
            }
            continue

        if mode == "full":
            char_count = int(snapshot.get("char_count", len(snapshot.get("content", ""))))
            used_total_chars += char_count
            files.append(
                {
                    "path": path,
                    "mode": "full",
                    "char_count": char_count,
                    "line_count": int(snapshot.get("line_count", 0)),
                    "changed_line_ranges": _coerce_manifest_ranges(
                        snapshot.get("changed_line_ranges", [])
                    ),
                    "omitted": False,
                    "reason": "",
                }
            )
            continue

        if mode != "chunked":
            omitted_candidates_by_path[path] = {
                "path": path,
                "mode": "skipped",
                "reason": DEEP_CI_REASON_UNAVAILABLE,
            }
            continue

        chunks = []
        chunk_content_chars = 0
        for chunk in snapshot.get("chunks", []):
            content = chunk.get("content", "")
            chunk_content_chars += len(content)
            included = chunk.get("changed_lines_included")
            if not isinstance(included, list):
                included = chunk.get("changed_lines", [])
            omitted = chunk.get("changed_lines_omitted") or []
            chunks.append(
                {
                    "start_line": int(chunk.get("start_line", 0)),
                    "end_line": int(chunk.get("end_line", 0)),
                    "changed_lines_included": sorted(
                        value for value in included if isinstance(value, int)
                    ),
                    "changed_lines_omitted": sorted(
                        value for value in omitted if isinstance(value, int)
                    ),
                }
            )

        used_total_chars += chunk_content_chars
        files.append(
            {
                "path": path,
                "mode": "chunked",
                "char_count": int(snapshot.get("char_count", 0)),
                "line_count": int(snapshot.get("line_count", 0)),
                "changed_line_ranges": _coerce_manifest_ranges(snapshot.get("changed_line_ranges", [])),
                "chunks": sorted(chunks, key=lambda item: item["start_line"]),
                "chunk_cap_omitted_windows": _coerce_manifest_windows(
                    snapshot.get("chunk_cap_omitted_windows")
                ),
                "total_cap_omitted_windows": _coerce_manifest_windows(
                    snapshot.get("total_cap_omitted_windows")
                ),
                "omitted": False,
                "reason": "",
            }
        )

    now = clock() if callable(clock) else _utc_now()
    if not isinstance(now, datetime):
        now = _utc_now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    generated_at = now.replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")

    files = sorted(files, key=lambda item: item["path"])
    omitted_candidates = sorted(
        omitted_candidates_by_path.values(),
        key=lambda item: item["path"],
    )
    return {
        "version": DEEP_CI_MANIFEST_VERSION,
        "generated_at": generated_at,
        "source": source,
        "budget": {
            "max_files": max_files,
            "selected_files": len(files),
            "max_total_chars": max_total_chars,
            "used_total_chars": used_total_chars,
            "remaining_total_chars": max_total_chars - used_total_chars,
            "max_file_chars": max_file_chars,
            "max_fetch_chars": max_fetch_chars,
            "max_chunks_per_file": max_chunks_per_file,
            "max_chunk_chars": max_chunk_chars,
            "context_lines": context_lines,
        },
        "files": files,
        "omitted_candidates": omitted_candidates,
    }


def _render_deep_ci_snapshots(snapshots, selected_files=None):
    """Render Deep CI snapshots and omission notes as prompt markdown."""
    if not snapshots:
        return "No eligible changed code files selected for Deep CI context review.\n"

    rendered = []
    selected_count = len(selected_files or snapshots)
    rendered.append(
        f"Selected {selected_count} changed code file(s) for bounded Deep CI context review."
    )
    for snapshot in snapshots:
        path = snapshot["path"]
        mode = snapshot.get("mode", "skipped")
        if mode == "skipped":
            rendered.append(
                f"## {path}\n"
                "Mode: skipped\n"
                f"Skipped Deep CI review for {path} because {snapshot['reason']}."
            )
            continue
        if mode == "full":
            content = snapshot["content"].rstrip()
            fence = markdown_code_fence(content)
            rendered.append(
                "\n".join(
                    [
                        f"## {path}",
                        "Mode: full-file",
                        f"Size: {snapshot.get('char_count', len(snapshot['content']))} chars, {snapshot.get('line_count', 0)} lines",
                        fence,
                        content,
                        fence,
                    ]
                )
            )
            continue

        chunks = snapshot.get("chunks", [])
        ranges = ", ".join(f"{chunk['start_line']}-{chunk['end_line']}" for chunk in chunks)
        file_lines = [
            f"## {path}",
            "Mode: chunked-large-file",
            f"Size: {snapshot.get('char_count', 0)} chars, {snapshot.get('line_count', 0)} lines",
            f"Included chunks: {len(chunks)}",
            f"Included line ranges: {ranges}",
            f"Omitted: {snapshot.get('reason', '')}",
        ]
        total_cap_omitted_windows = snapshot.get("total_cap_omitted_windows") or []
        if total_cap_omitted_windows:
            omitted_ranges = ", ".join(
                f"{w['start_line']}-{w['end_line']}" for w in total_cap_omitted_windows
            )
            file_lines.append(
                f"Total-cap omitted: {len(total_cap_omitted_windows)} changed-line "
                f"window(s) ({omitted_ranges}) dropped because the Deep CI total "
                f"character budget was exhausted"
            )
        chunk_cap_omitted_windows = snapshot.get("chunk_cap_omitted_windows") or []
        if chunk_cap_omitted_windows:
            omitted_ranges = ", ".join(
                f"{w['start_line']}-{w['end_line']}" for w in chunk_cap_omitted_windows
            )
            file_lines.append(
                f"Chunk-cap omitted: {len(chunk_cap_omitted_windows)} changed-line "
                f"window(s) ({omitted_ranges}) dropped because the per-file chunk "
                f"limit was reached"
            )
        for chunk in chunks:
            chunk_header = f"### {path} lines {chunk['start_line']}-{chunk['end_line']}"
            chunk_lines = [
                chunk_header,
                (
                    "Changed RIGHT-side lines in this chunk: "
                    + ", ".join(
                        str(line)
                        for line in chunk.get(
                            "changed_lines_included", chunk.get("changed_lines", [])
                        )
                    )
                ),
            ]
            omitted = chunk.get("changed_lines_omitted") or []
            if omitted:
                chunk_lines.append(
                    "changed_lines_included: "
                    + ", ".join(str(line) for line in chunk.get("changed_lines_included", []))
                )
                chunk_lines.append(
                    "changed_lines_omitted: " + ", ".join(str(line) for line in omitted)
                )
            content = chunk.get("content", "").rstrip()
            fence = markdown_code_fence(content)
            chunk_lines.extend([fence, content, fence])
            file_lines.append("\n".join(chunk_lines))
        rendered.append("\n\n".join(file_lines))

    return "\n\n".join(rendered).strip() + "\n"


def _manifest_file_to_snapshot(file_entry, source_snapshot):
    mode = file_entry.get("mode")
    if mode == "full":
        return {
            "path": file_entry["path"],
            "mode": "full",
            "content": (source_snapshot or {}).get("content", ""),
            "chunks": [],
            "char_count": file_entry.get("char_count", 0),
            "line_count": file_entry.get("line_count", 0),
            "changed_line_ranges": file_entry.get("changed_line_ranges", []),
            "omitted": False,
            "reason": file_entry.get("reason", ""),
        }

    chunk_content_by_range = {}
    for chunk in (source_snapshot or {}).get("chunks", []):
        key = (chunk.get("start_line"), chunk.get("end_line"))
        chunk_content_by_range[key] = chunk.get("content", "")

    chunks = []
    for chunk in sorted(
        file_entry.get("chunks", []),
        key=lambda item: item.get("start_line", 0),
    ):
        key = (chunk.get("start_line"), chunk.get("end_line"))
        included = sorted(chunk.get("changed_lines_included", []))
        omitted = sorted(chunk.get("changed_lines_omitted", []))
        chunks.append(
            {
                "start_line": chunk.get("start_line", 0),
                "end_line": chunk.get("end_line", 0),
                "content": chunk_content_by_range.get(key, ""),
                "changed_lines": sorted(set(included + omitted)),
                "changed_lines_included": included,
                "changed_lines_omitted": omitted,
            }
        )

    return {
        "path": file_entry["path"],
        "mode": "chunked",
        "content": "",
        "chunks": chunks,
        "char_count": file_entry.get("char_count", 0),
        "line_count": file_entry.get("line_count", 0),
        "changed_line_ranges": file_entry.get("changed_line_ranges", []),
        "chunk_cap_omitted_windows": file_entry.get("chunk_cap_omitted_windows", []),
        "total_cap_omitted_windows": file_entry.get("total_cap_omitted_windows", []),
        "omitted": False,
        "reason": file_entry.get("reason", ""),
    }


def _render_deep_ci_markdown_from_manifest(manifest, *, files_with_content=None, selected_files=None):
    manifest = manifest or {}
    manifest_files = sorted(manifest.get("files", []), key=lambda item: item.get("path", ""))
    content_by_path = {}
    selected_paths = []
    if isinstance(files_with_content, list):
        for snapshot in files_with_content:
            path = snapshot.get("path")
            if not path:
                continue
            content_by_path[path] = snapshot
            selected_paths.append(path)

    snapshots = []
    for file_entry in manifest_files:
        path = file_entry.get("path")
        if not path:
            continue
        snapshots.append(_manifest_file_to_snapshot(file_entry, content_by_path.get(path)))

    manifest_paths = {entry.get("path") for entry in manifest_files}
    if isinstance(files_with_content, list):
        for snapshot in files_with_content:
            path = snapshot.get("path")
            if not path or path in manifest_paths:
                continue
            if snapshot.get("mode") == "skipped" or snapshot.get("omitted"):
                snapshots.append(snapshot)
    else:
        for omitted in manifest.get("omitted_candidates", []):
            path = omitted.get("path")
            if not path:
                continue
            snapshots.append(_deep_ci_omitted_note(path, omitted.get("reason", "")))

    snapshots = sorted(snapshots, key=lambda item: item.get("path", ""))
    selected_for_render = selected_files
    if selected_for_render is None:
        selected_for_render = selected_paths or [snapshot.get("path") for snapshot in snapshots]
    return _render_deep_ci_snapshots(snapshots, selected_files=selected_for_render)


def render_deep_ci_markdown_from_manifest(manifest, *, files_with_content=None):
    """Render Deep CI markdown from the canonical manifest."""
    return _render_deep_ci_markdown_from_manifest(
        manifest,
        files_with_content=files_with_content,
    )


def render_deep_ci_context(snapshots, selected_files=None):
    """Render legacy Deep CI snapshot lists while preserving caller order."""
    return _render_deep_ci_snapshots(snapshots, selected_files=selected_files)


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
    diff_text = _read_text_if_exists("/tmp/pr.diff")
    changed_line_ranges = parse_changed_line_ranges(diff_text)
    deep_ci_snapshots = fetch_deep_ci_files(
        repo,
        head_sha,
        selected_deep_ci_files,
        changed_line_ranges=changed_line_ranges,
        file_metadata=changed_file_metadata,
    )
    deep_ci_manifest = build_deep_ci_manifest(
        repo,
        head_sha,
        changed_file_metadata,
        changed_line_ranges=changed_line_ranges,
        file_metadata=changed_file_metadata,
        source={
            "pr_diff_path": "/tmp/pr.diff",
            "changed_files_path": "/tmp/changed_files.json",
        },
        fetch=lambda *_args, **_kwargs: deep_ci_snapshots,
    )
    Path(DEEP_CI_MANIFEST_PATH).write_text(
        json.dumps(deep_ci_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    deep_ci_context = render_deep_ci_markdown_from_manifest(
        deep_ci_manifest,
        files_with_content=deep_ci_snapshots,
    )
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
