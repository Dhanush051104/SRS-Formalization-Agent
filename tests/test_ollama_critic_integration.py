import unittest
from pathlib import Path

import ollama

from app.analyst import OllamaAnalyst
from app.critic import CriticResult, OllamaCritic
from app.reasoning import OllamaReasoning
from app.retrieval import ContextBuilder, ObsidianRetriever, SQLiteRetriever


class TestOllamaCriticIntegration(unittest.TestCase):
    """
    Live integration test suite communicating with local Ollama service and llama3:latest.
    Automatically skips if Ollama daemon is unreachable or llama3:latest model is missing.
    """

    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parent.parent
        cls.model_name = "llama3:latest"

        # Check if Ollama service is reachable and has llama3:latest
        cls.ollama_available = False
        try:
            models_response = ollama.list()
            model_names = []
            if hasattr(models_response, "models"):
                model_names = [m.model for m in models_response.models]
            elif isinstance(models_response, dict) and "models" in models_response:
                model_names = [m["name"] if isinstance(m, dict) else str(m) for m in models_response["models"]]

            if any(cls.model_name in m for m in model_names) or any("llama3" in m for m in model_names):
                cls.ollama_available = True
        except Exception:
            cls.ollama_available = False

    def test_live_ollama_critic_r8(self):
        """Test live end-to-end pipeline (SQLite -> Analyst -> ContextBuilder -> Reasoning -> Critic) for R8 / [SRS178]."""
        if not self.ollama_available:
            self.skipTest(f"Ollama daemon or model '{self.model_name}' is not reachable. Skipping live critic integration test.")

        # 1. Retrieve requirement R8 from SQLite
        sqlite_retriever = SQLiteRetriever()
        req_context = sqlite_retriever.get_requirement_by_id(8)

        # 2. Run Analyst Model to classify patterns
        analyst = OllamaAnalyst(model=self.model_name)
        analyst_result = analyst.analyze(req_context)

        # 3. Assemble ContextPackage via ContextBuilder
        builder = ContextBuilder(
            sqlite_retriever=sqlite_retriever,
            obsidian_retriever=ObsidianRetriever(),
        )
        context_package = builder.build(
            requirement_ids=[req_context.requirement_id],
            pattern_names=analyst_result.identified_patterns,
        )

        # 4. Run Reasoning Model to generate candidate formalization
        reasoner = OllamaReasoning(model=self.model_name)
        reasoning_result = reasoner.reason(context_package)

        # 5. Run Critic Model to independently verify and critique the candidate ReasoningResult
        critic = OllamaCritic(model=self.model_name)
        result: CriticResult = critic.critique(context_package, reasoning_result)

        # 6. Assert identity matching and schema fields
        self.assertEqual(result.requirement_id, 8)
        self.assertEqual(result.global_number, 8)
        self.assertEqual(result.srs_id, "[SRS178]")
        self.assertIn(result.status, {"PASS", "NEEDS_REVISION", "BLOCKED"})
        self.assertIsInstance(result.findings, list)
        self.assertIsInstance(result.missing_constraints, list)
        self.assertIsInstance(result.unsupported_assumptions, list)
        self.assertIsInstance(result.formalization_assessment, str)
        self.assertIsInstance(result.summary, str)
        self.assertGreater(len(result.summary), 0)
        self.assertIn("sqlite", result.provenance)
        self.assertIn("obsidian", result.provenance)


if __name__ == "__main__":
    unittest.main()
