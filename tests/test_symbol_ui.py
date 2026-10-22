import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.symbols.schemas import SymbolDefinition, SymbolValidationError
from app.symbols.symbol_registry import SymbolRegistry
from app.symbols.symbol_retriever import SymbolRetriever
from app.pipeline import FormalizationPipeline
from app.reasoning.schemas import IntermediateRepresentation, PredicateDefinition, ReasoningResult
from app.retrieval.sqlite_retriever import RequirementContext
from app.ui.app import app


class TestSymbolRegistryUI(unittest.TestCase):
    """
    Focused, offline test suite verifying the User-Manageable Symbol Registry UI,
    including search/filtering, editing, user-approved protection, reference tracking,
    safe deactivation, deletion protection, and intermediate representation registration.
    """

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.registry_path = Path(self.tmp_dir) / "symbol_registry.json"
        self.result_cache_path = Path(self.tmp_dir) / "result_cache.json"
        self.history_store_path = Path(self.tmp_dir) / "history_store.json"

        # Copy canonical registry or seed a test registry
        orig_registry = Path("data") / "symbol_registry.json"
        if orig_registry.exists():
            shutil.copyfile(orig_registry, self.registry_path)
        else:
            seed_data = {
                "version": "1.0.0",
                "description": "Test registry",
                "symbols": [
                    {
                        "identifier": "sym_ltl_globally",
                        "spelling": "G",
                        "definition": "Globally operator",
                        "category": "TEMPORAL_OPERATOR",
                        "scope": "global",
                        "provenance": {"source": "LTL"},
                        "version": "1.0.0",
                        "aliases": ["[]"],
                        "notes": "Unary operator",
                    },
                    {
                        "identifier": "sym_srs178_loss_of_comm",
                        "spelling": "loss_of_comm",
                        "definition": "Loss of communication condition",
                        "category": "PREDICATE",
                        "scope": "[SRS178]",
                        "provenance": {"source": "NASA X-38", "srs_id": "[SRS178]", "requirement_id": 8},
                        "version": "1.0.0",
                        "aliases": ["comm_loss"],
                    },
                ],
            }
            self.registry_path.write_text(json.dumps(seed_data), encoding="utf-8")

        # Seed result cache referencing loss_of_comm
        cache_data = {
            "8": {
                "requirement_id": 8,
                "saved_at": "2026-10-18T10:00:00Z",
                "result": {
                    "requirement_id": 8,
                    "srs_id": "[SRS178]",
                    "formalization": "G (loss_of_comm -> F[0, 10ms] outputs_disabled)",
                    "predicates": ["loss_of_comm", "outputs_disabled"],
                    "symbols": ["G", "loss_of_comm", "outputs_disabled"],
                    "success": True,
                },
            }
        }
        self.result_cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

        # Configure Flask test client
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _get_registry(self) -> SymbolRegistry:
        reg = SymbolRegistry(registry_path=self.registry_path)
        reg.load()
        return reg

    def test_dashboard_renders_and_lists_symbols(self):
        """Dashboard route /symbols should return 200 and list symbols."""
        with patch("app.ui.app._get_symbol_registry", return_value=self._get_registry()):
            resp = self.client.get("/symbols")
            self.assertEqual(resp.status_code, 200)
            text = resp.get_data(as_text=True)
            self.assertIn("Symbol Registry &amp; Domain Dictionary", text)
            self.assertIn("G", text)
            self.assertIn("loss_of_comm", text)
            self.assertIn("Active Symbols", text)

    def test_dashboard_search_and_category_filter(self):
        """Test query and category filtering on /symbols."""
        with patch("app.ui.app._get_symbol_registry", return_value=self._get_registry()):
            # Filter by query
            resp = self.client.get("/symbols?q=loss_of_comm")
            self.assertEqual(resp.status_code, 200)
            text = resp.get_data(as_text=True)
            self.assertIn("loss_of_comm", text)

            # Filter by category TEMPORAL_OPERATOR
            resp2 = self.client.get("/symbols?category=TEMPORAL_OPERATOR")
            self.assertEqual(resp2.status_code, 200)
            text2 = resp2.get_data(as_text=True)
            self.assertIn("G", text2)

    def test_symbol_detail_view(self):
        """Detail page should display symbol identity, definition, and references."""
        with patch("app.ui.app._get_symbol_registry", return_value=self._get_registry()):
            resp = self.client.get("/symbols/sym_srs178_loss_of_comm")
            self.assertEqual(resp.status_code, 200)
            text = resp.get_data(as_text=True)
            self.assertIn("loss_of_comm", text)
            self.assertIn("sym_srs178_loss_of_comm", text)
            self.assertIn("Usage &amp; Historical References", text)

    def test_edit_symbol_definition_persists_and_marks_user_approved(self):
        """Editing definition updates disk, sets user_approved=True, and persists."""
        reg = self._get_registry()
        with patch("app.ui.app._get_symbol_registry", return_value=reg):
            resp = self.client.post(
                "/symbols/sym_srs178_loss_of_comm/edit",
                data={
                    "definition": "Engineered telemetry loss across primary and secondary dual buses.",
                    "signature": "State -> Bool",
                    "arity": "1",
                    "notes": "Verified against ICD 4.2",
                },
                follow_redirects=True,
            )
            self.assertEqual(resp.status_code, 200)

        # Reload registry from disk to verify persistence
        reloaded = self._get_registry()
        sym = reloaded.get_symbol_by_identifier("sym_srs178_loss_of_comm")
        self.assertIsNotNone(sym)
        self.assertEqual(sym.definition, "Engineered telemetry loss across primary and secondary dual buses.")
        self.assertEqual(sym.signature, "State -> Bool")
        self.assertEqual(sym.arity, 1)
        self.assertEqual(sym.notes, "Verified against ICD 4.2")
        self.assertTrue(sym.user_approved)
        self.assertTrue(sym.provenance.get("user_approved"))
        self.assertEqual(sym.provenance.get("last_edited_by"), "user")

    def test_edit_rejects_empty_definition(self):
        """Editing with an empty definition should be rejected."""
        reg = self._get_registry()
        with patch("app.ui.app._get_symbol_registry", return_value=reg):
            resp = self.client.post(
                "/symbols/sym_srs178_loss_of_comm/edit",
                data={"definition": "   "},
                follow_redirects=True,
            )
            self.assertEqual(resp.status_code, 200)
            text = resp.get_data(as_text=True)
            self.assertIn("Symbol definition cannot be empty", text)

    def test_core_operators_cannot_be_deleted_or_deactivated(self):
        """Core operators (G, F, etc.) are protected from deletion and deactivation."""
        reg = self._get_registry()
        with self.assertRaises(SymbolValidationError):
            reg.deactivate_symbol("sym_ltl_globally")

        with self.assertRaises(SymbolValidationError):
            reg.delete_symbol("sym_ltl_globally")

    def test_referenced_symbol_blocks_deletion_allows_deactivation(self):
        """A symbol referenced in past results blocks permanent deletion, but allows soft deactivation."""
        reg = self._get_registry()
        refs = reg.find_symbol_references("sym_srs178_loss_of_comm")
        self.assertFalse(refs["can_permanently_delete"])
        self.assertTrue(refs["can_deactivate"])
        self.assertGreater(refs["total_references"], 0)

        # Permanent deletion should raise validation error
        with self.assertRaises(SymbolValidationError):
            reg.delete_symbol("sym_srs178_loss_of_comm", force=False)

        # Deactivation should succeed
        updated = reg.deactivate_symbol("sym_srs178_loss_of_comm")
        self.assertFalse(updated.is_active)

        # Reload from disk and verify deactivation persisted
        reloaded = self._get_registry()
        sym = reloaded.get_symbol_by_identifier("sym_srs178_loss_of_comm")
        self.assertFalse(sym.is_active)

        # SymbolRetriever must exclude deactivated symbol
        retriever = SymbolRetriever(registry=reloaded)
        retrieval = retriever.get_symbols_for_requirement("[SRS178]")
        active_identifiers = [s.identifier for s in retrieval.symbols]
        self.assertNotIn("sym_srs178_loss_of_comm", active_identifiers)

        # Reactivation should succeed
        reloaded.activate_symbol("sym_srs178_loss_of_comm")
        reloaded_again = self._get_registry()
        self.assertTrue(reloaded_again.get_symbol_by_identifier("sym_srs178_loss_of_comm").is_active)

    def test_unreferenced_symbol_allows_safe_deletion(self):
        """An unreferenced custom symbol can be safely deleted permanently."""
        reg = self._get_registry()
        sym, created = reg.register_domain_symbol(
            spelling="temp_unused_flag",
            category="PREDICATE",
            scope="[SRS999]",
            definition="Temporary unused flag for testing deletion",
            user_approved=True,
        )
        self.assertTrue(created)
        self.assertIsNotNone(reg.get_symbol_by_identifier(sym.identifier))

        # Check references: should be 0
        refs = reg.find_symbol_references(sym.identifier)
        self.assertTrue(refs["can_permanently_delete"])

        # Delete symbol
        deleted = reg.delete_symbol(sym.identifier)
        self.assertTrue(deleted)

        # Verify it no longer exists on disk
        reloaded = self._get_registry()
        self.assertIsNone(reloaded.get_symbol_by_identifier(sym.identifier))

    def test_register_domain_symbol_from_ui(self):
        """Test registering a new domain symbol via POST /symbols/register."""
        reg = self._get_registry()
        with patch("app.ui.app._get_symbol_registry", return_value=reg):
            resp = self.client.post(
                "/symbols/register",
                data={
                    "spelling": "cabin_pressure_ok",
                    "category": "PREDICATE",
                    "scope": "[SRS200]",
                    "definition": "Indicates cabin environmental pressure is within 0.95 to 1.05 bar.",
                    "signature": "Pressure -> Bool",
                    "arity": "1",
                    "aliases": "pressure_ok, cabin_ok",
                    "notes": "Environmental Control System",
                },
                follow_redirects=True,
            )
            self.assertEqual(resp.status_code, 200)

        reloaded = self._get_registry()
        sym = reloaded.get_symbol_by_spelling("cabin_pressure_ok", scope="[SRS200]")
        self.assertIsNotNone(sym)
        self.assertEqual(sym.category, "PREDICATE")
        self.assertEqual(sym.scope, "[SRS200]")
        self.assertTrue(sym.user_approved)

    def test_intermediate_representation_registration(self):
        """Test pipeline registration of predicates, propositions, and entities from intermediate representation."""
        reg = self._get_registry()
        retriever = SymbolRetriever(registry=reg)

        pipeline = FormalizationPipeline(symbol_retriever=retriever)

        req_ctx = RequirementContext(
            requirement_id=42,
            global_number=42,
            source_number=42,
            srs_id="[SRS250]",
            section_number="4.2",
            section_title="Hydraulics",
            raw_text="The hydraulic pump shall maintain nominal pressure.",
            normalized_text="The hydraulic pump shall maintain nominal pressure.",
            page_number=10,
            element_index=1,
            document_id=1,
        )

        ir = IntermediateRepresentation(
            predicates=[
                PredicateDefinition(
                    name="pump_pressure_nominal",
                    entity="HydraulicPump",
                    condition_type="STATE",
                    description="Asserts hydraulic pump pressure is nominal",
                    formal_expression="HydraulicPump.pressure >= 3000psi",
                )
            ],
            atomic_clauses=["pump_enabled"],
        )

        reasoning = ReasoningResult(
            requirement_id=42,
            global_number=42,
            srs_id="[SRS250]",
            interpretation="Pump test",
            identified_entities=["HydraulicPump"],
            predicates=["pump_active"],
            intermediate_representation=ir.to_dict(),
        )

        pipeline._register_intermediate_symbols(req_ctx, reasoning)

        # Verify symbols registered in registry
        pred_sym = reg.get_symbol_by_spelling("pump_pressure_nominal", scope="[SRS250]")
        self.assertIsNotNone(pred_sym)
        self.assertEqual(pred_sym.category, "PREDICATE")
        self.assertEqual(pred_sym.signature, "HydraulicPump.pressure >= 3000psi")

        prop_sym = reg.get_symbol_by_spelling("pump_enabled", scope="[SRS250]")
        self.assertIsNotNone(prop_sym)
        self.assertEqual(prop_sym.category, "PROPOSITION")

        ent_sym = reg.get_symbol_by_spelling("HydraulicPump", scope="[SRS250]")
        self.assertIsNotNone(ent_sym)
        self.assertEqual(ent_sym.category, "ENTITY")

    def test_user_approved_symbol_not_overwritten_by_model(self):
        """A user-approved symbol's definition cannot be silently overwritten by automated model registration."""
        reg = self._get_registry()
        # 1. User registers/edits a symbol
        sym, _ = reg.register_domain_symbol(
            spelling="radar_track_valid",
            category="PREDICATE",
            scope="[SRS300]",
            definition="User approved: radar track has >= 3 consecutive target hits.",
            user_approved=True,
        )
        self.assertTrue(sym.user_approved)

        # 2. Automated model run attempts to register same symbol with different definition
        retriever = SymbolRetriever(registry=reg)
        pipeline = FormalizationPipeline(symbol_retriever=retriever)

        req_ctx = RequirementContext(
            requirement_id=50,
            global_number=50,
            source_number=50,
            srs_id="[SRS300]",
            section_number="5.0",
            section_title="Radar",
            raw_text="Radar tracking logic",
            normalized_text="Radar tracking logic",
            page_number=15,
            element_index=2,
            document_id=1,
        )

        ir = IntermediateRepresentation(
            predicates=[
                PredicateDefinition(
                    name="radar_track_valid",
                    entity="Radar",
                    condition_type="STATE",
                    description="Model proposed: track is valid",
                )
            ]
        )

        reasoning = ReasoningResult(
            requirement_id=50,
            global_number=50,
            srs_id="[SRS300]",
            intermediate_representation=ir.to_dict(),
        )

        pipeline._register_intermediate_symbols(req_ctx, reasoning)

        # 3. Verify user's definition was PRESERVED
        sym_after = reg.get_symbol_by_spelling("radar_track_valid", scope="[SRS300]")
        self.assertEqual(sym_after.definition, "User approved: radar track has >= 3 consecutive target hits.")
        self.assertTrue(sym_after.user_approved)


if __name__ == "__main__":
    unittest.main()
