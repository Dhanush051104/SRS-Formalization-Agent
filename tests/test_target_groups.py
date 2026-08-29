import unittest
import sqlite3
import os
import sys
from pathlib import Path

# Add root folder to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from app.parser.document_parser import parse_document
from app.structurer.requirement_segmenter import RequirementSegmenter
from app.structurer.document_cleaner import DocumentCleaner
from app.structurer.document_structurer import DocumentStructurer
from app.db.canonical_store import store_srs, get_db_connection, init_db
from app.db.target_service import (
    create_target_group,
    get_target_group,
    add_requirement_to_group,
    remove_requirement_from_group,
    cancel_target_group
)

PDF_PATH = "data/nasaX38 SRS.pdf"
DB_PATH = "test_target_groups.db"


class TestTargetGroups(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Clean up database if it exists
        if os.path.exists(DB_PATH):
            try:
                os.remove(DB_PATH)
            except Exception:
                pass

        # Initialize test DB
        init_db(DB_PATH)

        # Ingest document
        cls.elements = parse_document(PDF_PATH)
        segmenter = RequirementSegmenter()
        cls.raw_requirements = segmenter.segment(cls.elements)
        cleaner = DocumentCleaner()
        cls.requirements = [cleaner.clean_requirement(r) for r in cls.raw_requirements]
        structurer = DocumentStructurer(cls.elements)
        cls.structured_doc = structurer.build()
        cls.structured_doc = structurer.add_requirements(cls.structured_doc, cls.requirements)
        
        cls.doc_id = store_srs(
            DB_PATH,
            filename=os.path.basename(PDF_PATH),
            filepath=PDF_PATH,
            parsed_elements=cls.elements,
            structured_doc=cls.structured_doc,
            segmented_requirements=cls.requirements
        )

        # Let's create a second document in the DB to test cross-document validations
        conn = get_db_connection(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO documents (filename, filepath, uploaded_at) VALUES ('other.pdf', 'other.pdf', '2026-08-28T20:00:00');"
            )
            cls.other_doc_id = cursor.lastrowid
            
            # Add a section and requirement to the second document
            cursor.execute(
                "INSERT INTO sections (document_id, number, title, page_number, parent_number, element_index) VALUES (?, '1', 'SCOPE', 1, NULL, 0);",
                (cls.other_doc_id,)
            )
            cls.other_section_id = cursor.lastrowid
            
            cursor.execute(
                """
                INSERT INTO requirements (document_id, section_id, section_number, srs_id, global_number, source_number, raw_text, normalized_text, page_number, element_index)
                VALUES (?, ?, '1', '[SRS999]', 1, 1, 'Raw Text', 'Normalized Text', 1, 0);
                """,
                (cls.other_doc_id, cls.other_section_id)
            )
            cls.other_req_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def tearDownClass(cls):
        # We try to clean up but ignore lock errors in teardown; the next run's setUpClass will also clean it
        if os.path.exists(DB_PATH):
            try:
                os.remove(DB_PATH)
            except Exception:
                pass

    def setUp(self):
        self.conn = get_db_connection(DB_PATH)
        self.cursor = self.conn.cursor()

    def tearDown(self):
        self.conn.close()

    def get_reqs_for_321(self):
        """Helper to get requirement records for section 3.2.1."""
        conn = get_db_connection(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM requirements WHERE document_id = ? AND section_number = '3.2.1' ORDER BY global_number ASC;",
                (self.doc_id,)
            )
            rows = [dict(r) for r in cursor.fetchall()]
            return rows
        finally:
            conn.close()

    def test_01_invalid_section_rejected(self):
        """1. Invalid section_number is rejected."""
        reqs = self.get_reqs_for_321()
        req_ids = [reqs[0]["id"]]
        
        with self.assertRaises(ValueError) as ctx:
            create_target_group(DB_PATH, self.doc_id, "9.9.9", req_ids)
        self.assertIn("Section '9.9.9' does not exist", str(ctx.exception))

    def test_02_requirement_from_another_section_rejected(self):
        """2. Requirement from another section is rejected."""
        reqs_321 = self.get_reqs_for_321()
        
        # Find a requirement from any section other than 3.2.1
        conn = get_db_connection(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, section_number FROM requirements WHERE document_id = ? AND section_number != '3.2.1' LIMIT 1;",
                (self.doc_id,)
            )
            row = cursor.fetchone()
            self.assertIsNotNone(row, "Could not find any requirements in sections other than 3.2.1")
            req_other_id = row["id"]
            req_other_sec = row["section_number"]
        finally:
            conn.close()
        
        # Creating a group for section 3.2.1 but supplying a different section's requirement ID must fail
        with self.assertRaises(ValueError) as ctx:
            create_target_group(DB_PATH, self.doc_id, "3.2.1", [reqs_321[0]["id"], req_other_id])
        self.assertIn(f"belongs to section '{req_other_sec}', expected '3.2.1'", str(ctx.exception))

    def test_03_requirement_from_another_document_rejected(self):
        """3. Requirement from another document is rejected."""
        reqs_321 = self.get_reqs_for_321()
        
        # Supplying other document's requirement ID must fail
        with self.assertRaises(ValueError) as ctx:
            create_target_group(DB_PATH, self.doc_id, "3.2.1", [reqs_321[0]["id"], self.other_req_id])
        self.assertIn("does not belong to document", str(ctx.exception))

    def test_04_duplicate_requirement_ids_rejected(self):
        """4. Duplicate requirement IDs are rejected in input selection."""
        reqs_321 = self.get_reqs_for_321()
        r_id = reqs_321[0]["id"]
        
        with self.assertRaises(ValueError) as ctx:
            create_target_group(DB_PATH, self.doc_id, "3.2.1", [r_id, r_id])
        self.assertIn("Duplicate requirement IDs are not allowed", str(ctx.exception))

    def test_05_database_level_uniqueness_constraint(self):
        """5. Database-level UNIQUE constraint prevents duplicate target group membership."""
        reqs_321 = self.get_reqs_for_321()
        r1_id = reqs_321[0]["id"]
        r2_id = reqs_321[1]["id"]
        
        # Create valid group
        group_id = create_target_group(DB_PATH, self.doc_id, "3.2.1", [r1_id, r2_id])
        
        # Attempting to directly insert a duplicate membership into the DB table must raise sqlite3.IntegrityError
        conn = get_db_connection(DB_PATH)
        try:
            cursor = conn.cursor()
            with self.assertRaises(sqlite3.IntegrityError):
                cursor.execute(
                    "INSERT INTO target_group_members (target_group_id, requirement_id, selection_order) VALUES (?, ?, 3);",
                    (group_id, r1_id)
                )
        finally:
            conn.close()

    def test_06_single_requirement_group_works(self):
        """6. Target group with a single requirement works."""
        reqs_321 = self.get_reqs_for_321()
        r_id = reqs_321[0]["id"]
        
        group_id = create_target_group(DB_PATH, self.doc_id, "3.2.1", [r_id])
        group = get_target_group(DB_PATH, group_id)
        
        self.assertIsNotNone(group)
        self.assertEqual(len(group["requirements"]), 1)
        self.assertEqual(group["requirements"][0]["id"], r_id)
        self.assertEqual(group["requirements"][0]["selection_order"], 1)

    def test_07_multiple_requirement_group_works(self):
        """7. Target group with multiple requirements works."""
        reqs_321 = self.get_reqs_for_321()
        r_ids = [reqs_321[0]["id"], reqs_321[1]["id"], reqs_321[2]["id"]]
        
        group_id = create_target_group(DB_PATH, self.doc_id, "3.2.1", r_ids)
        group = get_target_group(DB_PATH, group_id)
        
        self.assertIsNotNone(group)
        self.assertEqual(len(group["requirements"]), 3)
        self.assertEqual([r["id"] for r in group["requirements"]], r_ids)

    def test_08_selection_order_is_preserved(self):
        """8. Target group preserves the selection order of requirements (e.g. reverse order)."""
        reqs_321 = self.get_reqs_for_321()
        # Pass requirements in reverse order: R3, then R2, then R1
        r_ids = [reqs_321[2]["id"], reqs_321[1]["id"], reqs_321[0]["id"]]
        
        group_id = create_target_group(DB_PATH, self.doc_id, "3.2.1", r_ids)
        group = get_target_group(DB_PATH, group_id)
        
        self.assertEqual([r["id"] for r in group["requirements"]], r_ids)
        self.assertEqual(group["requirements"][0]["selection_order"], 1)
        self.assertEqual(group["requirements"][1]["selection_order"], 2)
        self.assertEqual(group["requirements"][2]["selection_order"], 3)

    def test_09_removing_requirement_reindexes_selection_order(self):
        """9. Removing a requirement re-indexes selection_order for remaining members."""
        reqs_321 = self.get_reqs_for_321()
        r_ids = [reqs_321[0]["id"], reqs_321[1]["id"], reqs_321[2]["id"]]
        
        group_id = create_target_group(DB_PATH, self.doc_id, "3.2.1", r_ids)
        
        # Remove middle requirement (R2)
        remove_requirement_from_group(DB_PATH, group_id, reqs_321[1]["id"])
        
        group = get_target_group(DB_PATH, group_id)
        self.assertEqual(len(group["requirements"]), 2)
        self.assertEqual(group["requirements"][0]["id"], reqs_321[0]["id"])
        self.assertEqual(group["requirements"][0]["selection_order"], 1)
        self.assertEqual(group["requirements"][1]["id"], reqs_321[2]["id"])
        self.assertEqual(group["requirements"][1]["selection_order"], 2)

    def test_10_removing_final_requirement_deletes_group(self):
        """10. Removing the final requirement deletes the target group entirely."""
        reqs_321 = self.get_reqs_for_321()
        r_id = reqs_321[0]["id"]
        
        group_id = create_target_group(DB_PATH, self.doc_id, "3.2.1", [r_id])
        
        # Remove the last requirement
        remove_requirement_from_group(DB_PATH, group_id, r_id)
        
        group = get_target_group(DB_PATH, group_id)
        self.assertIsNone(group)

    def test_11_cancelling_group_does_not_delete_canonical_requirements(self):
        """11. Cancelling/deleting a target group does not delete or modify canonical requirements."""
        reqs_321 = self.get_reqs_for_321()
        r_ids = [reqs_321[0]["id"]]
        
        # Capture requirements count in database before cancellation
        conn = get_db_connection(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM requirements;")
            initial_count = cursor.fetchone()[0]
        finally:
            conn.close()
        
        # Create and cancel
        group_id = create_target_group(DB_PATH, self.doc_id, "3.2.1", r_ids)
        cancel_target_group(DB_PATH, group_id)
        
        # Verify group is deleted
        self.assertIsNone(get_target_group(DB_PATH, group_id))
        
        # Verify canonical requirements count is identical
        conn = get_db_connection(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM requirements;")
            after_count = cursor.fetchone()[0]
        finally:
            conn.close()
        
        self.assertEqual(initial_count, after_count)

    def test_12_canonical_requirements_records_remain_unchanged(self):
        """12. Canonical requirement records remain completely unchanged during target group operations."""
        reqs_321 = self.get_reqs_for_321()
        r_id = reqs_321[0]["id"]
        
        # Fetch initial state
        conn = get_db_connection(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM requirements WHERE id = ?;", (r_id,))
            initial_req = dict(cursor.fetchone())
        finally:
            conn.close()
        
        # Create group, add/remove members
        group_id = create_target_group(DB_PATH, self.doc_id, "3.2.1", [r_id])
        remove_requirement_from_group(DB_PATH, group_id, r_id)
        
        # Fetch current state
        conn = get_db_connection(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM requirements WHERE id = ?;", (r_id,))
            current_req = dict(cursor.fetchone())
        finally:
            conn.close()
        
        self.assertEqual(initial_req, current_req)

    def test_nasa_x38_manual_case_mock(self):
        """13. Explicitly verify creating target group for NASA X-38 Section 3.2.1 with R5, R6, R7."""
        reqs_321 = self.get_reqs_for_321()
        
        # Map requirements by global_number to find R5, R6, and R7
        req_by_global = {r["global_number"]: r for r in reqs_321}
        r5 = req_by_global[5]
        r6 = req_by_global[6]
        r7 = req_by_global[7]
        
        self.assertEqual(r5["srs_id"], "[SRS008]")
        self.assertEqual(r6["srs_id"], "[SRS010]")
        self.assertEqual(r7["srs_id"], "[SRS177]")
        
        r_ids = [r5["id"], r6["id"], r7["id"]]
        
        # Create target group
        group_id = create_target_group(DB_PATH, self.doc_id, "3.2.1", r_ids)
        group = get_target_group(DB_PATH, group_id)
        
        # Assert exact requirements matched in selection order
        self.assertEqual(len(group["requirements"]), 3)
        self.assertEqual(group["requirements"][0]["id"], r5["id"])
        self.assertEqual(group["requirements"][0]["srs_id"], "[SRS008]")
        self.assertEqual(group["requirements"][1]["id"], r6["id"])
        self.assertEqual(group["requirements"][1]["srs_id"], "[SRS010]")
        self.assertEqual(group["requirements"][2]["id"], r7["id"])
        self.assertEqual(group["requirements"][2]["srs_id"], "[SRS177]")


if __name__ == "__main__":
    unittest.main()
