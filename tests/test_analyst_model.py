import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.analyst import (
    ANALYST_SYSTEM_PROMPT,
    AnalystError,
    AnalystModel,
    AnalystResult,
    AnalystValidationError,
    NonCanonicalPatternError,
    OllamaAnalyst,
    build_analyst_user_prompt,
)
from app.retrieval import ContextBuilder, ObsidianRetriever, RequirementContext, SQLiteRetriever


class DummyAnalyst(AnalystModel):
    """Concrete stub Analyst for testing abstract AnalystModel base class logic."""

    def __init__(self, return_result: AnalystResult, registry_path=None):
        super().__init__(registry_path=registry_path)
        self.return_result = return_result

    def analyze(self, requirement_context: RequirementContext) -> AnalystResult:
        catalog = self.load_pattern_catalog()
        self.validate_result(requirement_context, self.return_result, catalog)
        return self.return_result


class TestAnalystModelUnit(unittest.TestCase):
    """Unit test suite for AnalystModel, validation rules, and OllamaAnalyst adapter."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.registry_path = self.project_root / "SRS-Knowledge" / "Index" / "Pattern-Registry.json"
        
        # Standard test RequirementContext (R8 / [SRS178])
        self.req_context = RequirementContext(
            requirement_id=8,
            global_number=8,
            source_number=8,
            srs_id="[SRS178]",
            section_number="3.2.1",
            section_title="System Initialization",
            raw_text=(
                "8. If the failed FCP processor has not synced in 2.5 seconds after the surviving triplex "
                "has detected the loss of the FCP, then the surviving triplex shall [SRS178], within 1 second, "
                "send a single voted VMEbus reset through the NE to the failed FCP."
            ),
            normalized_text=(
                "8. If the failed FCP processor has not synced in 2.5 seconds after the surviving triplex "
                "has detected the loss of the FCP, then the surviving triplex shall [SRS178], within 1 second, "
                "send a single voted VMEbus reset through the NE to the failed FCP."
            ),
            page_number=15,
            element_index=214,
            document_id=1,
            source_dependencies=[],
        )

    def test_load_pattern_catalog_from_registry(self):
        """Test that pattern catalog is loaded dynamically from Pattern-Registry.json."""
        analyst = DummyAnalyst(AnalystResult(8, 8, "[SRS178]"), registry_path=self.registry_path)
        catalog = analyst.load_pattern_catalog()

        self.assertIsInstance(catalog, list)
        self.assertGreater(len(catalog), 0)
        self.assertIn("Timeout / Deadline", catalog)
        self.assertIn("Bounded Waiting", catalog)
        self.assertIn("Failure Handling", catalog)
        self.assertIn("Component Interaction", catalog)
        self.assertIn("Cross-Requirement Dependency", catalog)

    def test_build_analyst_user_prompt_preserves_raw_text(self):
        """Test that user prompt contains exact raw requirement text and metadata."""
        catalog = ["Timeout / Deadline", "Bounded Waiting"]
        prompt = build_analyst_user_prompt(self.req_context, catalog)

        self.assertIn("requirement_id): 8", prompt)
        self.assertIn("R8", prompt)
        self.assertIn("[SRS178]", prompt)
        self.assertIn(self.req_context.raw_text, prompt)
        self.assertIn("Timeout / Deadline", prompt)
        self.assertIn("Bounded Waiting", prompt)

    def test_valid_canonical_patterns_accepted(self):
        """Test that valid canonical patterns matching registry keys pass validation."""
        valid_result = AnalystResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            identified_patterns=["Timeout / Deadline", "Bounded Waiting"],
            evidence={"Timeout / Deadline": "2.5 seconds timeout"},
            missing_information=[],
        )
        analyst = DummyAnalyst(valid_result, registry_path=self.registry_path)
        res = analyst.analyze(self.req_context)
        self.assertEqual(res.identified_patterns, ["Timeout / Deadline", "Bounded Waiting"])

    def test_non_canonical_pattern_rejected(self):
        """Test that unknown/invented pattern names raise NonCanonicalPatternError."""
        invalid_result = AnalystResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            identified_patterns=["Timeout", "Invalid Custom Pattern"],
        )
        analyst = DummyAnalyst(invalid_result, registry_path=self.registry_path)
        with self.assertRaises(NonCanonicalPatternError) as ctx:
            analyst.analyze(self.req_context)
        self.assertIn("Non-canonical pattern name identified by Analyst", str(ctx.exception))

    def test_duplicate_pattern_names_rejected(self):
        """Test that duplicate pattern names in output raise AnalystValidationError."""
        dup_result = AnalystResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            identified_patterns=["Timeout / Deadline", "Timeout / Deadline"],
        )
        analyst = DummyAnalyst(dup_result, registry_path=self.registry_path)
        with self.assertRaises(AnalystValidationError) as ctx:
            analyst.analyze(self.req_context)
        self.assertIn("Duplicate pattern name found", str(ctx.exception))

    def test_requirement_id_mismatch_rejected(self):
        """Test that requirement_id mismatch raises AnalystValidationError."""
        mismatch_result = AnalystResult(
            requirement_id=99,
            global_number=8,
            srs_id="[SRS178]",
            identified_patterns=["Timeout / Deadline"],
        )
        analyst = DummyAnalyst(mismatch_result, registry_path=self.registry_path)
        with self.assertRaises(AnalystValidationError) as ctx:
            analyst.analyze(self.req_context)
        self.assertIn("requirement_id mismatch", str(ctx.exception))

    def test_global_number_mismatch_rejected(self):
        """Test that global_number mismatch raises AnalystValidationError."""
        mismatch_result = AnalystResult(
            requirement_id=8,
            global_number=99,
            srs_id="[SRS178]",
            identified_patterns=["Timeout / Deadline"],
        )
        analyst = DummyAnalyst(mismatch_result, registry_path=self.registry_path)
        with self.assertRaises(AnalystValidationError) as ctx:
            analyst.analyze(self.req_context)
        self.assertIn("global_number mismatch", str(ctx.exception))

    def test_srs_id_mismatch_rejected(self):
        """Test that srs_id mismatch raises AnalystValidationError."""
        mismatch_result = AnalystResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS999]",
            identified_patterns=["Timeout / Deadline"],
        )
        analyst = DummyAnalyst(mismatch_result, registry_path=self.registry_path)
        with self.assertRaises(AnalystValidationError) as ctx:
            analyst.analyze(self.req_context)
        self.assertIn("srs_id mismatch", str(ctx.exception))

    def test_ollama_analyst_with_mocked_client_valid_json(self):
        """Test OllamaAnalyst with a mocked Ollama client returning valid JSON."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.message.content = json.dumps({
            "requirement_id": 8,
            "global_number": 8,
            "srs_id": "[SRS178]",
            "identified_patterns": [
                "Timeout / Deadline",
                "Bounded Waiting",
                "Failure Handling",
                "Component Interaction",
                "Cross-Requirement Dependency"
            ],
            "evidence": {
                "Timeout / Deadline": "2.5 seconds timeout",
                "Bounded Waiting": "within 1 second",
                "Failure Handling": "failed FCP processor",
                "Component Interaction": "voted VMEbus reset through NE",
                "Cross-Requirement Dependency": "synced in 2.5 seconds after loss"
            },
            "missing_information": []
        })
        mock_client.chat.return_value = mock_response

        ollama_analyst = OllamaAnalyst(
            model="llama3:latest",
            registry_path=self.registry_path,
            client=mock_client,
        )

        result = ollama_analyst.analyze(self.req_context)

        self.assertEqual(result.requirement_id, 8)
        self.assertEqual(result.global_number, 8)
        self.assertEqual(result.srs_id, "[SRS178]")
        self.assertEqual(len(result.identified_patterns), 5)
        self.assertEqual(result.identified_patterns[0], "Timeout / Deadline")

        # Verify mock client call
        mock_client.chat.assert_called_once()
        call_kwargs = mock_client.chat.call_args[1]
        self.assertEqual(call_kwargs["model"], "llama3:latest")
        self.assertEqual(call_kwargs["format"], "json")

    def test_ollama_analyst_invalid_json_raises_validation_error(self):
        """Test OllamaAnalyst raises AnalystValidationError when model outputs non-JSON."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.message.content = "This is not valid JSON string."
        mock_client.chat.return_value = mock_response

        ollama_analyst = OllamaAnalyst(
            model="llama3:latest",
            registry_path=self.registry_path,
            client=mock_client,
        )

        with self.assertRaises(AnalystValidationError) as ctx:
            ollama_analyst.analyze(self.req_context)
        self.assertIn("Failed to parse model output as JSON", str(ctx.exception))

    def test_analyst_result_integration_with_context_builder(self):
        """Test that AnalystResult.identified_patterns integrates seamlessly with ContextBuilder.build()."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.message.content = json.dumps({
            "requirement_id": 8,
            "global_number": 8,
            "srs_id": "[SRS178]",
            "identified_patterns": [
                "Timeout / Deadline",
                "Bounded Waiting"
            ],
            "evidence": {
                "Timeout / Deadline": "2.5 seconds timeout",
                "Bounded Waiting": "within 1 second"
            },
            "missing_information": []
        })
        mock_client.chat.return_value = mock_response

        ollama_analyst = OllamaAnalyst(
            model="llama3:latest",
            registry_path=self.registry_path,
            client=mock_client,
        )

        result = ollama_analyst.analyze(self.req_context)

        # Pass Analyst patterns into ContextBuilder
        builder = ContextBuilder(
            sqlite_retriever=SQLiteRetriever(),
            obsidian_retriever=ObsidianRetriever(),
        )

        context_package = builder.build(
            requirement_ids=[result.requirement_id],
            pattern_names=result.identified_patterns,
        )

        self.assertEqual(len(context_package.requirements), 1)
        self.assertEqual(context_package.requirements[0].requirement_id, 8)
        self.assertEqual(context_package.identified_patterns, ["Timeout / Deadline", "Bounded Waiting"])
        self.assertIn("obsidian", context_package.provenance)


if __name__ == "__main__":
    unittest.main()
