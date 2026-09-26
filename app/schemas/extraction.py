"""Pydantic DTOs for the extraction endpoint's input/output contract."""
from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings
from app.exceptions import EmptyFileError, FileTooLargeError, UnsupportedFileTypeError


class PDFUploadRequest(BaseModel):
    """Input contract describing an uploaded file before it is processed.

    Decoupling this from FastAPI's ``UploadFile`` keeps validation rules
    (content type, size) testable in isolation, independent of the web
    framework. Validators raise the same domain exceptions used by the
    service layer, so there is a single source of truth for what makes an
    upload invalid.
    """

    filename: str = Field(..., min_length=1)
    content_type: str | None = None
    size_bytes: int = Field(..., ge=0)

    @field_validator("content_type")
    @classmethod
    def content_type_must_be_allowed(cls, value: str | None) -> str | None:
        allowed = get_settings().allowed_content_types
        if value not in allowed:
            raise UnsupportedFileTypeError(value)
        return value

    @field_validator("size_bytes")
    @classmethod
    def size_must_be_within_limits(cls, value: int) -> int:
        if value == 0:
            raise EmptyFileError("Uploaded file is empty.")
        max_bytes = get_settings().max_file_size_bytes
        if value > max_bytes:
            raise FileTooLargeError(value, max_bytes)
        return value


class ExtractionMetadata(BaseModel):
    """Metadata describing the source file and the extraction result."""

    filename: str = Field(..., description="Original name of the uploaded file.")
    size_bytes: int = Field(..., ge=0, description="Size of the uploaded file in bytes.")
    page_count: int = Field(..., ge=0, description="Number of pages in the PDF.")
    processing_time_ms: float = Field(
        ..., ge=0, description="Time taken to extract the text, in milliseconds."
    )


class ExtractionResponse(BaseModel):
    """Response DTO returned by the extraction endpoint on success."""

    text: str = Field(..., description="Full text extracted from the PDF.")
    metadata: ExtractionMetadata
