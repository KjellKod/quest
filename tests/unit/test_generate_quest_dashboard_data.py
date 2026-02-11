import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "generate_quest_dashboard_data.py"
SPEC = importlib.util.spec_from_file_location("generate_quest_dashboard_data", MODULE_PATH)
GENERATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(GENERATOR)


class GenerateQuestDashboardDataTests(unittest.TestCase):
    def test_parse_journal_extracts_summary_and_dates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            journal_path = root / "docs" / "quest-journal" / "example-quest_2026-02-01.md"
            journal_path.parent.mkdir(parents=True, exist_ok=True)
            journal_path.write_text(
                "\n".join(
                    [
                        "# Quest Journal: Example Quest",
                        "",
                        "**Quest ID:** `example-quest_2026-02-01__1010`",
                        "**Completed:** 2026-02-02",
                        "",
                        "## Summary",
                        "",
                        "This is the elevator pitch.",
                        "",
                        "## Details",
                        "More details.",
                    ]
                ),
                encoding="utf-8",
            )

            record = GENERATOR.parse_journal_entry(journal_path, root)

            self.assertEqual(record["quest_id"], "example-quest_2026-02-01__1010")
            self.assertEqual(record["completed_date"], "2026-02-02")
            self.assertEqual(record["elevator_pitch"], "This is the elevator pitch.")
            self.assertEqual(record["title"], "Example Quest")
            self.assertEqual(record["journal_path"], "docs/quest-journal/example-quest_2026-02-01.md")

    def test_merge_prefers_state_fields_and_preserves_journal_pitch(self):
        journal = [
            {
                "quest_id": "dup_2026-02-02__1111",
                "slug": "dup",
                "title": "Duplicate",
                "elevator_pitch": "Journal narrative",
                "completed_date": "2026-02-02",
                "status_raw": "Complete",
                "journal_path": "docs/quest-journal/dup_2026-02-02.md",
            }
        ]

        active = [
            {
                "quest_id": "dup_2026-02-02__1111",
                "slug": "dup",
                "status_raw": "blocked",
                "phase": "building",
                "plan_iteration": 1,
                "fix_iteration": 0,
                "created_at": "2026-02-02T10:00:00Z",
                "updated_at": "2026-02-02T12:00:00Z",
                "state_path": ".quest/dup_2026-02-02__1111/state.json",
            }
        ]

        archive = [
            {
                "quest_id": "dup_2026-02-02__1111",
                "slug": "dup",
                "status_raw": "complete",
                "phase": "complete",
                "plan_iteration": 3,
                "fix_iteration": 1,
                "created_at": "2026-02-02T10:00:00Z",
                "updated_at": "2026-02-02T13:00:00Z",
                "state_path": ".quest/archive/dup_2026-02-02__1111/state.json",
            }
        ]

        quests = GENERATOR._merge_records(journal, active, archive)

        self.assertEqual(len(quests), 1)
        self.assertEqual(quests[0]["state_path"], ".quest/archive/dup_2026-02-02__1111/state.json")
        self.assertEqual(quests[0]["status"], "finished")
        self.assertEqual(quests[0]["plan_iteration"], 3)
        self.assertEqual(quests[0]["elevator_pitch"], "Journal narrative")

    def test_merge_includes_active_non_archived_quest_in_quests_and_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            journal_dir = root / "docs" / "quest-journal"
            quest_dir = root / ".quest"
            archive_dir = quest_dir / "archive"
            journal_dir.mkdir(parents=True, exist_ok=True)
            archive_dir.mkdir(parents=True, exist_ok=True)

            (journal_dir / "README.md").write_text("ignored", encoding="utf-8")
            (journal_dir / "active-only_2026-02-11.md").write_text(
                "\n".join(
                    [
                        "# Quest Journal: Active Only",
                        "",
                        "**Quest ID:** active-only_2026-02-11__0900",
                        "",
                        "## Summary",
                        "",
                        "Active narrative.",
                    ]
                ),
                encoding="utf-8",
            )

            active_state_dir = quest_dir / "active-only_2026-02-11__0900"
            active_state_dir.mkdir(parents=True, exist_ok=True)
            (active_state_dir / "state.json").write_text(
                json.dumps(
                    {
                        "quest_id": "active-only_2026-02-11__0900",
                        "slug": "active-only",
                        "status": "in_progress",
                        "phase": "building",
                        "plan_iteration": 2,
                        "fix_iteration": 0,
                        "created_at": "2026-02-11T09:00:00Z",
                        "updated_at": "2026-02-11T10:00:00Z",
                    }
                ),
                encoding="utf-8",
            )

            data = GENERATOR.build_dashboard_data(
                journal_dir=journal_dir,
                quest_dir=quest_dir,
                archive_dir=archive_dir,
                repo_root=root,
                generated_at="2026-02-11T12:00:00Z",
            )

            self.assertEqual(data["summary"]["total"], 1)
            self.assertEqual(data["summary"]["by_status"]["in_progress"], 1)
            self.assertEqual(data["quests"][0]["quest_id"], "active-only_2026-02-11__0900")

    def test_normalize_status_maps_variants_to_canonical_values(self):
        self.assertEqual(GENERATOR.normalize_status({"status_raw": "Completed"}, None), "finished")
        self.assertEqual(GENERATOR.normalize_status({"status_raw": "complete"}, None), "finished")
        self.assertEqual(
            GENERATOR.normalize_status(None, {"status_raw": "in_progress", "phase": "building"}),
            "in_progress",
        )
        self.assertEqual(GENERATOR.normalize_status({"status_raw": "blocked"}, None), "blocked")
        self.assertEqual(
            GENERATOR.normalize_status({"status_raw": "Abandoned (plan approved, never built)"}, None),
            "abandoned",
        )

    def test_normalize_status_unknown_values_map_to_unknown(self):
        self.assertEqual(GENERATOR.normalize_status({"status_raw": "paused"}, None), "unknown")
        self.assertEqual(
            GENERATOR.normalize_status(None, {"status_raw": "building", "phase": "routing"}),
            "unknown",
        )

    def test_build_trend_points_final_status_over_time_semantic_dataset(self):
        quests = [
            {
                "status": "finished",
                "completed_date": "2026-01-15",
                "updated_at": "2026-01-15T12:00:00Z",
                "created_at": None,
            },
            {
                "status": "blocked",
                "completed_date": None,
                "updated_at": "2026-01-22T12:00:00Z",
                "created_at": None,
            },
            {
                "status": "abandoned",
                "completed_date": "2026-02-01",
                "updated_at": None,
                "created_at": None,
            },
            {
                "status": "in_progress",
                "completed_date": None,
                "updated_at": "2026-02-08T12:00:00Z",
                "created_at": None,
            },
        ]

        points = GENERATOR.build_trend_points(quests)

        self.assertEqual(points[0]["period"], "2026-01")
        self.assertEqual(points[0]["finished"], 1)
        self.assertEqual(points[0]["blocked"], 1)
        self.assertEqual(points[1]["period"], "2026-02")
        self.assertEqual(points[1]["abandoned"], 1)
        self.assertEqual(points[1]["in_progress"], 1)

    def test_dashboard_data_schema_requires_quest_keys_and_nullable_completed_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            journal_dir = root / "docs" / "quest-journal"
            quest_dir = root / ".quest"
            archive_dir = quest_dir / "archive"
            journal_dir.mkdir(parents=True, exist_ok=True)
            archive_dir.mkdir(parents=True, exist_ok=True)

            (journal_dir / "schema-case_2026-02-11.md").write_text(
                "\n".join(
                    [
                        "# Quest Journal: Schema Case",
                        "",
                        "**Quest ID:** schema-case_2026-02-11__1000",
                        "",
                        "## Summary",
                        "",
                        "Schema summary.",
                    ]
                ),
                encoding="utf-8",
            )

            state_dir = quest_dir / "schema-case_2026-02-11__1000"
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "state.json").write_text(
                json.dumps(
                    {
                        "quest_id": "schema-case_2026-02-11__1000",
                        "slug": "schema-case",
                        "status": "in_progress",
                        "phase": "building",
                        "plan_iteration": 1,
                        "fix_iteration": 0,
                        "created_at": "2026-02-11T10:00:00Z",
                        "updated_at": "2026-02-11T10:30:00Z",
                    }
                ),
                encoding="utf-8",
            )

            data = GENERATOR.build_dashboard_data(
                journal_dir=journal_dir,
                quest_dir=quest_dir,
                archive_dir=archive_dir,
                repo_root=root,
                generated_at="2026-02-11T12:00:00Z",
            )

            self.assertEqual(len(data["quests"]), 1)
            quest = data["quests"][0]
            for key in (
                "quest_id",
                "slug",
                "title",
                "elevator_pitch",
                "status",
                "completed_date",
                "journal_path",
                "state_path",
            ):
                self.assertIn(key, quest)
            self.assertIsNone(quest["completed_date"])


if __name__ == "__main__":
    unittest.main()
