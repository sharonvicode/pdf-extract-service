"""Unit tests for the input DTO's validation rules."""
import pytest

from app.exceptions import EmptyFileError, FileTooLargeError, UnsupportedFileTypeError
from app.schemas.extraction import PDFUploadRequest


def test_accepts_a_valid_pdf_upload():
    request = PDFUploadRequest(filename="doc.pdf", content_type="application/pdf", size_bytes=1024)

    assert request.filename == "doc.pdf"
    assert request.size_bytes == 1024


def test_rejects_empty_file():
    with pytest.raises(EmptyFileError):
        PDFUploadRequest(filename="doc.pdf", content_type="application/pdf", size_bytes=0)


def test_rejects_unsupported_content_type():
    with pytest.raises(UnsupportedFileTypeError):
        PDFUploadRequest(filename="doc.txt", content_type="text/plain", size_bytes=100)


def test_rejects_file_larger_than_configured_limit():
    from app.core.config import get_settings

    max_bytes = get_settings().max_file_size_bytes

    with pytest.raises(FileTooLargeError):
        PDFUploadRequest(
            filename="doc.pdf", content_type="application/pdf", size_bytes=max_bytes + 1
        )
