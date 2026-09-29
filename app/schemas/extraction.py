"""Pydantic DTOs for the extraction endpoint's input/output contract."""
from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings
from app.exceptions import FileTooLargeError


class PDFUploadRequest(BaseModel):
    """Input contract describing an uploaded file before it is processed.

    Only the maximum size is enforced here, to protect the service's memory
    and CPU. Checking the file type or whether it is empty is the Validator's
    responsibility; unreadable content is rejected later by the PDF parser.
    """

    filename: str = Field(..., min_length=1)
    size_bytes: int = Field(..., ge=0)

    @field_validator("size_bytes")
    @classmethod
    def size_must_be_within_limits(cls, value: int) -> int:
        max_bytes = get_settings().max_file_size_bytes
        if value > max_bytes:
            raise FileTooLargeError(value, max_bytes)
        return value


class ExtractionMetadata(BaseModel):
    """Metadata describing the source file and the extraction result."""

    nombre_archivo: str = Field(..., description="Nombre original del archivo recibido.")
    tamanio_bytes: int = Field(..., ge=0, description="Tamaño del archivo recibido, en bytes.")
    cantidad_paginas: int = Field(..., ge=0, description="Cantidad de páginas del PDF.")
    tiempo_procesamiento_ms: float = Field(
        ..., ge=0, description="Tiempo que llevó extraer el texto, en milisegundos."
    )


class ExtractionResponse(BaseModel):
    """Response DTO returned by the extraction endpoint on success."""

    texto: str = Field(..., description="Texto completo extraído del PDF.")
    metadatos: ExtractionMetadata
