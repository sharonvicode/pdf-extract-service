"""POST /extract: the endpoint and contract required by the load-testing TP."""
from fastapi import APIRouter, Depends, File, Request, UploadFile

from app.api.dependencies import get_pdf_extractor_service
from app.api.error_handlers import DOMAIN_ERROR_RESPONSES
from app.core.config import get_settings
from app.exceptions import FileTooLargeError
from app.schemas.extraction import ExtractContentResponse
from app.services.pdf_extractor import PDFExtractorService

router = APIRouter()

MULTIPART_MEDIA_TYPE = "multipart/form-data"


async def read_pdf_bytes(request: Request, file: UploadFile | None) -> bytes:
    """Return the PDF sent either as the multipart ``file`` field or as the raw request body.

    A multipart request without ``file`` yields empty bytes, which the parser rejects as an unreadable PDF.
    """
    if request.headers.get("content-type", "").startswith(MULTIPART_MEDIA_TYPE):
        return await file.read() if file is not None else b""
    return await request.body()


@router.post(
    "/extract",
    response_model=ExtractContentResponse,
    summary="Extraer el contenido de un PDF",
    description="Recibe el PDF como campo `file` de un multipart/form-data o como body binario directo.",
    responses=DOMAIN_ERROR_RESPONSES,
)
async def extract_content(
    request: Request,
    file: UploadFile | None = File(None, description="PDF del que se extrae el contenido."),
    service: PDFExtractorService = Depends(get_pdf_extractor_service),
) -> ExtractContentResponse:
    file_bytes = await read_pdf_bytes(request, file)

    max_bytes = get_settings().max_file_size_bytes
    if len(file_bytes) > max_bytes:
        raise FileTooLargeError(len(file_bytes), max_bytes)

    result = await service.extract_text_async(file_bytes)

    return ExtractContentResponse(content=result.text, page_count=result.page_count)
