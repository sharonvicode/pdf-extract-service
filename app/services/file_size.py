"""Maximum file size rule, shared by every extraction endpoint."""
from app.core.config import get_settings
from app.exceptions import FileTooLargeError


def ensure_within_size_limit(size_bytes: int) -> None:
    """Protect the service's memory and CPU from oversized files.

    Raises:
        FileTooLargeError: if ``size_bytes`` exceeds the configured maximum.
    """
    max_bytes = get_settings().max_file_size_bytes
    if size_bytes > max_bytes:
        raise FileTooLargeError(size_bytes, max_bytes)
