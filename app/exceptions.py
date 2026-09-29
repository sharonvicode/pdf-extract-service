"""Domain-level exceptions for the extraction business logic.

Keeping these independent from FastAPI/HTTP concerns lets the service layer
stay framework-agnostic (SRP) - the API layer is responsible for translating
them into HTTP responses.
"""


class ExtractionError(Exception):
    """Base class for all extraction-related domain errors."""


class EmptyFileError(ExtractionError):
    """Raised when the uploaded file has no content."""


class FileTooLargeError(ExtractionError):
    """Raised when the uploaded file exceeds the configured size limit."""

    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"File size {size_bytes} bytes exceeds the maximum of {max_bytes} bytes."
        )


class UnsupportedFileTypeError(ExtractionError):
    """Raised when the uploaded file is not an accepted content type."""

    def __init__(self, content_type: str | None) -> None:
        self.content_type = content_type
        super().__init__(f"Unsupported content type: {content_type!r}.")


class InvalidPDFError(ExtractionError):
    """Raised when the file content cannot be parsed as a valid PDF."""


class NoExtractableTextError(ExtractionError):
    """Raised when a readable PDF contains no text (e.g. blank or scanned pages)."""
