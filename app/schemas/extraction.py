"""Pydantic DTOs for the extraction endpoint's input/output contract."""
from pydantic import BaseModel, Field, field_validator

from app.services.file_size import ensure_within_size_limit


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
        ensure_within_size_limit(value)
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


class ExtractContentResponse(BaseModel):
    """Response DTO of POST /extract, with the exact fields the load-testing TP requires."""

    content: str = Field(..., description="Contenido extraído del PDF.")
    page_count: int = Field(..., ge=0, description="Cantidad de páginas del PDF.")
