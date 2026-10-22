import json
import unittest

from app.critic.critic_prompt import CRITIC_SYSTEM_PROMPT, build_critic_user_prompt
from app.critic.schemas import CriticFinding, CriticResult
from app.reasoning.schemas import (
    ConstraintProvenance,
    DomainEntityDefinition,
    IntermediateRepresentation,
    PredicateDefinition,
    PropositionDefinition,
    ProvenanceCategory,
    ReasoningResult,
)
from app.retrieval.context_builder import ContextPackage, RequirementContext
from app.retrieval.obsidian_retriever import RetrievalResult
from app.revision.revision_prompt import REVISION_SYSTEM_PROMPT, build_revision_user_prompt


class TestPromptChainIntegrity(unittest.TestCase):
    def setUp(self):
        self.req_srs017 = RequirementContext(
            requirement_id=18,
            global_number=18,
            source_number=1,
            srs_id="[SRS017]",
            section_number="3.2.2.1",
            section_title="Rate Group Scheduling Architecture",
            raw_text="1. The scheduler shall [SRS017] provide an API call to install a task into a rate group. The API call is invoked during system initialization.",
            normalized_text="1. The scheduler shall [SRS017] provide an API call to install a task into a rate group. The API call is invoked during system initialization.",
            page_number=18,
            element_index=1,
            document_id=1,
        )
        self.context_srs017 = ContextPackage(
            requirements=[self.req_srs017],
            identified_patterns=["Capability / Interface Provision", "Phase Specific / Mode Specific Execution"],
            obsidian_knowledge=RetrievalResult(pattern_items=[], loaded_files_count=0, read_cache_hits=0),
            provenance={"db": "srs_canonical.db"},
        )

        self.ir_srs017 = IntermediateRepresentation(
            propositions=[
                PropositionDefinition(
                    symbol="P_install",
                    definition="Scheduler provides API call to install task into rate group",
                    notation="P_install := Scheduler provides API call to install task into rate group",
                    source_reference="SRS017",
                    provenance=ProvenanceCategory.EXPLICIT_SOURCE,
                ),
                PropositionDefinition(
                    symbol="P_init",
                    definition="System initialization is active",
                    notation="P_init := System initialization is active",
                    source_reference="SRS017",
                    provenance=ProvenanceCategory.EXPLICIT_SOURCE,
                ),
            ],
            predicates=[
                PredicateDefinition(
                    name="provides_install_api",
                    entity="scheduler",
                    arguments=["task", "rate_group"],
                    condition_type="ACTION",
                    description="Scheduler provides API call to install task into rate group",
                    notation="provides_install_api(task, rate_group) := Scheduler provides API call to install task into rate group",
                )
            ],
            entities=[
                DomainEntityDefinition(name="scheduler", category="ENTITY", description="Core executive scheduler"),
                DomainEntityDefinition(name="rate_group", category="ENTITY", description="Periodic execution bucket"),
            ],
            temporal_operators=["G"],
            formula_construction="Globally during system initialization, the install API is provided: G(P_init -> P_install)",
            unresolved_parameters=[],
        )

        self.provenance_srs017 = [
            ConstraintProvenance(
                constraint_id="C_SRS017_1",
                statement="API call installs task into rate group",
                category=ProvenanceCategory.EXPLICIT_SOURCE,
                source_text="provide an API call to install a task into a rate group",
                justification="Explicitly stated functional requirement",
            ),
            ConstraintProvenance(
                constraint_id="C_SRS017_2",
                statement="API call invoked during system initialization",
                category=ProvenanceCategory.EXPLICIT_SOURCE,
                source_text="The API call is invoked during system initialization.",
                justification="Explicitly stated phase precondition",
            ),
        ]

        self.reasoning_srs017 = ReasoningResult(
            requirement_id=18,
            global_number=18,
            srs_id="[SRS017]",
            interpretation="The scheduler provides an interface during initialization to install tasks into rate groups.",
            identified_entities=["scheduler", "task", "rate group", "API call", "system initialization"],
            predicates=["provides_install_api(task, rate_group)", "system_initialization()"],
            conditions=["system initialization is in progress"],
            actions=["provide API call to install task"],
            temporal_constraints=[],
            mathematical_constraints=[],
            dependencies=[],
            formalization="G(P_init -> P_install)",
            assumptions=["Rate groups are configured before task installation"],
            unresolved_items=[],
            reasoning_notes="Untimed functional provision requirement.",
            intermediate_representation=self.ir_srs017,
            constraint_provenance=[c.to_dict() for c in self.provenance_srs017],
        )

    def test_critic_prompt_includes_intermediate_representation(self):
        """Verify that build_critic_user_prompt receives full intermediate representation and constraint provenance."""
        prompt = build_critic_user_prompt(self.context_srs017, self.reasoning_srs017)

        # Check section existence
        self.assertIn("Intermediate Representation:", prompt)
        self.assertIn("Formula Construction Rationale:", prompt)
        self.assertIn("Constraint Provenance:", prompt)

        # Check proposition definitions
        self.assertIn("P_install", prompt)
        self.assertIn("Scheduler provides API call to install task into rate group", prompt)
        self.assertIn("P_init", prompt)
        self.assertIn("P_install := Scheduler provides API call to install task into rate group", prompt)

        # Check predicate and entity definitions
        self.assertIn("provides_install_api", prompt)
        self.assertIn("rate_group", prompt)

        # Check formula construction rationale
        self.assertIn("Globally during system initialization, the install API is provided: G(P_init -> P_install)", prompt)

        # Check constraint provenance
        self.assertIn("C_SRS017_1", prompt)
        self.assertIn("C_SRS017_2", prompt)
        self.assertIn("EXPLICIT_SOURCE", prompt)

    def test_critic_prompt_handles_partial_and_missing_ir_gracefully(self):
        """Verify that build_critic_user_prompt handles None, empty, or partial IR without error."""
        # 1. Test None IR and empty constraint provenance
        reasoning_none_ir = ReasoningResult(
            requirement_id=18,
            global_number=18,
            srs_id="[SRS017]",
            interpretation="Test without IR",
            formalization="G(Init -> Install)",
            intermediate_representation=None,
            constraint_provenance=[],
        )
        prompt_none = build_critic_user_prompt(self.context_srs017, reasoning_none_ir)
        self.assertIn("(No intermediate representation provided)", prompt_none)
        self.assertIn("(No constraint provenance recorded)", prompt_none)
        self.assertIn("N/A", prompt_none)

        # 2. Test dictionary IR with partial keys
        reasoning_dict_ir = ReasoningResult(
            requirement_id=18,
            global_number=18,
            srs_id="[SRS017]",
            interpretation="Test with partial dict IR",
            formalization="G(Init -> Install)",
            intermediate_representation={
                "propositions": [{"symbol": "P1", "definition": "Init"}],
                "unresolved_parameters": ["param_x"],
            },
            constraint_provenance=[{"constraint_id": "C1", "statement": "test constraint"}],
        )
        prompt_dict = build_critic_user_prompt(self.context_srs017, reasoning_dict_ir)
        self.assertIn("P1", prompt_dict)
        self.assertIn("param_x", prompt_dict)
        self.assertIn("C1", prompt_dict)

    def test_critic_instructions_forbid_penalizing_untimed_requirements(self):
        """Verify that Critic instructions state untimed requirements must not be penalized for lacking numbers."""
        # Check system prompt
        self.assertIn("If the source requirement text is untimed", CRITIC_SYSTEM_PROMPT)
        self.assertIn("DO NOT treat the absence of a numerical timing bound as a defect", CRITIC_SYSTEM_PROMPT)
        self.assertIn("Require a timing bound ONLY when the source requirement text", CRITIC_SYSTEM_PROMPT)
        self.assertIn("An unresolved parameter must not become a fabricated constraint", CRITIC_SYSTEM_PROMPT)
        self.assertIn("NO INVENTED NUMBERS OR FABRICATED CONSTRAINTS", CRITIC_SYSTEM_PROMPT)

        # Check user prompt instructions
        prompt = build_critic_user_prompt(self.context_srs017, self.reasoning_srs017)
        self.assertIn("DO NOT treat the absence of a numerical timing bound in an untimed requirement as a defect", prompt)

    def test_revision_prompt_includes_intermediate_representation(self):
        """Verify that build_revision_user_prompt carries previous IR and provenance to the revision model."""
        critic_result = CriticResult(
            requirement_id=18,
            global_number=18,
            srs_id="[SRS017]",
            status="NEEDS_REVISION",
            findings=[
                CriticFinding(
                    category="Actor Preservation",
                    severity="WARNING",
                    description="Clarify role of rate group configuration.",
                    source_evidence="1. The scheduler shall [SRS017] provide an API call...",
                    reasoning_evidence="Rate groups are configured before task installation",
                    recommendation="Retain P_install and P_init, update assumption notes.",
                )
            ],
            missing_constraints=[],
            unsupported_assumptions=[],
            contradictions=[],
            traceability_issues=[],
            pattern_coverage={"covered_patterns": ["Capability / Interface Provision"]},
            formalization_assessment="Formula structure is sound, proposition definitions are explicit.",
            revision_required=True,
            summary="Revise assumption notes while keeping formalization.",
        )

        prompt = build_revision_user_prompt(self.context_srs017, self.reasoning_srs017, critic_result)

        # Check that previous IR is present in Section 3
        self.assertIn("3. PREVIOUS CANDIDATE FORMALIZATION (BEING REVISED)", prompt)
        self.assertIn("Intermediate Representation:", prompt)
        self.assertIn("P_install", prompt)
        self.assertIn("Scheduler provides API call to install task into rate group", prompt)
        self.assertIn("provides_install_api", prompt)
        self.assertIn("Formula Construction Rationale:", prompt)
        self.assertIn("Constraint Provenance:", prompt)
        self.assertIn("C_SRS017_1", prompt)

        # Check revision instructions
        self.assertIn("Preserve valid intermediate representation", prompt)
        self.assertIn("Do not fabricate constraints or timing bounds", prompt)

    def test_revision_prompt_handles_partial_and_missing_ir_gracefully(self):
        """Verify that build_revision_user_prompt handles missing or partial IR gracefully."""
        critic_result = CriticResult(
            requirement_id=18,
            global_number=18,
            srs_id="[SRS017]",
            status="NEEDS_REVISION",
            findings=[],
            missing_constraints=[],
            unsupported_assumptions=[],
            contradictions=[],
            traceability_issues=[],
            pattern_coverage={},
            formalization_assessment="Needs check.",
            revision_required=True,
            summary="Review needed.",
        )

        reasoning_none_ir = ReasoningResult(
            requirement_id=18,
            global_number=18,
            srs_id="[SRS017]",
            interpretation="No IR candidate",
            formalization="G(A -> B)",
            intermediate_representation=None,
            constraint_provenance=[],
        )

        prompt = build_revision_user_prompt(self.context_srs017, reasoning_none_ir, critic_result)
        self.assertIn("(No intermediate representation provided)", prompt)
        self.assertIn("(No constraint provenance recorded)", prompt)
        self.assertIn("Formula Construction Rationale:", prompt)

    def test_revision_system_prompt_rules(self):
        """Verify that REVISION_SYSTEM_PROMPT directs model to preserve valid definitions and avoid fabricated bounds."""
        self.assertIn("Preserve valid definitions", REVISION_SYSTEM_PROMPT)
        self.assertIn("Retain valid proposition definitions", REVISION_SYSTEM_PROMPT)
        self.assertIn("No fabricated timing bounds or constraints", REVISION_SYSTEM_PROMPT)
        self.assertIn("An unstated parameter must not become a fabricated constraint", REVISION_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
