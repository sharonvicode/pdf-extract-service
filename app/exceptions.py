"""Domain-level exceptions for the extraction business logic.

Keeping these independent from FastAPI/HTTP concerns lets the service layer
stay framework-agnostic (SRP) - the API layer is responsible for translating
them into HTTP responses.
"""


class ExtractionError(Exception):
    """Base class for all extraction-related domain errors."""


class FileTooLargeError(ExtractionError):
    """Raised when the uploaded file exceeds the configured size limit."""

    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"El archivo pesa {size_bytes} bytes y supera el máximo de {max_bytes} bytes."
        )


class InvalidPDFError(ExtractionError):
    """Raised when the file content cannot be parsed as a valid PDF."""


class NoExtractableTextError(ExtractionError):
    """Raised when a readable PDF contains no text (e.g. blank or scanned pages)."""


class ServiceBusyError(ExtractionError):
    """Raised when every extraction slot and every waiting place is taken."""

    def __init__(self) -> None:
        super().__init__("El servicio está saturado. Reintentá en unos segundos.")
