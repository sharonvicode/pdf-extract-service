"""Dependency providers shared by every extraction endpoint."""
from app.services.pdf_extractor import PDFExtractorService


def get_pdf_extractor_service() -> PDFExtractorService:
    """Dependency provider, enabling substitution in tests (DIP)."""
    return PDFExtractorService()
