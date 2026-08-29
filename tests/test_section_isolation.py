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
DB_PATH = "test_section_isolation.db"


class TestSectionIsolation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Clean up database if it exists
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

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

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)

    def setUp(self):
        self.conn = get_db_connection(DB_PATH)
        self.cursor = self.conn.cursor()

    def tearDown(self):
        self.conn.close()

    def get_section_elements(self, section_num):
        """Helper to get elements in a section based on subtree boundary logic."""
        # 1. Get selected section
        self.cursor.execute("SELECT * FROM sections WHERE document_id = ? AND number = ?;", (self.doc_id, section_num))
        selected_section = self.cursor.fetchone()
        if not selected_section:
            return [], []

        start_index = selected_section["element_index"]

        # 2. Get all sections
        self.cursor.execute("SELECT number, element_index FROM sections WHERE document_id = ?;", (self.doc_id,))
        all_secs = self.cursor.fetchall()

        selected_prefix = section_num + "."
        next_sibling_index = None

        for sec in all_secs:
            sec_num = sec["number"]
            sec_idx = sec["element_index"]
            if sec_idx > start_index:
                # Find the next section that is NOT a descendant (e.g. sibling or parent's sibling)
                if not sec_num.startswith(selected_prefix):
                    if next_sibling_index is None or sec_idx < next_sibling_index:
                        next_sibling_index = sec_idx

        if next_sibling_index is None:
            # Reconstruct to the end of elements
            self.cursor.execute("SELECT COUNT(*) FROM elements WHERE document_id = ?;", (self.doc_id,))
            end_index = self.cursor.fetchone()[0]
        else:
            end_index = next_sibling_index

        # 3. Query elements
        self.cursor.execute(
            "SELECT * FROM elements WHERE document_id = ? AND element_index >= ? AND element_index < ? ORDER BY element_index;",
            (self.doc_id, start_index, end_index)
        )
        elements = [dict(el) for el in self.cursor.fetchall()]

        # 4. Fetch requirements in this range
        self.cursor.execute(
            "SELECT * FROM requirements WHERE document_id = ? AND element_index >= ? AND element_index < ? ORDER BY element_index;",
            (self.doc_id, start_index, end_index)
        )
        section_requirements = [dict(r) for r in self.cursor.fetchall()]

        # Mark starts and continuations
        req_by_start_idx = {r["element_index"]: r for r in section_requirements}
        sorted_reqs = sorted(section_requirements, key=lambda r: r["element_index"])
        
        continuation_indices = set()
        for i, req in enumerate(sorted_reqs):
            s_idx = req["element_index"]
            if i + 1 < len(sorted_reqs):
                n_start_idx = sorted_reqs[i+1]["element_index"]
            else:
                n_start_idx = end_index
            for idx in range(s_idx + 1, n_start_idx):
                continuation_indices.add(idx)

        for el in elements:
            idx = el["element_index"]
            if idx in req_by_start_idx:
                el["classification"] = "requirement"
                el["requirement_info"] = req_by_start_idx[idx]
                el["is_continuation"] = False
            elif idx in continuation_indices:
                el["is_continuation"] = True
            else:
                el["is_continuation"] = False

        return elements, section_requirements

    def test_section_321_isolation(self):
        """Selecting 3.2.1 must return its 17 requirements and must not contain content from 3.2.2."""
        elements, section_requirements = self.get_section_elements("3.2.1")
        
        # Verify the reconstructed section begins at the correct section heading
        self.assertEqual(elements[0]["raw_text"].strip(), "3.2.1 System Initialization")
        
        # Check requirement count in elements
        req_elements = [el for el in elements if el["classification"] == "requirement"]
        self.assertEqual(len(req_elements), 17)

        # Check that no element from before section 3.2.1 is present
        # Section 3.2 is at element index 624. 3.2.1 starts at 625.
        for el in elements:
            self.assertGreaterEqual(el["element_index"], 625)

        # Check that no element from Section 3.2.2 is present
        # Section 3.2.2 starts at element index 674.
        for el in elements:
            self.assertLess(el["element_index"], 674)
            self.assertNotIn("3.2.2 Scheduling Services", el["raw_text"])

    def test_section_3221_isolation(self):
        """Selecting 3.2.2.1 must return its requirements and terminate before 3.2.2.2."""
        elements, section_requirements = self.get_section_elements("3.2.2.1")
        
        # Section 3.2.2.1 starts at element index 675.
        self.assertEqual(elements[0]["raw_text"].strip(), "3.2.2.1 Scheduling Execution")
        
        # Section 3.2.2.2 starts at element index 743.
        for el in elements:
            self.assertGreaterEqual(el["element_index"], 675)
            self.assertLess(el["element_index"], 743)
            self.assertNotIn("3.2.2.2 Task and Rate Group Execution", el["raw_text"])

    def test_no_bleeding_from_cover_or_TOC(self):
        """Elements from cover page, revision history or TOC must not appear in section content."""
        # Query any section, e.g. 3.2.1
        elements, section_requirements = self.get_section_elements("3.2.1")
        
        for el in elements:
            # Reconstructed section must begin at the correct section heading or after
            self.assertNotIn("TABLE OF CONTENTS", el["raw_text"].upper())
            self.assertNotIn("NASA COOPERATIVE AGREEMENT", el["raw_text"].upper())

    def test_r1_r2_continuation_handling(self):
        """Verify R1 and R2 span continuation elements are marked properly, and contain full sentences."""
        elements, section_requirements = self.get_section_elements("3.2.1")
        
        # Map element_index to element dict for O(1) checks
        el_by_idx = {el["element_index"]: el for el in elements}
        
        # 1. R1 spans elements 629 and 630.
        # Element 629 should start the requirement
        r1_start = el_by_idx[629]
        self.assertEqual(r1_start["classification"], "requirement")
        self.assertFalse(r1_start["is_continuation"])
        # Reconstructed text contains the complete sentence
        self.assertIn("Whenever a power-on reset occurs, System Initialization shall [SRS194] perform the following functions.", r1_start["requirement_info"]["normalized_text"])
        
        # Element 630 is the continuation, so it must be marked as is_continuation = True
        r1_cont = el_by_idx[630]
        self.assertTrue(r1_cont["is_continuation"])
        
        # 2. R2 spans elements 631, 632, 633, and 634.
        # Element 631 should start the requirement
        r2_start = el_by_idx[631]
        self.assertEqual(r2_start["classification"], "requirement")
        self.assertFalse(r2_start["is_continuation"])
        self.assertIn("As part of System Initialization , the Boot ROM shall [SRS234] be configured to, after completing IBIT, call the manufacturer-supplied VxWorks Board Support Package (BSP) initialization software followed by a call to the FTSS System Initialization software.", r2_start["requirement_info"]["normalized_text"])
        
        # Elements 632, 633, 634 must be marked as is_continuation = True
        self.assertTrue(el_by_idx[632]["is_continuation"])
        self.assertTrue(el_by_idx[633]["is_continuation"])
        self.assertTrue(el_by_idx[634]["is_continuation"])


if __name__ == "__main__":
    unittest.main()
