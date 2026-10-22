import unittest
from unittest.mock import MagicMock

from app.analyst.analyst_model import AnalystModel
from app.analyst.schemas import AnalystResult
from app.analyst.set_analyst import CrossDependency, SetAnalysisResult, SetAnalyst
from app.critic.critic_model import CriticModel
from app.critic.schemas import CriticResult
from app.pipeline import FormalizationPipeline
from app.reasoning.reasoning_model import ReasoningModel
from app.reasoning.schemas import ReasoningResult
from app.retrieval.sqlite_retriever import RequirementContext, SQLiteRetriever


class TestSetAnalysis(unittest.TestCase):
    """
    Tests for SetAnalyst and batch-level requirement relationship analysis.
    """

    def setUp(self):
        self.analyst = SetAnalyst()
        self.req1 = RequirementContext(
            requirement_id=1,
            global_number=1,
            source_number=1,
            srs_id="[SRS001]",
            section_number="3.2.1",
            section_title="Safety Subsystem",
            raw_text="The system shall monitor comm_bus status continuously.",
            normalized_text="The system shall monitor comm_bus status continuously.",
            page_number=10,
            element_index=1,
            document_id=1,
        )
        self.req2 = RequirementContext(
            requirement_id=2,
            global_number=2,
            source_number=2,
            srs_id="[SRS002]",
            section_number="3.2.1",
            section_title="Safety Subsystem",
            raw_text="If comm_bus fails, the system shall disable all outputs in accordance with [SRS001].",
            normalized_text="If comm_bus fails, the system shall disable all outputs in accordance with [SRS001].",
            page_number=10,
            element_index=2,
            document_id=1,
        )
        self.req3 = RequirementContext(
            requirement_id=3,
            global_number=3,
            source_number=3,
            srs_id="[SRS003]",
            section_number="3.2.2",
            section_title="Actuator Controls",
            raw_text="While outputs are disabled, actuator commands shall be rejected.",
            normalized_text="While outputs are disabled, actuator commands shall be rejected.",
            page_number=11,
            element_index=3,
            document_id=1,
        )

    def test_section_clustering(self):
        res = self.analyst.analyze_set([self.req1, self.req2, self.req3])
        self.assertEqual(len(res.requirement_ids), 3)
        self.assertIn("3.2.1 - Safety Subsystem", res.section_clusters)
        self.assertIn("3.2.2 - Actuator Controls", res.section_clusters)
        self.assertEqual(res.section_clusters["3.2.1 - Safety Subsystem"], [1, 2])
        self.assertEqual(res.section_clusters["3.2.2 - Actuator Controls"], [3])

    def test_shared_entity_extraction(self):
        res = self.analyst.analyze_set([self.req1, self.req2, self.req3])
        # comm_bus appears in req 1 and 2
        self.assertIn("comm_bus", res.shared_entities)
        self.assertIn(1, res.shared_entities["comm_bus"])
        self.assertIn(2, res.shared_entities["comm_bus"])

    def test_cross_reference_discovery(self):
        res = self.analyst.analyze_set([self.req1, self.req2, self.req3])
        ref_deps = [d for d in res.cross_dependencies if d.dependency_type == "REFERENCE"]
        self.assertGreaterEqual(len(ref_deps), 1)
        dep = ref_deps[0]
        self.assertEqual(dep.source_srs_id, "[SRS002]")
        self.assertEqual(dep.target_srs_id, "[SRS001]")
        self.assertEqual(dep.target_requirement_id, 1)

    def test_producer_consumer_discovery(self):
        res = self.analyst.analyze_set([self.req1, self.req2, self.req3])
        pc_deps = [d for d in res.cross_dependencies if d.dependency_type == "PRODUCER_CONSUMER"]
        self.assertGreaterEqual(len(pc_deps), 1)
        # req 2 disables outputs, req 3 refers to disabled outputs
        matching = [d for d in pc_deps if d.source_requirement_id == 2 and d.target_requirement_id == 3]
        self.assertGreaterEqual(len(matching), 1)

    def test_requirement_specific_context_extraction(self):
        res = self.analyst.analyze_set([self.req1, self.req2, self.req3])
        req2_ctx = self.analyst.get_requirement_context_for_set(2, res)
        self.assertIn("3.2.1 - Safety Subsystem", req2_ctx["section_clusters"])
        self.assertIn("sibling req IDs: [1]", req2_ctx["section_clusters"])
        self.assertIn("comm_bus", req2_ctx["shared_entities"])

    def test_pipeline_run_batch_with_set_analysis(self):
        """Verifies that FormalizationPipeline.run_batch executes set analysis and enriches individual runs."""
        mock_sqlite = MagicMock(spec=SQLiteRetriever)
        mock_sqlite.db_path = "mock.db"
        mock_sqlite.get_requirement_by_id.side_effect = lambda rid: {
            1: self.req1,
            2: self.req2,
        }[rid]
        mock_sqlite.get_requirements_by_ids.side_effect = lambda rids: [
            {1: self.req1, 2: self.req2}[rid] for rid in rids
        ]

        mock_analyst = MagicMock(spec=AnalystModel)
        mock_analyst.analyze.return_value = AnalystResult(
            requirement_id=1,
            global_number=1,
            srs_id="[SRS001]",
            identified_patterns=["Failure Handling"],
            evidence={},
            missing_information=[],
        )

        mock_reasoning = MagicMock(spec=ReasoningModel)
        mock_reasoning.reason.side_effect = lambda ctx_pkg, **kwargs: ReasoningResult(
            requirement_id=ctx_pkg.requirements[0].requirement_id,
            global_number=ctx_pkg.requirements[0].global_number,
            srs_id=ctx_pkg.requirements[0].srs_id,
            formalization=f"G(trigger_{ctx_pkg.requirements[0].requirement_id})",
            interpretation="Test interpretation",
            constraint_provenance=[{
                "constraint_id": "C1",
                "statement": "test constraint",
                "category": "EXPLICIT_SOURCE",
            }],
        )

        mock_critic = MagicMock(spec=CriticModel)
        mock_critic.critique.side_effect = lambda ctx_pkg, r_res, **kwargs: CriticResult(
            requirement_id=r_res.requirement_id,
            global_number=r_res.global_number,
            srs_id=r_res.srs_id,
            status="PASS",
            summary="Pass",
        )

        pipeline = FormalizationPipeline(
            sqlite_retriever=mock_sqlite,
            analyst_model=mock_analyst,
            reasoning_model=mock_reasoning,
            critic_model=mock_critic,
            set_analyst=self.analyst,
        )

        results = pipeline.run_batch([1, 2], max_revisions=2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].requirement_id, 1)
        self.assertEqual(results[1].requirement_id, 2)
        self.assertIsNotNone(results[0].set_context)
        self.assertIsNotNone(results[1].set_context)
        self.assertIn("comm_bus", results[0].set_context["shared_entities"])
        self.assertEqual(len(results[0].constraint_provenance), 1)


if __name__ == "__main__":
    unittest.main()
