"""POST /extract: the endpoint and contract required by the load-testing TP."""
from fastapi import APIRouter, Depends, File, UploadFile

from app.api.error_handlers import DOMAIN_ERROR_RESPONSES
from app.api.v1.endpoints.extraction import get_pdf_extractor_service
from app.schemas.extraction import ExtractContentResponse
from app.services.pdf_extractor import PDFExtractorService

router = APIRouter()


@router.post(
    "/extract",
    response_model=ExtractContentResponse,
    summary="Extraer el contenido de un PDF",
    responses=DOMAIN_ERROR_RESPONSES,
)
async def extract_content(
    file: UploadFile = File(..., description="PDF del que se extrae el contenido."),
    service: PDFExtractorService = Depends(get_pdf_extractor_service),
) -> ExtractContentResponse:
    result = await service.extract_text_async(await file.read())

    return ExtractContentResponse(content=result.text, page_count=result.page_count)
