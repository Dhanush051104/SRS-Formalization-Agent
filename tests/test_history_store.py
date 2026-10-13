"""Offline unit and integration tests for Formalization History / Results Ledger.

Verifies persistence, recovery, searching, filtering, clarification updates,
and UI views without running Ollama inference or altering production data.
"""

import json
import sqlite3
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.db.canonical_store import DEFAULT_DB_PATH
from app.pipeline import PipelineResult
from app.ui import history_store, result_store
from tests.ui_test_support import (
    IsolatedAppTestCase,
    make_test_pipeline,
)


def _make_sample_result(
    req_id: int = 8,
    srs_id: str = "[SRS178]",
    formula: str = "G(trigger_8 -> F[0, 10ms] response_8)",
    status: str = "PASS",
    success: bool = True,
    validation_valid: bool = True,
    clarifications: list = None,
    raw_text: str = "Upon loss of communication, outputs shall be disabled within 10ms.",
) -> PipelineResult:
    return PipelineResult(
        requirement_id=req_id,
        global_number=req_id,
        srs_id=srs_id,
        section_number="3.2",
        section_title="Communication Interface",
        raw_text=raw_text,
        identified_patterns=["Timeout / Deadline", "Failure Handling"],
        analyst_rationale="Found timeout and failure patterns.",
        analyst_confidence="HIGH",
        retrieved_patterns=["Timeout / Deadline", "Failure Handling"],
        retrieved_files=["Patterns/pat-timeout-deadline.md"],
        retrieved_notes=[
            {"path": "Patterns/pat-timeout-deadline.md", "title": "Timeout", "role": "pattern", "content": "..."},
        ],
        symbols=[],
        provenance={"obsidian": {}, "sqlite": {}, "symbols": {}},
        formalization=formula,
        interpretation=f"Interpretation for requirement {req_id}",
        entities=["system", "outputs"],
        predicates=[f"trigger_{req_id}", f"response_{req_id}"],
        conditions=["trigger == true"],
        actions=["disable_outputs()"],
        temporal_constraints=["within 10ms"],
        mathematical_constraints=["response_time <= 10ms"],
        status=status,
        termination_reason="",
        validation_valid=validation_valid,
        validation_findings=[] if validation_valid else [{"rule": "SYNTAX", "message": "Syntax error in formula"}],
        critic_summary="Mock critic summary.",
        critic_findings=[],
        iterations_conducted=1,
        max_iterations=2,
        revision_history=[],
        assumptions=[],
        unresolved_items=[],
        clarifications=clarifications or [],
        success=success,
        error_stage=None if success else "REASONING",
        error_message=None if success else "Model inference failed",
    )


