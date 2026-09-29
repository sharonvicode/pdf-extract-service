"""Centralized translation of exceptions into RFC 9457 Problem Details responses.

Keeping this mapping in one place means endpoints never need to know about
HTTP status codes or error formats when raising domain errors (SRP + DRY).
"""
import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import (
    ExtractionError,
    FileTooLargeError,
    InvalidPDFError,
    NoExtractableTextError,
)
from app.schemas.problem_details import PROBLEM_JSON_MEDIA_TYPE, ProblemDetails

logger = logging.getLogger(__name__)

STATUS_BY_EXCEPTION: dict[type[ExtractionError], int] = {
    FileTooLargeError: status.HTTP_413_CONTENT_TOO_LARGE,
    InvalidPDFError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    NoExtractableTextError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}

UNEXPECTED_ERROR_DETAIL = "An unexpected error occurred."
INVALID_REQUEST_DETAIL = "The request is not valid."

# Python 3.12's HTTPStatus still uses the obsolete RFC 7231 phrases for these codes.
_RFC_9110_TITLES = {
    status.HTTP_413_CONTENT_TOO_LARGE: "Content Too Large",
    status.HTTP_422_UNPROCESSABLE_CONTENT: "Unprocessable Content",
}


def problem_title(status_code: int) -> str:
    """Return the standard (RFC 9110) reason phrase for ``status_code``."""
    return _RFC_9110_TITLES.get(status_code, HTTPStatus(status_code).phrase)


# OpenAPI documentation of the domain errors, derived from the same mapping used at runtime.
DOMAIN_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status_code: {
        "description": problem_title(status_code),
        "content": {PROBLEM_JSON_MEDIA_TYPE: {"schema": ProblemDetails.model_json_schema()}},
    }
    for status_code in STATUS_BY_EXCEPTION.values()
}


def problem_response(
    request: Request,
    status_code: int,
    detail: str,
    headers: dict[str, str] | None = None,
    **extensions: Any,
) -> JSONResponse:
    problem = ProblemDetails(
        title=problem_title(status_code),
        status=status_code,
        detail=detail,
        instance=request.url.path,
        **extensions,
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(),
        media_type=PROBLEM_JSON_MEDIA_TYPE,
        headers=headers,
    )


async def domain_error_handler(request: Request, exc: ExtractionError) -> JSONResponse:
    return problem_response(request, STATUS_BY_EXCEPTION[type(exc)], str(exc))


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return problem_response(request, exc.status_code, str(exc.detail), headers=exc.headers)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]} for error in exc.errors()]
    return problem_response(request, status.HTTP_422_UNPROCESSABLE_CONTENT, INVALID_REQUEST_DETAIL, errors=errors)


async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # The original error is only logged; it is never exposed to the client.
    logger.exception("Unexpected error processing %s %s", request.method, request.url.path, exc_info=exc)
    return problem_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, UNEXPECTED_ERROR_DETAIL)


def register_exception_handlers(app: FastAPI) -> None:
    for exc_class in STATUS_BY_EXCEPTION:
        app.add_exception_handler(exc_class, domain_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, unexpected_error_handler)
