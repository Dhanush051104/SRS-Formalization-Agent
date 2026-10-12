import json
import unittest
from unittest.mock import MagicMock

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
from app.ui.app import app as flask_app


class TestFormalizationPipeline(unittest.TestCase):
    """
    Deterministic offline tests for the Master Orchestrator (app/pipeline.py) and Flask UI.
    Requires no Ollama or network connectivity.
    """

    def setUp(self):
        self.flask_client = flask_app.test_client()

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

    def test_flask_formalize_routes(self):
        # 1. GET request to formalize page
        response_get = self.flask_client.get("/formalize/8")
        self.assertEqual(response_get.status_code, 200)
        self.assertIn(b"[SRS178]", response_get.data)
        self.assertIn(b"Automated Mathematical Formalization", response_get.data)

        # 2. POST request running fast mock pipeline
        response_post = self.flask_client.post(
            "/formalize/8",
            data={"mock_mode": "1", "max_revisions": "2"},
        )
        self.assertEqual(response_post.status_code, 200)
        self.assertIn(b"Pipeline Status: PASS", response_post.data)
        self.assertIn(b"G(failure_event -&gt; F[0, 10ms] safe_state)", response_post.data)
        self.assertIn(b"Timeout / Deadline", response_post.data)

        # 3. GET invalid requirement ID redirects with flash
        response_invalid = self.flask_client.get("/formalize/99999", follow_redirects=True)
        self.assertEqual(response_invalid.status_code, 200)
        self.assertIn(b"not found in database", response_invalid.data)


if __name__ == "__main__":
    unittest.main()
