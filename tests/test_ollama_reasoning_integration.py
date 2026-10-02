import unittest
from pathlib import Path

import ollama

from app.analyst import OllamaAnalyst
from app.reasoning import OllamaReasoning, ReasoningResult
from app.retrieval import ContextBuilder, ObsidianRetriever, SQLiteRetriever


class TestOllamaReasoningIntegration(unittest.TestCase):
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

    def test_live_ollama_reasoning_r8(self):
        """Test live end-to-end pipeline (SQLite -> Analyst -> ContextBuilder -> ReasoningModel) for R8 / [SRS178]."""
        if not self.ollama_available:
            self.skipTest(f"Ollama daemon or model '{self.model_name}' is not reachable. Skipping live reasoning integration test.")

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

        # 4. Run Reasoning Model to formalize the requirement
        reasoner = OllamaReasoning(model=self.model_name)
        result: ReasoningResult = reasoner.reason(context_package)

        # 5. Assert identity matching and formalization fields
        self.assertEqual(result.requirement_id, 8)
        self.assertEqual(result.global_number, 8)
        self.assertEqual(result.srs_id, "[SRS178]")
        self.assertIsInstance(result.interpretation, str)
        self.assertGreater(len(result.interpretation), 0)
        self.assertIsInstance(result.formalization, str)
        self.assertGreater(len(result.formalization), 0)
        self.assertIsInstance(result.identified_entities, list)
        self.assertIsInstance(result.predicates, list)
        self.assertIsInstance(result.assumptions, list)
        self.assertIsInstance(result.unresolved_items, list)
        self.assertIn("sqlite", result.provenance)
        self.assertIn("obsidian", result.provenance)


if __name__ == "__main__":
    unittest.main()
