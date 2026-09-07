import json
import shutil
import tempfile
import unittest
from pathlib import Path

from app.retrieval.obsidian_retriever import (
    ObsidianRetriever,
    InvalidRegistryError,
    MissingKnowledgeFileError,
    RegistryNotFoundError,
    UnknownPatternError,
    UnsafePathError,
    VaultNotFoundError,
)


class TestObsidianRetriever(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.vault_root = self.project_root / "SRS-Knowledge"
        self.retriever = ObsidianRetriever(vault_root=self.vault_root)

    def test_1_registry_loads_successfully(self):
        """1. Registry loads successfully."""
        self.assertIsInstance(self.retriever.registry, dict)
        self.assertEqual(len(self.retriever.registry), 21)

    def test_2_exact_pattern_lookup(self):
        """2. Exact pattern lookup works."""
        result = self.retriever.retrieve_patterns(["Timeout / Deadline"])
        self.assertEqual(len(result.pattern_items), 1)
        item = result.pattern_items[0]
        self.assertEqual(item.requested_pattern, "Timeout / Deadline")
        self.assertEqual(item.pattern_id, "pat-timeout-deadline")

    def test_3_unknown_pattern_produces_error(self):
        """3. Unknown or fuzzy pattern produces a clear UnknownPatternError."""
        with self.assertRaises(UnknownPatternError):
            self.retriever.retrieve_patterns(["timeout"])

        with self.assertRaises(UnknownPatternError):
            self.retriever.retrieve_patterns(["NonExistentPattern"])

    def test_4_pattern_note_retrieved(self):
        """4. Pattern note is retrieved with correct content and path."""
        result = self.retriever.retrieve_patterns(["Timeout / Deadline"])
        item = result.pattern_items[0]
        self.assertEqual(item.pattern_file_path, "Patterns/pat-timeout-deadline.md")
        self.assertIn("# Timeout / Deadline", item.pattern_note.content)

    def test_5_formalization_note_retrieved(self):
        """5. Formalization note is retrieved with correct content and path."""
        result = self.retriever.retrieve_patterns(["Timeout / Deadline"])
        item = result.pattern_items[0]
        self.assertTrue(len(item.formalization_notes) >= 1)
        form_paths = [fn.file_path for fn in item.formalization_notes]
        self.assertIn("Formalization/form-timed-ltl-rules.md", form_paths)

    def test_6_concept_note_retrieved(self):
        """6. Concept note is retrieved with correct content and path."""
        result = self.retriever.retrieve_patterns(["Timeout / Deadline"])
        item = result.pattern_items[0]
        self.assertTrue(len(item.concept_notes) >= 1)
        concept_paths = [cn.file_path for cn in item.concept_notes]
        self.assertIn("Concepts/concept-watchdog-timers.md", concept_paths)

    def test_7_multiple_patterns_preserve_input_order(self):
        """7. Multiple patterns preserve input order."""
        input_patterns = ["Failure Handling", "Timeout / Deadline", "Trigger -> Action"]
        result = self.retriever.retrieve_patterns(input_patterns)
        output_patterns = [item.requested_pattern for item in result.pattern_items]
        self.assertEqual(output_patterns, input_patterns)

    def test_8_shared_notes_cache_hits(self):
        """8. Shared notes are not redundantly read from filesystem (read cache hits)."""
        input_patterns = ["Timeout / Deadline", "Bounded Waiting"]
        result = self.retriever.retrieve_patterns(input_patterns)
        self.assertTrue(result.read_cache_hits >= 1)

    def test_9_missing_referenced_file_error(self):
        """9. Missing referenced file produces a clear MissingKnowledgeFileError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_vault = Path(temp_dir)
            index_dir = temp_vault / "Index"
            index_dir.mkdir(parents=True)

            registry_data = {
                "Test Pattern": {
                    "id": "pat-test",
                    "pattern_file": "Patterns/missing-file.md",
                    "formalization_notes": [],
                    "concept_notes": [],
                }
            }

            with open(index_dir / "Pattern-Registry.json", "w", encoding="utf-8") as f:
                json.dump(registry_data, f)

            temp_retriever = ObsidianRetriever(vault_root=temp_vault)
            with self.assertRaises(MissingKnowledgeFileError):
                temp_retriever.retrieve_patterns(["Test Pattern"])

    def test_10_unsafe_registry_path_rejected(self):
        """10. Unsafe registry path (absolute or path traversal) is rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_vault = Path(temp_dir)
            index_dir = temp_vault / "Index"
            index_dir.mkdir(parents=True)

            registry_data = {
                "Unsafe Pattern": {
                    "id": "pat-unsafe",
                    "pattern_file": "../outside-vault.md",
                    "formalization_notes": [],
                    "concept_notes": [],
                }
            }

            with open(index_dir / "Pattern-Registry.json", "w", encoding="utf-8") as f:
                json.dump(registry_data, f)

            with self.assertRaises(UnsafePathError):
                ObsidianRetriever(vault_root=temp_vault)

    def test_11_temp_vault_fixture(self):
        """11. Retrieval works with an isolated temporary vault fixture."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_vault = Path(temp_dir)
            (temp_vault / "Index").mkdir(parents=True)
            (temp_vault / "Patterns").mkdir(parents=True)
            (temp_vault / "Formalization").mkdir(parents=True)
            (temp_vault / "Concepts").mkdir(parents=True)

            registry_data = {
                "Fixture Pattern": {
                    "id": "pat-fixture",
                    "pattern_file": "Patterns/pat-fixture.md",
                    "formalization_notes": ["Formalization/form-fixture.md"],
                    "concept_notes": ["Concepts/concept-fixture.md"],
                }
            }

            with open(temp_vault / "Index" / "Pattern-Registry.json", "w", encoding="utf-8") as f:
                json.dump(registry_data, f)

            (temp_vault / "Patterns" / "pat-fixture.md").write_text("# Fixture Pattern", encoding="utf-8")
            (temp_vault / "Formalization" / "form-fixture.md").write_text("# Fixture Formalization", encoding="utf-8")
            (temp_vault / "Concepts" / "concept-fixture.md").write_text("# Fixture Concept", encoding="utf-8")

            fixture_retriever = ObsidianRetriever(vault_root=temp_vault)
            res = fixture_retriever.retrieve_patterns(["Fixture Pattern"])
            self.assertEqual(len(res.pattern_items), 1)
            item = res.pattern_items[0]
            self.assertEqual(item.pattern_note.content, "# Fixture Pattern")
            self.assertEqual(item.formalization_notes[0].content, "# Fixture Formalization")
            self.assertEqual(item.concept_notes[0].content, "# Fixture Concept")

    def test_12_real_vault_integration(self):
        """12. Real-vault integration test for ["Timeout / Deadline", "Failure Handling", "Component Interaction"]."""
        input_patterns = ["Timeout / Deadline", "Failure Handling", "Component Interaction"]
        res = self.retriever.retrieve_patterns(input_patterns)
        self.assertEqual(len(res.pattern_items), 3)

        retrieved_names = [item.requested_pattern for item in res.pattern_items]
        self.assertEqual(retrieved_names, input_patterns)

        # Verify expected files returned
        item0 = res.pattern_items[0]  # Timeout / Deadline
        self.assertEqual(item0.pattern_file_path, "Patterns/pat-timeout-deadline.md")

        item1 = res.pattern_items[1]  # Failure Handling
        self.assertEqual(item1.pattern_file_path, "Patterns/pat-failure-handling.md")

        item2 = res.pattern_items[2]  # Component Interaction
        self.assertEqual(item2.pattern_file_path, "Patterns/pat-component-interaction.md")

    def test_13_shared_formalization_knowledge(self):
        """13. Shared formalization knowledge resolves without duplicate reads."""
        input_patterns = ["Timeout / Deadline", "Bounded Waiting"]
        res = self.retriever.retrieve_patterns(input_patterns)
        self.assertEqual(len(res.pattern_items), 2)

        item1_form_paths = [fn.file_path for fn in res.pattern_items[0].formalization_notes]
        item2_form_paths = [fn.file_path for fn in res.pattern_items[1].formalization_notes]

        shared_file = "Formalization/form-timed-ltl-rules.md"
        self.assertIn(shared_file, item1_form_paths)
        self.assertIn(shared_file, item2_form_paths)
        self.assertTrue(res.read_cache_hits >= 1)


if __name__ == "__main__":
    unittest.main()
