"""Tests for the RFC 9457 (Problem Details) error contract of the API."""
import logging

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_pdf_extractor_service
from app.core.config import get_settings
from app.exceptions import ServiceBusyError
from app.main import app

PROBLEM_JSON = "application/problem+json"
EXTRACT_PATH = "/api/v1/extraer"

client = TestClient(app)


def _upload(content: bytes):
    return client.post(EXTRACT_PATH, files={"file": ("doc.pdf", content, "application/pdf")})


def _assert_is_problem(response, status: int, title: str, instance: str) -> dict:
    assert response.status_code == status
    assert response.headers["content-type"] == PROBLEM_JSON
    body = response.json()
    assert body["type"] == "about:blank"
    assert body["title"] == title
    assert body["status"] == status
    assert body["instance"] == instance
    assert isinstance(body["detail"], str) and body["detail"]
    return body


class TestDomainErrorsAreProblemDetails:
    def test_empty_file(self):
        body = _assert_is_problem(_upload(b""), 422, "Contenido no procesable", EXTRACT_PATH)
        assert body["detail"].startswith("No se pudo leer el archivo como PDF")

    def test_file_too_large(self):
        max_bytes = get_settings().max_file_size_bytes
        too_large = b"0" * (max_bytes + 1)

        body = _assert_is_problem(_upload(too_large), 413, "Contenido demasiado grande", EXTRACT_PATH)
        assert body["detail"] == f"El archivo pesa {max_bytes + 1} bytes y supera el máximo de {max_bytes} bytes."

    def test_invalid_pdf(self, corrupted_pdf_bytes):
        body = _assert_is_problem(_upload(corrupted_pdf_bytes), 422, "Contenido no procesable", EXTRACT_PATH)
        assert body["detail"].startswith("No se pudo leer el archivo como PDF")

    def test_pdf_without_extractable_text(self, blank_pdf_bytes):
        body = _assert_is_problem(_upload(blank_pdf_bytes), 422, "Contenido no procesable", EXTRACT_PATH)
        assert body["detail"] == "El PDF no tiene texto extraíble."


class TestFrameworkErrorsAreProblemDetails:
    def test_missing_file_field_lists_the_validation_errors(self):
        response = client.post(EXTRACT_PATH)

        body = _assert_is_problem(response, 422, "Contenido no procesable", EXTRACT_PATH)
        assert body["detail"] == "La solicitud no es válida."
        assert body["errors"] == [{"loc": ["body", "file"], "msg": "Field required", "type": "missing"}]

    def test_unknown_route(self):
        body = _assert_is_problem(client.get("/does-not-exist"), 404, "No encontrado", "/does-not-exist")
        assert body["detail"] == "La ruta solicitada no existe."

    def test_method_not_allowed(self):
        body = _assert_is_problem(client.get(EXTRACT_PATH), 405, "Método no permitido", EXTRACT_PATH)
        assert body["detail"] == "El método HTTP no está permitido en esta ruta."


class TestUnexpectedErrors:
    @pytest.fixture
    def failing_client(self):
        class _ExplodingService:
            async def extract_text_async(self, _: bytes):
                raise RuntimeError("internal secret")

        app.dependency_overrides[get_pdf_extractor_service] = _ExplodingService
        yield TestClient(app, raise_server_exceptions=False)
        app.dependency_overrides.clear()

    def test_returns_generic_500_without_leaking_internals(self, failing_client, small_pdf_bytes):
        response = failing_client.post(EXTRACT_PATH, files={"file": ("doc.pdf", small_pdf_bytes, "application/pdf")})

        body = _assert_is_problem(response, 500, "Error interno del servidor", EXTRACT_PATH)
        assert "internal secret" not in response.text
        assert body["detail"] == "Ocurrió un error inesperado."

    def test_logs_the_original_exception(self, failing_client, small_pdf_bytes, caplog):
        with caplog.at_level(logging.ERROR):
            failing_client.post(EXTRACT_PATH, files={"file": ("doc.pdf", small_pdf_bytes, "application/pdf")})

        assert "internal secret" in caplog.text


class TestServiceBusyIsProblemDetails:
    @pytest.fixture
    def busy_client(self):
        class _BusyService:
            async def extract_text_async(self, _: bytes):
                raise ServiceBusyError()

        app.dependency_overrides[get_pdf_extractor_service] = _BusyService
        yield TestClient(app)
        app.dependency_overrides.clear()

    @pytest.mark.parametrize("path", ["/extract", EXTRACT_PATH])
    def test_returns_503_with_retry_after(self, busy_client, small_pdf_bytes, path):
        response = busy_client.post(path, files={"file": ("doc.pdf", small_pdf_bytes, "application/pdf")})

        _assert_is_problem(response, 503, "Servicio no disponible", path)
        assert response.headers["Retry-After"] == str(get_settings().retry_after_seconds)


class TestOpenAPIDocumentsErrors:
    @pytest.mark.parametrize(
        ("status", "title"), [("413", "Contenido demasiado grande"), ("422", "Contenido no procesable")]
    )
    def test_extract_endpoint_documents_problem_responses(self, status, title):
        responses = app.openapi()["paths"][EXTRACT_PATH]["post"]["responses"]

        assert PROBLEM_JSON in responses[status]["content"]
        assert responses[status]["description"] == title

    @pytest.mark.parametrize("status", ["400", "415"])
    def test_does_not_document_validator_errors(self, status):
        responses = app.openapi()["paths"][EXTRACT_PATH]["post"]["responses"]

        assert status not in responses
