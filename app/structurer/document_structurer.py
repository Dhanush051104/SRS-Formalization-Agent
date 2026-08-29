import re
from typing import Optional


SECTION_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)*)\.?\s*[-–—]?\s+(.+?)\s*$"
)

SRS_PATTERN = re.compile(
    r"\[SRS\d+\]"
)


class DocumentStructurer:
    """
    Builds the hierarchical structure of the SRS.

    The Table of Contents is ignored when constructing the
    authoritative section hierarchy.

    Sections are detected from the actual document body,
    beginning at the real Section 3 REQUIREMENTS heading.

    Requirements are assigned to the most recent section that
    occurs before the requirement in the actual document.
    """

    def __init__(self, elements: list[dict]):

        self.elements = elements

        self.sections = {}

        # Ordered:
        # [(element_index, section_number), ...]
        self.section_positions = []

    # =========================================================
    # BUILD SECTION HIERARCHY
    # =========================================================

    def build(self) -> dict:

        self.sections = {}
        self.section_positions = []

        requirements_start = (
            self._find_actual_requirements_section()
        )

        if requirements_start is None:

            print(
                "WARNING: Could not find actual "
                "Section 3 REQUIREMENTS."
            )

            return {}

        # -----------------------------------------------------
        # Backward search to locate actual Section 1 start.
        # -----------------------------------------------------
        body_start = 0
        for idx in range(requirements_start - 1, -1, -1):
            text = self.elements[idx].get("text", "").strip()
            parsed = self._parse_section_heading(text)
            if parsed and parsed["number"] == "1":
                if parsed["title"].isupper():
                    body_start = idx
                    break

        # -----------------------------------------------------
        # Scan the actual document body sequentially.
        # -----------------------------------------------------
        max_top_level = 0
        for index in range(
            body_start,
            len(self.elements)
        ):

            text = self.elements[index].get(
                "text",
                ""
            ).strip()

            if not text:
                continue

            parsed = self._parse_section_heading(
                text
            )

            if parsed is None:
                continue

            number = parsed["number"]
            title = parsed["title"]

            parts = number.split(".")
            try:
                top_level_num = int(parts[0])
            except ValueError:
                continue

            # Sequential and case checks
            if len(parts) == 1:
                # Top level section: must be uppercase and sequential
                if not title.isupper():
                    continue
                if top_level_num > max_top_level + 1:
                    continue
                max_top_level = max(max_top_level, top_level_num)
            else:
                # Subsection: top-level parent must have been registered
                if top_level_num > max_top_level:
                    continue

            # Only accept a section once.
            if number in self.sections:
                continue

            self.sections[number] = {
                "number": number,
                "title": title,
                "page": self.elements[index].get(
                    "page"
                ),
                "parent": self._get_parent(
                    number
                ),
                "children": [],
                "requirements": [],
                "_element_index": index,
            }

            self.section_positions.append(
                (
                    index,
                    number
                )
            )

        # Make absolutely sure positions are ordered.
        self.section_positions.sort(
            key=lambda item: item[0]
        )

        self._build_parent_child_relationships()

        return self._public_document()

    # =========================================================
    # FIND ACTUAL SECTION 3
    # =========================================================

    def _find_actual_requirements_section(
        self
    ) -> Optional[int]:

        candidates = []

        for index, element in enumerate(
            self.elements
        ):

            text = element.get(
                "text",
                ""
            ).strip()

            if not text:
                continue

            parsed = self._parse_section_heading(
                text
            )

            if parsed is None:
                continue

            if parsed["number"] != "3":
                continue

            if parsed["title"].strip().upper() != (
                "REQUIREMENTS"
            ):
                continue

            candidates.append(index)

        if not candidates:
            return None

        # The actual Section 3 is the occurrence that is
        # followed by real [SRSxxx] requirement content.
        for candidate in candidates:

            for look_ahead in range(
                candidate + 1,
                min(
                    candidate + 500,
                    len(self.elements)
                )
            ):

                text = self.elements[
                    look_ahead
                ].get(
                    "text",
                    ""
                )

                if SRS_PATTERN.search(text):
                    return candidate

        return candidates[-1]

    # =========================================================
    # SECTION HEADING PARSER
    # =========================================================

    @staticmethod
    def _parse_section_heading(
        text: str
    ) -> Optional[dict]:

        text = text.strip()

        # Remove TOC leader dots + page number.
        cleaned = re.sub(
            r"\.{3,}\s*\d+\s*$",
            "",
            text
        ).strip()

        match = SECTION_PATTERN.match(
            cleaned
        )

        if match is None:
            return None

        number = match.group(1)
        title = match.group(2).strip()

        # A section heading must not contain an SRS ID.
        if SRS_PATTERN.search(title):
            return None

        # Prevent long requirement paragraphs from becoming
        # section headings.
        if len(title) > 180:
            return None

        return {
            "number": number,
            "title": title,
        }

    # =========================================================
    # PARENT
    # =========================================================

    @staticmethod
    def _get_parent(
        number: str
    ) -> Optional[str]:

        parts = number.split(".")

        if len(parts) <= 1:
            return None

        return ".".join(parts[:-1])

    # =========================================================
    # PARENT / CHILD RELATIONSHIPS
    # =========================================================

    def _build_parent_child_relationships(
        self
    ):

        for number, section in self.sections.items():

            parent_number = section["parent"]

            if parent_number is None:
                continue

            parent = self.sections.get(
                parent_number
            )

            if parent is None:
                continue

            if number not in parent["children"]:

                parent["children"].append(
                    number
                )

    # =========================================================
    # ATTACH REQUIREMENTS
    # =========================================================

    def add_requirements(
        self,
        document: dict,
        requirements: list[dict]
    ) -> dict:

        if not self.section_positions:
            return document

        # -----------------------------------------------------
        # Process requirements in document order.
        # -----------------------------------------------------

        ordered_requirements = sorted(
            requirements,
            key=lambda r: (
                r.get(
                    "_element_index",
                    float("inf")
                )
            )
        )

        for requirement in ordered_requirements:

            element_index = requirement.get(
                "_element_index"
            )

            if element_index is None:
                continue

            section_number = (
                self._find_section_for_requirement(
                    element_index
                )
            )

            if section_number is None:
                continue

            section = document.get(
                section_number
            )

            if section is None:
                continue

            requirement_number = (
                self._extract_requirement_number(
                    requirement.get(
                        "text",
                        ""
                    )
                )
            )

            section["requirements"].append(
                {
                    "local_number": requirement_number,
                    "srs_id": requirement[
                        "srs_id"
                    ],
                    "text": requirement[
                        "text"
                    ],
                    "raw_text": requirement.get(
                        "raw_text"
                    ),
                    "page": requirement.get(
                        "page"
                    ),
                    "_element_index": (
                        element_index
                    ),
                }
            )

        return document

    # =========================================================
    # FIND SECTION FOR REQUIREMENT
    # =========================================================

    def _find_section_for_requirement(
        self,
        requirement_index: int
    ) -> Optional[str]:

        """
        Find the most recent section heading before
        the requirement.

        Example:

            element 625 -> 3.2.1
            element 629 -> R1

        Therefore R1 belongs to 3.2.1.

        The same applies to all later requirements until
        another actual section heading occurs.
        """

        current_section = None

        for (
            section_index,
            section_number
        ) in self.section_positions:

            if section_index > requirement_index:
                break

            current_section = section_number

        return current_section

    # =========================================================
    # REQUIREMENT NUMBER
    # =========================================================

    @staticmethod
    def _extract_requirement_number(
        text: str
    ) -> Optional[int]:

        match = re.match(
            r"^\s*(\d+)\.\s+",
            text
        )

        if match is None:
            return None

        return int(
            match.group(1)
        )

    # =========================================================
    # PUBLIC DOCUMENT
    # =========================================================

    def _public_document(self) -> dict:

        result = {}

        for number, section in self.sections.items():

            result[number] = {
                "number": section[
                    "number"
                ],
                "title": section[
                    "title"
                ],
                "page": section[
                    "page"
                ],
                "parent": section[
                    "parent"
                ],
                "children": list(
                    section[
                        "children"
                    ]
                ),
                "requirements": list(
                    section[
                        "requirements"
                    ]
                ),
                "_element_index": section["_element_index"],
            }

        return result