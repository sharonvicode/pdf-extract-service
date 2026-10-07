"""Business logic for extracting the content of PDF files as Markdown.

This module is intentionally decoupled from FastAPI: it operates on plain
bytes in, plain data out, which keeps it independently unit-testable and
reusable outside of an HTTP context.
"""
import asyncio
import time
from collections import Counter
from dataclasses import dataclass

import pymupdf

from app.exceptions import InvalidPDFError, NoExtractableTextError

HEADING_SIZE_RATIO = 1.2


@dataclass(frozen=True)
class ExtractionResult:
    """Plain result of a text extraction, independent of any DTO/schema."""

    text: str
    page_count: int
    processing_time_ms: float


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
            try:
                blocks = [
                    block
                    for page in document
                    for block in page.get_text("dict", flags=pymupdf.TEXTFLAGS_TEXT)["blocks"]
                ]
            except Exception as exc:  # MuPDF can raise various low-level errors
                raise InvalidPDFError(f"No se pudo extraer el texto del PDF: {exc}") from exc

        lines = [line for block in blocks for line in block["lines"]]
        sizes = Counter()
        for line in lines:
            for span in line["spans"]:
                sizes[round(span["size"])] += len(span["text"])
        body_size = sizes.most_common(1)[0][0] if sizes else 0

        paragraphs = []
        for block in blocks:
            rendered = []
            for line in block["lines"]:
                line_text = "".join(span["text"] for span in line["spans"]).strip()
                if not line_text:
                    continue
                line_size = max(span["size"] for span in line["spans"])
                if line_size >= body_size * HEADING_SIZE_RATIO:
                    line_text = f"# {line_text}"
                rendered.append(line_text)
            if rendered:
                paragraphs.append("\n".join(rendered))

        text = "\n\n".join(paragraphs).strip()
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
