import unittest

from app.analyst.ollama_analyst import OllamaAnalyst
from app.critic.ollama_critic import OllamaCritic
from app.reasoning.ollama_reasoning import OllamaReasoning
from app.retrieval.context_builder import ContextBuilder
from app.revision.revision_manager import RevisionManager
from app.revision.schemas import RevisionResult


class TestOllamaRevisionIntegration(unittest.TestCase):
    """
    Live integration test executing the complete pipeline:
    SQLite -> Analyst -> Obsidian -> ContextBuilder -> OllamaReasoning -> OllamaCritic -> RevisionManager.
    """

    def setUp(self):
        try:
            self.analyst = OllamaAnalyst()
            self.reasoning = OllamaReasoning()
            self.critic = OllamaCritic()
            self.builder = ContextBuilder()
        except Exception as e:
            self.skipTest(f"Ollama models or service unavailable: {e}")

    def test_full_revision_pipeline_r8(self):
        # 1. Analyst identifies pattern names for requirement ID 8 ([SRS178])
        req_ids = [8]
        analyst_res = self.analyst.analyze(req_ids)
        pattern_names = analyst_res.identified_patterns

        self.assertGreater(len(pattern_names), 0, "Analyst should identify at least one pattern.")

        # 2. Build ContextPackage from SQLite & Obsidian
        context_pkg = self.builder.build(req_ids, pattern_names)
        self.assertEqual(len(context_pkg.requirements), 1)
        self.assertEqual(context_pkg.requirements[0].srs_id, "[SRS178]")

        # 3. Instantiate RevisionManager with max_iterations=2
        revision_manager = RevisionManager(
            reasoning_model=self.reasoning,
            critic_model=self.critic,
            max_iterations=2,
        )

        # 4. Run bounded revision loop
        rev_res = revision_manager.run_revision_loop(context_pkg)

        self.assertIsInstance(rev_res, RevisionResult)
        self.assertEqual(rev_res.requirement_id, 8)
        self.assertEqual(rev_res.srs_id, "[SRS178]")
        self.assertIn(rev_res.status, {"PASS", "BLOCKED", "MAX_ITERATIONS"})
        self.assertGreaterEqual(rev_res.iterations_conducted, 1)
        self.assertLessEqual(rev_res.iterations_conducted, 2)
        self.assertEqual(len(rev_res.history), rev_res.iterations_conducted)

        print(f"\n[INTEGRATION TEST] Revision outcome for R8 [SRS178]:")
        print(f"  Status: {rev_res.status}")
        print(f"  Termination Reason: {rev_res.termination_reason}")
        print(f"  Iterations Conducted: {rev_res.iterations_conducted}")
        print(f"  Final Formalization: {rev_res.final_reasoning_result.formalization}")
        print(f"  Final Critic Summary: {rev_res.final_critic_result.summary}")


if __name__ == "__main__":
    unittest.main()
