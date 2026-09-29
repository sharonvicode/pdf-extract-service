"""Integration tests for the /api/v1/extraer HTTP endpoint."""
from fastapi.testclient import TestClient

from app.main import app

EXTRACT_PATH = "/api/v1/extraer"

client = TestClient(app)


def _upload(filename: str, content: bytes, content_type: str = "application/pdf"):
    return client.post(
        EXTRACT_PATH,
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
        assert "Page 1" in body["texto"]
        assert body["metadatos"]["cantidad_paginas"] == 1
        assert body["metadatos"]["nombre_archivo"] == "small.pdf"

    def test_returns_all_metadata_fields(self, small_pdf_bytes):
        response = _upload("small.pdf", small_pdf_bytes)

        metadatos = response.json()["metadatos"]
        assert metadatos["tamanio_bytes"] == len(small_pdf_bytes)
        assert metadatos["tiempo_procesamiento_ms"] >= 0

    def test_extracts_text_from_medium_pdf(self, medium_pdf_bytes):
        response = _upload("medium.pdf", medium_pdf_bytes)

        assert response.status_code == 200
        body = response.json()
        assert body["metadatos"]["cantidad_paginas"] == 10

    def test_extracts_text_from_large_pdf(self, large_pdf_bytes):
        response = _upload("large.pdf", large_pdf_bytes)

        assert response.status_code == 200
        body = response.json()
        assert body["metadatos"]["cantidad_paginas"] == 100

    def test_previous_english_route_no_longer_exists(self, small_pdf_bytes):
        response = client.post("/api/v1/extract", files={"file": ("doc.pdf", small_pdf_bytes, "application/pdf")})

        assert response.status_code == 404


class TestExtractEndpointValidation:
    def test_rejects_empty_file_as_unreadable_pdf(self, empty_file_bytes):
        response = _upload("empty.pdf", empty_file_bytes)

        assert response.status_code == 422

    def test_does_not_validate_content_type(self, small_pdf_bytes):
        """Checking the declared file type is the Validator's responsibility."""
        response = _upload("doc.pdf", small_pdf_bytes, content_type="application/octet-stream")

        assert response.status_code == 200
        assert "Page 1" in response.json()["texto"]

    def test_rejects_corrupted_pdf(self, corrupted_pdf_bytes):
        response = _upload("corrupted.pdf", corrupted_pdf_bytes)

        assert response.status_code == 422
