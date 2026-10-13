"""Offline tests for deterministic validation, the bounded revision loop, the persistent result
cache and model-config persistence. No Ollama, no network, no writes to the real data/ folder."""

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.critic.critic_model import CriticModel
from app.critic.schemas import CriticResult
from app.formalization_validator import validate_formalization
from app.pipeline import PipelineResult
from app.reasoning.reasoning_model import ReasoningModel
from app.reasoning.schemas import ReasoningResult
from app.retrieval.context_builder import ContextPackage, RequirementContext
from app.retrieval.obsidian_retriever import RetrievalResult
from app.revision.revision_manager import RevisionManager
from app.symbols.symbol_registry import SymbolRegistry
from app.symbols.symbol_validator import SymbolValidator
from app.ui import model_config, result_store

KNOWN_BAD = "G(supports(up_to_3_rate_groups_per_vehicle_mode) -> F)"


class TestFormalizationValidator(unittest.TestCase):
    VALID = [
        "G(failed_sync_2.5s -> F[0,1s] send_vme_reset)",
        "G(loss_of_comm -> F[0, 10ms] outputs_disabled)",
        "G(comm_lost -> F safe_state)",          # unbracketed F with an operand
        "G (p -> F (q))",                         # whitespace before operand
        "G(supports(up_to_3_rate_groups_per_vehicle_mode) -> F supports_ok)",
        "G(!failed(FCP) && synced(FCP) -> X ready)",
        "time_since_loss > 2.5s",                 # non-temporal metric constraint
        "response_time <= 10ms",
    ]
    INVALID = [
        KNOWN_BAD,
        "G(p -> F[0,1s])",        # bounded F with no operand
        "G(p -> F )",
        "G",
        "G(p ->)",
        "G(-> p)",
        "p && && q",
        "G(p <->)",
        "G(p -> F q",             # unclosed delimiter
        "G p -> q)",              # unmatched closer
        "",
        "   ",
        None,
    ]

    def test_valid_formulas_are_accepted(self):
        for formula in self.VALID:
            report = validate_formalization(formula)
            self.assertTrue(report.is_valid, f"{formula!r} wrongly rejected: {report.findings}")
            self.assertEqual(report.findings, [])

    def test_malformed_formulas_are_rejected(self):
        for formula in self.INVALID:
            report = validate_formalization(formula)
            self.assertFalse(report.is_valid, f"{formula!r} wrongly accepted")
            self.assertGreater(len(report.findings), 0)

    def test_known_bad_formula_is_explained_once(self):
        report = validate_formalization(KNOWN_BAD)
        self.assertFalse(report.is_valid)
        self.assertEqual([f["rule"] for f in report.findings], ["INCOMPLETE_TEMPORAL_OPERATOR"])
        finding = report.findings[0]
        self.assertEqual(finding["category"], "FORMALIZATION_STRUCTURE")
        self.assertEqual(finding["severity"], "ERROR")
        self.assertIn("operand", finding["description"])
        self.assertTrue(finding["recommendation"])


