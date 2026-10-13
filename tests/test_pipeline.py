import dataclasses
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from flask import render_template
from werkzeug.datastructures import MultiDict

from app.analyst.analyst_model import AnalystModel
from app.analyst.schemas import AnalystResult
from app.critic.critic_model import CriticModel
from app.critic.schemas import CriticFinding, CriticResult
from app.pipeline import FormalizationPipeline, PipelineResult
from app.reasoning.reasoning_model import ReasoningModel
from app.reasoning.schemas import ReasoningResult
from app.retrieval.context_builder import ContextBuilder, ContextPackage
from app.retrieval.sqlite_retriever import RequirementContext, SQLiteRetriever
from app.revision.revision_manager import RevisionManager
from app.revision.schemas import RevisionHistoryEntry, RevisionResult
from app.ui import result_store
from app.ui.app import app as flask_app
from tests.ui_test_support import (
    IsolatedAppTestCase,
    default_formula,
    make_test_pipeline,
    result_segment,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestFormalizationPipeline(unittest.TestCase):
    """
    Deterministic offline tests for the Master Orchestrator (app/pipeline.py).
    Requires no Ollama or network connectivity.
    """

    def setUp(self):
        # Shared mock analyst
        self.mock_analyst = MagicMock(spec=AnalystModel)
        self.mock_analyst.analyze.return_value = AnalystResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            identified_patterns=["Timeout / Deadline", "Failure Handling"],
            evidence={"Timeout / Deadline": "within 10ms", "Failure Handling": "loss of communication"},
            missing_information=[],
        )

        # Shared mock reasoning
        self.sample_reasoning_1 = ReasoningResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            formalization="G(loss_of_comm -> F[0, 10ms] outputs_disabled)",
            interpretation="Outputs disabled within 10ms upon comm loss.",
            identified_entities=["system", "outputs", "comm_bus"],
            predicates=["loss_of_comm", "outputs_disabled"],
            conditions=["loss_of_comm == true"],
            actions=["disable_outputs()"],
            temporal_constraints=["within 10ms"],
            mathematical_constraints=["response_time <= 10ms"],
            assumptions=["Sensors operational"],
            unresolved_items=["Jitter bound"],
        )

        self.mock_reasoning = MagicMock(spec=ReasoningModel)
        self.mock_reasoning.reason.return_value = self.sample_reasoning_1

        # Shared mock critic
        self.sample_critic_pass = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="PASS",
            summary="All constraints verified successfully.",
            findings=[],
        )

        self.mock_critic = MagicMock(spec=CriticModel)
        self.mock_critic.critique.return_value = self.sample_critic_pass

    def test_successful_pipeline_execution(self):
        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            reasoning_model=self.mock_reasoning,
            critic_model=self.mock_critic,
        )

        res = pipeline.run(requirement_id=8, max_revisions=2)

        self.assertIsInstance(res, PipelineResult)
        self.assertTrue(res.success)
        self.assertEqual(res.status, "PASS")
        self.assertEqual(res.requirement_id, 8)
        self.assertEqual(res.srs_id, "[SRS178]")
        self.assertIn("Timeout / Deadline", res.identified_patterns)
        self.assertEqual(res.formalization, self.sample_reasoning_1.formalization)
        self.assertGreater(len(res.symbols), 0)
        self.assertIn("sqlite", res.provenance)
        self.assertIn("symbols", res.provenance)
        self.assertEqual(res.iterations_conducted, 1)

    def test_missing_requirement_id(self):
        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            reasoning_model=self.mock_reasoning,
            critic_model=self.mock_critic,
        )

        res = pipeline.run(requirement_id=99999)

        self.assertFalse(res.success)
        self.assertEqual(res.status, "FAILED")
        self.assertEqual(res.error_stage, "SQLITE_RETRIEVAL")
        self.assertIn("99999", res.error_message)

    def test_analyst_failure_handling(self):
        failing_analyst = MagicMock(spec=AnalystModel)
        failing_analyst.analyze.side_effect = RuntimeError("Analyst model unreachable")

        pipeline = FormalizationPipeline(
            analyst_model=failing_analyst,
            reasoning_model=self.mock_reasoning,
            critic_model=self.mock_critic,
        )

        res = pipeline.run(requirement_id=8)

        self.assertFalse(res.success)
        self.assertEqual(res.status, "FAILED")
        self.assertEqual(res.error_stage, "ANALYST")
        self.assertIn("Analyst pattern identification failed", res.error_message)

    def test_context_builder_failure_handling(self):
        mock_builder = MagicMock(spec=ContextBuilder)
        mock_builder.build.side_effect = ValueError("Corrupt knowledge path")

        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            context_builder=mock_builder,
            reasoning_model=self.mock_reasoning,
            critic_model=self.mock_critic,
        )

        res = pipeline.run(requirement_id=8)

        self.assertFalse(res.success)
        self.assertEqual(res.status, "FAILED")
        self.assertEqual(res.error_stage, "CONTEXT_BUILDER")

    def test_critic_revision_loop_to_pass(self):
        # Iteration 1 returns NEEDS_REVISION, Iteration 2 returns PASS
        mock_critic_retry = MagicMock(spec=CriticModel)
        critic_needs_rev = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="NEEDS_REVISION",
            summary="Missing explicit deadline bound.",
            missing_constraints=["Upper bound deadline of 10ms"],
        )
        critic_pass = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="PASS",
            summary="All constraints verified in revision.",
        )
        mock_critic_retry.critique.side_effect = [critic_needs_rev, critic_pass]

        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            reasoning_model=self.mock_reasoning,
            critic_model=mock_critic_retry,
        )

        res = pipeline.run(requirement_id=8, max_revisions=2)

        self.assertTrue(res.success)
        self.assertEqual(res.status, "PASS")
        self.assertEqual(res.iterations_conducted, 2)
        self.assertEqual(len(res.revision_history), 2)

    def test_blocked_status_outcome(self):
        mock_critic_blocked = MagicMock(spec=CriticModel)
        mock_critic_blocked.critique.return_value = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="BLOCKED",
            summary="Contradictory requirement specification.",
        )

        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            reasoning_model=self.mock_reasoning,
            critic_model=mock_critic_blocked,
        )

        res = pipeline.run(requirement_id=8)

        self.assertTrue(res.success)
        self.assertEqual(res.status, "BLOCKED")
        self.assertEqual(res.termination_reason, "CRITIC_BLOCKED")
        # Clarifications should identify BLOCKED status
        self.assertGreater(len(res.clarifications), 0)
        categories = [c["category"] for c in res.clarifications]
        self.assertIn("BLOCKED_FORMALIZATION", categories)

    def test_max_iterations_outcome(self):
        mock_critic_loop = MagicMock(spec=CriticModel)
        mock_critic_loop.critique.return_value = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="NEEDS_REVISION",
            summary="Still failing timing bound check.",
        )

        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            reasoning_model=self.mock_reasoning,
            critic_model=mock_critic_loop,
        )

        res = pipeline.run(requirement_id=8, max_revisions=2)

        self.assertTrue(res.success)
        self.assertEqual(res.status, "MAX_ITERATIONS")
        self.assertEqual(res.termination_reason, "MAX_ITERATIONS_REACHED")
        self.assertEqual(res.iterations_conducted, 2)

    def test_source_traceability_preservation(self):
        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            reasoning_model=self.mock_reasoning,
            critic_model=self.mock_critic,
        )

        res = pipeline.run(requirement_id=8)

        self.assertEqual(res.requirement_id, 8)
        self.assertEqual(res.global_number, 8)
        self.assertEqual(res.srs_id, "[SRS178]")
        self.assertEqual(res.section_number, "3.2.1")
        self.assertEqual(res.section_title, "System Initialization")
        self.assertIn("send a single voted VMEbus reset", res.raw_text)

        # Serialization roundtrip
        d = res.to_dict()
        res_from_dict = PipelineResult.from_dict(d)
        self.assertEqual(res.formalization, res_from_dict.formalization)
        self.assertEqual(res.status, res_from_dict.status)

    # ---- Deterministic validation wiring (new) ---------------------------------------------

    def test_valid_formula_records_passing_validation(self):
        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            reasoning_model=self.mock_reasoning,
            critic_model=self.mock_critic,
        )
        res = pipeline.run(requirement_id=8, max_revisions=2)
        self.assertEqual(res.status, "PASS")
        self.assertTrue(res.validation_valid)
        self.assertEqual(res.validation_findings, [])

    def test_critic_pass_cannot_override_invalid_formula(self):
        invalid = dataclasses.replace(
            self.sample_reasoning_1,
            formalization="G(supports(up_to_3_rate_groups_per_vehicle_mode) -> F)",
        )
        reasoning = MagicMock(spec=ReasoningModel)
        reasoning.reason.return_value = invalid  # critic (self.mock_critic) always says PASS

        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            reasoning_model=reasoning,
            critic_model=self.mock_critic,
        )
        res = pipeline.run(requirement_id=8, max_revisions=2)

        self.assertTrue(res.success)
        self.assertNotEqual(res.status, "PASS")
        self.assertEqual(res.status, "MAX_ITERATIONS")
        self.assertFalse(res.validation_valid)
        self.assertIn("INCOMPLETE_TEMPORAL_OPERATOR", [f["rule"] for f in res.validation_findings])
        # Revision is bounded by max_revisions.

    def test_critic_pass_cannot_override_out_of_scope_symbol(self):
        # Requirement 1 is in scope [SRS194]; using loss_of_comm (scoped to [SRS178]) must fail
        out_of_scope = dataclasses.replace(
            self.sample_reasoning_1,
            requirement_id=1,
            global_number=1,
            srs_id="[SRS194]",
            formalization="G(loss_of_comm -> F outputs_disabled)",
        )
        reasoning = MagicMock(spec=ReasoningModel)
        reasoning.reason.return_value = out_of_scope

        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            reasoning_model=reasoning,
            critic_model=self.mock_critic,
        )
        res = pipeline.run(requirement_id=1, max_revisions=2)

        self.assertTrue(res.success)
        self.assertNotEqual(res.status, "PASS")
        self.assertEqual(res.status, "MAX_ITERATIONS")
        self.assertFalse(res.validation_valid)
        rules = [f["rule"] for f in res.validation_findings]
        self.assertIn("OUT_OF_SCOPE_SYMBOL", rules)

    def test_advisory_unregistered_symbol_does_not_fail_valid_formula(self):
        # Legitimate domain predicate that is not in the seed registry
        valid_custom = dataclasses.replace(
            self.sample_reasoning_1,
            formalization="G(custom_subsystem_active -> F operational_state)",
        )
        reasoning = MagicMock(spec=ReasoningModel)
        reasoning.reason.return_value = valid_custom

        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            reasoning_model=reasoning,
            critic_model=self.mock_critic,
        )
        res = pipeline.run(requirement_id=8, max_revisions=2)

        self.assertTrue(res.success)
        self.assertEqual(res.status, "PASS")
        self.assertTrue(res.validation_valid)
        self.assertEqual(res.iterations_conducted, 1)
        self.assertEqual(reasoning.reason.call_count, 1)

    def test_invalid_formula_is_corrected_within_bound(self):
        invalid = dataclasses.replace(self.sample_reasoning_1, formalization="G(p -> F)")
        reasoning = MagicMock(spec=ReasoningModel)
        reasoning.reason.side_effect = [invalid, self.sample_reasoning_1]

        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            reasoning_model=reasoning,
            critic_model=self.mock_critic,
        )
        res = pipeline.run(requirement_id=8, max_revisions=3)

        self.assertEqual(res.status, "PASS")
        self.assertEqual(res.iterations_conducted, 2)
        self.assertTrue(res.validation_valid)
        self.assertEqual(res.formalization, self.sample_reasoning_1.formalization)

    def test_pipeline_result_from_older_dict_without_validation_fields(self):
        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            reasoning_model=self.mock_reasoning,
            critic_model=self.mock_critic,
        )
        data = pipeline.run(requirement_id=8).to_dict()
        data.pop("validation_valid")
        data.pop("validation_findings")
        data.pop("retrieved_notes")
        restored = PipelineResult.from_dict(data)
        self.assertIsNone(restored.validation_valid)
        self.assertEqual(restored.validation_findings, [])

    def test_retrieved_note_provenance_is_preserved(self):
        pipeline = FormalizationPipeline(
            analyst_model=self.mock_analyst,
            reasoning_model=self.mock_reasoning,
            critic_model=self.mock_critic,
        )
        res = pipeline.run(requirement_id=8)
        self.assertGreater(len(res.retrieved_notes), 0)
        for note in res.retrieved_notes:
            self.assertIn(note["role"], {"pattern", "formalization", "concept"})
            self.assertTrue(note["path"])
            self.assertIsInstance(note["content"], str)
        self.assertEqual([n["path"] for n in res.retrieved_notes], res.retrieved_files)


