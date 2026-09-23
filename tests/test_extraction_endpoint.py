"""Integration tests for the /api/v1/extract HTTP endpoint."""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _upload(filename: str, content: bytes, content_type: str = "application/pdf"):
    return client.post(
        "/api/v1/extract",
        files={"file": (filename, content, content_type)},
    )


class TestHealthCheck:
    def test_health_check_returns_ok(self):
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestExtractEndpointSuccess:
    def test_extracts_text_from_small_pdf(self, small_pdf_bytes):
        response = _upload("small.pdf", small_pdf_bytes)

        assert response.status_code == 200
        body = response.json()
        assert "Page 1" in body["text"]
        assert body["metadata"]["page_count"] == 1
        assert body["metadata"]["filename"] == "small.pdf"

    def test_extracts_text_from_medium_pdf(self, medium_pdf_bytes):
        response = _upload("medium.pdf", medium_pdf_bytes)

        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["page_count"] == 10

    def test_extracts_text_from_large_pdf(self, large_pdf_bytes):
        response = _upload("large.pdf", large_pdf_bytes)

        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["page_count"] == 100


class TestExtractEndpointValidation:
    def test_rejects_empty_file(self, empty_file_bytes):
        response = _upload("empty.pdf", empty_file_bytes)

        assert response.status_code == 400

    def test_rejects_non_pdf_content_type(self, small_pdf_bytes):
        response = _upload("doc.txt", small_pdf_bytes, content_type="text/plain")

        assert response.status_code == 415

    def test_rejects_corrupted_pdf(self, corrupted_pdf_bytes):
        response = _upload("corrupted.pdf", corrupted_pdf_bytes)

        assert response.status_code == 422
