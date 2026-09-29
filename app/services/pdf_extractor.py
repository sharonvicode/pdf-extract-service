"""Business logic for extracting text from PDF files.

This module is intentionally decoupled from FastAPI: it operates on plain
bytes in, plain data out, which keeps it independently unit-testable and
reusable outside of an HTTP context.
"""
import asyncio
import time
from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.exceptions import InvalidPDFError, NoExtractableTextError


@dataclass(frozen=True)
class ExtractionResult:
    """Plain result of a text extraction, independent of any DTO/schema."""

    text: str
    page_count: int
    processing_time_ms: float


class PDFExtractorService:
    """Extracts text content from PDF file bytes using pypdf."""

    def extract_text(self, file_bytes: bytes) -> ExtractionResult:
        """Synchronously parse ``file_bytes`` and return the extracted text.

        Raises:
            InvalidPDFError: if the bytes do not represent a readable PDF.
        """
        started_at = time.perf_counter()

        try:
            reader = PdfReader(BytesIO(file_bytes))
        except (PdfReadError, ValueError) as exc:
            raise InvalidPDFError(f"Could not parse file as PDF: {exc}") from exc

        try:
            pages_text = [page.extract_text() or "" for page in reader.pages]
        except Exception as exc:  # pypdf can raise various low-level errors
            raise InvalidPDFError(f"Could not extract text from PDF: {exc}") from exc

        text = "\n".join(pages_text).strip()
        if not text:
            raise NoExtractableTextError("The PDF has no extractable text.")

        elapsed_ms = (time.perf_counter() - started_at) * 1000

        return ExtractionResult(
            text=text,
            page_count=len(reader.pages),
            processing_time_ms=elapsed_ms,
        )

    async def extract_text_async(self, file_bytes: bytes) -> ExtractionResult:
        """Async wrapper that offloads the CPU-bound parsing to a thread.

        Keeps the FastAPI event loop free while pypdf (a synchronous,
        CPU-bound library) does its work.
        """
        return await asyncio.to_thread(self.extract_text, file_bytes)
