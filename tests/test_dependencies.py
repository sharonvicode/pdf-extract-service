"""Tests for how the endpoints get their extraction service."""
from app.api.dependencies import get_pdf_extractor_service
from app.services.throttled_extractor import ThrottledExtractor


class TestPdfExtractorDependency:
    def test_extractions_go_through_the_concurrency_limiter(self):
        assert isinstance(get_pdf_extractor_service(), ThrottledExtractor)

    def test_every_request_shares_the_same_limited_extractor(self):
        assert get_pdf_extractor_service() is get_pdf_extractor_service()
