"""HTTP endpoints for PDF text extraction.

This layer is only responsible for: receiving the request, validating the
input contract, delegating to the service layer, and shaping the response.
No extraction logic lives here (SRP).
"""
from fastapi import APIRouter, Depends, File, UploadFile

from app.api.dependencies import get_pdf_extractor_service
from app.api.error_handlers import DOMAIN_ERROR_RESPONSES
from app.schemas.extraction import ExtractionMetadata, ExtractionResponse, PDFUploadRequest
from app.services.pdf_extractor import PDFExtractorService

router = APIRouter()


@router.post(
    "/extraer",
    response_model=ExtractionResponse,
    summary="Extraer el texto de un PDF",
    responses=DOMAIN_ERROR_RESPONSES,
)
async def extract_pdf_text(
    file: UploadFile = File(..., description="PDF del que se extrae el texto."),
    service: PDFExtractorService = Depends(get_pdf_extractor_service),
) -> ExtractionResponse:
    file_bytes = await file.read()
    filename = file.filename or "unknown.pdf"

    PDFUploadRequest(filename=filename, size_bytes=len(file_bytes))

    result = await service.extract_text_async(file_bytes)

    return ExtractionResponse(
        texto=result.text,
        metadatos=ExtractionMetadata(
            nombre_archivo=filename,
            tamanio_bytes=len(file_bytes),
            cantidad_paginas=result.page_count,
            tiempo_procesamiento_ms=result.processing_time_ms,
        ),
    )
