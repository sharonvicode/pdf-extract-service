"""Unit tests (TDD) for the PDF extraction business logic.

Covers PDFs of different sizes (1, 10, 100 pages) plus the invalid-input
and no-text edge cases the service must reject with domain exceptions.
"""
import pytest

from app.exceptions import InvalidPDFError, NoExtractableTextError
from app.services.pdf_extractor import ExtractionResult, PDFExtractorService
from tests.conftest import FIRST_PARAGRAPH, SECOND_PARAGRAPH, TITLE


@pytest.fixture
def service() -> PDFExtractorService:
    return PDFExtractorService()


class TestExtractTextSync:
    def test_extracts_text_from_single_page_pdf(self, service, small_pdf_bytes):
        result = service.extract_text(small_pdf_bytes)

        assert isinstance(result, ExtractionResult)
        assert result.page_count == 1
        assert "Page 1" in result.text

    def test_extracts_text_from_medium_pdf(self, service, medium_pdf_bytes):
        result = service.extract_text(medium_pdf_bytes)

        assert result.page_count == 10
        assert "Page 1" in result.text
        assert "Page 10" in result.text

    def test_extracts_text_from_large_pdf(self, service, large_pdf_bytes):
        result = service.extract_text(large_pdf_bytes)

        assert result.page_count == 100
        assert "Page 1" in result.text
        assert "Page 100" in result.text

    def test_reports_processing_time(self, service, small_pdf_bytes):
        result = service.extract_text(small_pdf_bytes)

        assert result.processing_time_ms >= 0

    def test_raises_invalid_pdf_error_for_corrupted_pdf(self, service, corrupted_pdf_bytes):
        with pytest.raises(InvalidPDFError):
            service.extract_text(corrupted_pdf_bytes)

    def test_raises_invalid_pdf_error_for_non_pdf_bytes(self, service, not_a_pdf_bytes):
        with pytest.raises(InvalidPDFError):
            service.extract_text(not_a_pdf_bytes)

    def test_raises_no_extractable_text_error_for_pdf_without_text(self, service, blank_pdf_bytes):
        with pytest.raises(NoExtractableTextError):
            service.extract_text(blank_pdf_bytes)


class TestMarkdownOutput:
    """The TP requires the extracted content in Markdown."""

    def test_marks_large_font_line_as_heading(self, service, titled_pdf_bytes):
        result = service.extract_text(titled_pdf_bytes)

        assert result.text.startswith(f"# {TITLE}\n")

    def test_does_not_mark_body_text_as_heading(self, service, titled_pdf_bytes):
        lines = service.extract_text(titled_pdf_bytes).text.splitlines()

        assert FIRST_PARAGRAPH in lines
        assert SECOND_PARAGRAPH in lines

    def test_separates_paragraphs_with_a_blank_line(self, service, titled_pdf_bytes):
        result = service.extract_text(titled_pdf_bytes)

        assert f"{TITLE}\n\n{FIRST_PARAGRAPH}\n\n{SECOND_PARAGRAPH}" in result.text


class TestExtractTextAsync:
    @pytest.mark.asyncio
    async def test_extracts_text_asynchronously(self, service, small_pdf_bytes):
        result = await service.extract_text_async(small_pdf_bytes)

        assert result.page_count == 1
        assert "Page 1" in result.text

    @pytest.mark.asyncio
    async def test_raises_invalid_pdf_error_for_corrupted_pdf(self, service, corrupted_pdf_bytes):
        with pytest.raises(InvalidPDFError):
            await service.extract_text_async(corrupted_pdf_bytes)
