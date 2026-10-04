"""POST /extract: the endpoint and contract required by the load-testing TP."""
from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.api.dependencies import get_pdf_extractor_service
from app.api.error_handlers import DOMAIN_ERROR_RESPONSES
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
    request: Request,
    file: UploadFile | None = File(None, description="PDF del que se extrae el contenido."),
    service: PDFExtractorService = Depends(get_pdf_extractor_service),
) -> ExtractContentResponse:
    if request.headers.get("content-type", "").startswith("multipart/form-data"):
        file_bytes = await file.read() if file is not None else b""
    else:
        file_bytes = await request.body()

    result = await service.extract_text_async(file_bytes)

    return ExtractContentResponse(content=result.text, page_count=result.page_count)
