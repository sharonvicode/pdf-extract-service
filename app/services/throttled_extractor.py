"""Extraction service that waits for a free slot of the concurrency limiter before extracting."""
from app.services.concurrency_limiter import ConcurrencyLimiter
from app.services.pdf_extractor import ExtractionResult, PDFExtractor


class ThrottledExtractor:
    """Decorator over any PDFExtractor: same interface, but extractions take turns (backpressure).

    The wrapped extractor knows nothing about concurrency, so the limit can be
    added or removed without touching the extraction logic (SRP, OCP).
    """

    def __init__(self, extractor: PDFExtractor, limiter: ConcurrencyLimiter) -> None:
        self._extractor = extractor
        self._limiter = limiter

    async def extract_text_async(self, file_bytes: bytes) -> ExtractionResult:
        """Extract once a slot is free.

        Raises:
            ServiceBusyError: if the limiter's running and waiting places are all taken.
        """
        async with self._limiter.slot():
            return await self._extractor.extract_text_async(file_bytes)
