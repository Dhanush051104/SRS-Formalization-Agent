from app.parser.document_parser import parse_document


PDF_PATH = "data/nasaX38 SRS.pdf"


def main():

    elements = parse_document(PDF_PATH)

    print(f"Total elements: {len(elements)}")

    # =========================================================
    # Find every occurrence of:
    #   3.2.1
    #   System Initialization
    #   [SRS194]
    # =========================================================

    keywords = [
        "3.2.1",
        "System Initialization",
        "[SRS194]",
    ]

    for keyword in keywords:

        print(
            "\n"
            + "=" * 80
        )

        print(
            f"SEARCHING FOR: {keyword}"
        )

        print(
            "=" * 80
        )

        matches = []

        for index, element in enumerate(elements):

            text = element.get(
                "text",
                ""
            )

            if keyword.lower() in text.lower():

                matches.append(index)

        print(
            f"Matches found: {len(matches)}"
        )

        for index in matches:

            print(
                "\n"
                + "-" * 60
            )

            print(
                f"ELEMENT INDEX: {index}"
            )

            print(
                f"PAGE: "
                f"{elements[index].get('page')}"
            )

            print(
                f"TEXT:\n"
                f"{elements[index].get('text')}"
            )

            # Print surrounding elements.
            start = max(
                0,
                index - 3
            )

            end = min(
                len(elements),
                index + 4
            )

            print(
                "\nSURROUNDING ELEMENTS:"
            )

            for i in range(
                start,
                end
            ):

                print(
                    f"\n[{i}] "
                    f"(page "
                    f"{elements[i].get('page')})"
                )

                print(
                    elements[i].get(
                        "text",
                        ""
                    )
                )


if __name__ == "__main__":
    main()