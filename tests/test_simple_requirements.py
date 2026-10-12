import unittest
from pathlib import Path

from tests.fixtures.simple_requirements_loader import (
    DOMAIN_MAPPINGS,
    SimpleRequirement,
    SimpleRequirementsLoader,
)


class TestSimpleRequirementsCorpus(unittest.TestCase):
    """
    Deterministic tests verifying that the SimpleRequirements.txt corpus is loaded cleanly,
    with exact numbering, text, domain grouping, and duplicate separation preserved.
    """

    def setUp(self):
        self.loader = SimpleRequirementsLoader()

    def test_all_306_requirements_loaded(self):
        reqs = self.loader.load_all()
        self.assertEqual(len(reqs), 306, f"Expected exactly 306 requirements, got {len(reqs)}")

    def test_numbering_preserved(self):
        reqs = self.loader.load_all()
        for idx, req in enumerate(reqs, start=1):
            self.assertEqual(req.number, idx, f"Requirement at index {idx} has number {req.number}")

    def test_text_preserved(self):
        reqs = self.loader.load_all()
        for req in reqs:
            self.assertTrue(isinstance(req.text, str))
            self.assertGreater(len(req.text.strip()), 0, f"Requirement {req.number} text is empty")

        # Spot check exact text for specific requirements
        req_1 = self.loader.get_by_number(1)
        self.assertEqual(req_1.text, "When the Computer boots up, the Computer shall read the Channel ID from HW.")

        req_306 = self.loader.get_by_number(306)
        self.assertEqual(
            req_306.text,
            "While in moving, if there is either an internal or external request at the next floor, the elevator shall slow down and stop at the floor.",
        )

    def test_domain_grouping_preserved(self):
        domains = self.loader.get_domains()
        self.assertEqual(len(domains), 10, "Expected 10 distinct domains")

        expected_counts = {
            "redundant computer / bus-master system": 25,
            "ventilator": 24,
            "UAV": 31,
            "washing machine": 126,
            "microwave oven": 18,
            "refrigerator": 10,
            "ADAS": 40,
            "fire safety controller": 11,
            "access control": 11,
            "elevator": 10,
        }

        total_count = 0
        for start, end, domain in DOMAIN_MAPPINGS:
            domain_reqs = self.loader.get_by_domain(domain)
            expected = expected_counts[domain]
            self.assertEqual(
                len(domain_reqs),
                expected,
                f"Domain '{domain}' expected {expected} requirements, got {len(domain_reqs)}",
            )
            # Verify boundary numbers
            self.assertEqual(domain_reqs[0].number, start)
            self.assertEqual(domain_reqs[-1].number, end)
            total_count += len(domain_reqs)

        self.assertEqual(total_count, 306)

    def test_duplicate_and_near_duplicate_requirements_remain_separate(self):
        # Requirements 84 and 85 are near-duplicates
        req_84 = self.loader.get_by_number(84)
        req_85 = self.loader.get_by_number(85)
        self.assertNotEqual(req_84.number, req_85.number)
        self.assertIsNot(req_84, req_85)
        self.assertEqual(req_84.number, 84)
        self.assertEqual(req_85.number, 85)

        # Requirements 24 and 25 are near-duplicates
        req_24 = self.loader.get_by_number(24)
        req_25 = self.loader.get_by_number(25)
        self.assertNotEqual(req_24.number, req_25.number)
        self.assertIsNot(req_24, req_25)
        self.assertEqual(
            req_24.text,
            "If the Active Computer fails, the Standby Computer shall take over as Active Computer.",
        )
        self.assertEqual(
            req_25.text,
            "If the Active Computer fails, the Standby Computer shall assume the role of Active Computer.",
        )

    def test_arbitrary_requirement_selection(self):
        numbers_to_test = [1, 26, 50, 81, 84, 85, 207, 225, 235, 275, 286, 297, 306]
        for num in numbers_to_test:
            req = self.loader.get_by_number(num)
            self.assertIsInstance(req, SimpleRequirement)
            self.assertEqual(req.number, num)
            self.assertTrue(len(req.text) > 0)
            self.assertTrue(len(req.domain) > 0)

    def test_invalid_requirement_number(self):
        with self.assertRaises(KeyError):
            self.loader.get_by_number(0)

        with self.assertRaises(KeyError):
            self.loader.get_by_number(307)


if __name__ == "__main__":
    unittest.main()
