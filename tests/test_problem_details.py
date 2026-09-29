"""Tests for the RFC 9457 (Problem Details) error contract of the API."""
import logging

import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints.extraction import get_pdf_extractor_service
from app.core.config import get_settings
from app.main import app

PROBLEM_JSON = "application/problem+json"
EXTRACT_PATH = "/api/v1/extract"

client = TestClient(app)


def _upload(content: bytes, content_type: str = "application/pdf"):
    return client.post(EXTRACT_PATH, files={"file": ("doc.pdf", content, content_type)})


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
        _assert_is_problem(_upload(b""), 400, "Bad Request", EXTRACT_PATH)

    def test_unsupported_content_type(self, small_pdf_bytes):
        response = _upload(small_pdf_bytes, content_type="text/plain")

        _assert_is_problem(response, 415, "Unsupported Media Type", EXTRACT_PATH)

    def test_file_too_large(self):
        too_large = b"0" * (get_settings().max_file_size_bytes + 1)

        _assert_is_problem(_upload(too_large), 413, "Content Too Large", EXTRACT_PATH)

    def test_invalid_pdf(self, corrupted_pdf_bytes):
        _assert_is_problem(_upload(corrupted_pdf_bytes), 422, "Unprocessable Content", EXTRACT_PATH)

    def test_pdf_without_extractable_text(self, blank_pdf_bytes):
        body = _assert_is_problem(_upload(blank_pdf_bytes), 422, "Unprocessable Content", EXTRACT_PATH)
        assert "no extractable text" in body["detail"]


class TestFrameworkErrorsAreProblemDetails:
    def test_missing_file_field_lists_the_validation_errors(self):
        response = client.post(EXTRACT_PATH)

        body = _assert_is_problem(response, 422, "Unprocessable Content", EXTRACT_PATH)
        assert body["errors"] == [{"loc": ["body", "file"], "msg": "Field required", "type": "missing"}]

    def test_unknown_route(self):
        _assert_is_problem(client.get("/does-not-exist"), 404, "Not Found", "/does-not-exist")

    def test_method_not_allowed(self):
        _assert_is_problem(client.get(EXTRACT_PATH), 405, "Method Not Allowed", EXTRACT_PATH)


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

        body = _assert_is_problem(response, 500, "Internal Server Error", EXTRACT_PATH)
        assert "internal secret" not in response.text
        assert body["detail"] == "An unexpected error occurred."

    def test_logs_the_original_exception(self, failing_client, small_pdf_bytes, caplog):
        with caplog.at_level(logging.ERROR):
            failing_client.post(EXTRACT_PATH, files={"file": ("doc.pdf", small_pdf_bytes, "application/pdf")})

        assert "internal secret" in caplog.text


class TestOpenAPIDocumentsErrors:
    @pytest.mark.parametrize("status", ["400", "413", "415", "422"])
    def test_extract_endpoint_documents_problem_responses(self, status):
        responses = app.openapi()["paths"][EXTRACT_PATH]["post"]["responses"]

        assert PROBLEM_JSON in responses[status]["content"]
