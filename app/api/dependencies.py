"""Dependency providers shared by every extraction endpoint."""
from functools import lru_cache

from app.core.config import get_settings
from app.services.concurrency_limiter import ConcurrencyLimiter
from app.services.pdf_extractor import PDFExtractor, PDFExtractorService
from app.services.throttled_extractor import ThrottledExtractor


@lru_cache
def get_pdf_extractor_service() -> PDFExtractor:
    """Dependency provider, enabling substitution in tests (DIP).

    Cached so every request shares one limiter per process: a limiter per request would limit nothing.
    """
    settings = get_settings()
    limiter = ConcurrencyLimiter(settings.extraction_concurrency, settings.extraction_queue_size)
    return ThrottledExtractor(PDFExtractorService(), limiter)
