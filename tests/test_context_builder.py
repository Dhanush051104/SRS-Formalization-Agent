import unittest
from pathlib import Path

from app.retrieval.context_builder import ContextBuilder, ContextPackage
from app.retrieval.obsidian_retriever import (
    ObsidianRetriever,
    UnknownPatternError,
)
from app.retrieval.sqlite_retriever import (
    RequirementNotFoundError,
    SQLiteRetriever,
)


class TestContextBuilder(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.db_path = self.project_root / "srs_canonical.db"
        self.vault_root = self.project_root / "SRS-Knowledge"

        self.sqlite_retriever = SQLiteRetriever(db_path=self.db_path)
        self.obsidian_retriever = ObsidianRetriever(vault_root=self.vault_root)
        self.builder = ContextBuilder(
            sqlite_retriever=self.sqlite_retriever,
            obsidian_retriever=self.obsidian_retriever,
        )

    def test_1_build_context_package_r8(self):
        """1. Build context package for R8 and verify requirements and patterns are present."""
        req_ids = [8]
        pattern_names = [
            "Timeout / Deadline",
            "Bounded Waiting",
            "Failure Handling",
            "Component Interaction",
            "Cross-Requirement Dependency",
        ]

        pkg = self.builder.build(requirement_ids=req_ids, pattern_names=pattern_names)
        self.assertIsInstance(pkg, ContextPackage)
        self.assertEqual(len(pkg.requirements), 1)
        self.assertEqual(pkg.requirements[0].requirement_id, 8)
        self.assertEqual(pkg.requirements[0].srs_id, "[SRS178]")
        self.assertEqual(pkg.identified_patterns, pattern_names)

    def test_2_verify_all_five_patterns_in_obsidian_knowledge(self):
        """2. Verify all five requested patterns are present in obsidian_knowledge."""
        pattern_names = [
            "Timeout / Deadline",
            "Bounded Waiting",
            "Failure Handling",
            "Component Interaction",
            "Cross-Requirement Dependency",
        ]
        pkg = self.builder.build(requirement_ids=[8], pattern_names=pattern_names)
        retrieved_patterns = [item.requested_pattern for item in pkg.obsidian_knowledge.pattern_items]
        self.assertEqual(retrieved_patterns, pattern_names)

    def test_3_verify_obsidian_knowledge_contents(self):
        """3. Verify pattern note, formalization notes, and concept notes are present."""
        pkg = self.builder.build(
            requirement_ids=[8],
            pattern_names=["Timeout / Deadline", "Failure Handling"],
        )

        item0 = pkg.obsidian_knowledge.pattern_items[0]
        self.assertEqual(item0.pattern_file_path, "Patterns/pat-timeout-deadline.md")
        self.assertIn("# Timeout / Deadline", item0.pattern_note.content)
        self.assertTrue(len(item0.formalization_notes) >= 1)
        self.assertTrue(len(item0.concept_notes) >= 1)

    def test_4_verify_provenance_structure(self):
        """4. Verify provenance structure and source file paths."""
        pkg = self.builder.build(
            requirement_ids=[8],
            pattern_names=["Timeout / Deadline"],
        )
        self.assertIn("sqlite", pkg.provenance)
        self.assertIn("obsidian", pkg.provenance)

        self.assertEqual(pkg.provenance["sqlite"]["source"], "SQLite")
        self.assertEqual(pkg.provenance["sqlite"]["requirement_ids"], [8])

        self.assertEqual(pkg.provenance["obsidian"]["source"], "Obsidian")
        self.assertIn("Patterns/pat-timeout-deadline.md", pkg.provenance["obsidian"]["retrieved_file_paths"])

    def test_5_verify_pattern_input_order_preserved(self):
        """5. Verify pattern input order is preserved."""
        input_patterns = [
            "Cross-Requirement Dependency",
            "Component Interaction",
            "Timeout / Deadline",
        ]
        pkg = self.builder.build(requirement_ids=[8], pattern_names=input_patterns)
        retrieved_patterns = [item.requested_pattern for item in pkg.obsidian_knowledge.pattern_items]
        self.assertEqual(retrieved_patterns, input_patterns)

    def test_6_verify_requirement_input_order_preserved(self):
        """6. Verify requirement input order is preserved."""
        input_ids = [15, 8, 1, 17]
        pkg = self.builder.build(
            requirement_ids=input_ids,
            pattern_names=["Timeout / Deadline"],
        )
        output_ids = [r.requirement_id for r in pkg.requirements]
        self.assertEqual(output_ids, input_ids)

    def test_7_unknown_pattern_propagates_error(self):
        """7. Verify unknown pattern propagates UnknownPatternError from ObsidianRetriever."""
        with self.assertRaises(UnknownPatternError):
            self.builder.build(requirement_ids=[8], pattern_names=["UnknownPattern"])

    def test_8_missing_requirement_propagates_error(self):
        """8. Verify missing requirement ID propagates RequirementNotFoundError from SQLiteRetriever."""
        with self.assertRaises(RequirementNotFoundError):
            self.builder.build(requirement_ids=[9999], pattern_names=["Timeout / Deadline"])

    def test_9_end_to_end_r8_context_package(self):
        """9. Primary end-to-end integration test for R8 with five specified patterns."""
        req_ids = [8]
        pattern_names = [
            "Timeout / Deadline",
            "Bounded Waiting",
            "Failure Handling",
            "Component Interaction",
            "Cross-Requirement Dependency",
        ]

        pkg = self.builder.build(requirement_ids=req_ids, pattern_names=pattern_names)

        # 1. CANONICAL SRS Verification
        self.assertEqual(len(pkg.requirements), 1)
        r8 = pkg.requirements[0]
        self.assertEqual(r8.requirement_id, 8)
        self.assertEqual(r8.global_number, 8)
        self.assertEqual(r8.source_number, 8)
        self.assertEqual(r8.srs_id, "[SRS178]")
        self.assertEqual(r8.section_number, "3.2.1")
        self.assertEqual(r8.section_title, "System Initialization")
        expected_text = (
            "8. If the failed FCP processor has not synced in 2.5 seconds after the surviving triplex "
            "has detected the loss of the FCP, then the surviving triplex shall [SRS178], within 1 second, "
            "send a single voted VMEbus reset through the NE to the failed FCP."
        )
        self.assertEqual(r8.raw_text, expected_text)

        # 2. PATTERNS Verification
        self.assertEqual(pkg.identified_patterns, pattern_names)
        self.assertEqual(
            [item.requested_pattern for item in pkg.obsidian_knowledge.pattern_items],
            pattern_names,
        )

        # 3. OBSIDIAN KNOWLEDGE Verification
        item_map = {item.requested_pattern: item for item in pkg.obsidian_knowledge.pattern_items}
        self.assertEqual(item_map["Timeout / Deadline"].pattern_file_path, "Patterns/pat-timeout-deadline.md")
        self.assertEqual(item_map["Bounded Waiting"].pattern_file_path, "Patterns/pat-bounded-waiting.md")
        self.assertEqual(item_map["Failure Handling"].pattern_file_path, "Patterns/pat-failure-handling.md")
        self.assertEqual(item_map["Component Interaction"].pattern_file_path, "Patterns/pat-component-interaction.md")
        self.assertEqual(item_map["Cross-Requirement Dependency"].pattern_file_path, "Patterns/pat-cross-req-dependency.md")

        # 4. PROVENANCE Verification
        self.assertEqual(pkg.provenance["sqlite"]["source"], "SQLite")
        self.assertIn("srs_canonical.db", pkg.provenance["sqlite"]["db_path"])
        self.assertEqual(pkg.provenance["obsidian"]["source"], "Obsidian")
        self.assertIn("Patterns/pat-timeout-deadline.md", pkg.provenance["obsidian"]["retrieved_file_paths"])
        self.assertIn("Formalization/form-timed-ltl-rules.md", pkg.provenance["obsidian"]["retrieved_file_paths"])
        self.assertIn("Concepts/concept-watchdog-timers.md", pkg.provenance["obsidian"]["retrieved_file_paths"])


if __name__ == "__main__":
    unittest.main()