class TestHistoryStore(IsolatedAppTestCase):
    """Test suite for history storage, queries, and Flask routes."""

    def test_save_completed_single_requirement_run(self):
        res = _make_sample_result(8, "[SRS178]")
        run_id = history_store.record_run(
            run_type="single",
            requirement_ids=[8],
            results=[res],
            max_revisions=2,
            model_config={"analyst": "llama3:latest", "reasoning": "llama3:latest", "critic": "llama3:latest"},
        )

        self.assertTrue(run_id.startswith("run_"))
        run = history_store.get_run(run_id)
        self.assertIsNotNone(run)
        self.assertEqual(run["run_type"], "single")
        self.assertEqual(run["requirement_ids"], [8])
        self.assertEqual(run["requirement_count"], 1)
        self.assertEqual(run["status_summary"].get("PASS"), 1)
        self.assertEqual(len(run["items"]), 1)
        self.assertEqual(run["items"][0]["srs_id"], "[SRS178]")

    def test_save_completed_batch_run_with_multiple_requirements(self):
        res1 = _make_sample_result(1, "[SRS001]", formula="G(p -> q)", status="PASS")
        res2 = _make_sample_result(2, "[SRS002]", formula="G(r -> s)", status="PASS", validation_valid=False)
        res3 = _make_sample_result(3, "[SRS003]", formula="", status="BLOCKED", success=False)

        run_id = history_store.record_run(
            run_type="batch",
            requirement_ids=[1, 2, 3],
            results=[res1, res2, res3],
            max_revisions=3,
            group_id=42,
        )

        run = history_store.get_run(run_id)
        self.assertIsNotNone(run)
        self.assertEqual(run["run_type"], "batch")
        self.assertEqual(run["requirement_ids"], [1, 2, 3])
        self.assertEqual(run["requirement_count"], 3)
        self.assertEqual(run["group_id"], 42)
        self.assertEqual(run["max_revisions"], 3)
        self.assertEqual(run["status_summary"].get("PASS"), 1)
        self.assertEqual(run["status_summary"].get("INVALID FORMULA"), 1)
        self.assertEqual(run["status_summary"].get("FAILED"), 1)

    def test_persisting_history_across_reinitialization(self):
        res = _make_sample_result(8, "[SRS178]")
        run_id = history_store.record_run(
            run_type="single",
            requirement_ids=[8],
            results=[res],
        )

        # Force in-memory cache reset
        history_store._history_entries = None

        # Re-fetch from disk
        reloaded = history_store.get_run(run_id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded["run_id"], run_id)
        self.assertEqual(reloaded["items"][0]["formalization"], "G(trigger_8 -> F[0, 10ms] response_8)")

    def test_listing_runs_in_reverse_chronological_order(self):
        res1 = _make_sample_result(1, "[SRS001]")
        res2 = _make_sample_result(2, "[SRS002]")
        res3 = _make_sample_result(3, "[SRS003]")

        id1 = history_store.record_run("single", [1], [res1], created_at="2026-01-01T10:00:00")
        id2 = history_store.record_run("single", [2], [res2], created_at="2026-01-01T11:00:00")
        id3 = history_store.record_run("single", [3], [res3], created_at="2026-01-01T12:00:00")

        runs = history_store.get_runs()
        self.assertEqual(len(runs), 3)
        # Newest run recorded should appear first
        self.assertEqual(runs[0]["run_id"], id3)
        self.assertEqual(runs[1]["run_id"], id2)
        self.assertEqual(runs[2]["run_id"], id1)

    def test_searching_and_filtering_results(self):
        res1 = _make_sample_result(1, "[SRS100]", raw_text="Watchdog timer resets processor.", status="PASS")
        res2 = _make_sample_result(2, "[SRS200]", raw_text="VMEbus communication timeout.", validation_valid=False)
        res3 = _make_sample_result(3, "[SRS300]", raw_text="Sensor reading calibration.", status="PASS")

        history_store.record_run("single", [1], [res1])
        history_store.record_run("single", [2], [res2])
        history_store.record_run("batch", [3], [res3])

        # Search by SRS ID
        found_srs = history_store.get_runs(search_query="SRS200")
        self.assertEqual(len(found_srs), 1)
        self.assertEqual(found_srs[0]["requirement_ids"], [2])

        # Search by text keyword
        found_text = history_store.get_runs(search_query="Watchdog")
        self.assertEqual(len(found_text), 1)
        self.assertEqual(found_text[0]["requirement_ids"], [1])

        # Filter by run_type
        single_runs = history_store.get_runs(run_type="single")
        self.assertEqual(len(single_runs), 2)
        batch_runs = history_store.get_runs(run_type="batch")
        self.assertEqual(len(batch_runs), 1)

        # Filter by status
        invalid_runs = history_store.get_runs(status_filter="INVALID FORMULA")
        self.assertEqual(len(invalid_runs), 1)
        self.assertEqual(invalid_runs[0]["requirement_ids"], [2])

        # Test unique results search and filter
        unique_pass = history_store.get_all_unique_results(status_filter="PASS")
        self.assertEqual(len(unique_pass), 2)
        unique_search = history_store.get_all_unique_results(search_query="calibration")
        self.assertEqual(len(unique_search), 1)
        self.assertEqual(unique_search[0]["requirement_id"], 3)

    def test_open_individual_historical_result(self):
        res = _make_sample_result(8, "[SRS178]", formula="G(trigger_8 -> F[0, 10ms] response_8)")
        run_id = history_store.record_run("single", [8], [res])
        result_store.save(res)

        # Open run detail page
        response = self.client.get(f"/history/run/{run_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"[SRS178]", response.data)
        self.assertIn(b"G(trigger_8 -&gt; F[0, 10ms] response_8)", response.data)
        self.assertIn(b"SINGLE RUN", response.data)

        # Open Full View page
        fv_resp = self.client.get("/formalize/8")
        self.assertEqual(fv_resp.status_code, 200)
        self.assertIn(b"[SRS178]", fv_resp.data)
        self.assertIn(b"G(trigger_8 -&gt; F[0, 10ms] response_8)", fv_resp.data)
        self.assertIn(b"Showing the stored result", fv_resp.data)

    def test_preserving_clarifications_and_saved_answers(self):
        clarif = {
            "question_id": "CQ-8-1",
            "text": "What is the timeout duration?",
            "status": "OPEN",
            "options": ["10ms", "20ms", "50ms"],
            "answer": None,
            "answered_at": None,
        }
        res = _make_sample_result(8, "[SRS178]", clarifications=[clarif])
        run_id = history_store.record_run("single", [8], [res])
        result_store.save(res)

        # Answer question
        updated = history_store.update_clarification_in_history(
            requirement_id=8,
            question_id="CQ-8-1",
            answer="10ms",
            answered_at="2026-10-13T10:00:00Z",
        )
        self.assertTrue(updated)

        run = history_store.get_run(run_id)
        saved_q = run["items"][0]["clarifications"][0]
        self.assertEqual(saved_q["status"], "ANSWERED")
        self.assertEqual(saved_q["answer"], "10ms")
        self.assertEqual(saved_q["answered_at"], "2026-10-13T10:00:00Z")

    def test_preserving_earlier_successful_result_after_failed_rerun(self):
        success_res = _make_sample_result(8, "[SRS178]", formula="G(p -> q)", status="PASS", success=True)
        fail_res = _make_sample_result(8, "[SRS178]", formula="", status="FAILED", success=False)

        # First save successful
        self.assertTrue(result_store.save(success_res))
        history_store.record_run("single", [8], [success_res])

        # Failed run does not overwrite successful result in cache
        stored_success = result_store.save(fail_res)
        self.assertFalse(stored_success)

        # Cache still returns the successful result
        current_in_store = result_store.get(8)
        self.assertIsNotNone(current_in_store)
        self.assertTrue(current_in_store.success)
        self.assertEqual(current_in_store.formalization, "G(p -> q)")

    def test_handling_empty_history(self):
        stats = history_store.get_overview_stats()
        self.assertEqual(stats["total_runs"], 0)
        self.assertEqual(stats["total_evaluations"], 0)
        self.assertEqual(stats["unique_requirements_count"], 0)
        self.assertEqual(stats["unique_status_counts"]["PASS"], 0)

        runs = history_store.get_runs()
        self.assertEqual(runs, [])

        unique = history_store.get_all_unique_results()
        self.assertEqual(unique, [])

        # UI route loads empty state cleanly
        resp = self.client.get("/history")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"No formalization runs found", resp.data)

        # Non-existent run redirects gracefully
        non_existent = self.client.get("/history/run/invalid_run_id_xyz", follow_redirects=True)
        self.assertEqual(non_existent.status_code, 200)
        self.assertIn(b"not found in history store", non_existent.data)

    def test_handling_malformed_or_incomplete_records(self):
        # Write corrupted JSON to history store file
        history_store.HISTORY_STORE_PATH.write_text("MALFORMED JSON {{{", encoding="utf-8")
        history_store._history_entries = None

        # Should handle gracefully by backing up corrupt file and starting fresh
        loaded = history_store._load()
        self.assertEqual(loaded, {"runs": []})
        self.assertTrue(history_store.HISTORY_STORE_PATH.with_suffix(".corrupt.json").exists())

        # Test incomplete record dictionary
        incomplete_item = {
            "requirement_id": 99,
            "srs_id": "[SRS099]",
            "raw_text": "Incomplete record",
            "formalization": "G(a -> b)",
            # Missing clarifications, missing critic findings, etc.
        }
        run_id = history_store.record_run("single", [99], [incomplete_item])
        run = history_store.get_run(run_id)
        self.assertIsNotNone(run)
        self.assertEqual(run["requirement_ids"], [99])

    def test_viewing_history_never_triggers_model_inference(self):
        res = _make_sample_result(8, "[SRS178]")
        run_id = history_store.record_run("single", [8], [res])
        result_store.save(res)

        pipeline = make_test_pipeline()
        builder = self.use_pipeline(pipeline)

        # GET /history
        resp1 = self.client.get("/history")
        self.assertEqual(resp1.status_code, 200)

        # GET /history/run/<run_id>
        resp2 = self.client.get(f"/history/run/{run_id}")
        self.assertEqual(resp2.status_code, 200)

        # GET /formalize/8
        resp3 = self.client.get("/formalize/8")
        self.assertEqual(resp3.status_code, 200)

        # Builder and models were never invoked
        builder.assert_not_called()
        self.assertEqual(pipeline.analyst_model.analyze.call_count, 0)
        self.assertEqual(pipeline.reasoning_model.reason.call_count, 0)
        self.assertEqual(pipeline.critic_model.critique.call_count, 0)

    def test_history_operations_do_not_create_target_groups_or_modify_db(self):
        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT count(*) FROM target_groups;")
        tg_count_before = cursor.fetchone()[0]

        cursor.execute("SELECT count(*) FROM target_group_members;")
        tgr_count_before = cursor.fetchone()[0]

        cursor.execute("SELECT count(*) FROM requirements;")
        req_count_before = cursor.fetchone()[0]
        conn.close()

        # Perform comprehensive history store operations
        res = _make_sample_result(8, "[SRS178]")
        run_id = history_store.record_run("single", [8], [res])
        history_store.get_runs()
        history_store.get_run(run_id)
        history_store.get_overview_stats()
        history_store.get_all_unique_results()
        self.client.get("/history")
        self.client.get(f"/history/run/{run_id}")

        conn = sqlite3.connect(DEFAULT_DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT count(*) FROM target_groups;")
        tg_count_after = cursor.fetchone()[0]

        cursor.execute("SELECT count(*) FROM target_group_members;")
        tgr_count_after = cursor.fetchone()[0]

        cursor.execute("SELECT count(*) FROM requirements;")
        req_count_after = cursor.fetchone()[0]
        conn.close()

        self.assertEqual(tg_count_before, tg_count_after)
        self.assertEqual(tgr_count_before, tgr_count_after)
        self.assertEqual(req_count_before, req_count_after)


if __name__ == "__main__":
    unittest.main()
