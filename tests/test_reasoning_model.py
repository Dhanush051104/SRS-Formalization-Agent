import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.reasoning import (
    REASONING_SYSTEM_PROMPT,
    OllamaReasoning,
    ReasoningError,
    ReasoningModel,
    ReasoningResult,
    ReasoningValidationError,
    build_reasoning_user_prompt,
)
from app.retrieval import (
    ContextBuilder,
    ContextPackage,
    ObsidianRetriever,
    RequirementContext,
    SQLiteRetriever,
)


class DummyReasoning(ReasoningModel):
    """Stub ReasoningModel implementation for testing abstract base class logic."""

    def __init__(self, return_result: ReasoningResult):
        super().__init__()
        self.return_result = return_result

    def reason(self, context_package: ContextPackage) -> ReasoningResult:
        self.validate_result(context_package, self.return_result)
        return self.return_result


class TestReasoningModelUnit(unittest.TestCase):
    """Unit test suite for ReasoningModel, validation rules, and OllamaReasoning adapter."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent

        # Setup real test ContextPackage using R8 and 2 test patterns
        sqlite_retriever = SQLiteRetriever()
        obsidian_retriever = ObsidianRetriever()
        builder = ContextBuilder(
            sqlite_retriever=sqlite_retriever,
            obsidian_retriever=obsidian_retriever,
        )

        self.context_package = builder.build(
            requirement_ids=[8],
            pattern_names=["Timeout / Deadline", "Trigger -> Action"],
        )
        self.req_context = self.context_package.requirements[0]

    def test_build_reasoning_user_prompt_formatting(self):
        """Test that build_reasoning_user_prompt formats ContextPackage data correctly."""
        prompt = build_reasoning_user_prompt(self.context_package)

        self.assertIn("Requirement ID:        8", prompt)
        self.assertIn("R8", prompt)
        self.assertIn("[SRS178]", prompt)
        self.assertIn("Timeout / Deadline", prompt)
        self.assertIn("Trigger -> Action", prompt)
        self.assertIn(self.req_context.raw_text, prompt)

    def test_valid_reasoning_result_accepted(self):
        """Test that a valid ReasoningResult passes validation cleanly."""
        valid_result = ReasoningResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            interpretation="If FCP processor fails to sync in 2.5s, send VMEbus reset within 1s.",
            identified_entities=["FCP processor", "surviving triplex", "NE", "VMEbus reset"],
            predicates=["failed_sync(FCP, 2.5s)", "detected_loss(triplex, FCP)", "send_reset(triplex, NE, FCP)"],
            conditions=["failed FCP processor not synced in 2.5s after loss detected"],
            actions=["send single voted VMEbus reset through NE to failed FCP within 1s"],
            temporal_constraints=["sync_timeout <= 2.5s", "reset_delay <= 1.0s"],
            mathematical_constraints=["t_reset - t_loss_detect <= 3.5s"],
            dependencies=["SRS177"],
            formalization="G(failed_sync(FCP, 2.5s) -> F[0,1s] send_vmebus_reset(FCP))",
            assumptions=["NE subsystem is operational during reset transmission"],
            unresolved_items=["Recovery behavior during the 1 second reset window"],
            reasoning_notes="Combined Timeout / Deadline and Trigger -> Action patterns.",
        )

        model = DummyReasoning(valid_result)
        result = model.reason(self.context_package)

        self.assertEqual(result.requirement_id, 8)
        self.assertEqual(result.global_number, 8)
        self.assertEqual(result.srs_id, "[SRS178]")
        self.assertEqual(len(result.identified_entities), 4)
        self.assertEqual(len(result.predicates), 3)
        self.assertEqual(len(result.assumptions), 1)
        self.assertEqual(len(result.unresolved_items), 1)
        self.assertIn("obsidian", result.provenance)

    def test_requirement_id_mismatch_rejected(self):
        """Test that requirement_id mismatch raises ReasoningValidationError."""
        bad_result = ReasoningResult(
            requirement_id=999,
            global_number=8,
            srs_id="[SRS178]",
        )
        model = DummyReasoning(bad_result)
        with self.assertRaises(ReasoningValidationError) as ctx:
            model.reason(self.context_package)
        self.assertIn("requirement_id mismatch", str(ctx.exception))

    def test_global_number_mismatch_rejected(self):
        """Test that global_number mismatch raises ReasoningValidationError."""
        bad_result = ReasoningResult(
            requirement_id=8,
            global_number=999,
            srs_id="[SRS178]",
        )
        model = DummyReasoning(bad_result)
        with self.assertRaises(ReasoningValidationError) as ctx:
            model.reason(self.context_package)
        self.assertIn("global_number mismatch", str(ctx.exception))

    def test_srs_id_mismatch_rejected(self):
        """Test that srs_id mismatch raises ReasoningValidationError."""
        bad_result = ReasoningResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS999]",
        )
        model = DummyReasoning(bad_result)
        with self.assertRaises(ReasoningValidationError) as ctx:
            model.reason(self.context_package)
        self.assertIn("srs_id mismatch", str(ctx.exception))

    def test_invalid_field_type_rejected(self):
        """Test that non-list value for identified_entities raises ReasoningValidationError."""
        bad_dict = {
            "requirement_id": 8,
            "global_number": 8,
            "srs_id": "[SRS178]",
            "identified_entities": "Not a list",  # invalid
        }
        with self.assertRaises(ReasoningValidationError) as ctx:
            ReasoningResult.from_dict(bad_dict)
        self.assertIn("must be a list", str(ctx.exception))

    def test_ollama_reasoning_adapter_with_mocked_client(self):
        """Test OllamaReasoning adapter using a mocked Ollama client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.message.content = json.dumps({
            "requirement_id": 8,
            "global_number": 8,
            "srs_id": "[SRS178]",
            "interpretation": "Surviving triplex resets failed FCP if sync times out.",
            "identified_entities": ["FCP processor", "surviving triplex", "NE"],
            "predicates": ["loss_detected(FCP)", "synced(FCP)", "send_reset(FCP)"],
            "conditions": ["not synced in 2.5s after loss"],
            "actions": ["send single voted VMEbus reset within 1s"],
            "temporal_constraints": ["timeout = 2.5s", "action_window = 1s"],
            "mathematical_constraints": ["t <= 1s"],
            "dependencies": ["SRS177"],
            "formalization": "G(loss_detected(FCP) & !synced(FCP, 2.5s) -> F[0,1s] send_reset(FCP))",
            "assumptions": ["NE bus is healthy"],
            "unresolved_items": ["Behavior if VMEbus reset fails"],
            "reasoning_notes": "Formalized as timed LTL implication."
        })
        mock_client.chat.return_value = mock_response

        reasoner = OllamaReasoning(model="llama3:latest", client=mock_client)
        result = reasoner.reason(self.context_package)

        self.assertEqual(result.requirement_id, 8)
        self.assertEqual(result.global_number, 8)
        self.assertEqual(result.srs_id, "[SRS178]")
        self.assertEqual(len(result.identified_entities), 3)
        self.assertIn("G(loss_detected", result.formalization)
        self.assertEqual(len(result.assumptions), 1)

        # Check mock call arguments
        mock_client.chat.assert_called_once()
        call_kwargs = mock_client.chat.call_args[1]
        self.assertEqual(call_kwargs["model"], "llama3:latest")
        self.assertEqual(call_kwargs["format"], "json")

    def test_ollama_reasoning_invalid_json_raises_validation_error(self):
        """Test that OllamaReasoning raises ReasoningValidationError if JSON parsing fails."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.message.content = "Not JSON output from LLM."
        mock_client.chat.return_value = mock_response

        reasoner = OllamaReasoning(model="llama3:latest", client=mock_client)
        with self.assertRaises(ReasoningValidationError) as ctx:
            reasoner.reason(self.context_package)
        self.assertIn("Failed to parse model output as JSON", str(ctx.exception))

    def test_ollama_reasoning_recovers_missing_requirement_id_from_trusted_context(self):
        """
        Exact regression test: If the LLM omits 'requirement_id' from its JSON output,
        OllamaReasoning recovers the trusted requirement_id from ContextPackage rather than
        failing with 'Failed to map JSON data into ReasoningResult: 'requirement_id''.
        """
        mock_client = MagicMock()
        mock_response = MagicMock()
        # Model output completely lacks requirement_id, global_number, and srs_id
        mock_response.message.content = json.dumps({
            "interpretation": "Scheduler installs tasks during initialization.",
            "identified_entities": ["Scheduler", "Task"],
            "predicates": ["install_task(t)"],
            "conditions": ["init_phase"],
            "actions": ["install_task"],
            "temporal_constraints": [],
            "mathematical_constraints": [],
            "dependencies": [],
            "formalization": "G(init_phase -> install_task)",
            "assumptions": [],
            "unresolved_items": [],
            "intermediate_representation": {
                "propositions": [
                    {"symbol": "P_init", "definition": "init_phase", "notation": "P_init := init_phase"}
                ],
                "temporal_operators": ["G"],
            },
        })
        mock_client.chat.return_value = mock_response

        reasoner = OllamaReasoning(model="llama3:latest", client=mock_client)
        result = reasoner.reason(self.context_package)

        self.assertEqual(result.requirement_id, 8)
        self.assertEqual(result.global_number, 8)
        self.assertEqual(result.srs_id, "[SRS178]")
        self.assertEqual(result.formalization, "G(init_phase -> install_task)")
        self.assertEqual(result.assumptions, [])

    def test_ollama_reasoning_recovers_alias_and_swapped_id(self):
        """Test recovery when LLM uses alias 'id' or mistakenly puts SRS ID in requirement_id."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.message.content = json.dumps({
            "requirement_id": "[SRS178]",  # Swapped SRS ID string into requirement_id
            "global_num": 8,               # Alias key for global_number
            "srs_id": "[SRS178]",
            "interpretation": "Interpretation text.",
            "identified_entities": ["System"],
            "predicates": ["p(x)"],
            "conditions": [],
            "actions": [],
            "temporal_constraints": [],
            "mathematical_constraints": [],
            "dependencies": ["SRS177"],
            "formalization": "G(p)",
            "assumptions": [],
            "unresolved_items": [],
        })
        mock_client.chat.return_value = mock_response

        reasoner = OllamaReasoning(model="llama3:latest", client=mock_client)
        result = reasoner.reason(self.context_package)

        self.assertEqual(result.requirement_id, 8)
        self.assertEqual(result.global_number, 8)
        self.assertEqual(result.srs_id, "[SRS178]")
        self.assertEqual(result.dependencies, ["SRS177"])

    def test_ollama_reasoning_detects_explicit_requirement_id_mismatch(self):
        """Test that explicit conflicting requirement_id from the model is rejected."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.message.content = json.dumps({
            "requirement_id": 999,  # Explicit mismatch against expected ID 8
            "global_number": 8,
            "srs_id": "[SRS178]",
            "interpretation": "Mismatch test.",
            "identified_entities": [],
            "predicates": [],
            "conditions": [],
            "actions": [],
            "temporal_constraints": [],
            "mathematical_constraints": [],
            "dependencies": [],
            "formalization": "True",
            "assumptions": [],
            "unresolved_items": [],
        })
        mock_client.chat.return_value = mock_response

        reasoner = OllamaReasoning(model="llama3:latest", client=mock_client)
        with self.assertRaises(ReasoningValidationError) as ctx:
            reasoner.reason(self.context_package)
        self.assertIn("requirement_id mismatch", str(ctx.exception))
        self.assertIn("expected 8, got 999", str(ctx.exception))

    def test_reasoning_result_from_dict_missing_fields_raise_informative_error(self):
        """Test that ReasoningResult.from_dict raises informative ReasoningValidationError instead of KeyError."""
        with self.assertRaises(ReasoningValidationError) as ctx:
            ReasoningResult.from_dict({"global_number": 8, "srs_id": "[SRS178]"})
        self.assertIn("missing required field 'requirement_id'", str(ctx.exception))

        with self.assertRaises(ReasoningValidationError) as ctx2:
            ReasoningResult.from_dict({"requirement_id": 8, "srs_id": "[SRS178]"})
        self.assertIn("missing required field 'global_number'", str(ctx2.exception))

        with self.assertRaises(ReasoningValidationError) as ctx3:
            ReasoningResult.from_dict({"requirement_id": 8, "global_number": 8})
        self.assertIn("missing required field 'srs_id'", str(ctx3.exception))


if __name__ == "__main__":
    unittest.main()
