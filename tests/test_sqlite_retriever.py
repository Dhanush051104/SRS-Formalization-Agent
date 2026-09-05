import unittest
from pathlib import Path

from app.retrieval.sqlite_retriever import (
    RequirementContext,
    RequirementNotFoundError,
    SQLiteRetriever,
)


class TestSQLiteRetriever(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parent.parent
        self.db_path = self.project_root / "srs_canonical.db"
        self.retriever = SQLiteRetriever(db_path=self.db_path)

    def test_1_retrieve_known_requirement_r8(self):
        """1. Retrieve known requirement R8 / SRS178 by ID."""
        req = self.retriever.get_requirement_by_id(8)
        self.assertIsInstance(req, RequirementContext)
        self.assertEqual(req.requirement_id, 8)
        self.assertEqual(req.global_number, 8)
        self.assertEqual(req.source_number, 8)
        self.assertEqual(req.srs_id, "[SRS178]")
        self.assertEqual(req.section_number, "3.2.1")

    def test_2_verify_canonical_requirement_text(self):
        """2. Verify canonical requirement text matches SQLite exactly."""
        req = self.retriever.get_requirement_by_id(8)
        expected_text = (
            "8. If the failed FCP processor has not synced in 2.5 seconds after the surviving triplex "
            "has detected the loss of the FCP, then the surviving triplex shall [SRS178], within 1 second, "
            "send a single voted VMEbus reset through the NE to the failed FCP."
        )
        self.assertEqual(req.raw_text, expected_text)
        self.assertEqual(req.normalized_text, expected_text)

    def test_3_missing_requirement_produces_error(self):
        """3. Verify missing requirement ID produces a clear RequirementNotFoundError."""
        with self.assertRaises(RequirementNotFoundError):
            self.retriever.get_requirement_by_id(9999)

    def test_4_srs_identifier_lookup(self):
        """4. Verify SRS identifier lookup for SRS178 and [SRS178]."""
        req1 = self.retriever.get_requirement_by_srs_id("SRS178")
        self.assertEqual(req1.global_number, 8)

        req2 = self.retriever.get_requirement_by_srs_id("[SRS178]")
        self.assertEqual(req2.global_number, 8)

    def test_5_global_number_lookup(self):
        """5. Verify lookup by global requirement number."""
        req = self.retriever.get_requirement_by_global_number(8)
        self.assertEqual(req.requirement_id, 8)
        self.assertEqual(req.srs_id, "[SRS178]")

    def test_6_multiple_requirements_preserve_input_order(self):
        """6. Verify multiple requirements preserve input order."""
        input_ids = [15, 8, 1, 17]
        reqs = self.retriever.get_requirements_by_ids(input_ids)
        output_ids = [r.requirement_id for r in reqs]
        self.assertEqual(output_ids, input_ids)

    def test_7_source_dependencies_is_empty_list(self):
        """7. Verify source_dependencies is empty list (no non-existent fields created)."""
        req = self.retriever.get_requirement_by_id(8)
        self.assertIsInstance(req.source_dependencies, list)
        self.assertEqual(len(req.source_dependencies), 0)


if __name__ == "__main__":
    unittest.main()
