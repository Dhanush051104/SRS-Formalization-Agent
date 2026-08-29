import re


class DocumentCleaner:
    """
    Cleans PDF extraction artifacts while preserving the original text.

    The cleaner never modifies the raw parser output.
    """

    def clean_requirement(self, requirement: dict) -> dict:
        raw_text = requirement["text"]
        cleaned_text = raw_text

        # ---------------------------------------------------------
        # Remove X-38 document footer/header artifacts
        # Example:
        # 297749 Rev F 10 August 200112 March 2002
        # ---------------------------------------------------------

        cleaned_text = re.sub(
            r"\s*\d{6}\s+Rev\s+[A-Z]\s+"
            r"\d{1,2}\s+\w+\s+\d{4}"
            r"(?:\d{1,2}\s+\w+\s+\d{4})?",
            " ",
            cleaned_text,
            flags=re.IGNORECASE,
        )

        # ---------------------------------------------------------
        # Remove standalone page numbers at the end
        # ---------------------------------------------------------

        cleaned_text = re.sub(
            r"\s+\d{1,3}\s*$",
            "",
            cleaned_text
        )

        # ---------------------------------------------------------
        # Remove accidental following section text
        # Example:
        # "... 1.5 minutes. 3.2.2 Scheduling Services ..."
        # ---------------------------------------------------------

        next_section = re.search(
            r"\s+\d+\.\d+(?:\.\d+)*\s+[A-Z][^.]{2,}",
            cleaned_text
        )

        if next_section:
            cleaned_text = cleaned_text[:next_section.start()]

        # ---------------------------------------------------------
        # Normalize whitespace
        # ---------------------------------------------------------

        cleaned_text = re.sub(
            r"\s+",
            " ",
            cleaned_text
        ).strip()

        return {
            **requirement,
            "raw_text": raw_text,
            "text": cleaned_text,
        }