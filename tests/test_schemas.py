"""Unit tests for the input DTO's validation rules."""
import pytest

from app.core.config import get_settings
from app.exceptions import FileTooLargeError
from app.schemas.extraction import PDFUploadRequest


def test_accepts_a_valid_pdf_upload():
    request = PDFUploadRequest(filename="doc.pdf", size_bytes=1024)

    assert request.filename == "doc.pdf"
    assert request.size_bytes == 1024


def test_accepts_empty_file_leaving_it_to_pdf_parsing():
    request = PDFUploadRequest(filename="doc.pdf", size_bytes=0)

    assert request.size_bytes == 0


def test_rejects_file_larger_than_configured_limit():
    max_bytes = get_settings().max_file_size_bytes

    with pytest.raises(FileTooLargeError):
        PDFUploadRequest(filename="doc.pdf", size_bytes=max_bytes + 1)
