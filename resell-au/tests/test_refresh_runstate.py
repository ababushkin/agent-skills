"""
Unit tests for scripts/refresh_runstate.py.

Run:
    bash tests/check_refresh_runstate.sh
    # or directly:
    python3 -m unittest tests.test_refresh_runstate -v

These tests cover the deterministic surface area sub-task ABA-157 adds:
plan generation (resume classification), apply_update (status transitions
auto-stamp the matching *_at field), find_latest_runstate +
has_unfinished_work (resume-vs-new-file decision), and the cmd_init CLI
end-to-end (fresh-folder vs resume vs stale-terminal-file paths).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from refresh_runstate import (  # noqa: E402
    apply_update,
    build_plan,
    cmd_init,
    find_latest_runstate,
    has_unfinished_work,
    runstate_filename,
)


def _item(subfolder: str, status: str, **overrides) -> dict:
    base = {
        "subfolder": subfolder,
        "title": f"Title for {subfolder}",
        "old_url": f"https://www.facebook.com/marketplace/item/{subfolder}-old/",
        "old_price": 50,
        "new_price": 45,
        "floor": 35,
        "age_days": 12,
        "refresh_count_before": 0,
        "status": status,
        "delete_detection": None,
        "new_url": None,
        "failure_reason": None,
        "pending_at": None,
        "deleted_at": None,
        "recreated_at": None,
        "failed_at": None,
    }
    base.update(overrides)
    return base


def _state(items: list[dict]) -> dict:
    return {
        "run_started": "2026-05-21T14:00:00",
        "target_folder": "/tmp/fixture",
        "session_cap": 5,
        "items": items,
    }


class BuildPlanResumeClassification(unittest.TestCase):
    """plan emits the per-item action that the R1+R2 loop branches on."""

    def test_all_pending_yields_all_r1(self):
        state = _state([_item("a", "pending"), _item("b", "pending")])
        plan = build_plan(state)
        self.assertEqual([p["action"] for p in plan], ["r1", "r1"])

    def test_deleted_yields_r2_resume(self):
        # The headline resume case from ABA-157 acceptance criteria —
        # killed after R1, resumed re-invocation must skip R1 and run R2.
        state = _state([
            _item("a", "deleted", delete_detection="redirect"),
            _item("b", "pending"),
        ])
        plan = build_plan(state)
        self.assertEqual(plan[0]["action"], "r2")
        self.assertEqual(plan[1]["action"], "r1")

    def test_recreated_and_skipped_are_done(self):
        state = _state([
            _item("a", "recreated", new_url="https://x/new"),
            _item("b", "skipped"),
        ])
        plan = build_plan(state)
        self.assertEqual([p["action"] for p in plan], ["done", "done"])

    def test_failed_surfaces_for_manual_decision(self):
        # Failed items must not auto-retry — operator decides per the
        # refresh-strategy.md resume table.
        state = _state([_item("a", "failed", failure_reason="snapshot mismatch")])
        plan = build_plan(state)
        self.assertEqual(plan[0]["action"], "manual")
        self.assertEqual(plan[0]["failure_reason"], "snapshot mismatch")

    def test_plan_preserves_item_index_ordering(self):
        state = _state([
            _item("a", "recreated"),
            _item("b", "deleted"),
            _item("c", "pending"),
        ])
        plan = build_plan(state)
        self.assertEqual([p["item_index"] for p in plan], [0, 1, 2])
        self.assertEqual([p["subfolder"] for p in plan], ["a", "b", "c"])


class ApplyUpdateStatusTransitions(unittest.TestCase):
    """apply_update stamps the matching *_at field for each status."""

    def setUp(self):
        self.now = datetime(2026, 5, 21, 14, 30, 0)

    def test_pending_to_deleted_stamps_deleted_at(self):
        state = _state([_item("a", "pending")])
        apply_update(state, 0, status="deleted", delete_detection="redirect",
                     new_url=None, failure_reason=None, now=self.now)
        item = state["items"][0]
        self.assertEqual(item["status"], "deleted")
        self.assertEqual(item["deleted_at"], "2026-05-21T14:30:00")
        self.assertEqual(item["delete_detection"], "redirect")
        # Other *_at fields stay None.
        self.assertIsNone(item["recreated_at"])
        self.assertIsNone(item["failed_at"])

    def test_deleted_to_recreated_stamps_recreated_at_and_url(self):
        state = _state([_item("a", "deleted", delete_detection="redirect",
                              deleted_at="2026-05-21T14:00:00")])
        apply_update(state, 0, status="recreated", delete_detection=None,
                     new_url="https://www.facebook.com/marketplace/item/999/",
                     failure_reason=None, now=self.now)
        item = state["items"][0]
        self.assertEqual(item["status"], "recreated")
        self.assertEqual(item["recreated_at"], "2026-05-21T14:30:00")
        self.assertEqual(item["new_url"],
                         "https://www.facebook.com/marketplace/item/999/")
        # Prior delete stamp preserved.
        self.assertEqual(item["deleted_at"], "2026-05-21T14:00:00")

    def test_failed_records_reason_and_stamp(self):
        state = _state([_item("a", "pending")])
        apply_update(state, 0, status="failed", delete_detection=None,
                     new_url=None, failure_reason="snapshot mismatch",
                     now=self.now)
        item = state["items"][0]
        self.assertEqual(item["status"], "failed")
        self.assertEqual(item["failure_reason"], "snapshot mismatch")
        self.assertEqual(item["failed_at"], "2026-05-21T14:30:00")

    def test_unknown_status_raises(self):
        state = _state([_item("a", "pending")])
        with self.assertRaises(ValueError):
            apply_update(state, 0, status="bogus", delete_detection=None,
                         new_url=None, failure_reason=None, now=self.now)

    def test_item_index_out_of_range_raises(self):
        state = _state([_item("a", "pending")])
        with self.assertRaises(IndexError):
            apply_update(state, 7, status="deleted", delete_detection=None,
                         new_url=None, failure_reason=None, now=self.now)


class FindLatestAndUnfinished(unittest.TestCase):
    """File-discovery and resume-decision helpers."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="refresh-runstate-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_empty_folder_returns_none(self):
        self.assertIsNone(find_latest_runstate(self.tmp))

    def test_latest_by_lexicographic_filename(self):
        # YYYYMMDD-HHMM sorts correctly under lex order.
        for name in [".resell-au-refresh-20260501-0900.json",
                     ".resell-au-refresh-20260521-1400.json",
                     ".resell-au-refresh-20260510-2300.json"]:
            (self.tmp / name).write_text("{}", encoding="utf-8")
        latest = find_latest_runstate(self.tmp)
        assert latest is not None
        self.assertEqual(latest.name, ".resell-au-refresh-20260521-1400.json")

    def test_has_unfinished_work_true_when_any_pending(self):
        self.assertTrue(has_unfinished_work(_state([
            _item("a", "recreated"), _item("b", "pending"),
        ])))

    def test_has_unfinished_work_true_when_any_deleted(self):
        self.assertTrue(has_unfinished_work(_state([
            _item("a", "recreated"), _item("b", "deleted"),
        ])))

    def test_has_unfinished_work_true_when_any_failed(self):
        # Failed items count as unfinished — the operator might fix the
        # underlying issue and want to resume from the same file.
        self.assertTrue(has_unfinished_work(_state([
            _item("a", "recreated"), _item("b", "failed"),
        ])))

    def test_has_unfinished_work_false_when_all_terminal(self):
        self.assertFalse(has_unfinished_work(_state([
            _item("a", "recreated"), _item("b", "skipped"),
        ])))

    def test_has_unfinished_work_false_for_empty_items(self):
        self.assertFalse(has_unfinished_work(_state([])))


