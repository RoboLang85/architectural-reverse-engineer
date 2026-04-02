"""Document Ingester: extracts content from PDF, Word, and image files."""

from __future__ import annotations

from pathlib import Path

from app.errors import FileReadError, UnsupportedFileError
from app.models import DocumentInput, DocumentModel
from app import pdf_processor


SUPPORTED_TYPES = ["pdf", "docx", "png", "jpg", "svg"]
IMAGE_TYPES = {"png", "jpg", "svg"}


def ingest(document: DocumentInput) -> DocumentModel:
    """Ingest a document and extract its content.

    Args:
        document: Input specification with file_path and file_type.

    Returns:
        DocumentModel with extracted text_content and images.

    Raises:
        UnsupportedFileError: If file_type is not in the supported set.
        FileReadError: If the file is corrupted or unreadable.
    """
    if document.file_type not in SUPPORTED_TYPES:
        raise UnsupportedFileError(
            f"Unsupported file type: '{document.file_type}'. "
            f"Supported types: {', '.join(SUPPORTED_TYPES)}",
            supported_types=SUPPORTED_TYPES,
        )

    file_path = document.file_path

    if document.file_type == "pdf":
        return _ingest_pdf(file_path)
    elif document.file_type == "docx":
        return _ingest_docx(file_path)
    else:
        return _ingest_image(file_path, document.file_type)


def _ingest_pdf(file_path: str) -> DocumentModel:
    """Delegate PDF processing to pdf_processor."""
    try:
        pdf_content = pdf_processor.extract(file_path)
    except Exception as exc:
        raise FileReadError(
            f"Failed to read PDF file: {file_path}: {exc}",
            details={"file_path": file_path, "reason": "pdf_extraction_failed"},
        ) from exc

    return DocumentModel(
        source_path=file_path,
        file_type="pdf",
        text_content=pdf_content.text_blocks,
        images=pdf_content.images,
    )


def _ingest_docx(file_path: str) -> DocumentModel:
    """Extract text paragraphs and embedded images from a Word document."""
    try:
        import docx
    except ImportError as exc:
        raise FileReadError(
            "python-docx is required for Word document processing",
            details={"file_path": file_path, "reason": "missing_dependency"},
        ) from exc

    try:
        doc = docx.Document(file_path)
    except FileNotFoundError as exc:
        raise FileReadError(
            f"Word document not found: {file_path}",
            details={"file_path": file_path, "reason": "not_found"},
        ) from exc
    except Exception as exc:
        raise FileReadError(
            f"Failed to read Word document: {file_path}: {exc}",
            details={"file_path": file_path, "reason": "read_failed"},
        ) from exc

    text_content: list[str] = []
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        if text:
            text_content.append(text)

    images: list[bytes] = []
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            try:
                images.append(rel.target_part.blob)
            except Exception:
                continue

    return DocumentModel(
        source_path=file_path,
        file_type="docx",
        text_content=text_content,
        images=images,
    )


def _ingest_image(file_path: str, file_type: str) -> DocumentModel:
    """Read an image file and return it as a single image in DocumentModel."""
    path = Path(file_path)

    if not path.exists():
        raise FileReadError(
            f"Image file not found: {file_path}",
            details={"file_path": file_path, "reason": "not_found"},
        )

    try:
        image_bytes = path.read_bytes()
    except Exception as exc:
        raise FileReadError(
            f"Failed to read image file: {file_path}: {exc}",
            details={"file_path": file_path, "reason": "read_failed"},
        ) from exc

    if not image_bytes:
        raise FileReadError(
            f"Image file is empty: {file_path}",
            details={"file_path": file_path, "reason": "empty_file"},
        )

    return DocumentModel(
        source_path=file_path,
        file_type=file_type,
        text_content=[],
        images=[image_bytes],
    )
