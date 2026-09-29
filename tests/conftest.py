"""Shared pytest fixtures: builds real, valid PDF byte payloads on the fly.

Generating PDFs in-memory (rather than committing binary fixture files)
keeps the "different sizes" test matrix easy to extend and avoids binary
diffs in version control.
"""
from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter


def _build_single_page_pdf_bytes(text: str) -> bytes:
    """Return a minimal, valid single-page PDF containing ``text``.

    Built with a correctly computed xref table (rather than relying on
    pypdf's lenient recovery parser) so tests run without warning noise.
    """
    content_stream = f"BT /F1 24 Tf 72 700 Td ({text}) Tj ET".encode()

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >>"
        b" /MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content_stream)).encode() + b" >>\nstream\n"
        + content_stream
        + b"\nendstream",
    ]

    header = b"%PDF-1.4\n"
    buffer = bytearray(header)
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(buffer))
        buffer += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_offset = len(buffer)
    buffer += f"xref\n0 {len(objects) + 1}\n".encode()
    buffer += b"0000000000 65535 f \n"
    for offset in offsets:
        buffer += f"{offset:010d} 00000 n \n".encode()

    buffer += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF"
    ).encode()

    return bytes(buffer)


def _build_multi_page_pdf_bytes(page_count: int, text_prefix: str = "Page") -> bytes:
    """Concatenate ``page_count`` single-page PDFs into one document via pypdf."""
    writer = PdfWriter()
    for page_number in range(1, page_count + 1):
        single_page = PdfReader(BytesIO(_build_single_page_pdf_bytes(f"{text_prefix} {page_number}")))
        writer.add_page(single_page.pages[0])

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def make_pdf_bytes():
    """Factory fixture: build a PDF with an arbitrary number of pages."""

    def _factory(page_count: int = 1, text_prefix: str = "Page") -> bytes:
        return _build_multi_page_pdf_bytes(page_count, text_prefix)

    return _factory


@pytest.fixture
def small_pdf_bytes(make_pdf_bytes) -> bytes:
    """A 1-page PDF, representing the smallest valid document."""
    return make_pdf_bytes(page_count=1)


@pytest.fixture
def medium_pdf_bytes(make_pdf_bytes) -> bytes:
    """A 10-page PDF, representing a typical multi-page document."""
    return make_pdf_bytes(page_count=10)


@pytest.fixture
def large_pdf_bytes(make_pdf_bytes) -> bytes:
    """A 100-page PDF, representing a large document."""
    return make_pdf_bytes(page_count=100)


@pytest.fixture
def blank_pdf_bytes() -> bytes:
    """A valid 1-page PDF with no text at all (e.g. a blank or scanned page)."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture
def empty_file_bytes() -> bytes:
    return b""


@pytest.fixture
def corrupted_pdf_bytes() -> bytes:
    """Bytes that look like a PDF but are not a valid/parsable document."""
    return b"%PDF-1.4\nThis is not a real PDF body.\n%%EOF"


@pytest.fixture
def not_a_pdf_bytes() -> bytes:
    return b"just some plain text, not a pdf at all"