class TestRevisionLoopValidation(unittest.TestCase):
    def setUp(self):
        req = RequirementContext(
            requirement_id=8, global_number=8, source_number=8, srs_id="[SRS178]",
            section_number="3.2.1", section_title="Safety Subsystem",
            raw_text="The system shall disable all outputs within 10ms if loss of communication occurs.",
            normalized_text="The system shall disable all outputs within 10ms if loss of communication occurs.",
            page_number=12, element_index=1, document_id=1,
        )
        self.context = ContextPackage(
            requirements=[req], identified_patterns=[],
            obsidian_knowledge=RetrievalResult(pattern_items=[], loaded_files_count=0, read_cache_hits=0),
            provenance={},
        )
        self.valid = ReasoningResult(
            requirement_id=8, global_number=8, srs_id="[SRS178]",
            formalization="G(loss_of_comm -> F[0, 10ms] outputs_disabled)",
            interpretation="ok",
        )
        self.invalid = dataclasses.replace(self.valid, formalization=KNOWN_BAD)
        self.critic_pass = CriticResult(requirement_id=8, global_number=8, srs_id="[SRS178]",
                                        status="PASS", summary="Looks fine.")

    def manager(self, reasoning_outputs, critic_return, max_iterations):
        reasoning = MagicMock(spec=ReasoningModel)
        if isinstance(reasoning_outputs, list):
            reasoning.reason.side_effect = reasoning_outputs
        else:
            reasoning.reason.return_value = reasoning_outputs
        critic = MagicMock(spec=CriticModel)
        critic.critique.return_value = critic_return
        return reasoning, critic, RevisionManager(reasoning, critic, max_iterations=max_iterations)

    def test_critic_pass_with_invalid_formula_never_passes_and_is_bounded(self):
        reasoning, critic, manager = self.manager(self.invalid, self.critic_pass, 3)

        result = manager.run_revision_loop(self.context)

        self.assertEqual(result.status, "MAX_ITERATIONS")
        self.assertEqual(result.iterations_conducted, 3)
        self.assertEqual(reasoning.reason.call_count, 3)
        self.assertEqual(result.final_critic_result.status, "NEEDS_REVISION")
        self.assertTrue(result.final_critic_result.revision_required)
        categories = [f.category for f in result.final_critic_result.findings]
        self.assertIn("FORMALIZATION_STRUCTURE", categories)
        # The model's own critic object is not mutated.
        self.assertEqual(self.critic_pass.status, "PASS")
        self.assertEqual(self.critic_pass.findings, [])

    def test_invalid_formula_is_corrected_on_revision(self):
        reasoning, critic, manager = self.manager([self.invalid, self.valid], self.critic_pass, 3)

        result = manager.run_revision_loop(self.context)

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.iterations_conducted, 2)
        self.assertEqual(result.final_reasoning_result.formalization, self.valid.formalization)
        revision_prompt = reasoning.reason.call_args_list[1].kwargs["user_prompt"]
        self.assertIsNotNone(revision_prompt)
        self.assertIn("Deterministic structural validation failed", revision_prompt)

    def test_critic_blocked_is_not_downgraded_by_validator(self):
        blocked = dataclasses.replace(self.critic_pass, status="BLOCKED", summary="Contradictory.")
        reasoning, critic, manager = self.manager(self.invalid, blocked, 3)

        result = manager.run_revision_loop(self.context)

        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.termination_reason, "CRITIC_BLOCKED")
        self.assertEqual(result.iterations_conducted, 1)
        self.assertEqual(result.final_critic_result.status, "BLOCKED")
        self.assertIn("FORMALIZATION_STRUCTURE", [f.category for f in result.final_critic_result.findings])

    def test_single_iteration_bound_with_invalid_formula(self):
        reasoning, critic, manager = self.manager(self.invalid, self.critic_pass, 1)
        result = manager.run_revision_loop(self.context)
        self.assertEqual(result.status, "MAX_ITERATIONS")
        self.assertEqual(reasoning.reason.call_count, 1)

    def test_valid_formula_with_critic_pass_is_unchanged(self):
        reasoning, critic, manager = self.manager(self.valid, self.critic_pass, 3)
        result = manager.run_revision_loop(self.context)
        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.final_critic_result.findings, [])

    def test_out_of_scope_symbol_in_revision_loop_prevents_critic_pass(self):
        registry = SymbolRegistry()
        registry.load()
        validator = SymbolValidator(registry)
        req_015 = dataclasses.replace(self.context.requirements[0], requirement_id=1, global_number=1, srs_id="[SRS015]")
        context_015 = dataclasses.replace(self.context, requirements=[req_015])
        bad_scoped = dataclasses.replace(
            self.valid,
            srs_id="[SRS015]",
            formalization="G(loss_of_comm -> F outputs_disabled)"
        )
        reasoning = MagicMock(spec=ReasoningModel)
        reasoning.reason.return_value = bad_scoped
        critic = MagicMock(spec=CriticModel)
        critic.critique.return_value = self.critic_pass

        manager = RevisionManager(reasoning, critic, max_iterations=2, symbol_validator=validator)
        result = manager.run_revision_loop(context_015)

        self.assertEqual(result.status, "MAX_ITERATIONS")
        self.assertEqual(result.final_critic_result.status, "NEEDS_REVISION")
        categories = [f.category for f in result.final_critic_result.findings]
        self.assertIn("SYMBOL_VALIDATION", categories)

    def test_in_scope_symbol_in_revision_loop_passes(self):
        registry = SymbolRegistry()
        registry.load()
        validator = SymbolValidator(registry)
        reasoning = MagicMock(spec=ReasoningModel)
        reasoning.reason.return_value = self.valid
        critic = MagicMock(spec=CriticModel)
        critic.critique.return_value = self.critic_pass

        manager = RevisionManager(reasoning, critic, max_iterations=2, symbol_validator=validator)
        result = manager.run_revision_loop(self.context)

        self.assertEqual(result.status, "PASS")
        self.assertEqual(result.final_critic_result.findings, [])


