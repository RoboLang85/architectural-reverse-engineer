"""PDF Processor: extracts text and images from PDF files using PyMuPDF."""

from __future__ import annotations

import fitz  # PyMuPDF

from app.errors import ExtractionError
from app.models import PdfContent


def extract(pdf_path: str) -> PdfContent:
    """Extract text blocks and embedded images from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        PdfContent with extracted text_blocks and images.

    Raises:
        ExtractionError: If the file is not found, corrupted, or unreadable.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        msg = str(exc).lower()
        if "no such file" in msg or "not found" in msg:
            raise ExtractionError(
                f"PDF file not found: {pdf_path}",
                details={"file_path": pdf_path, "reason": "not_found"},
            ) from exc
        raise ExtractionError(
            f"Failed to open PDF: {pdf_path}: {exc}",
            details={"file_path": pdf_path, "reason": "open_failed"},
        ) from exc

    text_blocks: list[str] = []
    images: list[bytes] = []

    try:
        for page in doc:
            text = page.get_text()
            if text.strip():
                text_blocks.append(text.strip())

            for img_info in page.get_images(full=True):
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if base_image and base_image.get("image"):
                        images.append(base_image["image"])
                except Exception:
                    # Skip images that can't be extracted
                    continue
    except Exception as exc:
        raise ExtractionError(
            f"Error reading PDF content: {pdf_path}: {exc}",
            details={"file_path": pdf_path, "reason": "read_failed"},
        ) from exc
    finally:
        doc.close()

    return PdfContent(text_blocks=text_blocks, images=images)
