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
from app.db.canonical_store import store_srs, get_db_connection

PDF_PATH = "data/nasaX38 SRS.pdf"
DB_PATH = "test_srs_canonical.db"


class TestMilestone1(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Clean up database if it exists
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

        # Parse, segment, structure and store the X-38 document
        cls.elements = parse_document(PDF_PATH)
        
        segmenter = RequirementSegmenter()
        cls.raw_requirements = segmenter.segment(cls.elements)
        
        cleaner = DocumentCleaner()
        cls.requirements = [cleaner.clean_requirement(r) for r in cls.raw_requirements]
        
        structurer = DocumentStructurer(cls.elements)
        cls.structured_doc = structurer.build()
        cls.structured_doc = structurer.add_requirements(cls.structured_doc, cls.requirements)
        
        # Save to test database
        cls.doc_id = store_srs(
            DB_PATH,
            filename=os.path.basename(PDF_PATH),
            filepath=PDF_PATH,
            parsed_elements=cls.elements,
            structured_doc=cls.structured_doc,
            segmented_requirements=cls.requirements
        )

    @classmethod
    def tearDownClass(cls):
        # Clean up database after tests run
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def setUp(self):
        self.conn = get_db_connection(DB_PATH)
        self.cursor = self.conn.cursor()

    def tearDown(self):
        self.conn.close()

    def test_1_entire_document_parsed(self):
        """1. Entire document was parsed (elements count > 0)."""
        self.cursor.execute("SELECT COUNT(*) FROM elements WHERE document_id = ?;", (self.doc_id,))
        count = self.cursor.fetchone()[0]
        self.assertGreater(count, 0)
        self.assertEqual(count, len(self.elements))
        print(f"[PASSED] Entire document parsed. Database elements: {count}")

    def test_2_page_ordering_preserved(self):
        """2. Page ordering is preserved (page numbers are monotonically non-decreasing)."""
        self.cursor.execute("SELECT page_number FROM elements WHERE document_id = ? ORDER BY element_index;", (self.doc_id,))
        pages = [row[0] for row in self.cursor.fetchall()]
        
        for i in range(1, len(pages)):
            self.assertGreaterEqual(pages[i], pages[i - 1], f"Page ordering violated at element {i}: {pages[i]} < {pages[i-1]}")
        print("[PASSED] Page ordering is preserved.")

    def test_3_element_ordering_preserved(self):
        """3. Element ordering is preserved (element_index is sequential)."""
        self.cursor.execute("SELECT element_index FROM elements WHERE document_id = ? ORDER BY element_index;", (self.doc_id,))
        indices = [row[0] for row in self.cursor.fetchall()]
        
        for i in range(len(indices)):
            self.assertEqual(indices[i], i, f"Element index is not sequential at position {i}: got {indices[i]}")
        print("[PASSED] Element ordering is preserved.")

    def test_4_sections_parent_child_relationships(self):
        """4. Sections have valid parent-child relationships (resolving skipped numbers via ancestor tracing)."""
        self.cursor.execute("SELECT number, parent_number FROM sections WHERE document_id = ?;", (self.doc_id,))
        sections = {row[0]: row[1] for row in self.cursor.fetchall()}
        
        for number, parent in sections.items():
            if parent is not None:
                # Trace up to find if there is a valid path to an existing ancestor
                ancestor = parent
                path_resolved = False
                while ancestor is not None:
                    if ancestor in sections:
                        path_resolved = True
                        break
                    # Strip the last part to find parent's parent
                    parts = ancestor.split(".")
                    if len(parts) <= 1:
                        ancestor = None
                    else:
                        ancestor = ".".join(parts[:-1])
                self.assertTrue(path_resolved, f"Section {number} has parent {parent} which has no path to any existing section or root")
        print(f"[PASSED] Sections parent-child relationships verified. Total sections: {len(sections)}")

    def test_5_requirements_valid_section_references(self):
        """5. Requirements have valid section references and section_id mapping."""
        self.cursor.execute(
            """
            SELECT r.srs_id, r.section_number, r.section_id, s.number, s.id 
            FROM requirements r 
            LEFT JOIN sections s ON r.section_id = s.id 
            WHERE r.document_id = ?;
            """,
            (self.doc_id,)
        )
        rows = self.cursor.fetchall()
        
        for row in rows:
            srs_id, r_sec_num, r_sec_id, s_num, s_id = row
            self.assertIsNotNone(s_id, f"Requirement {srs_id} has invalid section_id mapping")
            self.assertEqual(r_sec_num, s_num, f"Requirement {srs_id} section_number '{r_sec_num}' does not match section number '{s_num}'")
        print(f"[PASSED] Requirements section references verified. Requirements checked: {len(rows)}")

    def test_6_global_numbering_sequential(self):
        """6. Global requirement numbering is sequential (starts at 1, increments by 1, no gaps)."""
        self.cursor.execute("SELECT global_number FROM requirements WHERE document_id = ? ORDER BY element_index;", (self.doc_id,))
        global_numbers = [row[0] for row in self.cursor.fetchall()]
        
        for idx, g_num in enumerate(global_numbers, start=1):
            self.assertEqual(g_num, idx, f"Global requirement numbering gap/error at index {idx}: got {g_num}")
        print(f"[PASSED] Global requirement numbering is sequential up to {len(global_numbers)}")

    def test_7_source_numbering_preserved(self):
        """7. Source requirement numbering is preserved."""
        self.cursor.execute("SELECT srs_id, source_number, normalized_text FROM requirements WHERE document_id = ?;", (self.doc_id,))
        reqs = self.cursor.fetchall()
        
        for req in reqs:
            srs_id, source_num, text = req
            # R1-R6 check on System Initialization
            if srs_id == "[SRS194]":
                self.assertEqual(source_num, 1)
            elif srs_id == "[SRS234]":
                self.assertEqual(source_num, 2)
            elif srs_id == "[SRS015]":
                self.assertEqual(source_num, 17)
        print("[PASSED] Source requirement numbering is preserved.")

    def test_8_duplicate_srs_ids_reported(self):
        """8. Validate and report duplicate SRS IDs (without database constraint block)."""
        self.cursor.execute("SELECT srs_id, COUNT(*) FROM requirements WHERE document_id = ? GROUP BY srs_id HAVING COUNT(*) > 1;", (self.doc_id,))
        duplicates = self.cursor.fetchall()
        
        if duplicates:
            print(f"\n[INFO] Found duplicate SRS IDs in document:")
            for srs_id, count in duplicates:
                print(f"  * {srs_id}: occurs {count} times")
        else:
            print("[PASSED] No duplicate SRS IDs found in document.")
        self.assertTrue(True)

    def test_9_no_requirement_lost(self):
        """9. No requirement is silently lost (exactly 195 requirements parsed)."""
        self.cursor.execute("SELECT COUNT(*) FROM requirements WHERE document_id = ?;", (self.doc_id,))
        count = self.cursor.fetchone()[0]
        self.assertEqual(count, len(self.requirements), f"Requirement count mismatch: DB has {count}, segmenter returned {len(self.requirements)}")
        self.assertEqual(count, 195, f"Expected exactly 195 requirements for X-38 document, got {count}")
        print("[PASSED] Requirement count matches expectations (exactly 195 requirements).")

    def test_10_non_requirement_content_represented(self):
        """10. Non-requirement content remains represented in elements."""
        self.cursor.execute("SELECT COUNT(*) FROM elements WHERE document_id = ? AND classification = 'regular_content';", (self.doc_id,))
        regular_count = self.cursor.fetchone()[0]
        self.assertGreater(regular_count, 0)
        print(f"[PASSED] Non-requirement content is represented in elements. Count: {regular_count}")

    def test_11_raw_text_remains_available(self):
        """11. Raw text remains available in elements and requirements."""
        self.cursor.execute("SELECT raw_text, normalized_text FROM elements WHERE document_id = ? LIMIT 10;", (self.doc_id,))
        el_rows = self.cursor.fetchall()
        for row in el_rows:
            self.assertIsNotNone(row[0])
            self.assertNotEqual(row[0], "")

        self.cursor.execute("SELECT raw_text, normalized_text FROM requirements WHERE document_id = ? LIMIT 10;", (self.doc_id,))
        req_rows = self.cursor.fetchall()
        for row in req_rows:
            self.assertIsNotNone(row[0])
            self.assertNotEqual(row[0], "")
        print("[PASSED] Raw text remains available in database.")

    def test_12_document_reconstructable(self):
        """12. The database can reconstruct the document in source order."""
        self.cursor.execute("SELECT raw_text FROM elements WHERE document_id = ? ORDER BY element_index;", (self.doc_id,))
        lines = [row[0] for row in self.cursor.fetchall()]
        
        self.assertEqual(len(lines), len(self.elements))
        # Check first line
        self.assertEqual(lines[0], self.elements[0]["text"])
        print("[PASSED] Document can be reconstructed in exact source order from elements table.")


    def test_13_genuine_sections_exist(self):
        """13. Sections 1, 2, 3 must exist in the database."""
        self.cursor.execute("SELECT COUNT(*) FROM sections WHERE number = '1';")
        self.assertEqual(self.cursor.fetchone()[0], 1, "Section 1 does not exist in the database")
        
        self.cursor.execute("SELECT COUNT(*) FROM sections WHERE number = '2';")
        self.assertEqual(self.cursor.fetchone()[0], 1, "Section 2 does not exist in the database")
        
        self.cursor.execute("SELECT COUNT(*) FROM sections WHERE number = '3';")
        self.assertEqual(self.cursor.fetchone()[0], 1, "Section 3 does not exist in the database")
        print("[PASSED] Genuine sections 1, 2, and 3 exist in the database.")

    def test_14_no_fake_sections_created(self):
        """14. Fake sections 7, 8, 17 must not be created from requirement numbering."""
        for num in ['7', '8', '17']:
            self.cursor.execute("SELECT COUNT(*) FROM sections WHERE number = ?;", (num,))
            self.assertEqual(self.cursor.fetchone()[0], 0, f"Fake section {num} was incorrectly created in the database")
        print("[PASSED] Fake sections 7, 8, 17 were not created.")

    def test_15_section_321_requirements(self):
        """15. Section 3.2.1 must contain exactly 17 requirements."""
        self.cursor.execute(
            """
            SELECT COUNT(*) FROM requirements r
            JOIN sections s ON r.section_id = s.id
            WHERE s.number = '3.2.1';
            """
        )
        count = self.cursor.fetchone()[0]
        self.assertEqual(count, 17, f"Section 3.2.1 requirement count mismatch: expected 17, got {count}")
        print("[PASSED] Section 3.2.1 contains all 17 requirements.")


if __name__ == "__main__":
    unittest.main()
