"""Deterministic helpers for PR shepherd state, markers, and scope."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


ADDRESSED_MARKER = "<!-- pr-shepherd:addressed v1 -->"
FOLLOWUP_MARKER = "<!-- pr-shepherd:followup v1 -->"
SUMMARY_MARKER = "<!-- pr-shepherd:summary v1 -->"

_ADDRESSED_PREFIX = "<!-- pr-shepherd:addressed v"
_FOLLOWUP_PREFIX = "<!-- pr-shepherd:followup v"
_SUMMARY_PREFIX = "<!-- pr-shepherd:summary v"
_ACTIVITY_ORDER = {"addressed": 0, "uncertain": 1, "active": 2}


JsonObject = dict[str, Any]


def has_marker(body: str, marker: str) -> bool:
    """Return whether ``body`` contains a current or older marker of this kind."""

    prefix = {
        ADDRESSED_MARKER: _ADDRESSED_PREFIX,
        FOLLOWUP_MARKER: _FOLLOWUP_PREFIX,
        SUMMARY_MARKER: _SUMMARY_PREFIX,
    }.get(marker, marker)
    return prefix in body


def append_marker(body: str, marker: str) -> str:
    """Append ``marker`` to ``body`` if it is not already present."""

    text = body.rstrip()
    if has_marker(text, marker):
        return text + "\n"
    if text:
        return f"{text}\n\n{marker}\n"
    return f"{marker}\n"


def stable_fingerprint(payload: JsonObject) -> str:
    """Return a stable sha256 fingerprint for a PR feedback payload."""

    relevant = {
        "source_kind": payload.get("source_kind"),
        "path": payload.get("path"),
        "line": payload.get("line"),
        "title": payload.get("title"),
        "body": payload.get("body") or payload.get("body_excerpt"),
        "url": payload.get("url"),
    }
    encoded = json.dumps(relevant, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _activity_timestamp(activity: JsonObject) -> str:
    return max(str(activity.get("created_at") or ""), str(activity.get("updated_at") or ""))


def activity_state(activities: list[JsonObject]) -> str:
    """Classify marker recency for one thread/comment/fingerprint activity list."""

    ordered = sorted(
        activities,
        key=_activity_timestamp,
    )
    last_marker_index: int | None = None
    for index, activity in enumerate(ordered):
        body = str(activity.get("body") or "")
        marker_trusted = activity.get("marker_trusted") is not False
        if marker_trusted and (has_marker(body, ADDRESSED_MARKER) or has_marker(body, SUMMARY_MARKER)):
            last_marker_index = index

    if last_marker_index is None:
        return "active"

    after_marker = ordered[last_marker_index + 1 :]
    if not after_marker:
        return "addressed"

    for activity in after_marker:
        author_kind = str(activity.get("author_kind") or "").strip().lower()
        if author_kind == "human":
            return "active"
    return "uncertain"


def merge_activity_state(current: object, candidate: object) -> str:
    """Return the more actionable activity state."""

    current_text = str(current or "addressed")
    candidate_text = str(candidate or "addressed")
    if current_text not in _ACTIVITY_ORDER:
        current_text = "addressed"
    if candidate_text not in _ACTIVITY_ORDER:
        candidate_text = "addressed"
    if _ACTIVITY_ORDER[candidate_text] > _ACTIVITY_ORDER[current_text]:
        return candidate_text
    return current_text


@dataclass(frozen=True)
class OperationalResult:
    operational_state: str
    blocker: str | None
    next_action: str
    progress: dict[str, int]
    waiting_on: str | None = None

    def to_json(self) -> JsonObject:
        payload: JsonObject = {
            "operational_state": self.operational_state,
            "next_action": self.next_action,
            "progress": self.progress,
        }
        if self.blocker:
            payload["blocker"] = self.blocker
        if self.waiting_on:
            payload["waiting_on"] = self.waiting_on
        return payload


def _int_fact(pass_facts: JsonObject, key: str) -> int:
    value = pass_facts.get(key)
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _bool_fact(pass_facts: JsonObject, key: str) -> bool:
    return pass_facts.get(key) is True


def classify_operational_state(loop_result: JsonObject, pass_facts: JsonObject) -> JsonObject:
    """Classify a whole PR shepherd pass as clean, progressing, or stuck."""

    ci_state = str(pass_facts.get("ci_state") or "unknown").strip().lower()
    pushed = _int_fact(pass_facts, "pushed_commits_count")
    replies = _int_fact(pass_facts, "posted_replies_count")
    active = _int_fact(pass_facts, "active_feedback_count")
    uncertain = _int_fact(pass_facts, "uncertain_feedback_count")
    human_decisions = _int_fact(pass_facts, "unresolved_human_decision_count")
    blockers = [
        str(item).strip()
        for item in pass_facts.get("blockers", [])
        if isinstance(item, str) and item.strip()
    ] if isinstance(pass_facts.get("blockers"), list) else []

    hard_blockers = list(blockers)
    for key in ("checkout_mismatch", "auth_unavailable", "logs_unavailable", "merge_conflict"):
        if _bool_fact(pass_facts, key):
            hard_blockers.append(key)
    if _bool_fact(pass_facts, "loop_cap_enforced"):
        hard_blockers.append("loop_cap_enforced")
    if human_decisions:
        hard_blockers.append("human_decision_required")
    if ci_state in {"failing", "unknown"}:
        hard_blockers.append(f"ci_{ci_state}")
    if (active or uncertain) and not (pushed or replies):
        hard_blockers.append("feedback_remaining")

    progress = {"pushed_commits_count": pushed, "posted_replies_count": replies}

    if hard_blockers:
        blocker = hard_blockers[0]
        return OperationalResult(
            "stuck",
            blocker,
            f"Resolve blocker: {blocker}.",
            progress,
        ).to_json()

    if (
        loop_result.get("outcome") == "success"
        and ci_state == "green"
        and active == 0
        and uncertain == 0
        and human_decisions == 0
    ):
        return OperationalResult(
            "clean",
            None,
            "PR can be marked ready when other readiness guards pass.",
            progress,
        ).to_json()

    if pushed or replies:
        waiting_on = "ci" if ci_state == "pending" or pushed else "reviewer"
        return OperationalResult(
            "progressing",
            None,
            f"Wait for {waiting_on} before the next shepherd pass.",
            progress,
            waiting_on=waiting_on,
        ).to_json()

    return OperationalResult(
        "stuck",
        "no_safe_action",
        "No safe automated action is available for this pass.",
        progress,
    ).to_json()


def compact_summary_body(rows: list[JsonObject]) -> str:
    """Render a compact marker-owned summary comment body."""

    lines = ["PR shepherd status", "", "| state | fingerprint | url |", "|---|---|---|"]
    for row in rows:
        state = str(row.get("state") or row.get("activity_state") or "unknown")
        fingerprint = str(row.get("fingerprint") or "")[:16]
        url = str(row.get("url") or "")
        lines.append(f"| {state} | `{fingerprint}` | {url} |")
    return append_marker("\n".join(lines), SUMMARY_MARKER)
