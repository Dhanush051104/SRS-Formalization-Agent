import json
import unittest
from unittest.mock import MagicMock, call

from app.critic.critic_model import CriticModel
from app.critic.schemas import CriticFinding, CriticResult
from app.reasoning.reasoning_model import ReasoningModel
from app.reasoning.schemas import ReasoningResult
from app.retrieval.context_builder import ContextPackage, RequirementContext
from app.retrieval.obsidian_retriever import RetrievalResult
from app.revision.revision_manager import RevisionManager
from app.revision.schemas import (
    RevisionHistoryEntry,
    RevisionResult,
    RevisionValidationError,
)


class TestRevisionManager(unittest.TestCase):
    def setUp(self):
        self.req_context = RequirementContext(
            requirement_id=8,
            global_number=8,
            source_number=8,
            srs_id="[SRS178]",
            section_number="3.2.1",
            section_title="Safety Subsystem",
            raw_text="The system shall disable all outputs within 10ms if loss of communication occurs.",
            normalized_text="The system shall disable all outputs within 10ms if loss of communication occurs.",
            page_number=12,
            element_index=1,
            document_id=1,
        )
        self.context_package = ContextPackage(
            requirements=[self.req_context],
            identified_patterns=[],
            obsidian_knowledge=RetrievalResult(pattern_items=[], loaded_files_count=0, read_cache_hits=0),
            provenance={"db": "test.db"},
        )

        self.sample_reasoning_1 = ReasoningResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            interpretation="Disable outputs on comm loss",
            identified_entities=["system", "outputs", "comm"],
            predicates=["disable", "loss_of_comm"],
            conditions=["loss_of_comm == true"],
            actions=["disable(outputs)"],
            temporal_constraints=["within 10ms"],
            mathematical_constraints=["response_time <= 10ms"],
            dependencies=[],
            formalization="G(loss_of_comm -> F[0,10ms] outputs_disabled)",
            assumptions=[],
            unresolved_items=[],
        )

        self.sample_reasoning_2 = ReasoningResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            interpretation="Disable all outputs within 10ms upon comm loss",
            identified_entities=["system", "all_outputs", "comm_bus"],
            predicates=["is_disabled", "comm_lost"],
            conditions=["comm_lost == true"],
            actions=["disable_all_outputs()"],
            temporal_constraints=["t <= 10ms"],
            mathematical_constraints=["response_delay <= 10ms"],
            dependencies=[],
            formalization="G(comm_lost -> F[0, 10ms] all_outputs_disabled)",
            assumptions=["comm_lost detected hardware trigger"],
            unresolved_items=[],
        )

    def test_revision_immediate_pass(self):
        mock_reasoning = MagicMock(spec=ReasoningModel)
        mock_critic = MagicMock(spec=CriticModel)

        mock_reasoning.reason.return_value = self.sample_reasoning_1
        mock_critic.critique.return_value = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="PASS",
            summary="Formalization is complete and accurate.",
        )

        manager = RevisionManager(
            reasoning_model=mock_reasoning,
            critic_model=mock_critic,
            max_iterations=3,
        )

        res = manager.run_revision_loop(self.context_package)

        self.assertEqual(res.status, "PASS")
        self.assertEqual(res.termination_reason, "CRITIC_PASSED")
        self.assertEqual(res.iterations_conducted, 1)
        self.assertEqual(len(res.history), 1)
        self.assertEqual(res.final_reasoning_result.formalization, self.sample_reasoning_1.formalization)
        mock_reasoning.reason.assert_called_once_with(self.context_package, user_prompt=None)

    def test_revision_needs_revision_then_pass(self):
        mock_reasoning = MagicMock(spec=ReasoningModel)
        mock_critic = MagicMock(spec=CriticModel)

        mock_reasoning.reason.side_effect = [self.sample_reasoning_1, self.sample_reasoning_2]

        critic_res_1 = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="NEEDS_REVISION",
            summary="Missing explicit scope for ALL outputs.",
            findings=[
                CriticFinding(
                    category="Completeness",
                    severity="WARNING",
                    description="Formalization uses outputs instead of all_outputs.",
                    recommendation="Specify all outputs explicitly.",
                )
            ],
            missing_constraints=["Explicit all_outputs scope"],
        )

        critic_res_2 = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="PASS",
            summary="Revised formalization successfully verified.",
        )

        mock_critic.critique.side_effect = [critic_res_1, critic_res_2]

        manager = RevisionManager(
            reasoning_model=mock_reasoning,
            critic_model=mock_critic,
            max_iterations=3,
        )

        res = manager.run_revision_loop(self.context_package)

        self.assertEqual(res.status, "PASS")
        self.assertEqual(res.termination_reason, "CRITIC_PASSED")
        self.assertEqual(res.iterations_conducted, 2)
        self.assertEqual(len(res.history), 2)
        self.assertEqual(res.final_reasoning_result.formalization, self.sample_reasoning_2.formalization)

        # Check call arguments: first with user_prompt=None, second with formatted prompt
        self.assertEqual(mock_reasoning.reason.call_count, 2)
        args_1 = mock_reasoning.reason.call_args_list[0]
        args_2 = mock_reasoning.reason.call_args_list[1]
        self.assertIsNone(args_1.kwargs["user_prompt"])
        self.assertIsNotNone(args_2.kwargs["user_prompt"])
        self.assertIn("REVISION REQUEST FOR REQUIREMENT [SRS178]", args_2.kwargs["user_prompt"])
        self.assertIn("Missing explicit scope for ALL outputs", args_2.kwargs["user_prompt"])

    def test_revision_immediate_blocked(self):
        mock_reasoning = MagicMock(spec=ReasoningModel)
        mock_critic = MagicMock(spec=CriticModel)

        mock_reasoning.reason.return_value = self.sample_reasoning_1
        mock_critic.critique.return_value = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="BLOCKED",
            summary="Requirement is fundamentally contradictory and un-formalizable.",
        )

        manager = RevisionManager(
            reasoning_model=mock_reasoning,
            critic_model=mock_critic,
            max_iterations=3,
        )

        res = manager.run_revision_loop(self.context_package)

        self.assertEqual(res.status, "BLOCKED")
        self.assertEqual(res.termination_reason, "CRITIC_BLOCKED")
        self.assertEqual(res.iterations_conducted, 1)

    def test_revision_max_iterations_reached(self):
        mock_reasoning = MagicMock(spec=ReasoningModel)
        mock_critic = MagicMock(spec=CriticModel)

        mock_reasoning.reason.return_value = self.sample_reasoning_1
        mock_critic.critique.return_value = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="NEEDS_REVISION",
            summary="Still missing timing upper bound constraint.",
        )

        manager = RevisionManager(
            reasoning_model=mock_reasoning,
            critic_model=mock_critic,
            max_iterations=2,
        )

        res = manager.run_revision_loop(self.context_package)

        self.assertEqual(res.status, "MAX_ITERATIONS")
        self.assertEqual(res.termination_reason, "MAX_ITERATIONS_REACHED")
        self.assertEqual(res.iterations_conducted, 2)
        self.assertEqual(mock_reasoning.reason.call_count, 2)

    def test_revision_validation_error_empty_context(self):
        mock_reasoning = MagicMock(spec=ReasoningModel)
        mock_critic = MagicMock(spec=CriticModel)
        empty_package = ContextPackage(
            requirements=[],
            identified_patterns=[],
            obsidian_knowledge=RetrievalResult(pattern_items=[], loaded_files_count=0, read_cache_hits=0),
            provenance={},
        )

        manager = RevisionManager(reasoning_model=mock_reasoning, critic_model=mock_critic)

        with self.assertRaises(RevisionValidationError):
            manager.run_revision_loop(empty_package)

    def test_revision_invalid_max_iterations(self):
        mock_reasoning = MagicMock(spec=ReasoningModel)
        mock_critic = MagicMock(spec=CriticModel)

        with self.assertRaises(RevisionValidationError):
            RevisionManager(reasoning_model=mock_reasoning, critic_model=mock_critic, max_iterations=0)

    def test_revision_result_serialization(self):
        entry = RevisionHistoryEntry(
            iteration=1,
            reasoning_result=self.sample_reasoning_1,
            critic_result=CriticResult(
                requirement_id=8,
                global_number=8,
                srs_id="[SRS178]",
                status="PASS",
            ),
        )

        res = RevisionResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="PASS",
            final_reasoning_result=self.sample_reasoning_1,
            final_critic_result=entry.critic_result,
            iterations_conducted=1,
            max_iterations=3,
            history=[entry],
            termination_reason="CRITIC_PASSED",
        )

        # Dictionary roundtrip
        d = res.to_dict()
        res_from_dict = RevisionResult.from_dict(d)
        self.assertEqual(res_from_dict.status, "PASS")
        self.assertEqual(res_from_dict.iterations_conducted, 1)
        self.assertEqual(len(res_from_dict.history), 1)

        # JSON roundtrip
        json_str = res.to_json(indent=2)
        res_from_json = RevisionResult.from_json(json_str)
        self.assertEqual(res_from_json.srs_id, "[SRS178]")
        self.assertEqual(res_from_json.termination_reason, "CRITIC_PASSED")


if __name__ == "__main__":
    unittest.main()
