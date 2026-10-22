import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.analyst.analyst_model import AnalystModel
from app.analyst.schemas import AnalystResult
from app.critic.critic_model import CriticModel
from app.critic.schemas import CriticResult
from app.formalization_validator import validate_formalization
from app.pipeline import FormalizationPipeline, PipelineResult
from app.reasoning.reasoning_model import ReasoningModel
from app.reasoning.schemas import (
    ConstraintProvenance,
    DomainEntityDefinition,
    IntermediateRepresentation,
    PredicateDefinition,
    PropositionDefinition,
    ProvenanceCategory,
    ReasoningResult,
)
from app.retrieval.context_builder import ContextBuilder, ContextPackage, RequirementContext
from app.retrieval.sqlite_retriever import SQLiteRetriever
from app.revision.revision_manager import RevisionManager
from app.revision.schemas import RevisionResult
from app.symbols.schemas import SymbolDefinition
from app.symbols.symbol_registry import SymbolRegistry
from app.symbols.symbol_retriever import SymbolRetriever
from app.symbols.symbol_validator import SymbolValidator
from app.ui.app import app as flask_app


class TestStagedFormalization(unittest.TestCase):
    """
    Focused regression tests for Phase 2:
    - Staged formalization flow (Propositions -> Predicates -> Formula Construction -> Validation).
    - Decoupling API capability from invocation events (SRS017).
    - Untimed requirements fidelity without fabricated timing bounds or unjustified 'U' operators.
    - Symbol registration, proposal status, and persistence.
    - UI presentation of the 6 stages in exact order.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.registry_file = Path(self.temp_dir.name) / "test_symbol_registry.json"
        base_registry = SymbolRegistry()
        base_registry.load()
        base_registry.save(target_path=self.registry_file)

        self.registry = SymbolRegistry(registry_path=self.registry_file)
        self.registry.load()
        self.validator = SymbolValidator(self.registry)
        self.retriever = SymbolRetriever(self.registry)

        # SRS017 context
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

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_proposition_definitions_produced_and_preserved(self):
        """Proposition definitions are created with P := Notation and preserved in IntermediateRepresentation."""
        p_cap = PropositionDefinition(
            symbol="P_install_api",
            definition="Scheduler provides an API call to install a task into a rate group",
            source_reference="SRS017",
            provenance=ProvenanceCategory.EXPLICIT_SOURCE,
        )
        self.assertEqual(p_cap.notation, "P_install_api := Scheduler provides an API call to install a task into a rate group")
        self.assertFalse(p_cap.user_approved)

        ir = IntermediateRepresentation(propositions=[p_cap])
        d = ir.to_dict()
        self.assertEqual(len(d["propositions"]), 1)
        self.assertEqual(d["propositions"][0]["symbol"], "P_install_api")

        ir_restored = IntermediateRepresentation.from_dict(d)
        self.assertEqual(ir_restored.propositions[0].notation, p_cap.notation)

    def test_predicate_definitions_and_arguments(self):
        """Predicate definitions preserve entity, arguments, condition type, and formal notation."""
        pred = PredicateDefinition(
            name="install_task_api",
            entity="scheduler",
            arguments=["task", "rate_group"],
            condition_type="ACTION",
            description="Provides an API call to install task into rate group",
        )
        self.assertIn("install_task_api(task, rate_group) :=", pred.notation)
        self.assertEqual(pred.condition_type, "ACTION")
        self.assertEqual(pred.arguments, ["task", "rate_group"])

    def test_formula_construction_using_declared_symbols(self):
        """SymbolValidator accepts formulas referencing declared propositions and rejects disconnected formulas."""
        p_cap = PropositionDefinition(symbol="P_install_api", definition="API provided")
        p_inv = PropositionDefinition(symbol="P_init_phase", definition="System initialization phase")
        ir = IntermediateRepresentation(
            propositions=[p_cap, p_inv],
            temporal_operators=["G"],
            formula_construction="Globally, initialization implies install API is provided: G(P_init_phase -> P_install_api)",
        )

        # 1. Valid formula referencing declared propositions
        report_valid = self.validator.validate_candidate(
            formalization="G(P_init_phase -> P_install_api)",
            current_scope="[SRS017]",
            intermediate_representation=ir,
        )
        self.assertTrue(report_valid.is_valid)

        # 2. Disconnected formula not referencing any declared proposition
        report_disconnected = self.validator.validate_candidate(
            formalization="G(P_other -> P_alien)",
            current_scope="[SRS017]",
            intermediate_representation=ir,
        )
        self.assertFalse(report_disconnected.is_valid)
        rules = [v.rule for v in report_disconnected.violations]
        self.assertIn("FORMULA_IR_DISCONNECTED", rules)

    def test_distinguishing_api_capability_from_api_invocation_srs017(self):
        """SRS017 separates API capability provision from initialization invocation event."""
        p_cap = PropositionDefinition(
            symbol="P_provide_api",
            definition="Scheduler provides an API call to install a task into a rate group",
            notation="P_provide_api := Scheduler provides an API call to install a task into a rate group",
            source_reference="1. The scheduler shall [SRS017] provide an API call...",
        )
        p_inv = PropositionDefinition(
            symbol="P_init_invoked",
            definition="The API call is invoked during system initialization",
            notation="P_init_invoked := The API call is invoked during system initialization",
            source_reference="The API call is invoked during system initialization.",
        )
        # Verify that capability and invocation are distinct propositions
        self.assertNotEqual(p_cap.symbol, p_inv.symbol)
        self.assertNotEqual(p_cap.definition, p_inv.definition)

        ir = IntermediateRepresentation(
            propositions=[p_cap, p_inv],
            temporal_operators=["G"],
            formula_construction="Globally, during system initialization, the install API capability is provided and invoked: G(P_init_invoked -> P_provide_api)",
        )
        report = self.validator.validate_candidate(
            formalization="G(P_init_invoked -> P_provide_api)",
            current_scope="[SRS017]",
            intermediate_representation=ir,
        )
        self.assertTrue(report.is_valid)

    def test_untimed_requirements_not_receiving_timing_bounds(self):
        """Untimed requirements like SRS017 do not accept unstated timing bounds like t_bound."""
        p_cap = PropositionDefinition(symbol="P_provide_api", definition="API provided")
        p_inv = PropositionDefinition(symbol="P_init_invoked", definition="API invoked")
        ir = IntermediateRepresentation(
            propositions=[p_cap, p_inv],
            temporal_operators=["G"],
            unresolved_parameters=[],
        )
        # Attempting to inject an unstated bound 't_bound'
        report = self.validator.validate_candidate(
            formalization="G(P_init_invoked -> F[0, t_bound] P_provide_api)",
            current_scope="[SRS017]",
            intermediate_representation=ir,
        )
        self.assertFalse(report.is_valid)
        rules = [v.rule for v in report.violations]
        self.assertIn("UNSTATED_TIMING_BOUND", rules)

    def test_unsupported_temporal_operators_flagged(self):
        """Artificial 'U' (Until) operator is flagged if not justified in IR temporal operators."""
        p_cap = PropositionDefinition(symbol="P_provide_api", definition="API provided")
        p_inv = PropositionDefinition(symbol="P_init_invoked", definition="API invoked")
        # IR only specifies 'G', does NOT declare 'U'
        ir = IntermediateRepresentation(
            propositions=[p_cap, p_inv],
            temporal_operators=["G"],
        )
        report = self.validator.validate_candidate(
            formalization="G(P_provide_api U P_init_invoked)",
            current_scope="[SRS017]",
            intermediate_representation=ir,
        )
        self.assertFalse(report.is_valid)
        rules = [v.rule for v in report.violations]
        self.assertIn("UNJUSTIFIED_TEMPORAL_OPERATOR", rules)

    def test_symbol_registration_and_persistence(self):
        """Pipeline registers intermediate propositions and predicates in SymbolRegistry with proposal status."""
        pipeline = FormalizationPipeline(
            symbol_retriever=self.retriever,
            symbol_validator=self.validator,
        )

        reasoning = ReasoningResult(
            requirement_id=18,
            global_number=18,
            srs_id="[SRS017]",
            formalization="G(P_init -> P_install)",
            intermediate_representation=IntermediateRepresentation(
                propositions=[
                    PropositionDefinition(
                        symbol="P_install",
                        definition="Scheduler provides task install API",
                        notation="P_install := Scheduler provides task install API",
                        provenance=ProvenanceCategory.EXPLICIT_SOURCE,
                        user_approved=False,
                    )
                ],
                predicates=[
                    PredicateDefinition(
                        name="install_task",
                        entity="scheduler",
                        arguments=["task"],
                        description="Install task into rate group",
                        user_approved=False,
                    )
                ],
            ),
        )

        # Register intermediate symbols
        pipeline._register_intermediate_symbols(self.req_srs017, reasoning)

        # Verify proposition registration
        sym_prop = self.registry.get_symbol_by_spelling("P_install", scope="[SRS017]")
        self.assertIsNotNone(sym_prop)
        self.assertEqual(sym_prop.category, "PROPOSITION")
        self.assertFalse(sym_prop.user_approved)

        # Verify predicate registration
        sym_pred = self.registry.get_symbol_by_spelling("install_task", scope="[SRS017]")
        self.assertIsNotNone(sym_pred)
        self.assertEqual(sym_pred.category, "PREDICATE")
        self.assertFalse(sym_pred.user_approved)

        # Verify duplicate registration does not duplicate or overwrite
        pipeline._register_intermediate_symbols(self.req_srs017, reasoning)
        matches = [s for s in self.registry.get_all_symbols() if s.spelling == "P_install"]
        self.assertEqual(len(matches), 1)

        # Verify that if user approves symbol, subsequent model registration preserves approval
        self.registry.update_symbol_definition(sym_prop.identifier, new_definition="Approved def", user_approved=True)
        pipeline._register_intermediate_symbols(self.req_srs017, reasoning)
        sym_after = self.registry.get_symbol_by_identifier(sym_prop.identifier)
        self.assertTrue(sym_after.user_approved)
        self.assertEqual(sym_after.definition, "Approved def")

    def test_ui_displays_staged_intermediate_representation(self):
        """UI renders the 6 stages in exact order: 1. Source -> 2. Props -> 3. Preds -> 4. Formula -> 5. Explanation -> 6. Validation."""
        p_cap = PropositionDefinition(
            symbol="P_install_api",
            definition="Scheduler provides task install API",
            notation="P_install_api := Scheduler provides task install API",
        )
        pred = PredicateDefinition(
            name="install_task",
            entity="scheduler",
            arguments=["task", "rate_group"],
            description="Install task into rate group",
        )
        ir = IntermediateRepresentation(
            propositions=[p_cap],
            predicates=[pred],
            entities=[DomainEntityDefinition(name="scheduler", category="ENTITY", description="Core executive scheduler")],
            temporal_operators=["G"],
            formula_construction="Globally, initialization triggers installation API provision: G(P_init -> P_install_api)",
        )

        pipeline_result = PipelineResult(
            requirement_id=18,
            global_number=18,
            srs_id="[SRS017]",
            section_number="3.2.2.1",
            section_title="Rate Group Scheduling Architecture",
            raw_text=self.req_srs017.raw_text,
            formalization="G(P_init -> P_install_api)",
            interpretation="The scheduler provides task installation during initialization.",
            dependencies=["[SRS016]"],
            status="PASS",
            termination_reason="VERIFIED",
            validation_valid=True,
            validation_findings=[],
            intermediate_representation=ir.to_dict(),
            constraint_provenance=[
                {"constraint_id": "C1", "statement": "API provided", "category": "EXPLICIT_SOURCE"}
            ],
            unresolved_items=[],
            assumptions=["Static initialization"],
        )

        with flask_app.test_request_context("/formalize/18"):
            from flask import render_template
            html = render_template(
                "formalize.html",
                req=self.req_srs017,
                result=pipeline_result,
                from_cache=False,
            )

            # Check that all 6 stage markers are present
            self.assertIn("Stage 1", html)
            self.assertIn("Stage 2", html)
            self.assertIn("Stage 3", html)
            self.assertIn("Stage 4", html)
            self.assertIn("Stage 5", html)
            self.assertIn("Stage 6", html)

            # Check exact sequential ordering of the 6 stages in the rendered HTML
            idx_stage1 = html.index("Stage 1")
            idx_stage2 = html.index("Stage 2")
            idx_stage3 = html.index("Stage 3")
            idx_stage4 = html.index("Stage 4")
            idx_stage5 = html.index("Stage 5")
            idx_stage6 = html.index("Stage 6")

            self.assertLess(idx_stage1, idx_stage2, "Stage 1 must precede Stage 2")
            self.assertLess(idx_stage2, idx_stage3, "Stage 2 must precede Stage 3")
            self.assertLess(idx_stage3, idx_stage4, "Stage 3 must precede Stage 4")
            self.assertLess(idx_stage4, idx_stage5, "Stage 4 must precede Stage 5")
            self.assertLess(idx_stage5, idx_stage6, "Stage 5 must precede Stage 6")

            # Check stage contents
            self.assertIn("P_install_api := Scheduler provides task install API", html)
            self.assertIn("install_task", html)
            self.assertTrue("G(P_init -&gt; P_install_api)" in html or "G(P_init -> P_install_api)" in html)
            self.assertIn("Globally, initialization triggers installation API provision", html)
            self.assertIn("[SRS016]", html)

    def test_srs017_defect_case_rejected_by_validator(self):
        """
        Exact regression test for the historical SRS017 defect:
        - Formula uses Until operator 'U' without textual or pattern justification.
        - Formula uses undefined symbols 'system_initialization_event' and 'E'.
        - Only 'P' and 'install_task_into_rate_group' are defined in the IR.
        - Validator must reject candidate with ERRORs for unjustified 'U' and undefined symbols.
        """
        defect_formula = "G (install_task_into_rate_group(P) -> system_initialization_event(E)) U (install_task_into_rate_group(P) -> ~system_initialization_event(E))"
        ir = IntermediateRepresentation(
            propositions=[
                PropositionDefinition(
                    symbol="P",
                    definition="The scheduler provides an API call to install a task into a rate group.",
                    notation="P := The scheduler provides an API call to install a task into a rate group",
                    provenance=ProvenanceCategory.EXPLICIT_SOURCE,
                )
            ],
            predicates=[
                PredicateDefinition(
                    name="install_task_into_rate_group",
                    entity="scheduler",
                    arguments=["task"],
                    condition_type="ACTION",
                    description="Installs task into rate group",
                )
            ],
            temporal_operators=["G", "U"],
            atomic_clauses=["P", "E"],
            unresolved_parameters=["t_bound (UNRESOLVED)"],
        )

        report = self.validator.validate_candidate(
            formalization=defect_formula,
            current_scope="[SRS017]",
            intermediate_representation=ir,
            identified_patterns=["Response", "Precedence"],
            source_text=self.req_srs017.raw_text,
        )

        self.assertFalse(report.is_valid)
        rule_map = {v.rule: v.symbol_spelling for v in report.violations if v.severity == "ERROR"}
        self.assertIn("UNJUSTIFIED_TEMPORAL_OPERATOR", rule_map)
        self.assertEqual(rule_map["UNJUSTIFIED_TEMPORAL_OPERATOR"], "U")

        undefined_symbols = {v.symbol_spelling for v in report.violations if v.rule == "UNDEFINED_FORMULA_SYMBOL"}
        self.assertIn("system_initialization_event", undefined_symbols)
        self.assertIn("E", undefined_symbols)

    def test_valid_grounded_formula_accepted(self):
        """
        A properly grounded candidate formula where all symbols are defined
        in the intermediate representation and operators are justified must pass validation.
        """
        p_cap = PropositionDefinition(
            symbol="P_provide_api",
            definition="The scheduler provides an API call to install a task into a rate group",
            notation="P_provide_api := The scheduler provides an API call to install a task into a rate group",
            provenance=ProvenanceCategory.EXPLICIT_SOURCE,
        )
        p_inv = PropositionDefinition(
            symbol="P_init_invoked",
            definition="The API call is invoked during system initialization",
            notation="P_init_invoked := The API call is invoked during system initialization",
            provenance=ProvenanceCategory.EXPLICIT_SOURCE,
        )
        ir = IntermediateRepresentation(
            propositions=[p_cap, p_inv],
            temporal_operators=["G"],
            formula_construction="Globally, initialization triggers installation API provision: G(P_init_invoked -> P_provide_api)",
        )

        report = self.validator.validate_candidate(
            formalization="G(P_init_invoked -> P_provide_api)",
            current_scope="[SRS017]",
            intermediate_representation=ir,
            identified_patterns=["Response"],
            source_text=self.req_srs017.raw_text,
        )

        self.assertTrue(report.is_valid)
        error_violations = [v for v in report.violations if v.severity == "ERROR"]
        self.assertEqual(len(error_violations), 0)

    def test_until_operator_accepted_when_supported_by_source_or_pattern(self):
        """
        Temporal operator 'U' is accepted if supported by requirement text keywords ('until'/'unless')
        or by structural patterns (e.g. 'Bounded Waiting').
        """
        p_wait = PropositionDefinition(symbol="P_wait", definition="System is waiting")
        p_ready = PropositionDefinition(symbol="P_ready", definition="System becomes ready")
        ir = IntermediateRepresentation(
            propositions=[p_wait, p_ready],
            temporal_operators=["U"],
            formula_construction="P_wait U P_ready",
        )

        # Case 1: Supported by source text containing 'until'
        report_text = self.validator.validate_candidate(
            formalization="P_wait U P_ready",
            current_scope="[SRS_UNTIL_TEST]",
            intermediate_representation=ir,
            source_text="The system shall remain waiting until it becomes ready.",
        )
        self.assertTrue(report_text.is_valid)

        # Case 2: Supported by pattern 'Bounded Waiting'
        report_pat = self.validator.validate_candidate(
            formalization="P_wait U P_ready",
            current_scope="[SRS_UNTIL_TEST]",
            intermediate_representation=ir,
            identified_patterns=["Bounded Waiting"],
            source_text="The system holds waiting state.",
        )
        self.assertTrue(report_pat.is_valid)

    def test_pipeline_revision_loop_recovers_when_reasoning_omits_requirement_id(self):
        """
        End-to-end pipeline regression test for the exact failure:
        'Pipeline Failed at stage [REVISION_LOOP]: Formalization reasoning/critic loop failed: Failed to map JSON data into ReasoningResult: 'requirement_id''
        Verifies that when the LLM omits 'requirement_id' in its JSON response, OllamaReasoning
        recovers using the trusted ContextPackage context and the pipeline completes stage REVISION_LOOP successfully.
        """
        from app.reasoning.ollama_reasoning import OllamaReasoning
        from app.critic.critic_model import CriticModel
        from app.critic.schemas import CriticResult

        mock_client = MagicMock()
        mock_response = MagicMock()
        # Response missing requirement_id entirely:
        mock_response.message.content = json.dumps({
            "interpretation": "Scheduler provides task install API during initialization.",
            "identified_entities": ["Scheduler", "Task", "Rate Group"],
            "predicates": ["install_task_api(t, rg)"],
            "conditions": ["init_phase"],
            "actions": ["install_task_api"],
            "temporal_constraints": [],
            "mathematical_constraints": [],
            "dependencies": [],
            "formalization": "G(P_init -> P_install_api)",
            "assumptions": [],
            "unresolved_items": [],
            "intermediate_representation": {
                "propositions": [
                    {
                        "symbol": "P_install_api",
                        "definition": "Scheduler provides task install API",
                        "notation": "P_install_api := Scheduler provides task install API",
                        "provenance": "EXPLICIT_SOURCE",
                    },
                    {
                        "symbol": "P_init",
                        "definition": "System initialization phase",
                        "notation": "P_init := System initialization phase",
                        "provenance": "EXPLICIT_SOURCE",
                    },
                ],
                "predicates": [
                    {
                        "name": "install_task_api",
                        "entity": "Scheduler",
                        "arguments": ["t", "rg"],
                        "description": "Installs task into rate group",
                        "notation": "install_task_api(t, rg) := Installs task into rate group",
                    }
                ],
                "temporal_operators": ["G"],
                "formula_construction": "G(P_init -> P_install_api)",
            },
        })
        mock_client.chat.return_value = mock_response

        reasoner = OllamaReasoning(model="llama3:latest", client=mock_client)

        # Mock critic that passes
        mock_critic = MagicMock(spec=CriticModel)
        mock_critic.critique.return_value = CriticResult(
            requirement_id=18,
            global_number=18,
            srs_id="[SRS017]",
            status="PASS",
            findings=[],
            missing_constraints=[],
            unsupported_assumptions=[],
            contradictions=[],
            traceability_issues=[],
            revision_required=False,
            summary="Critique passed.",
        )

        mock_sqlite = MagicMock()
        mock_sqlite.get_requirement_by_id.return_value = self.req_srs017
        mock_sqlite.get_requirements_by_ids.return_value = [self.req_srs017]

        mock_analyst = MagicMock()
        mock_analyst.analyze.return_value = MagicMock(
            identified_patterns=["Function / API Invocation", "Initialization"],
            rationale="Test",
            confidence="HIGH",
        )

        pipeline = FormalizationPipeline(
            sqlite_retriever=mock_sqlite,
            analyst_model=mock_analyst,
            reasoning_model=reasoner,
            critic_model=mock_critic,
            symbol_validator=self.validator,
            symbol_retriever=self.retriever,
        )

        result = pipeline.run(requirement_id=18, max_revisions=2)

        self.assertTrue(result.success, f"Pipeline failed: {result.error_message}")
        self.assertNotEqual(result.error_stage, "REVISION_LOOP")
        self.assertEqual(result.requirement_id, 18)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.formalization, "G(P_init -> P_install_api)")

    def test_exact_srs017_definition_embedded_in_formula_rejected(self):
        """
        Exact regression test for the live SRS017 defect:
        'G(P_install_task(task, rate_group) := Installer API call installs task into rate group)'
        Both validate_formalization and SymbolValidator must reject this malformed formula
        with DEFINITION_EMBEDDED_IN_FORMULA rather than polluting findings with spurious undefined
        symbol errors for words in the natural-language definition prose.
        """
        malformed_formula = "G(P_install_task(task, rate_group) := Installer API call installs task into rate group)"

        # 1. Structural validator test
        struct_report = validate_formalization(malformed_formula)
        self.assertFalse(struct_report.is_valid)
        rules = [f["rule"] for f in struct_report.findings]
        self.assertIn("DEFINITION_EMBEDDED_IN_FORMULA", rules)

        # 2. Symbol validator test
        p_cap = PropositionDefinition(
            symbol="P_install_task",
            definition="Installer API call installs task into rate group",
            notation="P_install_task(task, rate_group) := Installer API call installs task into rate group",
        )
        ir = IntermediateRepresentation(
            propositions=[p_cap],
            temporal_operators=["G"],
        )
        sym_report = self.validator.validate_candidate(
            formalization=malformed_formula,
            current_scope="[SRS017]",
            intermediate_representation=ir,
        )
        self.assertFalse(sym_report.is_valid)
        sym_rules = [v.rule for v in sym_report.violations]
        self.assertIn("DEFINITION_EMBEDDED_IN_FORMULA", sym_rules)
        # Verify that natural language words after ':=' were not spuriously flagged as undefined formula symbols
        undefined_symbols = [v.symbol_spelling for v in sym_report.violations if v.rule == "UNDEFINED_FORMULA_SYMBOL"]
        self.assertNotIn("Installer", undefined_symbols)
        self.assertNotIn("installs", undefined_symbols)
        self.assertNotIn("into", undefined_symbols)

    def test_valid_formula_with_declared_predicate_and_propositions_passes(self):
        """
        Valid formula referencing declared propositions and predicates with arguments passes cleanly.
        """
        p_init = PropositionDefinition(
            symbol="P_init",
            definition="System initialization phase",
            notation="P_init := System initialization phase",
        )
        pred = PredicateDefinition(
            name="install_task",
            entity="scheduler",
            arguments=["task", "rate_group"],
            condition_type="ACTION",
            description="Scheduler installs task into rate group",
        )
        ir = IntermediateRepresentation(
            propositions=[p_init],
            predicates=[pred],
            temporal_operators=["G"],
            formula_construction="Globally, initialization triggers task installation: G(P_init -> install_task(task, rate_group))",
        )
        formula = "G(P_init -> install_task(task, rate_group))"

        # Structural check passes
        struct_report = validate_formalization(formula)
        self.assertTrue(struct_report.is_valid)

        # Symbol check passes
        sym_report = self.validator.validate_candidate(
            formalization=formula,
            current_scope="[SRS017]",
            intermediate_representation=ir,
        )
        self.assertTrue(sym_report.is_valid)
        error_violations = [v for v in sym_report.violations if v.severity == "ERROR"]
        self.assertEqual(len(error_violations), 0)

    def test_revision_loop_exhaustion_produces_consistent_status_and_labels(self):
        """
        When the revision loop exhausts max_revisions, the pipeline must produce a complete,
        truthful result with status MAX_ITERATIONS and termination_reason MAX_ITERATIONS_REACHED.
        classify_result maps it to INVALID FORMULA (if invalid) or REVISION LIMIT REACHED (if valid).
        """
        from app.ui.app import classify_result
        from app.reasoning.ollama_reasoning import OllamaReasoning

        mock_client = MagicMock()
        mock_response = MagicMock()
        # Candidate formula that is malformed with embedded definition
        mock_response.message.content = json.dumps({
            "requirement_id": 18,
            "global_number": 18,
            "srs_id": "[SRS017]",
            "interpretation": "Malformatted test.",
            "identified_entities": [],
            "predicates": [],
            "conditions": [],
            "actions": [],
            "temporal_constraints": [],
            "mathematical_constraints": [],
            "dependencies": [],
            "formalization": "G(P := Malformed definition inside formula)",
            "assumptions": [],
            "unresolved_items": [],
            "intermediate_representation": {
                "propositions": [{"symbol": "P", "definition": "Test def"}],
                "temporal_operators": ["G"],
            },
        })
        mock_client.chat.return_value = mock_response
        reasoner = OllamaReasoning(model="llama3:latest", client=mock_client)

        mock_critic = MagicMock(spec=CriticModel)
        mock_critic.critique.return_value = CriticResult(
            requirement_id=18,
            global_number=18,
            srs_id="[SRS017]",
            status="NEEDS_REVISION",
            findings=[],
            missing_constraints=[],
            unsupported_assumptions=[],
            contradictions=[],
            traceability_issues=[],
            revision_required=True,
            summary="Needs revision.",
        )

        mock_sqlite = MagicMock()
        mock_sqlite.get_requirement_by_id.return_value = self.req_srs017
        mock_sqlite.get_requirements_by_ids.return_value = [self.req_srs017]

        mock_analyst = MagicMock()
        mock_analyst.analyze.return_value = MagicMock(
            identified_patterns=["Initialization"],
            rationale="Test",
            confidence="HIGH",
        )

        pipeline = FormalizationPipeline(
            sqlite_retriever=mock_sqlite,
            analyst_model=mock_analyst,
            reasoning_model=reasoner,
            critic_model=mock_critic,
            symbol_validator=self.validator,
            symbol_retriever=self.retriever,
        )

        result = pipeline.run(requirement_id=18, max_revisions=2)

        # 1. Pipeline completes gracefully
        self.assertTrue(result.success)
        self.assertIsNone(result.error_message)
        self.assertEqual(result.status, "MAX_ITERATIONS")
        self.assertEqual(result.termination_reason, "MAX_ITERATIONS_REACHED")
        self.assertFalse(result.validation_valid)

        # 2. classify_result correctly flags it as INVALID FORMULA
        info = classify_result(result)
        self.assertEqual(info["label"], "INVALID FORMULA")
        self.assertEqual(info["css"], "danger")

    def test_rendering_failed_or_unresolved_candidates(self):
        """
        Verify that failed executions, unresolved parameters, and revision-exhausted
        results render in the UI without template errors or misleading success badges.
        """
        from flask import render_template

        # Case 1: Exhausted revisions with invalid formula
        res_exhausted = PipelineResult(
            requirement_id=18,
            global_number=18,
            srs_id="[SRS017]",
            section_number="3.2.2.1",
            section_title="Scheduling",
            raw_text=self.req_srs017.raw_text,
            formalization="G(P_install := Installer API call)",
            status="MAX_ITERATIONS",
            termination_reason="MAX_ITERATIONS_REACHED",
            validation_valid=False,
            validation_findings=[{"category": "FORMALIZATION_STRUCTURE", "severity": "ERROR", "rule": "DEFINITION_EMBEDDED_IN_FORMULA", "description": "Embedded definition."}],
            unresolved_items=["Timing bound for initialization"],
            intermediate_representation={
                "propositions": [{"symbol": "P_install", "definition": "Installer API call", "user_approved": False, "provenance": "EXPLICIT_SOURCE"}],
                "unresolved_parameters": ["t_bound"],
            },
        )

        # Case 2: Pipeline execution failure
        res_failed = PipelineResult(
            requirement_id=18,
            global_number=18,
            srs_id="[SRS017]",
            section_number="3.2.2.1",
            section_title="Scheduling",
            raw_text=self.req_srs017.raw_text,
            formalization="",
            status="FAILED",
            success=False,
            error_stage="REVISION_LOOP",
            error_message="Ollama connection refused",
        )

        with flask_app.test_request_context("/formalize/18"):
            html_exhausted = render_template("formalize.html", req=self.req_srs017, result=res_exhausted, from_cache=False)
            self.assertIn("INVALID FORMULA", html_exhausted)
            self.assertIn("DEFINITION_EMBEDDED_IN_FORMULA", html_exhausted)
            self.assertIn("t_bound", html_exhausted)
            self.assertIn("Proposal", html_exhausted)

            html_failed = render_template("formalize.html", req=self.req_srs017, result=res_failed, from_cache=False)
            self.assertIn("Pipeline Failed at stage [REVISION_LOOP]", html_failed)
            self.assertIn("Ollama connection refused", html_failed)


if __name__ == "__main__":
    unittest.main()
