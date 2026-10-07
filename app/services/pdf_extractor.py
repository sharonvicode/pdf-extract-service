"""Business logic for extracting the content of PDF files as Markdown.

This module is intentionally decoupled from FastAPI: it operates on plain
bytes in, plain data out, which keeps it independently unit-testable and
reusable outside of an HTTP context.
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Protocol

import pymupdf

from app.exceptions import InvalidPDFError, NoExtractableTextError
from app.services.markdown_renderer import Block, render_markdown


@dataclass(frozen=True)
class ExtractionResult:
    """Plain result of a text extraction, independent of any DTO/schema."""

    text: str
    page_count: int
    processing_time_ms: float


class PDFExtractor(Protocol):
    """What the endpoints need from an extraction service, whatever adds limits or logging around it."""

    async def extract_text_async(self, file_bytes: bytes) -> ExtractionResult: ...


class PDFExtractorService:
    """Extracts the content of PDF file bytes as Markdown using PyMuPDF."""

    def extract_text(self, file_bytes: bytes) -> ExtractionResult:
        """Synchronously parse ``file_bytes`` and return the extracted content as Markdown.

        Raises:
            InvalidPDFError: if the bytes do not represent a readable PDF.
            NoExtractableTextError: if the PDF has no text.
        """
        started_at = time.perf_counter()

        try:
            document = pymupdf.open(stream=file_bytes, filetype="pdf")
        except pymupdf.FileDataError as exc:
            raise InvalidPDFError(f"No se pudo leer el archivo como PDF: {exc}") from exc

        with document:
            page_count = document.page_count
            blocks = self._read_text_blocks(document)

        text = render_markdown(blocks).strip()
        if not text:
            raise NoExtractableTextError("El PDF no tiene texto extraíble.")

        elapsed_ms = (time.perf_counter() - started_at) * 1000

        return ExtractionResult(
            text=text,
            page_count=page_count,
            processing_time_ms=elapsed_ms,
        )

    async def extract_text_async(self, file_bytes: bytes) -> ExtractionResult:
        """Async wrapper that offloads the CPU-bound parsing to a thread.

        Keeps the FastAPI event loop free while PyMuPDF does its work.
        """
        return await asyncio.to_thread(self.extract_text, file_bytes)

    @staticmethod
    def _read_text_blocks(document: pymupdf.Document) -> list[Block]:
        """Return the text blocks of every page, with the font size of each span."""
        try:
            return [
                block
                for page in document
                for block in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]
            ]
        except Exception as exc:  # MuPDF can raise various low-level errors
            raise InvalidPDFError(f"No se pudo extraer el texto del PDF: {exc}") from exc
