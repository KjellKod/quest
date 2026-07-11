"""Tests for the repo-local Quest checksum drift helper."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_module():
    module_path = _repo_root() / "scripts" / "check_quest_checksum_drift.py"
    spec = importlib.util.spec_from_file_location(
        "check_quest_checksum_drift", module_path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_reports_no_drift_for_matching_repo_file(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "tracked.txt"
    target.write_text("ok\n", encoding="utf-8")
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    (repo / ".quest-checksums").write_text(
        f"{checksum}  tracked.txt\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(sys, "argv", ["check_quest_checksum_drift.py", str(repo)])

    assert module.main() == 0
    assert capsys.readouterr().out.strip() == "OK: no checksum drift"


def test_main_reports_unsafe_path_without_hashing_outside_repo(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module = _load_module()
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    (repo / ".quest-checksums").write_text(
        "0" * 64 + "  ../outside.txt\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(sys, "argv", ["check_quest_checksum_drift.py", str(repo)])

    assert module.main() == 1
    captured = capsys.readouterr().out
    assert "DRIFT" in captured
    assert "../outside.txt\tunsafe path" in captured
    assert hashlib.sha256(outside.read_bytes()).hexdigest() not in captured
