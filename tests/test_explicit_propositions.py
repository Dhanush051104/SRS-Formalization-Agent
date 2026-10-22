import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.analyst.analyst_model import AnalystModel
from app.analyst.schemas import AnalystResult
from app.critic.critic_model import CriticModel
from app.critic.schemas import CriticResult
from app.pipeline import FormalizationPipeline
from app.reasoning.reasoning_model import ReasoningModel
from app.reasoning.schemas import (
    DomainEntityDefinition,
    IntermediateRepresentation,
    PredicateDefinition,
    PropositionDefinition,
    ProvenanceCategory,
    ReasoningResult,
)
from app.symbols.schemas import SymbolDefinition
from app.symbols.symbol_registry import SymbolRegistry
from app.symbols.symbol_retriever import SymbolRetriever
from app.symbols.symbol_validator import SymbolValidator
from app.ui.app import app as flask_app


class TestExplicitPropositionsAndPredicates(unittest.TestCase):
    """
    Offline regression tests for explicit proposition and predicate formalization,
    mathematical notation (P := Definition), formula construction, symbol validation,
    symbol registry persistence, and UI rendering.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.registry_file = Path(self.temp_dir.name) / "test_symbol_registry.json"
        # Seed basic registry with core operators
        base_registry = SymbolRegistry()
        base_registry.load()
        base_registry.save(target_path=self.registry_file)

        self.registry = SymbolRegistry(registry_path=self.registry_file)
        self.registry.load()
        self.validator = SymbolValidator(self.registry)
        self.retriever = SymbolRetriever(self.registry)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_proposition_definition_notation_auto_formatting(self):
        """PropositionDefinition should automatically format notation as P := Definition."""
        prop = PropositionDefinition(
            symbol="P_RESET",
            definition="power-on reset occurs",
            provenance="EXPLICIT_SOURCE",
        )
        self.assertEqual(prop.notation, "P_RESET := power-on reset occurs")
        self.assertEqual(prop.symbol, "P_RESET")
        self.assertFalse(prop.user_approved)

        d = prop.to_dict()
        self.assertEqual(d["notation"], "P_RESET := power-on reset occurs")
        self.assertEqual(d["provenance"], "EXPLICIT_SOURCE")

        prop_roundtrip = PropositionDefinition.from_dict(d)
        self.assertEqual(prop_roundtrip.symbol, "P_RESET")
        self.assertEqual(prop_roundtrip.notation, "P_RESET := power-on reset occurs")

    def test_predicate_definition_notation_and_arguments(self):
        """PredicateDefinition should format notation with signature and description."""
        pred = PredicateDefinition(
            name="perform_init",
            entity="System_Initialization",
            arguments=["sys"],
            condition_type="ACTION",
            description="executes power-on initialization functions",
        )
        self.assertIn("perform_init(sys) :=", pred.notation)
        self.assertEqual(pred.entity, "System_Initialization")

        d = pred.to_dict()
        self.assertEqual(d["arguments"], ["sys"])
        pred_roundtrip = PredicateDefinition.from_dict(d)
        self.assertEqual(pred_roundtrip.name, "perform_init")
        self.assertEqual(pred_roundtrip.arguments, ["sys"])

    def test_intermediate_representation_schema_and_dict_access(self):
        """IntermediateRepresentation supports propositions, formula construction, and dict-like access."""
        p1 = PropositionDefinition(symbol="P1", definition="power-on reset event")
        p2 = PropositionDefinition(symbol="P2", definition="watchdog timer initiated")
        ir = IntermediateRepresentation(
            propositions=[p1, p2],
            temporal_operators=["G", "F"],
            composition_rules=["G(P1 -> F P2)"],
            formula_construction="Whenever power-on reset occurs (P1), eventually watchdog timer is initiated (P2).",
            unresolved_parameters=["t_timeout"],
        )
        # Test object access
        self.assertEqual(len(ir.propositions), 2)
        self.assertEqual(ir.propositions[0].symbol, "P1")
        self.assertEqual(ir.formula_construction, "Whenever power-on reset occurs (P1), eventually watchdog timer is initiated (P2).")

        # Test dict compatibility
        self.assertEqual(len(ir.get("propositions")), 2)
        self.assertEqual(ir["formula_construction"], "Whenever power-on reset occurs (P1), eventually watchdog timer is initiated (P2).")
        self.assertEqual(ir.get("unresolved_parameters"), ["t_timeout"])

        # Test roundtrip serialization
        d = ir.to_dict()
        ir_roundtrip = IntermediateRepresentation.from_dict(d)
        self.assertEqual(len(ir_roundtrip.propositions), 2)
        self.assertEqual(ir_roundtrip.propositions[1].symbol, "P2")
        self.assertEqual(ir_roundtrip.unresolved_parameters, ["t_timeout"])

    def test_symbol_validator_accepts_grounded_propositions(self):
        """Validator accepts candidate formula when all formula tokens are declared in IR propositions."""
        p_reset = PropositionDefinition(symbol="P_RESET", definition="power-on reset occurs")
        p_init = PropositionDefinition(symbol="InitFuncs", definition="initialization functions execute")
        ir = IntermediateRepresentation(
            propositions=[p_reset, p_init],
            temporal_operators=["G", "F"],
            formula_construction="Globally, P_RESET implies eventually InitFuncs.",
        )
        report = self.validator.validate_candidate(
            formalization="G(P_RESET -> F InitFuncs)",
            current_scope="[SRS194]",
            intermediate_representation=ir,
        )
        self.assertTrue(report.is_valid)
        error_violations = [v for v in report.violations if v.severity == "ERROR"]
        self.assertEqual(len(error_violations), 0)

    def test_symbol_validator_rejects_undefined_formula_symbol(self):
        """Validator reports ERROR when candidate formula uses a symbol missing from IR propositions."""
        p_reset = PropositionDefinition(symbol="P_RESET", definition="power-on reset occurs")
        ir = IntermediateRepresentation(
            propositions=[p_reset],
            temporal_operators=["G", "F"],
        )
        # Formula uses P_UNDEFINED which is not declared in IR or registry
        report = self.validator.validate_candidate(
            formalization="G(P_RESET -> F P_UNDEFINED)",
            current_scope="[SRS194]",
            intermediate_representation=ir,
        )
        self.assertFalse(report.is_valid)
        rules = [v.rule for v in report.violations if v.severity == "ERROR"]
        self.assertIn("UNDEFINED_FORMULA_SYMBOL", rules)
        bad_syms = [v.symbol_spelling for v in report.violations if v.rule == "UNDEFINED_FORMULA_SYMBOL"]
        self.assertIn("P_UNDEFINED", bad_syms)

    def test_symbol_validator_detects_unsupported_timing_bound(self):
        """Validator rejects unstated timing bounds like t_bound when not declared in unresolved_parameters."""
        p_reset = PropositionDefinition(symbol="P_RESET", definition="power-on reset occurs")
        p_init = PropositionDefinition(symbol="InitFuncs", definition="initialization functions execute")
        ir = IntermediateRepresentation(
            propositions=[p_reset, p_init],
            temporal_operators=["G", "F"],
            unresolved_parameters=[],  # NOT acknowledged as unresolved!
        )
        report = self.validator.validate_candidate(
            formalization="G(P_RESET -> F[0, t_bound] InitFuncs)",
            current_scope="[SRS194]",
            intermediate_representation=ir,
        )
        self.assertFalse(report.is_valid)
        rules = [v.rule for v in report.violations if v.severity == "ERROR"]
        self.assertIn("UNSTATED_TIMING_BOUND", rules)

    def test_symbol_validator_allows_acknowledged_unresolved_bound(self):
        """Validator permits t_bound when it is explicitly listed in unresolved_parameters."""
        p_reset = PropositionDefinition(symbol="P_RESET", definition="power-on reset occurs")
        p_init = PropositionDefinition(symbol="InitFuncs", definition="initialization functions execute")
        ir = IntermediateRepresentation(
            propositions=[p_reset, p_init],
            temporal_operators=["G", "F"],
            unresolved_parameters=["t_bound"],  # Acknowledged unresolved parameter
        )
        report = self.validator.validate_candidate(
            formalization="G(P_RESET -> F[0, t_bound] InitFuncs)",
            current_scope="[SRS194]",
            intermediate_representation=ir,
        )
        unstated_bounds = [v for v in report.violations if v.rule == "UNSTATED_TIMING_BOUND"]
        self.assertEqual(len(unstated_bounds), 0)

    def test_pipeline_registers_propositions_and_persists_to_registry(self):
        """Pipeline registers propositions and predicates in SymbolRegistry and saves to disk."""
        analyst = MagicMock(spec=AnalystModel)
        analyst.analyze.return_value = AnalystResult(
            requirement_id=1,
            global_number=1,
            srs_id="[SRS194]",
            identified_patterns=["Timeout / Deadline"],
            evidence={},
            missing_information=[],
        )

        p_reset = PropositionDefinition(
            symbol="P_RESET",
            definition="power-on reset occurs",
            notation="P_RESET := power-on reset occurs",
            provenance="EXPLICIT_SOURCE",
        )
        pred_init = PredicateDefinition(
            name="perform_init_functions",
            entity="System_Initialization",
            arguments=["System_Initialization"],
            condition_type="ACTION",
            description="System Initialization performs power-on functions",
            notation="perform_init_functions(sys) := System Initialization performs functions",
        )
        ir = IntermediateRepresentation(
            propositions=[p_reset],
            predicates=[pred_init],
            temporal_operators=["G", "F"],
            formula_construction="Globally when P_RESET occurs, eventually perform_init_functions.",
        )

        reasoning = MagicMock(spec=ReasoningModel)
        reasoning.reason.return_value = ReasoningResult(
            requirement_id=1,
            global_number=1,
            srs_id="[SRS194]",
            formalization="G(P_RESET -> F perform_init_functions)",
            interpretation="When power-on reset occurs, System Initialization performs functions.",
            identified_entities=["System_Initialization"],
            predicates=["perform_init_functions"],
            intermediate_representation=ir,
        )

        critic = MagicMock(spec=CriticModel)
        critic.critique.return_value = CriticResult(
            requirement_id=1,
            global_number=1,
            srs_id="[SRS194]",
            status="PASS",
            summary="Formalization accurately captures untimed trigger and response.",
            findings=[],
        )

        pipeline = FormalizationPipeline(
            analyst_model=analyst,
            reasoning_model=reasoning,
            critic_model=critic,
        )
        pipeline.symbol_retriever = self.retriever
        pipeline.symbol_validator = self.validator

        result = pipeline.run(requirement_id=1, max_revisions=1)
        self.assertEqual(result.status, "PASS")
        self.assertTrue(result.validation_valid)

        # Verify that P_RESET is now registered in the registry
        sym_prop = self.registry.get_symbol_by_spelling("P_RESET", scope="[SRS194]")
        self.assertIsNotNone(sym_prop)
        self.assertEqual(sym_prop.category, "PROPOSITION")
        self.assertEqual(sym_prop.definition, "power-on reset occurs")
        self.assertEqual(sym_prop.signature, "P_RESET := power-on reset occurs")
        self.assertFalse(sym_prop.user_approved)

        # Verify that perform_init_functions is registered as a PREDICATE
        sym_pred = self.registry.get_symbol_by_spelling("perform_init_functions", scope="[SRS194]")
        self.assertIsNotNone(sym_pred)
        self.assertEqual(sym_pred.category, "PREDICATE")

        # Verify persistence to disk
        reloaded = SymbolRegistry(registry_path=self.registry_file)
        reloaded.load()
        disk_sym = reloaded.get_symbol_by_spelling("P_RESET", scope="[SRS194]")
        self.assertIsNotNone(disk_sym)
        self.assertEqual(disk_sym.category, "PROPOSITION")

    def test_pipeline_preserves_user_approved_symbol_definitions(self):
        """User-approved definitions in SymbolRegistry must never be overwritten by model proposals."""
        # 1. Register a user-approved symbol
        sym, is_new = self.registry.register_domain_symbol(
            spelling="P_RESET",
            category="PROPOSITION",
            scope="[SRS194]",
            definition="User-approved exact electrical power-on sequence definition",
            signature="P_RESET := User-approved exact definition",
            user_approved=True,
        )
        self.assertTrue(is_new)
        self.assertTrue(sym.user_approved)

        # 2. Automated model produces a different proposal with user_approved=False
        p_model = PropositionDefinition(
            symbol="P_RESET",
            definition="Automated generic model definition",
            user_approved=False,
        )
        ir = IntermediateRepresentation(propositions=[p_model])
        reasoning = MagicMock(spec=ReasoningModel)
        reasoning.reason.return_value = ReasoningResult(
            requirement_id=1,
            global_number=1,
            srs_id="[SRS194]",
            formalization="G(P_RESET -> true)",
            intermediate_representation=ir,
        )

        analyst = MagicMock(spec=AnalystModel)
        analyst.analyze.return_value = AnalystResult(
            requirement_id=1,
            global_number=1,
            srs_id="[SRS194]",
            identified_patterns=[],
            evidence={},
            missing_information=[],
        )

        critic = MagicMock(spec=CriticModel)
        critic.critique.return_value = CriticResult(
            requirement_id=1,
            global_number=1,
            srs_id="[SRS194]",
            status="PASS",
            summary="Pass",
            findings=[],
        )

        pipeline = FormalizationPipeline(analyst_model=analyst, reasoning_model=reasoning, critic_model=critic)
        pipeline.symbol_retriever = self.retriever
        pipeline.symbol_validator = self.validator
        pipeline.run(1)

        # Verify the user-approved definition was preserved intact
        existing = self.registry.get_symbol_by_spelling("P_RESET", scope="[SRS194]")
        self.assertEqual(existing.definition, "User-approved exact electrical power-on sequence definition")
        self.assertTrue(existing.user_approved)

    def test_ui_templates_render_propositions_and_formula_construction(self):
        """Flask UI templates (formalize.html and batch_formalize.html) render propositions and formula construction."""
        p_reset = PropositionDefinition(
            symbol="P_RESET",
            definition="power-on reset event occurs",
            notation="P_RESET := power-on reset event occurs",
            provenance="EXPLICIT_SOURCE",
        )
        ir = IntermediateRepresentation(
            propositions=[p_reset],
            formula_construction="Formula is assembled as G(P_RESET -> F perform_init).",
            unresolved_parameters=["t_bound"],
        )

        result_dict = {
            "requirement_id": 1,
            "global_number": 1,
            "srs_id": "[SRS194]",
            "section_number": "3.2.1",
            "section_title": "System Initialization",
            "raw_text": "Whenever a power-on reset occurs, System Initialization shall perform functions.",
            "status": "PASS",
            "success": True,
            "formalization": "G(P_RESET -> F perform_init)",
            "interpretation": "Interpretation text",
            "validation_valid": True,
            "validation_findings": [],
            "clarifications": [],
            "intermediate_representation": ir.to_dict(),
        }

        with flask_app.test_request_context():
            from flask import render_template
            # Render individual requirement formalization template
            dummy_req = {
                "id": 1,
                "document_id": 1,
                "section_number": "3.2.1",
                "section_title": "System Initialization",
                "page_number": 1,
            }
            html = render_template(
                "formalize.html",
                result=result_dict,
                req=dummy_req,
                can_reformalize=True,
                max_revisions=2,
            )
            self.assertIn("Propositions & Predicates", html)
            self.assertIn("P_RESET := power-on reset event occurs", html)
            self.assertIn("Formula Construction & Composition", html)
            self.assertIn("Formula is assembled as G(P_RESET -&gt; F perform_init).", html)
            self.assertIn("t_bound", html)

            # Render batch formalization template
            batch_html = render_template(
                "batch_formalize.html",
                results=[result_dict],
                req_ids=[1],
                max_revisions=2,
                summary={"PASS": {"count": 1, "css": "success"}},
            )
            self.assertIn("Propositions & Formula Construction", batch_html)
            self.assertIn("P_RESET := power-on reset event occurs", batch_html)


if __name__ == "__main__":
    unittest.main()
