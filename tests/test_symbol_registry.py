import json
import tempfile
import unittest
from pathlib import Path

from app.symbols.schemas import (
    SymbolDefinition,
    SymbolRegistryError,
    SymbolValidationError,
    SymbolValidationReport,
)
from app.symbols.symbol_registry import SymbolRegistry
from app.symbols.symbol_retriever import SymbolRetriever
from app.symbols.symbol_validator import SymbolValidator


class TestSymbolRegistry(unittest.TestCase):
    """
    Deterministic unit tests for SymbolRegistry, SymbolRetriever, and SymbolValidator.
    Requires no Ollama or network connectivity.
    """

    def setUp(self):
        self.registry = SymbolRegistry()
        self.registry.load()
        self.retriever = SymbolRetriever(self.registry)
        self.validator = SymbolValidator(self.registry)

    def test_load_canonical_registry(self):
        self.assertGreater(len(self.registry), 10)
        self.assertEqual(self.registry.version, "1.0.0")
        all_symbols = self.registry.get_all_symbols()
        identifiers = [s.identifier for s in all_symbols]
        self.assertIn("sym_ltl_globally", identifiers)
        self.assertIn("sym_ltl_finally", identifiers)
        self.assertIn("sym_srs178_loss_of_comm", identifiers)

    def test_retrieve_global_symbols(self):
        result = self.retriever.get_global_symbols()
        self.assertEqual(result.query_type, "global")
        self.assertGreater(len(result.symbols), 5)
        for sym in result.symbols:
            self.assertTrue(sym.is_global())
        spellings = [s.spelling for s in result.symbols]
        self.assertIn("G", spellings)
        self.assertIn("F", spellings)
        self.assertIn("->", spellings)

    def test_retrieve_requirement_specific_symbols(self):
        # Retrieve symbols for [SRS178]
        result = self.retriever.get_symbols_for_requirement("[SRS178]")
        self.assertEqual(result.query_type, "requirement")
        spellings = [s.spelling for s in result.symbols]
        self.assertIn("G", spellings)
        self.assertIn("loss_of_comm", spellings)
        self.assertIn("outputs_disabled", spellings)
        self.assertIn("10ms", spellings)

    def test_alias_lookup(self):
        # Lookup '[]' alias of 'G'
        sym_box = self.retriever.get_symbol_by_spelling_or_alias("[]")
        self.assertIsNotNone(sym_box)
        self.assertEqual(sym_box.identifier, "sym_ltl_globally")

        # Lookup '<>' alias of 'F'
        sym_diamond = self.retriever.get_symbol_by_spelling_or_alias("<>")
        self.assertIsNotNone(sym_diamond)
        self.assertEqual(sym_diamond.identifier, "sym_ltl_finally")

        # Lookup 'comm_loss' alias of 'loss_of_comm' under scope [SRS178]
        sym_comm = self.retriever.get_symbol_by_spelling_or_alias("comm_loss", scope="[SRS178]")
        self.assertIsNotNone(sym_comm)
        self.assertEqual(sym_comm.identifier, "sym_srs178_loss_of_comm")

    def test_scope_isolation(self):
        # Scope [SRS015] must NOT include [SRS178]-specific symbols
        result = self.retriever.get_symbols_for_requirement("[SRS015]")
        spellings = [s.spelling for s in result.symbols]
        self.assertIn("G", spellings)
        self.assertNotIn("loss_of_comm", spellings)
        self.assertNotIn("outputs_disabled", spellings)

    def test_duplicate_identifier_rejection(self):
        duplicate_sym = SymbolDefinition(
            identifier="sym_ltl_globally",
            spelling="GL",
            definition="Duplicate identifier test",
            category="TEMPORAL_OPERATOR",
            scope="global",
        )
        with self.assertRaises(SymbolValidationError):
            self.registry.register_symbol(duplicate_sym)

    def test_conflicting_spelling_in_same_scope_rejection(self):
        conflicting_sym = SymbolDefinition(
            identifier="sym_custom_g",
            spelling="G",
            definition="Conflicting spelling in global scope",
            category="TEMPORAL_OPERATOR",
            scope="global",
        )
        with self.assertRaises(SymbolValidationError):
            self.registry.register_symbol(conflicting_sym)

    def test_alias_collision_in_same_scope_rejection(self):
        colliding_alias_sym = SymbolDefinition(
            identifier="sym_box_collision",
            spelling="BOX",
            definition="Colliding alias with G's [] alias",
            category="TEMPORAL_OPERATOR",
            scope="global",
            aliases=["[]"],
        )
        with self.assertRaises(SymbolValidationError):
            self.registry.register_symbol(colliding_alias_sym)

    def test_legitimate_different_meanings_in_different_scopes(self):
        # A symbol 'P' in scope [SRS001] and 'P' in scope [SRS002] can coexist
        sym_p1 = SymbolDefinition(
            identifier="sym_srs001_p",
            spelling="P",
            definition="Pressure sensor in SRS001",
            category="PREDICATE",
            scope="[SRS001]",
        )
        sym_p2 = SymbolDefinition(
            identifier="sym_srs002_p",
            spelling="P",
            definition="Power bus in SRS002",
            category="PREDICATE",
            scope="[SRS002]",
        )
        self.registry.register_symbol(sym_p1)
        self.registry.register_symbol(sym_p2)

        retrieved_1 = self.retriever.get_symbol_by_spelling_or_alias("P", scope="[SRS001]")
        retrieved_2 = self.retriever.get_symbol_by_spelling_or_alias("P", scope="[SRS002]")
        self.assertIsNotNone(retrieved_1)
        self.assertIsNotNone(retrieved_2)
        self.assertEqual(retrieved_1.identifier, "sym_srs001_p")
        self.assertEqual(retrieved_2.identifier, "sym_srs002_p")

    def test_invalid_registry_file_or_content(self):
        non_existent = Path("non_existent_symbol_file.json")
        reg = SymbolRegistry(registry_path=non_existent)
        with self.assertRaises(SymbolRegistryError):
            reg.load()

        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tmp:
            tmp.write("{ invalid json")
            tmp_path = tmp.name

        try:
            reg_bad = SymbolRegistry(registry_path=tmp_path)
            with self.assertRaises(SymbolRegistryError):
                reg_bad.load()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_empty_registry_handling(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as tmp:
            tmp.write(json.dumps({"version": "1.0.0", "symbols": []}))
            tmp_path = tmp.name

        try:
            empty_reg = SymbolRegistry(registry_path=tmp_path)
            empty_reg.load()
            self.assertEqual(len(empty_reg), 0)
            retriever = SymbolRetriever(empty_reg)
            global_res = retriever.get_global_symbols()
            self.assertEqual(len(global_res.symbols), 0)
            self.assertIsNone(retriever.get_symbol_by_identifier("any"))
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_serialization_roundtrip(self):
        sym = self.registry.get_symbol_by_identifier("sym_ltl_globally")
        d = sym.to_dict()
        sym_roundtrip = SymbolDefinition.from_dict(d)
        self.assertEqual(sym.identifier, sym_roundtrip.identifier)
        self.assertEqual(sym.spelling, sym_roundtrip.spelling)
        self.assertEqual(sym.category, sym_roundtrip.category)

    def test_validator_detects_out_of_scope_symbol(self):
        # loss_of_comm is registered specifically for [SRS178], should fail in scope [SRS015]
        report = self.validator.validate_candidate(
            formalization="G(loss_of_comm -> F outputs_disabled)",
            current_scope="[SRS015]",
        )
        self.assertFalse(report.is_valid)
        error_rules = [v.rule for v in report.violations if v.severity == "ERROR"]
        self.assertIn("OUT_OF_SCOPE_SYMBOL", error_rules)

    def test_validator_detects_conflicting_definition(self):
        # Candidate asserts that G means "Ground state" instead of temporal Globally
        report = self.validator.validate_candidate(
            formalization="G(safe_state)",
            current_scope="global",
            candidate_definitions={"G": "Ground state vehicle orientation indicator"},
        )
        self.assertFalse(report.is_valid)
        error_rules = [v.rule for v in report.violations if v.severity == "ERROR"]
        self.assertIn("CONFLICTING_DEFINITION", error_rules)

    def test_validator_reports_unregistered_symbol(self):
        report = self.validator.validate_candidate(
            formalization="G(custom_unregistered_subsystem_active -> true)",
            current_scope="[SRS178]",
        )
        # Advisory notice
        info_symbols = [v.symbol_spelling for v in report.violations if v.rule == "UNREGISTERED_SYMBOL"]
        self.assertIn("custom_unregistered_subsystem_active", info_symbols)

    def test_validator_valid_formalization_in_correct_scope(self):
        report = self.validator.validate_candidate(
            formalization="G(loss_of_comm -> F[0, 10ms] outputs_disabled)",
            current_scope="[SRS178]",
        )
        # Should have zero ERROR violations
        error_count = sum(1 for v in report.violations if v.severity == "ERROR")
        self.assertEqual(error_count, 0)
        self.assertTrue(report.is_valid)


if __name__ == "__main__":
    unittest.main()
