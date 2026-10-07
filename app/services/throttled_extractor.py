"""Extraction service that waits for a free slot of the concurrency limiter before extracting."""
from app.services.concurrency_limiter import ConcurrencyLimiter
from app.services.pdf_extractor import ExtractionResult, PDFExtractorService


class ThrottledExtractor:
    def __init__(self, extractor: PDFExtractorService, limiter: ConcurrencyLimiter) -> None:
        self._extractor = extractor
        self._limiter = limiter

    async def extract_text_async(self, file_bytes: bytes) -> ExtractionResult:
        async with self._limiter.slot():
            return await self._extractor.extract_text_async(file_bytes)
