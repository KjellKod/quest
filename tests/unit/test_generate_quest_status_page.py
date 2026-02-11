import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "generate_quest_status_page.py"
    spec = importlib.util.spec_from_file_location("generate_quest_status_page", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


mod = _load_module()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_quest(root: Path, quest_id: str, status: str = "in_progress", phase: str = "plan", brief: str = "") -> Path:
    quest_dir = root / quest_id
    quest_dir.mkdir(parents=True, exist_ok=True)
    _write(
        quest_dir / "state.json",
        (
            "{\n"
            f'  "quest_id": "{quest_id}",\n'
            f'  "phase": "{phase}",\n'
            f'  "status": "{status}",\n'
            '  "updated_at": "2026-02-10T10:00:00Z"\n'
            "}\n"
        ),
    )
    _write(
        quest_dir / "quest_brief.md",
        brief
        or (
            f"# Quest Brief: {quest_id}\n\n"
            "## User Input\n"
            "Simple prompt.\n\n"
            "## Goal\n"
            "Deliver a small feature.\n"
        ),
    )
    return quest_dir


class GenerateQuestStatusPageTests(unittest.TestCase):
    def test_cli_default_command_generates_html_with_required_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            quest_root = workspace / ".quest"
            _make_quest(quest_root, "quest-ongoing", status="in_progress", phase="build")
            _make_quest(quest_root, "quest-finished", status="complete", phase="complete")

            script_path = Path(__file__).resolve().parents[2] / "scripts" / "generate_quest_status_page.py"
            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=workspace,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            output_path = workspace / "docs" / "quest-status" / "index.html"
            self.assertTrue(output_path.is_file())
            html_output = output_path.read_text(encoding="utf-8")

            self.assertIn("Quest Status Dashboard", html_output)
            self.assertIn("Ongoing", html_output)
            self.assertIn("Completed", html_output)
            self.assertIn('>1<', html_output)  # metric values
            self.assertIn("Quest Ongoing", html_output)
            self.assertIn("phase-build", html_output)

    def test_discover_quest_dirs_requires_state_and_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".quest"
            _make_quest(root, "quest-valid")
            (root / "missing-brief").mkdir(parents=True, exist_ok=True)
            _write(root / "missing-brief" / "state.json", "{}")
            (root / "missing-state").mkdir(parents=True, exist_ok=True)
            _write(root / "missing-state" / "quest_brief.md", "# Quest Brief: Missing State")
            _write(root / "README.md", "not a quest")

            discovered = mod.discover_quest_dirs(root)
            self.assertEqual([p.name for p in discovered], ["quest-valid"])

    def test_discover_quest_dirs_includes_active_and_archive_roots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".quest"
            _make_quest(root, "active-quest")
            _make_quest(root / "archive", "archived-quest", status="complete", phase="complete")

            discovered = mod.discover_quest_dirs(root)
            names = sorted(p.name for p in discovered)
            self.assertEqual(names, ["active-quest", "archived-quest"])

    def test_build_dashboard_model_splits_ongoing_and_finished(self):
        quests = [
            {"quest_id": "q1", "status": "complete", "updated_at": "2026-02-10T09:00:00Z"},
            {"quest_id": "q2", "status": "in_progress", "updated_at": "2026-02-10T10:00:00Z"},
            {"quest_id": "q3", "status": "blocked", "updated_at": "2026-02-10T11:00:00Z"},
        ]
        model = mod.build_dashboard_model(quests)
        self.assertEqual(model["counts"]["finished"], 1)
        self.assertEqual(model["counts"]["ongoing"], 2)
        self.assertEqual(model["counts"]["blocked"], 1)
        self.assertEqual([q["quest_id"] for q in model["ongoing"]], ["q3", "q2"])

    def test_parse_quest_brief_pitch_priority_user_input_original_prompt_user_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brief1 = root / "one.md"
            _write(
                brief1,
                (
                    "# Quest Brief: One\n\n"
                    "## Original Prompt\n"
                    "Original text.\n\n"
                    "## User Input\n"
                    "Preferred user input.\n\n"
                    "## User Request\n"
                    "Request text.\n"
                ),
            )
            self.assertEqual(mod.parse_quest_brief(brief1)["elevator_pitch"], "Preferred user input.")

            brief2 = root / "two.md"
            _write(
                brief2,
                (
                    "# Quest Brief: Two\n\n"
                    "## Original Prompt\n"
                    "Only original prompt.\n"
                ),
            )
            self.assertEqual(mod.parse_quest_brief(brief2)["elevator_pitch"], "Only original prompt.")

            brief3 = root / "three.md"
            _write(
                brief3,
                (
                    "# Quest Brief: Three\n\n"
                    "## User Request\n"
                    "Only user request.\n"
                ),
            )
            self.assertEqual(mod.parse_quest_brief(brief3)["elevator_pitch"], "Only user request.")

    def test_parse_quest_brief_description_priority_and_not_available_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            brief_goal = root / "goal.md"
            _write(
                brief_goal,
                (
                    "# Quest Brief: Goal\n\n"
                    "## Problem\n"
                    "Problem paragraph.\n\n"
                    "## Goal\n"
                    "Goal paragraph.\n"
                ),
            )
            self.assertEqual(mod.parse_quest_brief(brief_goal)["description"], "Goal paragraph.")

            brief_context = root / "context.md"
            _write(
                brief_context,
                (
                    "# Quest Brief: Context\n\n"
                    "## Context\n"
                    "Context paragraph.\n"
                ),
            )
            self.assertEqual(mod.parse_quest_brief(brief_context)["description"], "Context paragraph.")

            brief_fallback = root / "fallback.md"
            _write(
                brief_fallback,
                (
                    "# Quest Brief: Fallback\n\n"
                    "## Router Classification\n"
                    "```json\n"
                    '{"route":"workflow"}\n'
                    "```\n\n"
                    "Meaningful fallback paragraph.\n"
                ),
            )
            self.assertEqual(mod.parse_quest_brief(brief_fallback)["description"], "Meaningful fallback paragraph.")

            brief_empty = root / "empty.md"
            _write(
                brief_empty,
                (
                    "# Quest Brief: Empty\n\n"
                    "## Router Classification\n"
                    "```json\n"
                    '{"route":"workflow"}\n'
                    "```\n"
                ),
            )
            self.assertEqual(mod.parse_quest_brief(brief_empty)["description"], "Not available")

    def test_render_html_generates_matching_finished_links_and_anchors(self):
        quests = [
            {
                "quest_id": "done-1",
                "phase": "complete",
                "status": "complete",
                "title": "Done <One>",
                "elevator_pitch": "Ship <script>alert(1)</script>",
                "description": "Desc & details",
                "original_request": "Build the thing",
                "anchor": mod.sanitize_anchor("done-1"),
                "updated_at": "2026-02-10T12:00:00Z",
                "created_at": "2026-02-10T10:00:00Z",
                "artifact_path": ".quest/archive/done-1",
                "journal_filename": "done-1_2026-02-10.md",
                "warnings": [],
            },
            {
                "quest_id": "working",
                "phase": "plan",
                "status": "in_progress",
                "title": "Working",
                "elevator_pitch": "n/a",
                "description": "n/a",
                "original_request": "n/a",
                "anchor": mod.sanitize_anchor("working"),
                "updated_at": "2026-02-10T13:00:00Z",
                "created_at": "2026-02-10T11:00:00Z",
                "artifact_path": ".quest/working",
                "journal_filename": "",
                "warnings": [],
            },
        ]
        model = mod.build_dashboard_model(quests)
        html_output = mod.render_html(model, "2026-02-10 12:30:00Z")
        anchor = mod.sanitize_anchor("done-1")
        self.assertIn(f'href="#{anchor}"', html_output)
        self.assertIn(f'id="{anchor}"', html_output)
        self.assertNotIn("<script>", html_output)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html_output)

    def test_render_html_sanitizes_anchor_at_render_time(self):
        quests = [
            {
                "quest_id": "done-unsafe",
                "phase": "complete",
                "status": "complete",
                "title": "Done Unsafe",
                "elevator_pitch": "Pitch",
                "description": "Desc",
                "original_request": "Fix it",
                "anchor": 'bad" onclick="alert(1)<script>',
                "updated_at": "2026-02-10T12:00:00Z",
                "created_at": "2026-02-10T10:00:00Z",
                "artifact_path": ".quest/archive/done-unsafe",
                "journal_filename": "done-unsafe_2026-02-10.md",
                "warnings": [],
            }
        ]
        model = mod.build_dashboard_model(quests)
        html_output = mod.render_html(model, "2026-02-10 12:30:00Z")
        safe_anchor = "quest-bad-onclick-alert-1-script"
        self.assertIn(f'href="#{safe_anchor}"', html_output)
        self.assertIn(f'id="{safe_anchor}"', html_output)

    def test_archive_quests_appear_in_finished_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".quest"
            _make_quest(root, "active-quest", status="in_progress", phase="build")
            _make_quest(root / "archive", "archived-finished", status="complete", phase="complete")

            quests = mod.load_quests(root)
            model = mod.build_dashboard_model(quests)
            finished_ids = {quest["quest_id"] for quest in model["finished"]}
            self.assertIn("archived-finished", finished_ids)

    def test_load_quests_deduplicates_sanitized_anchor_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".quest"
            _make_quest(root, "quest a", status="complete", phase="complete")
            _make_quest(root, "quest-a", status="complete", phase="complete")

            anchors = sorted(quest["anchor"] for quest in mod.load_quests(root))
            self.assertEqual(anchors, ["quest-quest-a", "quest-quest-a-2"])

    def test_load_state_when_json_invalid_continues_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".quest"
            _make_quest(root, "good-quest", status="in_progress", phase="plan")

            bad_dir = root / "bad-quest"
            bad_dir.mkdir(parents=True, exist_ok=True)
            _write(bad_dir / "state.json", "{ invalid json")
            _write(
                bad_dir / "quest_brief.md",
                (
                    "# Quest Brief: bad-quest\n\n"
                    "## User Input\n"
                    "Bad state should not break generation.\n"
                ),
            )

            missing_state = mod.load_state(root / "missing/state.json")
            self.assertEqual(missing_state["status"], "unknown")
            self.assertTrue(missing_state["warnings"])

            quests = mod.load_quests(root)
            model = mod.build_dashboard_model(quests)
            ids = {quest["quest_id"] for quest in model["ongoing"]}
            self.assertIn("good-quest", ids)
            self.assertIn("bad-quest", ids)
            self.assertGreaterEqual(len(model["warnings"]), 1)

    def test_load_state_when_utf8_invalid_continues_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".quest"
            _make_quest(root, "good-quest", status="in_progress", phase="plan")

            bad_dir = root / "bad-utf8-state"
            bad_dir.mkdir(parents=True, exist_ok=True)
            (bad_dir / "state.json").write_bytes(b"\xff\xfe\xfa")
            _write(
                bad_dir / "quest_brief.md",
                (
                    "# Quest Brief: bad-utf8-state\n\n"
                    "## User Input\n"
                    "State decode failure should not break generation.\n"
                ),
            )

            quests = mod.load_quests(root)
            model = mod.build_dashboard_model(quests)
            ids = {quest["quest_id"] for quest in model["ongoing"]}
            self.assertIn("good-quest", ids)
            self.assertIn("bad-utf8-state", ids)
            self.assertTrue(any("Invalid state.json" in warning for warning in model["warnings"]))

    def test_parse_quest_brief_when_utf8_invalid_uses_fallback_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ".quest"
            quest_id = "bad-utf8-brief"
            quest_dir = root / quest_id
            quest_dir.mkdir(parents=True, exist_ok=True)
            _write(
                quest_dir / "state.json",
                (
                    "{\n"
                    f'  "quest_id": "{quest_id}",\n'
                    '  "phase": "complete",\n'
                    '  "status": "complete"\n'
                    "}\n"
                ),
            )
            (quest_dir / "quest_brief.md").write_bytes(b"\xff\xfe\xfa")

            quests = mod.load_quests(root)
            by_id = {quest["quest_id"]: quest for quest in quests}
            self.assertIn(quest_id, by_id)
            self.assertEqual(by_id[quest_id]["title"], quest_id)
            self.assertEqual(by_id[quest_id]["elevator_pitch"], "Not available")
            self.assertEqual(by_id[quest_id]["description"], "Not available")


if __name__ == "__main__":
    unittest.main()
