from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class SimpleRequirement:
    """
    Structured representation of a single requirement from the evaluation corpus.
    """
    number: int
    text: str
    domain: str


DOMAIN_MAPPINGS: List[Tuple[int, int, str]] = [
    (1, 25, "redundant computer / bus-master system"),
    (26, 49, "ventilator"),
    (50, 80, "UAV"),
    (81, 206, "washing machine"),
    (207, 224, "microwave oven"),
    (225, 234, "refrigerator"),
    (235, 274, "ADAS"),
    (275, 285, "fire safety controller"),
    (286, 296, "access control"),
    (297, 306, "elevator"),
]


class SimpleRequirementsLoader:
    """
    Lightweight structured loader for the SimpleRequirements.txt evaluation corpus.
    Provides methods to load the full ordered corpus, query requirements by number,
    and retrieve requirements grouped by domain.
    """

    def __init__(self, file_path: Optional[Path] = None) -> None:
        if file_path is None:
            file_path = Path(__file__).resolve().parent / "simple_requirements.txt"
        self.file_path = Path(file_path).resolve()
        self._requirements: Optional[List[SimpleRequirement]] = None
        self._by_number: Optional[Dict[int, SimpleRequirement]] = None

    def _get_domain_for_number(self, num: int) -> str:
        for start, end, domain in DOMAIN_MAPPINGS:
            if start <= num <= end:
                return domain
        raise ValueError(f"Requirement number {num} is outside known domain mapping ranges (1-306).")

    def load_all(self) -> List[SimpleRequirement]:
        """
        Reads and parses the complete ordered SimpleRequirements.txt corpus.

        Returns:
            List of 306 SimpleRequirement instances in exact input order.
        """
        if self._requirements is not None:
            return list(self._requirements)

        if not self.file_path.exists():
            raise FileNotFoundError(f"Corpus file not found: {self.file_path}")

        requirements: List[SimpleRequirement] = []
        by_number: Dict[int, SimpleRequirement] = {}

        with open(self.file_path, "r", encoding="utf-8") as f:
            lines = [line.rstrip("\r\n") for line in f if line.rstrip("\r\n")]

        for idx, text in enumerate(lines, start=1):
            domain = self._get_domain_for_number(idx)
            req = SimpleRequirement(
                number=idx,
                text=text,
                domain=domain,
            )
            requirements.append(req)
            by_number[idx] = req

        self._requirements = requirements
        self._by_number = by_number
        return list(self._requirements)

    def get_by_number(self, number: int) -> SimpleRequirement:
        """
        Retrieves a single requirement by 1-indexed requirement number.

        Args:
            number: Requirement number (1 to 306).

        Returns:
            SimpleRequirement instance.
        """
        if self._by_number is None:
            self.load_all()

        if number not in self._by_number:
            raise KeyError(f"Requirement number {number} not found in evaluation corpus (valid range: 1-306).")

        return self._by_number[number]

    def get_by_domain(self, domain: str) -> List[SimpleRequirement]:
        """
        Retrieves all requirements belonging to a specific domain/category.

        Args:
            domain: Category name (e.g. 'washing machine', 'UAV', 'elevator').

        Returns:
            List of SimpleRequirement instances belonging to that domain.
        """
        all_reqs = self.load_all()
        matching = [req for req in all_reqs if req.domain.lower() == domain.lower()]
        if not matching:
            valid_domains = [d[2] for d in DOMAIN_MAPPINGS]
            raise ValueError(f"Domain '{domain}' not recognized. Valid domains: {valid_domains}")
        return matching

    def get_domains(self) -> List[str]:
        """Returns the ordered list of all 10 domain names."""
        return [mapping[2] for mapping in DOMAIN_MAPPINGS]
