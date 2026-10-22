import unittest
from app.critic.critic_prompt import CRITIC_SYSTEM_PROMPT, build_critic_user_prompt
from app.critic.schemas import CriticResult
from app.reasoning.reasoning_prompt import REASONING_SYSTEM_PROMPT, build_reasoning_user_prompt
from app.reasoning.schemas import (
    ConstraintProvenance,
    IntermediateRepresentation,
    PredicateDefinition,
    ProvenanceCategory,
    ReasoningResult,
)
from app.retrieval.context_builder import ContextPackage, RequirementContext
from app.retrieval.obsidian_retriever import RetrievalResult
from app.revision.revision_prompt import REVISION_SYSTEM_PROMPT, build_revision_user_prompt


class TestSourceFidelityAndDecontamination(unittest.TestCase):
    """
    Verifies that system and generic user prompts are free of hardcoded requirement 8
    contaminants (e.g. 2.5s, VMEbus reset, FCP), and that constraint provenance categories
    are properly enforced.
    """

    def test_reasoning_system_prompt_decontaminated(self):
        """Generic Reasoning system prompt must not contain R8-specific values."""
        self.assertNotIn("2.5 seconds", REASONING_SYSTEM_PROMPT)
        self.assertNotIn("failed_sync_2.5s", REASONING_SYSTEM_PROMPT)
        self.assertNotIn("send_vme_reset", REASONING_SYSTEM_PROMPT)
        self.assertNotIn("FCP", REASONING_SYSTEM_PROMPT)
        # Must instruct preserving exact source parameters
        self.assertIn("EXPLICIT_SOURCE", REASONING_SYSTEM_PROMPT)
        self.assertIn("SUPPORTED_DEPENDENCY", REASONING_SYSTEM_PROMPT)
        self.assertIn("APPROVED_DERIVATION", REASONING_SYSTEM_PROMPT)
        self.assertIn("UNRESOLVED", REASONING_SYSTEM_PROMPT)
        self.assertIn("UNSUPPORTED", REASONING_SYSTEM_PROMPT)

    def test_critic_system_prompt_decontaminated(self):
        """Generic Critic system prompt must not contain R8-specific values."""
        self.assertNotIn("2.5 seconds", CRITIC_SYSTEM_PROMPT)
        self.assertNotIn("surviving triplex", CRITIC_SYSTEM_PROMPT)
        self.assertNotIn("failed FCP processor", CRITIC_SYSTEM_PROMPT)
        self.assertNotIn("send single voted VMEbus reset", CRITIC_SYSTEM_PROMPT)
        self.assertIn("NO INVENTED NUMBERS", CRITIC_SYSTEM_PROMPT)

    def test_constraint_provenance_schema_and_serialization(self):
        """Tests ConstraintProvenance dataclass and provenance categories."""
        cp = ConstraintProvenance(
            constraint_id="C1",
            statement="System shall shutdown within 10ms",
            category=ProvenanceCategory.EXPLICIT_SOURCE,
            source_text="within 10ms",
            justification="Direct literal requirement parameter",
        )
        d = cp.to_dict()
        self.assertEqual(d["constraint_id"], "C1")
        self.assertEqual(d["category"], "EXPLICIT_SOURCE")
        self.assertEqual(d["source_text"], "within 10ms")

        cp_roundtrip = ConstraintProvenance.from_dict(d)
        self.assertEqual(cp_roundtrip.constraint_id, "C1")
        self.assertEqual(cp_roundtrip.category, ProvenanceCategory.EXPLICIT_SOURCE)

    def test_intermediate_representation_schema(self):
        """Tests IntermediateRepresentation and PredicateDefinition serialization."""
        pred = PredicateDefinition(
            name="loss_of_comm",
            entity="comm_bus",
            condition_type="TRIGGER",
            description="Loss of redundant bus communication",
            formal_expression="bus_state == OFFLINE",
        )
        ir = IntermediateRepresentation(
            predicates=[pred],
            temporal_operators=["G", "F[0, 10ms]"],
            atomic_clauses=["loss_of_comm", "outputs_disabled"],
            composition_rules=["G(loss_of_comm -> F[0, 10ms] outputs_disabled)"],
        )
        d = ir.to_dict()
        self.assertEqual(len(d["predicates"]), 1)
        self.assertEqual(d["predicates"][0]["name"], "loss_of_comm")
        self.assertEqual(d["predicates"][0]["condition_type"], "TRIGGER")

        ir_roundtrip = IntermediateRepresentation.from_dict(d)
        self.assertEqual(len(ir_roundtrip.predicates), 1)
        self.assertEqual(ir_roundtrip.predicates[0].name, "loss_of_comm")
        self.assertEqual(ir_roundtrip.temporal_operators, ["G", "F[0, 10ms]"])

    def test_reasoning_result_with_provenance_and_ir(self):
        """ReasoningResult captures and serializes constraint_provenance and intermediate_representation."""
        res = ReasoningResult(
            requirement_id=1,
            global_number=1,
            srs_id="[SRS001]",
            interpretation="Test interpretation",
            constraint_provenance=[{
                "constraint_id": "C1",
                "statement": "pressure > 100",
                "category": ProvenanceCategory.EXPLICIT_SOURCE,
                "source_text": "pressure exceeds 100 psi",
                "justification": "Direct source quote",
            }],
            intermediate_representation={
                "predicates": [{"name": "high_pressure", "entity": "sensor"}],
                "atomic_clauses": ["high_pressure"],
            },
        )
        d = res.to_dict()
        self.assertEqual(len(d["constraint_provenance"]), 1)
        self.assertEqual(d["constraint_provenance"][0]["category"], "EXPLICIT_SOURCE")
        self.assertIsNotNone(d["intermediate_representation"])

        res_roundtrip = ReasoningResult.from_dict(d)
        self.assertEqual(len(res_roundtrip.constraint_provenance), 1)
        self.assertEqual(res_roundtrip.constraint_provenance[0]["category"], "EXPLICIT_SOURCE")

    def test_revision_user_prompt_includes_answered_clarifications(self):
        """build_revision_user_prompt must include answered stakeholder clarifications."""
        req = RequirementContext(
            requirement_id=1,
            global_number=1,
            source_number=1,
            srs_id="[SRS001]",
            section_number="3.1",
            section_title="Sensors",
            raw_text="The sensor shall sample pressure continuously.",
            normalized_text="The sensor shall sample pressure continuously.",
            page_number=5,
            element_index=1,
            document_id=1,
        )
        pkg = ContextPackage(
            requirements=[req],
            identified_patterns=[],
            obsidian_knowledge=RetrievalResult(pattern_items=[], loaded_files_count=0, read_cache_hits=0),
            provenance={},
            clarifications=[{
                "question_id": "CLARIF-001",
                "question_text": "What is the sampling frequency?",
                "status": "ANSWERED",
                "answer": "100 Hz approved sampling rate",
            }],
        )
        reasoning_res = ReasoningResult(
            requirement_id=1,
            global_number=1,
            srs_id="[SRS001]",
            formalization="G(sample_pressure)",
        )
        critic_res = CriticResult(
            requirement_id=1,
            global_number=1,
            srs_id="[SRS001]",
            status="NEEDS_REVISION",
            summary="Needs sampling frequency",
        )

        prompt = build_revision_user_prompt(pkg, reasoning_res, critic_res)
        self.assertIn("STAKEHOLDER CLARIFICATION RESOLUTIONS (BINDING)", prompt)
        self.assertIn("CLARIF-001", prompt)
        self.assertIn("What is the sampling frequency?", prompt)
        self.assertIn("100 Hz approved sampling rate", prompt)

    def test_reasoning_user_prompt_includes_set_context(self):
        """build_reasoning_user_prompt must format set_context when present."""
        req = RequirementContext(
            requirement_id=1,
            global_number=1,
            source_number=1,
            srs_id="[SRS001]",
            section_number="3.1",
            section_title="Sensors",
            raw_text="The sensor shall sample pressure continuously.",
            normalized_text="The sensor shall sample pressure continuously.",
            page_number=5,
            element_index=1,
            document_id=1,
        )
        pkg = ContextPackage(
            requirements=[req],
            identified_patterns=[],
            obsidian_knowledge=RetrievalResult(pattern_items=[], loaded_files_count=0, read_cache_hits=0),
            provenance={},
            set_context={
                "section_clusters": "Section 3.1 - Sensors (sibling req IDs: [2, 3])",
                "shared_entities": "pressure, sensor, bus",
                "cross_dependencies": ["Requirement [SRS001] feeds pressure value to [SRS002]."],
                "summary": "Sensor subsystem cluster with 3 interdependent requirements.",
            },
        )
        prompt = build_reasoning_user_prompt(pkg)
        self.assertIn("SET-LEVEL CONTEXT & CROSS-REQUIREMENT DEPENDENCIES", prompt)
        self.assertIn("Section 3.1 - Sensors", prompt)
        self.assertIn("pressure, sensor, bus", prompt)
        self.assertIn("Requirement [SRS001] feeds pressure value to [SRS002]", prompt)


if __name__ == "__main__":
    unittest.main()
