import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.critic import (
    CRITIC_SYSTEM_PROMPT,
    CriticError,
    CriticFinding,
    CriticModel,
    CriticResult,
    CriticValidationError,
    OllamaCritic,
    build_critic_user_prompt,
)
from app.reasoning import ReasoningResult
from app.retrieval import ContextBuilder, ContextPackage, ObsidianRetriever, SQLiteRetriever


class DummyCritic(CriticModel):
    """Stub CriticModel implementation for testing abstract base class logic."""

    def __init__(self, return_result: CriticResult):
        super().__init__()
        self.return_result = return_result

    def critique(self, context_package: ContextPackage, reasoning_result: ReasoningResult) -> CriticResult:
        self.validate_result(context_package, reasoning_result, self.return_result)
        return self.return_result


class TestCriticModelUnit(unittest.TestCase):
    """Unit test suite for CriticModel, schemas, findings, and OllamaCritic adapter."""

    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent

        # Setup real test ContextPackage using R8 and test patterns
        sqlite_retriever = SQLiteRetriever()
        obsidian_retriever = ObsidianRetriever()
        builder = ContextBuilder(
            sqlite_retriever=sqlite_retriever,
            obsidian_retriever=obsidian_retriever,
        )

        self.context_package = builder.build(
            requirement_ids=[8],
            pattern_names=["Timeout / Deadline", "Conditional Behavior"],
        )

        # Standard test ReasoningResult
        self.reasoning_result = ReasoningResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            interpretation="If failed FCP processor has not synced in 2.5s, send VMEbus reset within 1s.",
            identified_entities=["failed FCP processor", "surviving triplex", "NE", "VMEbus reset"],
            predicates=["failed(FCP)", "synced(FCP)"],
            conditions=["failed FCP processor not synced in 2.5s after loss"],
            actions=["send single voted VMEbus reset through NE within 1s"],
            temporal_constraints=["within 1 second", "2.5 seconds timeout"],
            mathematical_constraints=["time_since_loss > 2.5s"],
            dependencies=["[SRS178]"],
            formalization="G(failed(FCP) -> F[0,1s] send_vme_reset)",
            assumptions=["surviving triplex is capable of sending a VMEbus reset"],
            unresolved_items=["time_since_loss parameter definition"],
        )

    def test_build_critic_user_prompt_formatting(self):
        """Test that build_critic_user_prompt formats ContextPackage and ReasoningResult data correctly."""
        prompt = build_critic_user_prompt(self.context_package, self.reasoning_result)

        self.assertIn("Requirement ID:        8", prompt)
        self.assertIn("R8", prompt)
        self.assertIn("[SRS178]", prompt)
        self.assertIn("Timeout / Deadline", prompt)
        self.assertIn(self.reasoning_result.formalization, prompt)
        self.assertIn("surviving triplex is capable of sending a VMEbus reset", prompt)

    def test_valid_pass_result_accepted(self):
        """Test that a valid PASS CriticResult passes validation cleanly."""
        pass_result = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="PASS",
            findings=[],
            missing_constraints=[],
            unsupported_assumptions=[],
            contradictions=[],
            traceability_issues=[],
            pattern_coverage={"covered_patterns": ["Timeout / Deadline", "Conditional Behavior"]},
            formalization_assessment="Formalization statement correctly preserves temporal bounds.",
            revision_required=False,
            summary="Verification passed with zero material issues.",
        )

        model = DummyCritic(pass_result)
        res = model.critique(self.context_package, self.reasoning_result)
        self.assertEqual(res.status, "PASS")
        self.assertFalse(res.revision_required)

    def test_needs_revision_result_accepted(self):
        """Test that a valid NEEDS_REVISION CriticResult passes validation."""
        finding = CriticFinding(
            category="Timing Preservation",
            severity="WARNING",
            description="The 2.5 second precondition timing bound is omitted in the formalization expression.",
            source_evidence="If the failed FCP processor has not synced in 2.5 seconds",
            reasoning_evidence="G(failed(FCP) -> F[0,1s] send_vme_reset)",
            recommendation="Incorporate 2.5s timeout condition into LHS of implication.",
        )
        needs_rev_result = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="NEEDS_REVISION",
            findings=[finding],
            missing_constraints=["2.5s precondition bound in formalization statement"],
            unsupported_assumptions=[],
            contradictions=[],
            traceability_issues=[],
            pattern_coverage={"covered_patterns": ["Timeout / Deadline"], "unaddressed_patterns": ["Conditional Behavior"]},
            formalization_assessment="Candidate formalization omits the 2.5s precondition timing bound.",
            revision_required=True,
            summary="Critique identified 1 timing preservation warning requiring revision.",
        )

        model = DummyCritic(needs_rev_result)
        res = model.critique(self.context_package, self.reasoning_result)
        self.assertEqual(res.status, "NEEDS_REVISION")
        self.assertTrue(res.revision_required)
        self.assertEqual(len(res.findings), 1)
        self.assertEqual(res.findings[0].category, "Timing Preservation")

    def test_blocked_result_accepted(self):
        """Test that a valid BLOCKED CriticResult passes validation."""
        blocked_result = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="BLOCKED",
            findings=[
                CriticFinding(
                    category="Contradiction",
                    severity="ERROR",
                    description="Severe conflict between source requirement and candidate reasoning.",
                    source_evidence="2.5 seconds",
                    reasoning_evidence="10 seconds",
                    recommendation="Re-evaluate source requirement.",
                )
            ],
            missing_constraints=["Essential trigger condition"],
            contradictions=["Direct timing conflict"],
            revision_required=True,
            summary="Verification blocked due to severe contradiction.",
        )

        model = DummyCritic(blocked_result)
        res = model.critique(self.context_package, self.reasoning_result)
        self.assertEqual(res.status, "BLOCKED")
        self.assertTrue(res.revision_required)

    def test_invalid_status_rejected(self):
        """Test that an invalid status string raises CriticValidationError."""
        bad_result = CriticResult(
            requirement_id=8,
            global_number=8,
            srs_id="[SRS178]",
            status="INVALID_STATUS_STRING",
        )
        model = DummyCritic(bad_result)
        with self.assertRaises(CriticValidationError) as ctx:
            model.critique(self.context_package, self.reasoning_result)
        self.assertIn("status must be one of", str(ctx.exception))

    def test_requirement_id_mismatch_rejected(self):
        """Test that requirement_id mismatch raises CriticValidationError."""
        bad_result = CriticResult(
            requirement_id=999,
            global_number=8,
            srs_id="[SRS178]",
            status="PASS",
        )
        model = DummyCritic(bad_result)
        with self.assertRaises(CriticValidationError) as ctx:
            model.critique(self.context_package, self.reasoning_result)
        self.assertIn("requirement_id mismatch", str(ctx.exception))

    def test_invalid_field_type_rejected(self):
        """Test that non-list value for missing_constraints raises CriticValidationError."""
        bad_dict = {
            "requirement_id": 8,
            "global_number": 8,
            "srs_id": "[SRS178]",
            "status": "PASS",
            "missing_constraints": "Not a list",
        }
        with self.assertRaises(CriticValidationError) as ctx:
            CriticResult.from_dict(bad_dict)
        self.assertIn("must be a list", str(ctx.exception))

    def test_ollama_critic_adapter_with_mocked_client(self):
        """Test OllamaCritic adapter using a mocked Ollama client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.message.content = json.dumps({
            "requirement_id": 8,
            "global_number": 8,
            "srs_id": "[SRS178]",
            "status": "NEEDS_REVISION",
            "findings": [
                {
                    "category": "Timing Preservation",
                    "severity": "WARNING",
                    "description": "2.5 second precondition bound omitted in formalization string.",
                    "source_evidence": "has not synced in 2.5 seconds",
                    "reasoning_evidence": "G(failed(FCP) -> F[0,1s] send_vme_reset)",
                    "recommendation": "Add 2.5s timeout bound to condition."
                },
                {
                    "category": "Unsupported Assumption",
                    "severity": "INFO",
                    "description": "Assumption restates an explicit SRS capability.",
                    "source_evidence": "surviving triplex shall ... send",
                    "reasoning_evidence": "surviving triplex is capable",
                    "recommendation": "Remove redundant assumption."
                }
            ],
            "missing_constraints": ["2.5s precondition bound"],
            "unsupported_assumptions": ["surviving triplex is capable"],
            "contradictions": [],
            "traceability_issues": [],
            "pattern_coverage": {
                "covered_patterns": ["Timeout / Deadline"],
                "unaddressed_patterns": ["Conditional Behavior"]
            },
            "formalization_assessment": "Formalization is partially complete; missing 2.5s precondition bound.",
            "revision_required": True,
            "summary": "Critique identified timing preservation warning and redundant assumption."
        })
        mock_client.chat.return_value = mock_response

        critic = OllamaCritic(model="llama3:latest", client=mock_client)
        result = critic.critique(self.context_package, self.reasoning_result)

        self.assertEqual(result.requirement_id, 8)
        self.assertEqual(result.status, "NEEDS_REVISION")
        self.assertTrue(result.revision_required)
        self.assertEqual(len(result.findings), 2)
        self.assertEqual(result.findings[0].category, "Timing Preservation")
        self.assertEqual(result.findings[0].severity, "WARNING")
        self.assertEqual(result.findings[1].category, "Unsupported Assumption")

        # Verify mock client call
        mock_client.chat.assert_called_once()
        call_kwargs = mock_client.chat.call_args[1]
        self.assertEqual(call_kwargs["model"], "llama3:latest")
        self.assertEqual(call_kwargs["format"], "json")

    def test_ollama_critic_invalid_json_raises_validation_error(self):
        """Test that OllamaCritic raises CriticValidationError if model returns non-JSON."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.message.content = "Invalid non-JSON response text."
        mock_client.chat.return_value = mock_response

        critic = OllamaCritic(model="llama3:latest", client=mock_client)
        with self.assertRaises(CriticValidationError) as ctx:
            critic.critique(self.context_package, self.reasoning_result)
        self.assertIn("Failed to parse model output as JSON", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