class RunstateFilenameFormat(unittest.TestCase):
    """Filename format is the resume contract — pin it explicitly."""

    def test_format_matches_documented_pattern(self):
        when = datetime(2026, 5, 21, 14, 30, 45)
        self.assertEqual(runstate_filename(when),
                         ".resell-au-refresh-20260521-1430.json")

    def test_format_zero_pads_single_digit_components(self):
        when = datetime(2026, 1, 5, 9, 3, 0)
        self.assertEqual(runstate_filename(when),
                         ".resell-au-refresh-20260105-0903.json")


class CmdInitIntegration(unittest.TestCase):
    """End-to-end CLI behaviour for the three init paths."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="refresh-runstate-init-"))
        os.environ["REFRESH_RUNSTATE_NOW"] = "2026-05-21T14:00:00"
        queued = [{
            "subfolder": "kettlebell",
            "title": "12kg Kettlebell",
            "old_url": "https://www.facebook.com/marketplace/item/111/",
            "old_price": 45,
            "new_price": 40,
            "floor": 35,
            "age_days": 12,
        }]
        self.queued_path = self.tmp / "queued.json"
        self.queued_path.write_text(json.dumps(queued), encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.environ.pop("REFRESH_RUNSTATE_NOW", None)

    def _run_init(self, queued_json: Path | None) -> tuple[int, Path | None]:
        import contextlib
        import io
        from types import SimpleNamespace
        buf = io.StringIO()
        err = io.StringIO()
        args = SimpleNamespace(
            folder=self.tmp,
            queued_json=str(queued_json) if queued_json else None,
        )
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = cmd_init(args)
        printed = buf.getvalue().strip()
        path = Path(printed) if printed else None
        return rc, path

    def test_fresh_init_creates_file_from_queued_json(self):
        rc, path = self._run_init(self.queued_path)
        self.assertEqual(rc, 0)
        assert path is not None
        self.assertTrue(path.exists())
        self.assertEqual(path.name, ".resell-au-refresh-20260521-1400.json")
        state = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(state["session_cap"], 5)
        self.assertEqual(len(state["items"]), 1)
        self.assertEqual(state["items"][0]["status"], "pending")

    def test_resume_returns_existing_file_when_work_unfinished(self):
        rc, first = self._run_init(self.queued_path)
        self.assertEqual(rc, 0)
        # Second init call (no --queued-json) should return the same path —
        # this is the "kill mid-flight + restart" path from the sub-task
        # acceptance criteria.
        rc2, second = self._run_init(None)
        self.assertEqual(rc2, 0)
        self.assertEqual(first, second)

    def test_resume_ignores_queued_json_argument(self):
        rc, first = self._run_init(self.queued_path)
        self.assertEqual(rc, 0)
        # Even if --queued-json is provided again on resume, the existing
        # file wins. Otherwise R0 re-running with a different queued set
        # (e.g. an item was hand-edited) would silently lose the resume
        # state.
        alt_queued = [{
            "subfolder": "violin", "title": "Violin",
            "old_url": "https://www.facebook.com/marketplace/item/999/",
            "old_price": 100, "new_price": 90, "floor": 70, "age_days": 30,
        }]
        alt_path = self.tmp / "queued-alt.json"
        alt_path.write_text(json.dumps(alt_queued), encoding="utf-8")
        rc2, second = self._run_init(alt_path)
        self.assertEqual(rc2, 0)
        self.assertEqual(first, second)
        state = json.loads(second.read_text(encoding="utf-8"))
        self.assertEqual(state["items"][0]["subfolder"], "kettlebell")

    def test_all_terminal_file_with_no_queued_json_errors(self):
        # Existing all-recreated file but no new queued list — the script
        # should not silently create an empty new file.
        state = _state([_item("a", "recreated")])
        (self.tmp / ".resell-au-refresh-20260520-0900.json").write_text(
            json.dumps(state), encoding="utf-8",
        )
        rc, path = self._run_init(None)
        self.assertEqual(rc, 2)
        self.assertIsNone(path)

    def test_all_terminal_file_with_queued_json_creates_new_file(self):
        # All-terminal old file + a new queued list → new run, new file
        # at the current timestamp. This is the typical "next session
        # after the queue drained" path.
        state = _state([_item("a", "recreated")])
        (self.tmp / ".resell-au-refresh-20260520-0900.json").write_text(
            json.dumps(state), encoding="utf-8",
        )
        rc, path = self._run_init(self.queued_path)
        self.assertEqual(rc, 0)
        assert path is not None
        self.assertEqual(path.name, ".resell-au-refresh-20260521-1400.json")

    def test_missing_required_field_in_queued_rejected(self):
        bad = [{"subfolder": "x", "title": "y"}]  # missing prices/floor/etc.
        bad_path = self.tmp / "bad.json"
        bad_path.write_text(json.dumps(bad), encoding="utf-8")
        rc, path = self._run_init(bad_path)
        self.assertEqual(rc, 2)
        self.assertIsNone(path)


if __name__ == "__main__":
    unittest.main()
