from app.parser.document_parser import parse_document

from app.structurer.requirement_segmenter import (
    RequirementSegmenter
)

from app.structurer.document_cleaner import (
    DocumentCleaner
)

from app.structurer.document_structurer import (
    DocumentStructurer
)


PDF_PATH = "data/nasaX38 SRS.pdf"


def print_section_recursive(document: dict, section_number: str, depth: int = 0):
    sec = document.get(section_number)
    if not sec:
        return
    indent = "    " * depth
    print(f"{indent}{sec['number']} - {sec['title']} (Page: {sec['page']})")

    for req in sec.get("requirements", []):
        num = req.get("local_number")
        label = f"R{num}" if num is not None else "R?"
        print(f"{indent}  * {label} {req['srs_id']}: {req['text']}")

    children = sec.get("children", [])
    def sort_key(s):
        return [int(x) for x in s.split('.') if x.isdigit()]

    try:
        sorted_children = sorted(children, key=sort_key)
    except Exception:
        sorted_children = children

    for child in sorted_children:
        print_section_recursive(document, child, depth + 1)


def main():

    # =========================================================
    # 1. Parse entire SRS
    # =========================================================

    elements = parse_document(PDF_PATH)

    print(
        f"Parsed elements: {len(elements)}"
    )

    # =========================================================
    # 2. Segment requirements
    # =========================================================

    segmenter = RequirementSegmenter()

    requirements = segmenter.segment(
        elements
    )

    print(
        f"Unique SRS requirements detected: "
        f"{len(requirements)}"
    )

    # =========================================================
    # 3. Clean requirements
    # =========================================================

    cleaner = DocumentCleaner()

    requirements = [
        cleaner.clean_requirement(
            requirement
        )
        for requirement in requirements
    ]

    # =========================================================
    # 4. Build section hierarchy
    # =========================================================

    structurer = DocumentStructurer(
        elements
    )

    document = structurer.build()

    print(
        f"Sections detected: "
        f"{len(document)}"
    )

    # =========================================================
    # 5. Attach requirements
    # =========================================================

    document = structurer.add_requirements(
        document,
        requirements
    )

    # =========================================================
    # 6. Section 3 (Recursive Hierarchy)
    # =========================================================

    print(
        "\n========== SECTION 3 HIERARCHY ==========\n"
    )

    if document.get("3"):
        print_section_recursive(document, "3")
    else:
        print(
            "Section 3 not found."
        )

    # =========================================================
    # 7. System Initialization
    # =========================================================

    print(
        "\n========== SYSTEM INITIALIZATION ==========\n"
    )

    system_init = document.get(
        "3.2.1"
    )

    if system_init:

        print(
            f"Section: "
            f"{system_init['number']}"
        )

        print(
            f"Title: "
            f"{system_init['title']}"
        )

        print(
            f"Page: "
            f"{system_init['page']}"
        )

        print(
            f"Parent: "
            f"{system_init['parent']}"
        )

        print(
            f"Requirements: "
            f"{len(system_init['requirements'])}"
        )

        for requirement in system_init[
            "requirements"
        ]:

            number = (
                requirement[
                    "local_number"
                ]
            )

            label = (
                f"R{number}"
                if number is not None
                else "R?"
            )

            print(
                f"\n{label} "
                f"{requirement['srs_id']}"
            )

            print(
                requirement["text"]
            )

    else:

        print(
            "System Initialization "
            "section not found."
        )


if __name__ == "__main__":
    main()