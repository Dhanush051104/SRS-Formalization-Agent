from pathlib import Path

from docx import Document
from pypdf import PdfReader


def parse_document(file_path: str) -> list[dict]:
    """
    Parse a PDF or DOCX document and return its content
    in a common structured format.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _parse_pdf(path)

    if suffix == ".docx":
        return _parse_docx(path)

    raise ValueError(
        f"Unsupported file type: {suffix}. "
        "Only PDF and DOCX are currently supported."
    )


def _parse_pdf(path: Path) -> list[dict]:
    """Extract text from a PDF while preserving page information."""

    reader = PdfReader(path)
    elements = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text()

        if not text:
            continue

        for index, line in enumerate(text.splitlines()):
            line = line.strip()

            if not line:
                continue

            elements.append({
                "type": "text",
                "page": page_number,
                "index": index,
                "text": line,
                "style": None,
            })

    return elements


def _parse_docx(path: Path) -> list[dict]:
    """Extract paragraphs from a DOCX while preserving style information."""

    document = Document(path)
    elements = []

    for index, paragraph in enumerate(document.paragraphs):
        text = paragraph.text.strip()

        if not text:
            continue

        elements.append({
            "type": "text",
            "page": None,
            "index": index,
            "text": text,
            "style": paragraph.style.name,
        })

    return elements