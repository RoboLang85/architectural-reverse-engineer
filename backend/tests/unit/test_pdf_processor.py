"""Unit tests for the PDF Processor component."""

from __future__ import annotations

import os
import tempfile

import fitz  # PyMuPDF
import pytest

from app.errors import ExtractionError
from app.models import PdfContent
from app.pdf_processor import extract


@pytest.fixture
def simple_pdf(tmp_path):
    """Create a simple PDF with text on two pages."""
    path = str(tmp_path / "simple.pdf")
    doc = fitz.open()
    page1 = doc.new_page()
    page1.insert_text((72, 72), "Hello from page one")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Hello from page two")
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def empty_pdf(tmp_path):
    """Create a PDF with no text content."""
    path = str(tmp_path / "empty.pdf")
    doc = fitz.open()
    doc.new_page()  # blank page
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def pdf_with_image(tmp_path):
    """Create a PDF with an embedded image."""
    path = str(tmp_path / "with_image.pdf")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Page with image")

    # Create a small PNG image in memory
    img_path = str(tmp_path / "test_img.png")
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10), 1)
    pix.set_rect(pix.irect, (255, 0, 0, 255))  # red square with alpha
    pix.save(img_path)
    pix = None

    rect = fitz.Rect(72, 100, 172, 200)
    page.insert_image(rect, filename=img_path)

    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def corrupted_pdf(tmp_path):
    """Create a file that is not a valid PDF."""
    path = str(tmp_path / "corrupted.pdf")
    with open(path, "wb") as f:
        f.write(b"this is not a pdf file at all")
    return path


class TestExtractText:
    """Tests for text extraction from PDFs."""

    def test_extracts_text_from_simple_pdf(self, simple_pdf):
        result = extract(simple_pdf)
        assert isinstance(result, PdfContent)
        assert len(result.text_blocks) == 2
        assert "Hello from page one" in result.text_blocks[0]
        assert "Hello from page two" in result.text_blocks[1]

    def test_empty_pdf_returns_no_text(self, empty_pdf):
        result = extract(empty_pdf)
        assert isinstance(result, PdfContent)
        assert result.text_blocks == []

    def test_returns_pdfcontent_model(self, simple_pdf):
        result = extract(simple_pdf)
        assert isinstance(result, PdfContent)
        assert isinstance(result.text_blocks, list)
        assert isinstance(result.images, list)


class TestExtractImages:
    """Tests for image extraction from PDFs."""

    def test_extracts_image_from_pdf(self, pdf_with_image):
        result = extract(pdf_with_image)
        assert len(result.images) >= 1
        assert all(isinstance(img, bytes) for img in result.images)
        assert all(len(img) > 0 for img in result.images)

    def test_no_images_in_text_only_pdf(self, simple_pdf):
        result = extract(simple_pdf)
        assert result.images == []


class TestErrorHandling:
    """Tests for error handling in PDF extraction."""

    def test_file_not_found_raises_extraction_error(self):
        with pytest.raises(ExtractionError, match="not found"):
            extract("/nonexistent/path/to/file.pdf")

    def test_corrupted_pdf_raises_extraction_error(self, corrupted_pdf):
        with pytest.raises(ExtractionError):
            extract(corrupted_pdf)

    def test_extraction_error_contains_file_path_in_details(self):
        bad_path = "/no/such/file.pdf"
        with pytest.raises(ExtractionError) as exc_info:
            extract(bad_path)
        assert exc_info.value.details["file_path"] == bad_path
