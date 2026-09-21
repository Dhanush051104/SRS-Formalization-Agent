import unittest
from pathlib import Path

import ollama

from app.analyst import AnalystResult, OllamaAnalyst
from app.retrieval import ContextBuilder, ObsidianRetriever, SQLiteRetriever


class TestOllamaAnalystIntegration(unittest.TestCase):
    """
    Live integration test suite communicating with local Ollama service and llama3:latest.
    Automatically skips if Ollama daemon is unreachable or llama3:latest model is missing.
    """

    @classmethod
    def setUpClass(cls):
        cls.project_root = Path(__file__).resolve().parent.parent
        cls.registry_path = cls.project_root / "SRS-Knowledge" / "Index" / "Pattern-Registry.json"
        cls.model_name = "llama3:latest"
        
        # Check if Ollama service is reachable and has llama3:latest
        cls.ollama_available = False
        try:
            models_response = ollama.list()
            # Extract model names
            model_names = []
            if hasattr(models_response, "models"):
                model_names = [m.model for m in models_response.models]
            elif isinstance(models_response, dict) and "models" in models_response:
                model_names = [m["name"] if isinstance(m, dict) else str(m) for m in models_response["models"]]

            if any(cls.model_name in m for m in model_names) or any("llama3" in m for m in model_names):
                cls.ollama_available = True
        except Exception:
            cls.ollama_available = False

    def test_live_ollama_analyst_r8(self):
        """Test live OllamaAnalyst classification for requirement R8 / [SRS178]."""
        if not self.ollama_available:
            self.skipTest(f"Ollama daemon or model '{self.model_name}' is not reachable. Skipping live integration test.")

        sqlite_retriever = SQLiteRetriever()
        req_context = sqlite_retriever.get_requirement_by_id(8)

        analyst = OllamaAnalyst(
            model=self.model_name,
            registry_path=self.registry_path,
        )

        result: AnalystResult = analyst.analyze(req_context)

        # 1. Verify requirement identity matching
        self.assertEqual(result.requirement_id, 8)
        self.assertEqual(result.global_number, 8)
        self.assertEqual(result.srs_id, "[SRS178]")

        # 2. Verify patterns were identified and are valid canonical names
        self.assertIsInstance(result.identified_patterns, list)
        self.assertGreater(len(result.identified_patterns), 0)

        catalog = analyst.load_pattern_catalog()
        for pat in result.identified_patterns:
            self.assertIn(pat, catalog, f"Identified pattern '{pat}' is not in canonical Pattern-Registry.json")

        # 3. Verify ContextBuilder integration
        builder = ContextBuilder(
            sqlite_retriever=sqlite_retriever,
            obsidian_retriever=ObsidianRetriever(),
        )

        context_package = builder.build(
            requirement_ids=[req_context.requirement_id],
            pattern_names=result.identified_patterns,
        )

        self.assertEqual(len(context_package.requirements), 1)
        self.assertEqual(context_package.identified_patterns, result.identified_patterns)
        self.assertGreater(len(context_package.obsidian_knowledge.pattern_items), 0)
        self.assertIn("obsidian", context_package.provenance)


if __name__ == "__main__":
    unittest.main()