class TestResultStore(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "nested" / "result_cache.json"
        for patcher in (patch.object(result_store, "STORE_PATH", self.path),
                        patch.object(result_store, "_entries", None)):
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def ok(rid, status="PASS", **kw):
        return PipelineResult(rid, rid, f"[SRS{rid}]", "3", "t", "raw text", status=status, **kw)

    @staticmethod
    def failed(rid):
        return PipelineResult(rid, 0, "", "", "", "", status="FAILED", success=False,
                              error_stage="PIPELINE", error_message="boom")

    def restart(self):
        result_store._entries = None

    def test_unknown_requirement_returns_none(self):
        self.assertIsNone(result_store.get(8))
        self.assertIsNone(result_store.get_saved_at(8))

    def test_save_get_roundtrip_and_identity(self):
        result_store.save(self.ok(8, validation_valid=True))
        result_store.save(self.ok(9, status="BLOCKED"))
        self.assertEqual(result_store.get(8).status, "PASS")
        self.assertEqual(result_store.get(9).status, "BLOCKED")
        self.assertEqual(result_store.get(8).srs_id, "[SRS8]")
        self.assertTrue(result_store.get_saved_at(8))

    def test_results_survive_restart_and_parent_dir_is_created(self):
        result_store.save(self.ok(8, provenance={"path": Path("some/where")}))
        self.assertTrue(self.path.exists())
        self.restart()
        restored = result_store.get(8)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.requirement_id, 8)

    def test_failed_run_does_not_replace_stored_success(self):
        result_store.save(self.ok(8))
        self.assertFalse(result_store.save(self.failed(8)))
        self.restart()
        self.assertEqual(result_store.get(8).status, "PASS")

    def test_failure_is_stored_when_no_success_exists_and_success_replaces_it(self):
        self.assertTrue(result_store.save(self.failed(8)))
        self.assertEqual(result_store.get(8).status, "FAILED")
        self.assertTrue(result_store.save(self.ok(8, status="MAX_ITERATIONS")))
        self.assertEqual(result_store.get(8).status, "MAX_ITERATIONS")

    def test_corrupt_file_is_preserved_and_cache_recovers(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertLogs(result_store.logger, level="ERROR"):
            self.assertIsNone(result_store.get(8))
        self.assertTrue(self.path.with_suffix(".corrupt.json").exists())
        result_store.save(self.ok(8))
        self.restart()
        self.assertEqual(result_store.get(8).status, "PASS")

    def test_wrong_top_level_type_is_ignored(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("[1, 2]", encoding="utf-8")
        with self.assertLogs(result_store.logger, level="ERROR"):
            self.assertIsNone(result_store.get(8))

    def test_entry_from_incompatible_schema_is_ignored(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"8": {"saved_at": "x", "result": {"bogus": 1}}}), encoding="utf-8")
        with self.assertLogs(result_store.logger, level="ERROR"):
            self.assertIsNone(result_store.get(8))


class TestModelConfig(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "cfg" / "model_config.json"
        patcher = patch.object(model_config, "CONFIG_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_missing_file_gives_defaults(self):
        self.assertEqual(model_config.load_model_config(), model_config.DEFAULT_MODELS)

    def test_save_creates_directory_and_roundtrips_independent_roles(self):
        chosen = {"analyst": "a:1", "reasoning": "r:2", "critic": "c:3"}
        model_config.save_model_config(chosen)
        self.assertTrue(self.path.exists())
        self.assertEqual(model_config.load_model_config(), chosen)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), chosen)

    def test_whitespace_is_stripped(self):
        model_config.save_model_config({"analyst": " a:1 ", "reasoning": "r", "critic": "c"})
        self.assertEqual(model_config.load_model_config()["analyst"], "a:1")

    def test_corrupt_file_falls_back_to_defaults(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{oops", encoding="utf-8")
        self.assertEqual(model_config.load_model_config(), model_config.DEFAULT_MODELS)

    def test_non_object_json_falls_back_to_defaults(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("[1, 2]", encoding="utf-8")
        self.assertEqual(model_config.load_model_config(), model_config.DEFAULT_MODELS)

    def test_incomplete_or_invalid_values_fall_back_per_role(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"analyst": "only:1", "critic": "", "reasoning": 5}), encoding="utf-8")
        config = model_config.load_model_config()
        self.assertEqual(config["analyst"], "only:1")
        self.assertEqual(config["critic"], model_config.DEFAULT_MODELS["critic"])
        self.assertEqual(config["reasoning"], model_config.DEFAULT_MODELS["reasoning"])


if __name__ == "__main__":
    unittest.main()
