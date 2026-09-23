"""Centralized translation of domain exceptions into HTTP responses.

Keeping this mapping in one place means endpoints never need to know about
HTTP status codes when raising domain errors (SRP + DRY).
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.exceptions import (
    EmptyFileError,
    FileTooLargeError,
    InvalidPDFError,
    UnsupportedFileTypeError,
)

_STATUS_BY_EXCEPTION = {
    EmptyFileError: status.HTTP_400_BAD_REQUEST,
    UnsupportedFileTypeError: status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    FileTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
    InvalidPDFError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def register_exception_handlers(app: FastAPI) -> None:
    for exc_class, http_status in _STATUS_BY_EXCEPTION.items():

        def _make_handler(status_code: int):
            async def _handler(_: Request, exc: Exception) -> JSONResponse:
                return JSONResponse(status_code=status_code, content={"detail": str(exc)})

            return _handler

        app.add_exception_handler(exc_class, _make_handler(http_status))
