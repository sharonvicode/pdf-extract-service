"""HTTP endpoints for PDF text extraction.

This layer is only responsible for: receiving the request, validating the
input contract, delegating to the service layer, and shaping the response.
No extraction logic lives here (SRP).
"""
from fastapi import APIRouter, Depends, File, UploadFile

from app.api.error_handlers import DOMAIN_ERROR_RESPONSES
from app.schemas.extraction import ExtractionMetadata, ExtractionResponse, PDFUploadRequest
from app.services.pdf_extractor import PDFExtractorService

router = APIRouter()


def get_pdf_extractor_service() -> PDFExtractorService:
    """Dependency provider, enabling substitution in tests (DIP)."""
    return PDFExtractorService()


@router.post(
    "/extract",
    response_model=ExtractionResponse,
    summary="Extract text from a PDF file",
    responses=DOMAIN_ERROR_RESPONSES,
)
async def extract_pdf_text(
    file: UploadFile = File(..., description="PDF file to extract text from."),
    service: PDFExtractorService = Depends(get_pdf_extractor_service),
) -> ExtractionResponse:
    file_bytes = await file.read()

    PDFUploadRequest(
        filename=file.filename or "unknown.pdf",
        content_type=file.content_type,
        size_bytes=len(file_bytes),
    )

    result = await service.extract_text_async(file_bytes)

    return ExtractionResponse(
        text=result.text,
        metadata=ExtractionMetadata(
            filename=file.filename or "unknown.pdf",
            size_bytes=len(file_bytes),
            page_count=result.page_count,
            processing_time_ms=result.processing_time_ms,
        ),
    )