class TestFullViewAndRoutes(IsolatedAppTestCase):
    """Single-requirement routes and Full View, with the pipeline boundary patched (no Ollama)."""

    def test_get_without_stored_result_does_not_run_pipeline(self):
        builder = self.use_pipeline(make_test_pipeline())
        response = self.client.get("/formalize/8")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"[SRS178]", response.data)
        self.assertIn(b"Automated Mathematical Formalization", response.data)
        self.assertNotIn(b"Pipeline Status", response.data)
        builder.assert_not_called()

    def test_post_runs_pipeline_and_renders_result_with_validation(self):
        pipeline = make_test_pipeline()
        builder = self.use_pipeline(pipeline)
        response = self.client.post("/formalize/8", data={"max_revisions": "2"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Pipeline Status: PASS", response.data)
        self.assertIn(b"trigger_8", response.data)
        self.assertIn(b"Deterministic Validation", response.data)
        self.assertIn(b"Structural validation passed", response.data)
        self.assertIn(b"Retrieved Knowledge Notes", response.data)
        self.assertIn(b"Timeout / Deadline", response.data)
        self.assertEqual(builder.call_count, 1)
        self.assertEqual(pipeline.reasoning_model.reason.call_count, 1)

    def test_full_view_reuses_stored_result_without_rerunning(self):
        pipeline = make_test_pipeline()
        builder = self.use_pipeline(pipeline)
        self.client.post("/formalize/8", data={"max_revisions": "2"})
        self.assertEqual(pipeline.reasoning_model.reason.call_count, 1)

        response = self.client.get("/formalize/8")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Showing the stored result", response.data)
        self.assertIn(b"trigger_8", response.data)
        self.assertIn(b"Pipeline Status: PASS", response.data)
        # No second pipeline construction or model invocation.
        self.assertEqual(builder.call_count, 1)
        self.assertEqual(pipeline.reasoning_model.reason.call_count, 1)
        self.assertEqual(pipeline.analyst_model.analyze.call_count, 1)

    def test_full_view_survives_simulated_server_restart(self):
        pipeline = make_test_pipeline()
        builder = self.use_pipeline(pipeline)
        self.client.post("/formalize/8", data={"max_revisions": "2"})

        result_store._entries = None  # forget in-memory state; the stored file must be enough
        response = self.client.get("/formalize/8")

        self.assertIn(b"trigger_8", response.data)
        self.assertEqual(builder.call_count, 1)

    def test_invalid_formula_is_shown_as_invalid_not_pass(self):
        pipeline = make_test_pipeline(formula_for=lambda req: "G(p -> F)", critic_status="PASS")
        self.use_pipeline(pipeline)
        response = self.client.post("/formalize/8", data={"max_revisions": "2"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"Pipeline Status: PASS", response.data)
        self.assertIn(b"INVALID FORMULA", response.data)
        self.assertIn(b"Structural validation FAILED", response.data)
        self.assertIn(b"INCOMPLETE_TEMPORAL_OPERATOR", response.data)

    def test_configuration_failure_is_explicit_and_not_stored(self):
        builder = self.use_pipeline(make_test_pipeline())
        builder.side_effect = RuntimeError("Configured Ollama model(s) are not installed: ghost:1.")
        response = self.client.post("/formalize/8", data={"max_revisions": "2"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"OLLAMA_CONFIGURATION", response.data)
        self.assertIn(b"ghost:1", response.data)

        later = self.client.get("/formalize/8")
        self.assertNotIn(b"Pipeline Failed", later.data)

    def test_unexpected_pipeline_exception_becomes_failed_result(self):
        pipeline = make_test_pipeline()
        pipeline.run = MagicMock(side_effect=ValueError("boom"))
        self.use_pipeline(pipeline)
        response = self.client.post("/formalize/8", data={"max_revisions": "2"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Pipeline Failed at stage [PIPELINE]", response.data)
        self.assertIn(b"boom", response.data)

    def test_invalid_requirement_id_redirects(self):
        self.use_pipeline(make_test_pipeline())
        response = self.client.get("/formalize/99999")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/", response.location)

    def test_non_numeric_max_revisions_does_not_crash(self):
        self.use_pipeline(make_test_pipeline())
        response = self.client.post("/formalize/8", data={"max_revisions": "abc"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Pipeline Status: PASS", response.data)

    def test_max_revisions_is_bounded(self):
        pipeline = make_test_pipeline(critic_status="NEEDS_REVISION")
        self.use_pipeline(pipeline)
        self.client.post("/formalize/8", data={"max_revisions": "999"})
        self.assertEqual(pipeline.reasoning_model.reason.call_count, 5)

        low = make_test_pipeline(critic_status="NEEDS_REVISION")
        self.use_pipeline(low)
        self.client.post("/formalize/8", data={"max_revisions": "0"})
        self.assertEqual(low.reasoning_model.reason.call_count, 1)

    def test_answer_clarification_persists_and_updates_view(self):
        pipeline = make_test_pipeline(unresolved=("Maximum allowable jitter tolerance",))
        self.use_pipeline(pipeline)
        resp1 = self.client.post("/formalize/8", data={"max_revisions": "2"})
        self.assertEqual(resp1.status_code, 200)
        self.assertIn(b"PASS (NEEDS CLARIFICATION)", resp1.data)
        self.assertIn(b"Maximum allowable jitter tolerance", resp1.data)

        stored_before = result_store.get(8)
        self.assertIsNotNone(stored_before)
        self.assertEqual(len(stored_before.clarifications), 1)
        q_id = stored_before.clarifications[0]["question_id"]
        self.assertEqual(stored_before.clarifications[0]["status"], "OPEN")

        # Submit answer via POST /clarify/8
        resp_clarify = self.client.post(
            "/clarify/8",
            data={
                "question_id": q_id,
                "answer": "Option A: Bound 10ms",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp_clarify.status_code, 200)
        self.assertIn(b"Recorded Stakeholder Resolution", resp_clarify.data)
        self.assertIn(b"Option A: Bound 10ms", resp_clarify.data)
        self.assertIn(b"Pipeline Status: PASS", resp_clarify.data)
        self.assertNotIn(b"PASS (NEEDS CLARIFICATION)", resp_clarify.data)

        stored_after = result_store.get(8)
        self.assertEqual(stored_after.clarifications[0]["status"], "ANSWERED")
        self.assertEqual(stored_after.clarifications[0]["answer"], "Option A: Bound 10ms")
        self.assertTrue(stored_after.clarifications[0]["answered_at"])

    def test_answer_clarification_with_custom_text(self):
        pipeline = make_test_pipeline(unresolved=("Unstated parameter",))
        self.use_pipeline(pipeline)
        self.client.post("/formalize/8")

        stored = result_store.get(8)
        q_id = stored.clarifications[0]["question_id"]

        resp = self.client.post(
            "/clarify/8",
            data={
                "question_id": q_id,
                "answer": "__custom__",
                "custom_answer": "Custom stakeholder approved parameter value 42",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Custom stakeholder approved parameter value 42", resp.data)

        stored_after = result_store.get(8)
        self.assertEqual(stored_after.clarifications[0]["answer"], "Custom stakeholder approved parameter value 42")

    def test_answer_clarification_with_rerun(self):
        pipeline = make_test_pipeline(unresolved=("Unstated parameter",))
        self.use_pipeline(pipeline)
        self.client.post("/formalize/8")
        self.assertEqual(pipeline.reasoning_model.reason.call_count, 1)

        stored = result_store.get(8)
        q_id = stored.clarifications[0]["question_id"]

        resp = self.client.post(
            "/clarify/8",
            data={
                "question_id": q_id,
                "answer": "Approved resolution",
                "rerun": "1",
                "max_revisions": "2",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        # Verify second pipeline execution occurred for the re-run
        self.assertEqual(pipeline.reasoning_model.reason.call_count, 2)
        stored_after = result_store.get(8)
        self.assertIsNotNone(stored_after)
        self.assertEqual(stored_after.clarifications[0]["status"], "ANSWERED")



class TestBatchFormalization(IsolatedAppTestCase):
    """
    Offline tests for /formalize/batch. The pipeline construction boundary is patched with mock
    models wired into a real FormalizationPipeline; no Ollama is contacted.
    """

    def post_batch(self, ids, **extra):
        fields = [("requirement_ids", str(i)) for i in ids] + list(extra.items())
        return self.client.post("/formalize/batch", data=MultiDict(fields))

    def test_empty_selection_redirects(self):
        self.use_pipeline(make_test_pipeline())
        response = self.client.post("/formalize/batch", data={})
        self.assertEqual(response.status_code, 302)

    def test_all_non_integer_ids_redirect_with_visible_message(self):
        builder = self.use_pipeline(make_test_pipeline())
        response = self.client.post(
            "/formalize/batch",
            data=MultiDict([("requirement_ids", "abc"), ("requirement_ids", "xyz")]),
        )
        self.assertEqual(response.status_code, 302)
        followed = self.client.get(response.location)
        self.assertEqual(followed.status_code, 200)
        self.assertIn(b"No valid integer requirement IDs", followed.data)
        builder.assert_not_called()

    def test_single_id_returns_result(self):
        self.use_pipeline(make_test_pipeline())
        response = self.post_batch([8], max_revisions="2")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Batch Mathematical Formalization", response.data)
        self.assertIn(b"[SRS178]", response.data)
        self.assertIn(b">PASS<", response.data)

    def test_multiple_ids_each_processed_once_independently(self):
        pipeline = make_test_pipeline()
        builder = self.use_pipeline(pipeline)
        response = self.post_batch([1, 2, 3], max_revisions="2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b"accordion-item"), 3)
        self.assertEqual(builder.call_count, 1)
        self.assertEqual(pipeline.reasoning_model.reason.call_count, 3)
        self.assertEqual(pipeline.analyst_model.analyze.call_count, 3)

    def test_results_are_associated_with_their_own_requirement(self):
        self.use_pipeline(make_test_pipeline())
        response = self.post_batch([3, 1, 2])
        html = response.data.decode("utf-8")
        # Order of the selection is preserved.
        self.assertLess(html.index('id="result-3"'), html.index('id="result-1"'))
        self.assertLess(html.index('id="result-1"'), html.index('id="result-2"'))
        for rid in (1, 2, 3):
            segment = result_segment(response.data, rid)
            self.assertIn(f"trigger_{rid}", segment)
            self.assertIn(f"Req ID {rid}", segment)
            for other in {1, 2, 3} - {rid}:
                self.assertNotIn(f"trigger_{other}", segment)
            self.assertIn(f"/formalize/{rid}", segment)  # Full View link points at the same requirement

    def test_duplicate_ids_are_processed_once(self):
        pipeline = make_test_pipeline()
        self.use_pipeline(pipeline)
        response = self.post_batch([8, 8, 8])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b"accordion-item"), 1)
        self.assertEqual(pipeline.reasoning_model.reason.call_count, 1)
        self.assertIn(b"2 duplicate requirement ID(s) were ignored", response.data)

    def test_non_integer_id_is_skipped_and_reported(self):
        self.use_pipeline(make_test_pipeline())
        response = self.post_batch(["abc", 8])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b"accordion-item"), 1)
        self.assertIn(b"Ignored non-integer", response.data)
        self.assertIn(b"abc", response.data)

    def test_invalid_id_fails_without_stopping_valid_ids(self):
        self.use_pipeline(make_test_pipeline())
        response = self.post_batch([8, 99999, 1])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b"accordion-item"), 3)

        good = result_segment(response.data, 8)
        self.assertIn(">PASS<", good)
        self.assertIn("trigger_8", good)

        bad = result_segment(response.data, 99999)
        self.assertIn(">FAILED<", bad)
        self.assertIn("SQLITE_RETRIEVAL", bad)
        self.assertIn("Req ID 99999", bad)
        self.assertNotIn(">PASS<", bad)
        self.assertNotIn("/formalize/99999", bad)  # no Full View link for a failed requirement

        later = result_segment(response.data, 1)
        self.assertIn(">PASS<", later)
        self.assertIn("trigger_1", later)

    def test_crash_in_one_requirement_does_not_affect_others(self):
        self.use_pipeline(make_test_pipeline(fail_reasoning_for={2}))
        response = self.post_batch([1, 2, 3])
        self.assertEqual(response.data.count(b"accordion-item"), 3)

        failed = result_segment(response.data, 2)
        self.assertIn(">FAILED<", failed)
        self.assertIn("REVISION_LOOP", failed)
        self.assertNotIn(">PASS<", failed)
        for rid in (1, 3):
            ok = result_segment(response.data, rid)
            self.assertIn(">PASS<", ok)
            self.assertIn(f"trigger_{rid}", ok)

    def test_invalid_formula_with_critic_pass_is_not_reported_as_pass(self):
        self.use_pipeline(make_test_pipeline(formula_for=lambda req: "G(p -> F)", critic_status="PASS"))
        response = self.post_batch([8], max_revisions="2")
        segment = result_segment(response.data, 8)
        self.assertIn("INVALID FORMULA", segment)
        self.assertNotIn(">PASS<", segment)
        self.assertIn("INCOMPLETE_TEMPORAL_OPERATOR", segment)

    def test_pass_with_open_clarifications_is_distinguished(self):
        self.use_pipeline(make_test_pipeline(unresolved=("Maximum allowable jitter tolerance",)))
        response = self.post_batch([8])
        segment = result_segment(response.data, 8)
        self.assertIn("PASS (NEEDS CLARIFICATION)", segment)
        self.assertNotIn(">PASS<", segment)
        self.assertIn("Maximum allowable jitter tolerance", segment)

    def test_blocked_is_distinguished(self):
        self.use_pipeline(make_test_pipeline(critic_status="BLOCKED"))
        response = self.post_batch([8])
        segment = result_segment(response.data, 8)
        self.assertIn(">BLOCKED<", segment)
        self.assertNotIn(">PASS<", segment)

    def test_configuration_failure_marks_every_requirement_failed_and_stores_nothing(self):
        builder = self.use_pipeline(make_test_pipeline())
        builder.side_effect = RuntimeError("Ollama is unavailable or returned invalid installed-model data: refused")
        response = self.post_batch([1, 2])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b"accordion-item"), 2)
        for rid in (1, 2):
            segment = result_segment(response.data, rid)
            self.assertIn(">FAILED<", segment)
            self.assertIn("OLLAMA_CONFIGURATION", segment)
            self.assertNotIn(">PASS<", segment)
        self.assertNotIn(b"Pipeline Failed", self.client.get("/formalize/1").data)

    def test_batch_results_are_stored_and_full_view_does_not_rerun(self):
        pipeline = make_test_pipeline()
        builder = self.use_pipeline(pipeline)
        self.post_batch([1, 2])
        self.assertEqual(pipeline.reasoning_model.reason.call_count, 2)

        response = self.client.get("/formalize/2")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Showing the stored result", response.data)
        self.assertIn(b"trigger_2", response.data)
        self.assertNotIn(b"trigger_1", response.data)
        self.assertEqual(builder.call_count, 1)
        self.assertEqual(pipeline.reasoning_model.reason.call_count, 2)

    def test_later_failure_does_not_replace_stored_success(self):
        builder = self.use_pipeline(make_test_pipeline())
        self.post_batch([8])
        builder.return_value = make_test_pipeline(fail_reasoning_for={8})
        rerun = self.post_batch([8])
        self.assertIn(">FAILED<", result_segment(rerun.data, 8))

        full_view = self.client.get("/formalize/8")
        self.assertIn(b"trigger_8", full_view.data)
        self.assertIn(b"Pipeline Status: PASS", full_view.data)

    def test_batch_get_with_query_params(self):
        self.use_pipeline(make_test_pipeline())
        response = self.client.get("/formalize/batch?requirement_ids=8&max_revisions=2")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"[SRS178]", response.data)

    def test_non_numeric_max_revisions_does_not_crash_batch(self):
        self.use_pipeline(make_test_pipeline())
        response = self.post_batch([8], max_revisions="not-a-number")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b">PASS<", response.data)


class TestUiRendering(unittest.TestCase):
    def test_uploaded_at_renders_as_a_date_not_a_generator(self):
        documents = [
            {"id": 1, "filename": "a.pdf", "uploaded_at": "2026-10-12T10:11:12.123456", "recommended_section": None},
            {"id": 2, "filename": "b.pdf", "uploaded_at": None, "recommended_section": None},
        ]
        with flask_app.test_request_context("/"):
            html = render_template("index.html", documents=documents)
        self.assertIn("2026-10-12 10:11:12", html)
        self.assertNotIn("generator object", html)
        self.assertNotIn("sync_do_slice", html)
        self.assertNotIn(".123456", html)

    def test_no_fast_mode_or_production_mock_remains_in_ui(self):
        sources = [PROJECT_ROOT / "app" / "ui" / "app.py"]
        sources += sorted((PROJECT_ROOT / "app" / "ui" / "templates").glob("*.html"))
        for path in sources:
            text = path.read_text(encoding="utf-8")
            for forbidden in ("mock_mode", "Fast Mode", "_build_mock_pipeline", "MagicMock"):
                self.assertNotIn(forbidden, text, f"{forbidden!r} found in {path.name}")


if __name__ == "__main__":
    unittest.main()
