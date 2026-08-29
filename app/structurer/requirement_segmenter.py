import re
from typing import Optional


# Matches:
# 1. Whenever...
# 2. As part...
# 17. System Initialization...
REQUIREMENT_START_PATTERN = re.compile(
    r"^\s*(\d+)\.\s+"
)


# Matches:
# [SRS194]
# [SRS234]
# [SRS015]
SRS_ID_PATTERN = re.compile(
    r"\[SRS\d+\]"
)


class RequirementSegmenter:
    """
    Reconstructs individual SRS requirements from the raw
    PDF parser output.

    A PDF extractor does not guarantee that one requirement
    corresponds to one extracted element.

    A requirement may:

        - span multiple PDF elements
        - contain multiple lines
        - share one PDF element with another requirement

    Therefore this class:

        1. Finds numbered requirement starts.
        2. Reconstructs complete requirement blocks.
        3. Finds [SRSxxx] identifiers.
        4. Splits multiple requirements when necessary.
        5. Preserves the original PDF element index.

    The element index is important because the DocumentStructurer
    uses it to associate each requirement with the correct section.
    """

    # =========================================================
    # PUBLIC ENTRY POINT
    # =========================================================

    def segment(
        self,
        elements: list[dict]
    ) -> list[dict]:

        blocks = self._build_requirement_blocks(
            elements
        )

        requirements = []

        for block in blocks:

            text = block["text"]

            page = block["page"]

            element_index = block[
                "_element_index"
            ]

            srs_ids = SRS_ID_PATTERN.findall(
                text
            )

            if not srs_ids:
                continue

            split_requirements = (
                self._split_by_srs_ids(
                    text=text,
                    page=page,
                    element_index=element_index,
                    srs_ids=srs_ids,
                )
            )

            requirements.extend(
                split_requirements
            )

        return self._deduplicate(
            requirements
        )

    # =========================================================
    # BUILD REQUIREMENT BLOCKS
    # =========================================================

    def _build_requirement_blocks(
        self,
        elements: list[dict]
    ) -> list[dict]:

        blocks = []

        current_lines = []

        current_number: Optional[int] = None

        current_page: Optional[int] = None

        current_element_index: Optional[int] = None

        for element_index, element in enumerate(
            elements
        ):

            raw_text = element.get(
                "text",
                ""
            )

            text = raw_text.strip()

            if not text:
                continue

            page = element.get(
                "page"
            )

            lines = text.splitlines()

            for line in lines:

                line = line.strip()

                if not line:
                    continue

                match = (
                    REQUIREMENT_START_PATTERN.match(
                        line
                    )
                )

                if match:

                    number = int(
                        match.group(1)
                    )

                    # -------------------------------------------------
                    # A new numbered requirement begins.
                    # Flush the previous requirement.
                    # -------------------------------------------------

                    if current_number is not None:

                        blocks.append(
                            {
                                "number": current_number,
                                "text": " ".join(
                                    current_lines
                                ).strip(),
                                "page": current_page,
                                "_element_index": (
                                    current_element_index
                                ),
                            }
                        )

                    # -------------------------------------------------
                    # Start new requirement.
                    # -------------------------------------------------

                    current_number = number

                    current_page = page

                    current_element_index = (
                        element_index
                    )

                    current_lines = [
                        line
                    ]

                else:

                    # -------------------------------------------------
                    # Continuation of current requirement.
                    # -------------------------------------------------

                    if current_number is not None:

                        current_lines.append(
                            line
                        )

        # =============================================================
        # Flush final requirement.
        # =============================================================

        if current_number is not None:

            blocks.append(
                {
                    "number": current_number,
                    "text": " ".join(
                        current_lines
                    ).strip(),
                    "page": current_page,
                    "_element_index": (
                        current_element_index
                    ),
                }
            )

        return blocks

    # =========================================================
    # SPLIT BY SRS IDENTIFIERS
    # =========================================================

    def _split_by_srs_ids(
        self,
        text: str,
        page: Optional[int],
        element_index: int,
        srs_ids: list[str]
    ) -> list[dict]:

        # ---------------------------------------------------------
        # Normal case:
        # one requirement contains one SRS identifier.
        # ---------------------------------------------------------

        if len(srs_ids) == 1:

            return [
                {
                    "srs_id": srs_ids[0],
                    "text": text,
                    "page": page,
                    "_element_index": (
                        element_index
                    ),
                }
            ]

        # ---------------------------------------------------------
        # Multiple SRS identifiers occur inside one block.
        #
        # This happens in the X-38 SRS because PDF extraction can
        # merge adjacent requirement material.
        # ---------------------------------------------------------

        matches = list(
            SRS_ID_PATTERN.finditer(
                text
            )
        )

        results = []

        for index, match in enumerate(
            matches
        ):

            srs_id = match.group(0)

            # -----------------------------------------------------
            # End of this segment = beginning of next SRS ID.
            # -----------------------------------------------------

            if index + 1 < len(matches):

                end = matches[
                    index + 1
                ].start()

            else:

                end = len(text)

            # -----------------------------------------------------
            # Find beginning of this numbered requirement.
            # -----------------------------------------------------

            start = (
                self._find_requirement_start_for_srs(
                    text=text,
                    srs_position=match.start(),
                    index=index,
                    matches=matches,
                )
            )

            segment_text = (
                text[start:end].strip()
            )

            if not segment_text:
                continue

            results.append(
                {
                    "srs_id": srs_id,
                    "text": segment_text,
                    "page": page,
                    "_element_index": (
                        element_index
                    ),
                }
            )

        return results

    # =========================================================
    # FIND REQUIREMENT START
    # =========================================================

    @staticmethod
    def _find_requirement_start_for_srs(
        text: str,
        srs_position: int,
        index: int,
        matches
    ) -> int:

        # ---------------------------------------------------------
        # First SRS identifier in the block.
        # ---------------------------------------------------------

        if index == 0:

            # Look for a numbered requirement at the beginning.
            match = re.search(
                r"^\s*\d+\.\s+",
                text
            )

            if match:

                return match.start()

            return 0

        # ---------------------------------------------------------
        # Later SRS identifiers.
        #
        # Search backwards for the numbered requirement that
        # precedes this SRS identifier.
        # ---------------------------------------------------------

        prefix = text[
            :srs_position
        ]

        numbered_starts = list(
            re.finditer(
                r"(?<!\d)(\d+)\.\s+",
                prefix
            )
        )

        if numbered_starts:

            return numbered_starts[
                -1
            ].start()

        # ---------------------------------------------------------
        # Fallback:
        # start at SRS identifier.
        # ---------------------------------------------------------

        return srs_position

    # =========================================================
    # DEDUPLICATE
    # =========================================================

    @staticmethod
    def _deduplicate(
        requirements: list[dict]
    ) -> list[dict]:

        result = []

        seen = set()

        for requirement in requirements:

            srs_id = requirement[
                "srs_id"
            ]

            if srs_id in seen:
                continue

            seen.add(
                srs_id
            )

            result.append(
                requirement
            )

        return result