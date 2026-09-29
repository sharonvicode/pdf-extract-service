"""Unit tests for the input DTO's validation rules."""
import pytest

from app.exceptions import FileTooLargeError
from app.schemas.extraction import PDFUploadRequest


def test_accepts_a_valid_pdf_upload():
    request = PDFUploadRequest(filename="doc.pdf", content_type="application/pdf", size_bytes=1024)

    assert request.filename == "doc.pdf"
    assert request.size_bytes == 1024


def test_accepts_empty_file_leaving_it_to_pdf_parsing():
    request = PDFUploadRequest(filename="doc.pdf", content_type="application/pdf", size_bytes=0)

    assert request.size_bytes == 0


def test_accepts_any_content_type_because_the_validator_checks_it():
    request = PDFUploadRequest(filename="doc.pdf", content_type="application/octet-stream", size_bytes=100)

    assert request.size_bytes == 100


def test_rejects_file_larger_than_configured_limit():
    from app.core.config import get_settings

    max_bytes = get_settings().max_file_size_bytes

    with pytest.raises(FileTooLargeError):
        PDFUploadRequest(
            filename="doc.pdf", content_type="application/pdf", size_bytes=max_bytes + 1
        )
